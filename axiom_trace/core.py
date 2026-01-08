"""
Core AxiomTrace class - the main SDK interface.

Provides record(), query(), export_session(), verify_integrity(), and stats()
methods for interacting with the trace vault.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson
from filelock import FileLock, Timeout

from axiom_trace.backend import AxiomLockError, MemvidBackend
from axiom_trace.canonical import canonicalize, compute_frame_hash, verify_frame_hash
from axiom_trace.redaction import redact_frame
from axiom_trace.schema import AxiomValidationError, validate_frame


# Constants
VAULT_VERSION = "1.1.0"
HASH_ALGO = "sha256"
FLUSH_INTERVAL_SECONDS = 5
FLUSH_QUEUE_SIZE = 50
DEFAULT_SIZE_WARNING_GB = 20

# Configure logging
logger = logging.getLogger("axiom_trace")


class AxiomTrace:
    """
    Main SDK interface for Axiom Trace.
    
    A local-first, append-only trace vault for AI agents with cryptographic
    integrity and hybrid search.
    """
    
    def __init__(
        self, 
        vault_dir: str | None = None,
        redaction_enabled: bool = True,
        auto_flush: bool = True,
        size_warning_gb: float = DEFAULT_SIZE_WARNING_GB,
        memvid_api_key: str | None = None
    ):
        """
        Initialize an AxiomTrace vault.
        
        Args:
            vault_dir: Path to the vault directory. Defaults to '.axiom_trace/' 
                      in the current working directory if not specified.
            redaction_enabled: Whether to enable automatic redaction
            auto_flush: Whether to enable automatic background flushing
            size_warning_gb: Size threshold for warnings in GB
            memvid_api_key: Optional Memvid API key for cloud features
                           (can also be set via MEMVID_API_KEY env var)
        """
        # Default to .axiom_trace/ in current working directory
        if vault_dir is None:
            vault_dir = os.path.join(os.getcwd(), ".axiom_trace")
        
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        
        self.redaction_enabled = redaction_enabled
        self.size_warning_gb = size_warning_gb
        
        # Paths
        self.manifest_path = self.vault_dir / "vault.manifest.json"
        self.lock_path = self.vault_dir / "vault.lock"
        self.log_path = self.vault_dir / "axiom.log"
        
        # Initialize backend with optional API key
        self._backend = MemvidBackend(self.vault_dir, api_key=memvid_api_key)
        
        # Queue for batched writes
        self._queue: list[dict[str, Any]] = []
        self._queue_lock = threading.Lock()
        
        # File lock for writes
        self._file_lock = FileLock(str(self.lock_path), timeout=10)
        
        # Initialize or load manifest
        self._manifest = self._load_or_create_manifest()
        
        # Setup logging
        self._setup_logging()
        
        # Background flush thread
        self._flush_thread: threading.Thread | None = None
        self._stop_flush = threading.Event()
        
        if auto_flush:
            self._start_flush_thread()
        
        # Register cleanup on exit
        atexit.register(self.close)
    
    def _setup_logging(self) -> None:
        """Configure rotating file logger."""
        from logging.handlers import RotatingFileHandler
        
        handler = RotatingFileHandler(
            self.log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    def _load_or_create_manifest(self) -> dict[str, Any]:
        """Load existing manifest or create a new one."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        manifest = {
            "vault_version": VAULT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "vault_id": str(uuid.uuid4()),
            "hash_algo": HASH_ALGO,
            "head_hash": "",
            "frame_count": 0,
            "bytes_written": 0,
            "memvid_index_version": "unknown"
        }
        
        self._save_manifest_atomic(manifest)
        return manifest
    
    def _save_manifest_atomic(self, manifest: dict[str, Any]) -> None:
        """Save manifest atomically using tmp file + rename."""
        tmp_path = self.manifest_path.with_suffix(".json.tmp")
        
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        os.rename(tmp_path, self.manifest_path)
    
    def _start_flush_thread(self) -> None:
        """Start background flush thread."""
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="axiom-flush"
        )
        self._flush_thread.start()
    
    def _flush_loop(self) -> None:
        """Background flush loop."""
        while not self._stop_flush.wait(FLUSH_INTERVAL_SECONDS):
            try:
                self.flush()
            except Exception as e:
                logger.error(f"Flush error: {e}")
    
    def record(self, event: dict[str, Any]) -> str:
        """
        Record an event to the vault.
        
        Args:
            event: Event dictionary (without frame_id, timestamp, prev_hash, frame_hash)
            
        Returns:
            The frame_id of the recorded frame
            
        Raises:
            AxiomValidationError: If event validation fails
        """
        # Generate frame fields
        frame_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        # Default content if not provided
        content = event.get("content")
        if content is None:
            # Try to build content from 'text' or 'data' fields
            if "text" in event:
                content = {"text": event["text"]}
            elif "data" in event:
                content = {"json": event["data"]}
            else:
                content = {"text": ""}
        
        # Default actor if not provided
        actor = event.get("actor")
        if actor is None:
            actor = {"type": "agent", "id": "default"}
        
        # Build complete frame
        frame = {
            "frame_id": frame_id,
            "session_id": event.get("session_id", str(uuid.uuid4())),
            "timestamp": timestamp,
            "event_type": event.get("event_type"),
            "actor": actor,
            "content": content,
            "metadata": event.get("metadata", {}),
            "vector_key": event.get("vector_key", self._generate_vector_key(event)),
            "prev_hash": "",  # Will be set during flush
            "frame_hash": ""  # Will be computed during flush
        }
        
        # Validate
        validate_frame(frame)
        
        # Redact if enabled
        if self.redaction_enabled:
            frame = redact_frame(frame)
        
        # Add to queue
        with self._queue_lock:
            self._queue.append(frame)
            
            # Flush if queue is full
            if len(self._queue) >= FLUSH_QUEUE_SIZE:
                self._flush_queue_locked()
        
        logger.info(f"Recorded frame {frame_id}")
        return frame_id
    
    def _generate_vector_key(self, event: dict[str, Any]) -> str:
        """Generate a vector key for search indexing."""
        parts = []
        
        event_type = event.get("event_type", "")
        parts.append(event_type)
        
        content = event.get("content", {})
        if "rationale_summary" in content:
            parts.append(content["rationale_summary"][:200])
        elif "text" in content:
            parts.append(content["text"][:200])
        
        metadata = event.get("metadata", {})
        if "tool_name" in metadata:
            parts.append(f"tool:{metadata['tool_name']}")
        if "tags" in metadata:
            parts.extend(metadata["tags"][:5])
        
        key = " | ".join(parts)
        return key[:512]
    
    def flush(self) -> None:
        """Flush pending frames to storage."""
        with self._queue_lock:
            self._flush_queue_locked()
    
    def _flush_queue_locked(self) -> None:
        """Flush queue while holding lock."""
        if not self._queue:
            return
        
        frames_to_write = self._queue.copy()
        self._queue.clear()
        
        try:
            self._file_lock.acquire()
        except Timeout:
            raise AxiomLockError("Failed to acquire vault lock")
        
        try:
            # Reload manifest for latest head_hash
            if self.manifest_path.exists():
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    self._manifest = json.load(f)
            
            prev_hash = self._manifest["head_hash"]
            bytes_written = 0
            
            for frame in frames_to_write:
                # Set prev_hash and compute frame_hash
                frame["prev_hash"] = prev_hash
                frame_without_hash = {k: v for k, v in frame.items() if k != "frame_hash"}
                frame["frame_hash"] = compute_frame_hash(frame_without_hash, prev_hash)
                
                # Canonicalize and write
                canonical_bytes = canonicalize(frame)
                self._backend.append(canonical_bytes, frame["vector_key"])
                
                prev_hash = frame["frame_hash"]
                bytes_written += len(canonical_bytes)
            
            # Update manifest
            self._manifest["head_hash"] = prev_hash
            self._manifest["frame_count"] += len(frames_to_write)
            self._manifest["bytes_written"] += bytes_written
            
            self._save_manifest_atomic(self._manifest)
            
            logger.info(f"Flushed {len(frames_to_write)} frames")
            
        finally:
            self._file_lock.release()
    
    def query(
        self, 
        prompt: str, 
        limit: int = 5, 
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Query the vault for matching frames.
        
        Args:
            prompt: Search prompt
            limit: Maximum number of results
            filters: Optional filters (session_id, event_type, time_start, time_end, risk_level, tool_name)
            
        Returns:
            List of matching frames with explain fields
        """
        # Flush pending frames first
        self.flush()
        
        # Search
        result_bytes = self._backend.hybrid_search(prompt, limit * 2, filters)
        
        # Parse and score results
        results = []
        for frame_bytes in result_bytes:
            frame = orjson.loads(frame_bytes)
            
            # Calculate simple relevance score
            content = frame.get("content", {})
            text = content.get("text", "")
            vector_key = frame.get("vector_key", "")
            
            searchable = f"{text} {vector_key}".lower()
            prompt_lower = prompt.lower()
            
            # Simple scoring: word overlap
            prompt_words = set(prompt_lower.split())
            text_words = set(searchable.split())
            overlap = len(prompt_words & text_words)
            score = overlap / max(len(prompt_words), 1)
            
            frame["explain"] = {
                "method": "hybrid",
                "score": round(score, 4),
                "tiebreaker": "timestamp_desc"
            }
            results.append(frame)
        
        # Sort by score (desc), timestamp (desc), frame_id (desc)
        results.sort(
            key=lambda f: (
                -f["explain"]["score"],
                f["timestamp"],  # Natural string comparison works for ISO format
                f["frame_id"]
            ),
            reverse=True
        )
        
        # Re-sort for proper ordering
        results.sort(
            key=lambda f: (
                -f["explain"]["score"],
                -self._timestamp_to_float(f["timestamp"]),
                f["frame_id"]
            )
        )
        
        return results[:limit]
    
    def _timestamp_to_float(self, ts: str) -> float:
        """Convert ISO timestamp to float for sorting."""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0.0
    
    def export_session(
        self, 
        session_id: str, 
        out_path: str, 
        format: str = "md"
    ) -> None:
        """
        Export a session to a file.
        
        Args:
            session_id: Session ID to export
            out_path: Output file path
            format: Export format ("md" for Markdown)
        """
        # Flush first
        self.flush()
        
        # Get all frames for session
        all_frames = self._backend.get_all_frames()
        session_frames = []
        
        for frame_bytes in all_frames:
            frame = orjson.loads(frame_bytes)
            if frame.get("session_id") == session_id:
                session_frames.append(frame)
        
        # Sort by timestamp
        session_frames.sort(key=lambda f: f["timestamp"])
        
        if format == "md":
            self._export_markdown(session_frames, out_path, session_id)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_markdown(
        self, 
        frames: list[dict[str, Any]], 
        out_path: str,
        session_id: str
    ) -> None:
        """Export frames to Markdown format."""
        lines = []
        
        # Header
        lines.append("# Axiom Trace Export")
        lines.append("")
        lines.append(f"- **Vault ID**: {self._manifest['vault_id']}")
        lines.append(f"- **Session ID**: {session_id}")
        lines.append(f"- **Export Time**: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"- **Frame Count**: {len(frames)}")
        lines.append("")
        
        # Timeline table
        lines.append("## Timeline")
        lines.append("")
        lines.append("| Timestamp | Event Type | Actor | Preview |")
        lines.append("|-----------|------------|-------|---------|")
        
        for frame in frames:
            ts = frame["timestamp"]
            event_type = frame["event_type"]
            actor_id = frame.get("actor", {}).get("id", "unknown")
            
            content = frame.get("content", {})
            preview = content.get("text", "")
            if not preview and "json" in content:
                preview = json.dumps(content["json"])
            preview = preview[:120].replace("|", "\\|").replace("\n", " ")
            if len(preview) == 120:
                preview += "..."
            
            lines.append(f"| {ts} | {event_type} | {actor_id} | {preview} |")
        
        lines.append("")
        
        # Full entries
        lines.append("## Full Entries")
        lines.append("")
        
        for i, frame in enumerate(frames, 1):
            lines.append(f"### {i}. {frame['event_type']} ({frame['timestamp']})")
            lines.append("")
            lines.append(f"- **Frame ID**: {frame['frame_id']}")
            lines.append(f"- **Actor**: {frame.get('actor', {}).get('id', 'unknown')} ({frame.get('actor', {}).get('type', 'unknown')})")
            lines.append("")
            
            content = frame.get("content", {})
            if "text" in content:
                lines.append("**Content:**")
                lines.append("```")
                lines.append(content["text"])
                lines.append("```")
            elif "json" in content:
                lines.append("**Content (JSON):**")
                lines.append("```json")
                lines.append(json.dumps(content["json"], indent=2))
                lines.append("```")
            
            if content.get("rationale_summary"):
                lines.append("")
                lines.append(f"**Rationale**: {content['rationale_summary']}")
            
            metadata = frame.get("metadata", {})
            if metadata:
                lines.append("")
                lines.append(f"**Metadata**: `{json.dumps(metadata)}`")
            
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # Write file
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def verify_integrity(self) -> dict[str, Any]:
        """
        Verify the integrity of the vault.
        
        Returns:
            Dict with ok, checked_frames, head_hash, and error fields
        """
        # Flush first
        self.flush()
        
        all_frames = self._backend.get_all_frames()
        
        if not all_frames:
            return {
                "ok": True,
                "checked_frames": 0,
                "head_hash": "",
                "error": None
            }
        
        prev_hash = ""
        
        for i, frame_bytes in enumerate(all_frames):
            frame = orjson.loads(frame_bytes)
            
            # Verify prev_hash chain
            expected_prev = prev_hash
            actual_prev = frame.get("prev_hash", "")
            
            if actual_prev != expected_prev:
                return {
                    "ok": False,
                    "checked_frames": i,
                    "head_hash": prev_hash,
                    "error": f"Frame {i}: prev_hash mismatch (expected {expected_prev[:16]}..., got {actual_prev[:16]}...)"
                }
            
            # Verify frame_hash
            if not verify_frame_hash(frame, prev_hash):
                return {
                    "ok": False,
                    "checked_frames": i,
                    "head_hash": prev_hash,
                    "error": f"Frame {i}: frame_hash verification failed"
                }
            
            prev_hash = frame["frame_hash"]
        
        # Verify manifest head_hash
        manifest_head = self._manifest.get("head_hash", "")
        if manifest_head and manifest_head != prev_hash:
            return {
                "ok": False,
                "checked_frames": len(all_frames),
                "head_hash": prev_hash,
                "error": f"Manifest head_hash mismatch (manifest: {manifest_head[:16]}..., computed: {prev_hash[:16]}...)"
            }
        
        return {
            "ok": True,
            "checked_frames": len(all_frames),
            "head_hash": prev_hash,
            "error": None
        }
    
    def stats(self) -> dict[str, Any]:
        """
        Get vault statistics.
        
        Returns:
            Dict with frame_count, bytes_written, head_hash, approx_size_mb, over_limit
        """
        # Flush first
        self.flush()
        
        # Calculate actual size
        total_size = 0
        for path in self.vault_dir.rglob("*"):
            if path.is_file():
                total_size += path.stat().st_size
        
        size_mb = total_size / (1024 * 1024)
        size_gb = size_mb / 1024
        
        return {
            "frame_count": self._manifest["frame_count"],
            "bytes_written": self._manifest["bytes_written"],
            "head_hash": self._manifest["head_hash"],
            "approx_size_mb": round(size_mb, 2),
            "over_limit": size_gb > self.size_warning_gb
        }
    
    def close(self) -> None:
        """Close the vault and flush pending data."""
        # Stop flush thread
        self._stop_flush.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)
        
        # Final flush
        try:
            self.flush()
        except Exception as e:
            logger.error(f"Error during final flush: {e}")
        
        # Close backend
        self._backend.close()
        
        logger.info("Vault closed")
    
    def __enter__(self) -> "AxiomTrace":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

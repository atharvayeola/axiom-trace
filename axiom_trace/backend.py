"""
Backend abstraction layer for Axiom Trace.

Defines the MemoryBackend protocol and implements the MemvidBackend
adapter for persistent storage with hybrid search.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import orjson

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

try:
    from memvid import MemvidEncoder, MemvidRetriever
    MEMVID_AVAILABLE = True
except ImportError:
    MEMVID_AVAILABLE = False


class AxiomLockError(Exception):
    """Raised when vault lock acquisition fails."""
    pass


@runtime_checkable
class MemoryBackend(Protocol):
    """Protocol for storage backends."""
    
    def append(self, canonical_bytes: bytes, vector_key: str) -> None:
        """Append a frame to storage."""
        ...
    
    def hybrid_search(
        self, 
        query: str, 
        limit: int, 
        filters: dict[str, Any] | None = None
    ) -> list[bytes]:
        """Search frames using hybrid BM25 + semantic search."""
        ...
    
    def get_all_frames(self) -> list[bytes]:
        """Get all frames in order."""
        ...
    
    def get_frame_count(self) -> int:
        """Get the total number of frames."""
        ...
    
    def close(self) -> None:
        """Close the backend and release resources."""
        ...


class InMemoryBackend:
    """In-memory backend for testing and development."""
    
    def __init__(self):
        self._frames: list[bytes] = []
    
    def append(self, canonical_bytes: bytes, vector_key: str) -> None:
        """Append a frame to storage."""
        self._frames.append(canonical_bytes)
    
    def hybrid_search(
        self, 
        query: str, 
        limit: int, 
        filters: dict[str, Any] | None = None
    ) -> list[bytes]:
        """Simple text search for in-memory backend."""
        query_lower = query.lower()
        results = []
        
        for frame_bytes in self._frames:
            frame = orjson.loads(frame_bytes)
            
            # Apply filters
            if filters:
                if not self._matches_filters(frame, filters):
                    continue
            
            # Simple text matching
            content = frame.get("content", {})
            text = content.get("text", "")
            json_content = content.get("json", {})
            vector_key = frame.get("vector_key", "")
            
            searchable = f"{text} {json.dumps(json_content)} {vector_key}".lower()
            
            if query_lower in searchable:
                results.append(frame_bytes)
        
        return results[:limit]
    
    def _matches_filters(self, frame: dict, filters: dict) -> bool:
        """Check if a frame matches the given filters."""
        if "session_id" in filters:
            if frame.get("session_id") != filters["session_id"]:
                return False
        
        if "event_type" in filters:
            if frame.get("event_type") != filters["event_type"]:
                return False
        
        if "time_start" in filters:
            if frame.get("timestamp", "") < filters["time_start"]:
                return False
        
        if "time_end" in filters:
            if frame.get("timestamp", "") > filters["time_end"]:
                return False
        
        if "risk_level" in filters:
            metadata = frame.get("metadata", {})
            if metadata.get("risk_level") != filters["risk_level"]:
                return False
        
        if "tool_name" in filters:
            metadata = frame.get("metadata", {})
            if metadata.get("tool_name") != filters["tool_name"]:
                return False
        
        return True
    
    def get_all_frames(self) -> list[bytes]:
        """Get all frames in order."""
        return list(self._frames)
    
    def get_frame_count(self) -> int:
        """Get the total number of frames."""
        return len(self._frames)
    
    def close(self) -> None:
        """Close the backend."""
        pass


class MemvidBackend:
    """
    Memvid-based backend for persistent storage with hybrid search.
    
    Uses Memvid for vector storage and semantic search capabilities.
    Falls back to file-based storage if Memvid is not available.
    
    Environment Variables:
        MEMVID_API_KEY: API key for Memvid cloud features (optional)
    """
    
    def __init__(self, vault_dir: str | Path, api_key: str | None = None):
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.environ.get("MEMVID_API_KEY")
        
        self.mv2_path = self.vault_dir / "vault.mv2"
        self._frames_cache: list[bytes] = []
        self._encoder = None
        self._retriever = None
        
        # Load existing frames if vault exists
        self._load_existing_frames()
    
    def _load_existing_frames(self) -> None:
        """Load existing frames from vault file."""
        frames_file = self.vault_dir / "frames.jsonl"
        if frames_file.exists():
            with open(frames_file, "rb") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._frames_cache.append(line)
        
        # Initialize Memvid if available
        if MEMVID_AVAILABLE and self.mv2_path.exists():
            try:
                self._retriever = MemvidRetriever(str(self.mv2_path))
            except Exception:
                pass
    
    def append(self, canonical_bytes: bytes, vector_key: str) -> None:
        """Append a frame to storage."""
        self._frames_cache.append(canonical_bytes)
        
        # Append to JSONL file for durability
        frames_file = self.vault_dir / "frames.jsonl"
        with open(frames_file, "ab") as f:
            f.write(canonical_bytes + b"\n")
            f.flush()
            os.fsync(f.fileno())
    
    def build_index(self) -> None:
        """Build or rebuild the Memvid index."""
        if not MEMVID_AVAILABLE:
            return
        
        try:
            # Prepare documents for Memvid
            documents = []
            for frame_bytes in self._frames_cache:
                frame = orjson.loads(frame_bytes)
                vector_key = frame.get("vector_key", "")
                content = frame.get("content", {})
                text = content.get("text", "")
                if not text and "json" in content:
                    text = json.dumps(content["json"])
                
                doc_text = f"{vector_key}\n{text}"
                documents.append(doc_text)
            
            if documents:
                # Pass API key to encoder if available for cloud features
                encoder_kwargs = {}
                if self.api_key:
                    encoder_kwargs["api_key"] = self.api_key
                
                encoder = MemvidEncoder(**encoder_kwargs)
                for doc in documents:
                    encoder.add_text(doc)
                
                encoder.build_video(
                    str(self.mv2_path),
                    str(self.vault_dir / "vault_index.json")
                )
                
                self._retriever = MemvidRetriever(str(self.mv2_path))
        except Exception:
            # Fall back to simple search if Memvid fails
            pass
    
    def hybrid_search(
        self, 
        query: str, 
        limit: int, 
        filters: dict[str, Any] | None = None
    ) -> list[bytes]:
        """Search frames using hybrid BM25 + semantic search."""
        # Try Memvid search first
        if self._retriever is not None:
            try:
                results = self._retriever.search(query, top_k=limit * 2)
                # Map results back to frames
                matched_frames = []
                for result in results:
                    for frame_bytes in self._frames_cache:
                        frame = orjson.loads(frame_bytes)
                        content = frame.get("content", {})
                        text = content.get("text", "")
                        vector_key = frame.get("vector_key", "")
                        
                        if result.get("text", "") in f"{vector_key}\n{text}":
                            if filters and not self._matches_filters(frame, filters):
                                continue
                            matched_frames.append(frame_bytes)
                            break
                
                return matched_frames[:limit]
            except Exception:
                pass
        
        # Fallback to simple search
        return self._simple_search(query, limit, filters)
    
    def _simple_search(
        self, 
        query: str, 
        limit: int, 
        filters: dict[str, Any] | None = None
    ) -> list[bytes]:
        """Simple text search fallback."""
        query_lower = query.lower()
        results = []
        
        for frame_bytes in self._frames_cache:
            frame = orjson.loads(frame_bytes)
            
            # Apply filters
            if filters and not self._matches_filters(frame, filters):
                continue
            
            content = frame.get("content", {})
            text = content.get("text", "")
            json_content = content.get("json", {})
            vector_key = frame.get("vector_key", "")
            
            searchable = f"{text} {json.dumps(json_content)} {vector_key}".lower()
            
            if query_lower in searchable:
                results.append(frame_bytes)
        
        return results[:limit]
    
    def _matches_filters(self, frame: dict, filters: dict) -> bool:
        """Check if a frame matches the given filters."""
        if "session_id" in filters:
            if frame.get("session_id") != filters["session_id"]:
                return False
        
        if "event_type" in filters:
            if frame.get("event_type") != filters["event_type"]:
                return False
        
        if "time_start" in filters:
            if frame.get("timestamp", "") < filters["time_start"]:
                return False
        
        if "time_end" in filters:
            if frame.get("timestamp", "") > filters["time_end"]:
                return False
        
        if "risk_level" in filters:
            metadata = frame.get("metadata", {})
            if metadata.get("risk_level") != filters["risk_level"]:
                return False
        
        if "tool_name" in filters:
            metadata = frame.get("metadata", {})
            if metadata.get("tool_name") != filters["tool_name"]:
                return False
        
        return True
    
    def get_all_frames(self) -> list[bytes]:
        """Get all frames in order."""
        return list(self._frames_cache)
    
    def get_frame_count(self) -> int:
        """Get the total number of frames."""
        return len(self._frames_cache)
    
    def close(self) -> None:
        """Close the backend and build index."""
        self.build_index()

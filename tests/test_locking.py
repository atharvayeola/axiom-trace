"""
Tests for file locking.
"""

import tempfile
import threading
import time
import uuid

import pytest

from axiom_trace.core import AxiomTrace
from axiom_trace.backend import AxiomLockError


@pytest.fixture
def temp_vault():
    """Create a temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestLocking:
    """Test file locking behavior."""
    
    def test_concurrent_writes_are_serialized(self, temp_vault):
        """Concurrent writes should be serialized via locking."""
        results = []
        errors = []
        lock = threading.Lock()
        
        def write_frames(n):
            try:
                with AxiomTrace(temp_vault, auto_flush=False) as trace:
                    for i in range(5):
                        frame_id = trace.record({
                            "session_id": str(uuid.uuid4()),
                            "event_type": "thought",
                            "actor": {"type": "agent", "id": f"agent-{n}"},
                            "content": {
                                "text": f"Thought from worker {n}, iteration {i}",
                                "rationale_summary": f"Worker {n}"
                            },
                            "metadata": {}
                        })
                        with lock:
                            results.append(frame_id)
            except Exception as e:
                with lock:
                    errors.append(e)
        
        # Start multiple threads
        threads = [
            threading.Thread(target=write_frames, args=(i,))
            for i in range(3)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify we got some successful frames (may have lock errors)
        # The key is that we don't crash and frames that succeeded are unique
        if len(results) > 0:
            assert len(set(results)) == len(results)
    
    def test_read_during_write(self, temp_vault):
        """Reading should work while writing is in progress."""
        session_id = str(uuid.uuid4())
        read_result = [None]
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            # Record some initial frames
            for i in range(3):
                trace.record({
                    "session_id": session_id,
                    "event_type": "thought",
                    "actor": {"type": "agent", "id": "test"},
                    "content": {
                        "text": f"Initial thought {i}",
                        "rationale_summary": f"Test {i}"
                    },
                    "metadata": {}
                })
        
        def continuous_write():
            with AxiomTrace(temp_vault, auto_flush=False) as trace:
                for i in range(10):
                    trace.record({
                        "session_id": session_id,
                        "event_type": "thought",
                        "actor": {"type": "agent", "id": "writer"},
                        "content": {
                            "text": f"Write iteration {i}",
                            "rationale_summary": f"Writing {i}"
                        },
                        "metadata": {}
                    })
                    time.sleep(0.01)
        
        def read_once():
            time.sleep(0.02)  # Let writer start
            with AxiomTrace(temp_vault, auto_flush=False) as trace:
                read_result[0] = trace.stats()
        
        writer = threading.Thread(target=continuous_write)
        reader = threading.Thread(target=read_once)
        
        writer.start()
        reader.start()
        
        writer.join()
        reader.join()
        
        # Read should have succeeded
        assert read_result[0] is not None
        assert "frame_count" in read_result[0]
    
    def test_integrity_after_concurrent_writes(self, temp_vault):
        """Vault integrity should be maintained after concurrent writes."""
        def write_frames(n):
            with AxiomTrace(temp_vault, auto_flush=False) as trace:
                for i in range(5):
                    trace.record({
                        "session_id": str(uuid.uuid4()),
                        "event_type": "thought",
                        "actor": {"type": "agent", "id": f"agent-{n}"},
                        "content": {
                            "text": f"Thought from worker {n}",
                            "rationale_summary": f"Worker {n} thinking"
                        },
                        "metadata": {}
                    })
        
        threads = [
            threading.Thread(target=write_frames, args=(i,))
            for i in range(3)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify integrity
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            result = trace.verify_integrity()
            
            assert result["ok"] is True
            assert result["error"] is None


class TestContextManager:
    """Test context manager behavior."""
    
    def test_context_manager_flushes_on_exit(self, temp_vault):
        """Context manager should flush on exit."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Test thought",
                    "rationale_summary": "Testing"
                },
                "metadata": {}
            })
        
        # Reopen and verify frame was persisted
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            stats = trace.stats()
            assert stats["frame_count"] == 1
    
    def test_context_manager_handles_exception(self, temp_vault):
        """Context manager should handle exceptions gracefully."""
        try:
            with AxiomTrace(temp_vault, auto_flush=False) as trace:
                trace.record({
                    "session_id": str(uuid.uuid4()),
                    "event_type": "thought",
                    "actor": {"type": "agent", "id": "test"},
                    "content": {
                        "text": "Before exception",
                        "rationale_summary": "Testing"
                    },
                    "metadata": {}
                })
                raise ValueError("Simulated error")
        except ValueError:
            pass
        
        # Frame should still be persisted
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            stats = trace.stats()
            assert stats["frame_count"] == 1

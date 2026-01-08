"""
Tests for record and query operations.
"""

import tempfile
import uuid
from pathlib import Path

import pytest

from axiom_trace.core import AxiomTrace
from axiom_trace.schema import AxiomValidationError


@pytest.fixture
def temp_vault():
    """Create a temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestRecord:
    """Test record() method."""
    
    def test_record_valid_event_returns_frame_id(self, temp_vault):
        """Recording a valid event should return a frame_id."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            frame_id = trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test-agent"},
                "content": {
                    "text": "This is a test thought",
                    "rationale_summary": "Testing recording"
                },
                "metadata": {}
            })
            
            assert frame_id is not None
            assert isinstance(frame_id, str)
            # Should be a valid UUID
            uuid.UUID(frame_id)
    
    def test_record_multiple_events(self, temp_vault):
        """Recording multiple events should work."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            ids = []
            for i in range(5):
                frame_id = trace.record({
                    "session_id": str(uuid.uuid4()),
                    "event_type": "thought",
                    "actor": {"type": "agent", "id": "test-agent"},
                    "content": {
                        "text": f"Thought {i}",
                        "rationale_summary": f"Test {i}"
                    },
                    "metadata": {}
                })
                ids.append(frame_id)
            
            assert len(ids) == 5
            assert len(set(ids)) == 5  # All unique
    
    def test_record_invalid_event_raises(self, temp_vault):
        """Recording an invalid event should raise AxiomValidationError."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            with pytest.raises(AxiomValidationError):
                trace.record({
                    "event_type": "invalid_type",
                    "actor": {"type": "agent", "id": "test"},
                    "content": {"text": "test"},
                    "metadata": {}
                })
    
    def test_record_persists_after_close(self, temp_vault):
        """Recorded events should persist after closing vault."""
        session_id = str(uuid.uuid4())
        
        # Record an event
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session_id,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test-agent"},
                "content": {
                    "text": "Persistent thought",
                    "rationale_summary": "Should persist"
                },
                "metadata": {}
            })
        
        # Reopen and verify
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            stats = trace.stats()
            assert stats["frame_count"] == 1


class TestQuery:
    """Test query() method."""
    
    def test_query_returns_list(self, temp_vault):
        """Query should return a list."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Test content for query",
                    "rationale_summary": "Testing query"
                },
                "metadata": {}
            })
            
            results = trace.query("test", limit=5)
            
            assert isinstance(results, list)
    
    def test_query_matches_content(self, temp_vault):
        """Query should find matching content."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "The quick brown fox jumps over the lazy dog",
                    "rationale_summary": "Animal observation"
                },
                "metadata": {}
            })
            
            results = trace.query("fox", limit=5)
            
            assert len(results) >= 1
            assert "fox" in results[0]["content"]["text"]
    
    def test_query_respects_limit(self, temp_vault):
        """Query should respect the limit parameter."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            for i in range(10):
                trace.record({
                    "session_id": str(uuid.uuid4()),
                    "event_type": "thought",
                    "actor": {"type": "agent", "id": "test"},
                    "content": {
                        "text": f"Test thought number {i}",
                        "rationale_summary": f"Test {i}"
                    },
                    "metadata": {}
                })
            
            results = trace.query("thought", limit=3)
            
            assert len(results) <= 3
    
    def test_query_includes_explain_field(self, temp_vault):
        """Query results should include explain field."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Searchable content here",
                    "rationale_summary": "For search test"
                },
                "metadata": {}
            })
            
            results = trace.query("searchable", limit=5)
            
            assert len(results) >= 1
            result = results[0]
            
            assert "explain" in result
            assert "method" in result["explain"]
            assert "score" in result["explain"]
            assert "tiebreaker" in result["explain"]
    
    def test_query_with_session_filter(self, temp_vault):
        """Query with session_id filter should only return matching frames."""
        session1 = str(uuid.uuid4())
        session2 = str(uuid.uuid4())
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session1,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Session one thought",
                    "rationale_summary": "First session"
                },
                "metadata": {}
            })
            trace.record({
                "session_id": session2,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Session two thought",
                    "rationale_summary": "Second session"
                },
                "metadata": {}
            })
            
            results = trace.query(
                "thought", 
                limit=10, 
                filters={"session_id": session1}
            )
            
            for result in results:
                assert result["session_id"] == session1
    
    def test_query_with_event_type_filter(self, temp_vault):
        """Query with event_type filter should only return matching frames."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "A thought about search",
                    "rationale_summary": "Thinking"
                },
                "metadata": {}
            })
            trace.record({
                "session_id": str(uuid.uuid4()),
                "event_type": "tool_call",
                "actor": {"type": "agent", "id": "test"},
                "content": {"json": {"tool": "search", "query": "test"}},
                "metadata": {"tool_name": "search"}
            })
            
            results = trace.query(
                "search", 
                limit=10, 
                filters={"event_type": "tool_call"}
            )
            
            for result in results:
                assert result["event_type"] == "tool_call"


class TestIntegrity:
    """Test verify_integrity() method."""
    
    def test_empty_vault_passes_verification(self, temp_vault):
        """Empty vault should pass verification."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            result = trace.verify_integrity()
            
            assert result["ok"] is True
            assert result["checked_frames"] == 0
            assert result["error"] is None
    
    def test_vault_with_frames_passes_verification(self, temp_vault):
        """Vault with valid frames should pass verification."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            for i in range(5):
                trace.record({
                    "session_id": str(uuid.uuid4()),
                    "event_type": "thought",
                    "actor": {"type": "agent", "id": "test"},
                    "content": {
                        "text": f"Thought {i}",
                        "rationale_summary": f"Test {i}"
                    },
                    "metadata": {}
                })
            
            result = trace.verify_integrity()
            
            assert result["ok"] is True
            assert result["checked_frames"] == 5
            assert result["error"] is None
            assert result["head_hash"] != ""


class TestStats:
    """Test stats() method."""
    
    def test_stats_on_empty_vault(self, temp_vault):
        """Stats on empty vault should return zeros."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            stats = trace.stats()
            
            assert stats["frame_count"] == 0
            assert stats["bytes_written"] == 0
            assert stats["head_hash"] == ""
            assert stats["over_limit"] is False
    
    def test_stats_reflects_recorded_frames(self, temp_vault):
        """Stats should reflect recorded frames."""
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            for i in range(3):
                trace.record({
                    "session_id": str(uuid.uuid4()),
                    "event_type": "thought",
                    "actor": {"type": "agent", "id": "test"},
                    "content": {
                        "text": f"Thought {i}",
                        "rationale_summary": f"Test {i}"
                    },
                    "metadata": {}
                })
            
            stats = trace.stats()
            
            assert stats["frame_count"] == 3
            assert stats["bytes_written"] > 0
            assert stats["approx_size_mb"] >= 0  # May be 0.0 for very small vaults

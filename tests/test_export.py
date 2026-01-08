"""
Tests for session export functionality.
"""

import tempfile
import uuid

import pytest

from axiom_trace.core import AxiomTrace


@pytest.fixture
def temp_vault():
    """Create a temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestExportSession:
    """Test export_session() method."""
    
    def test_export_creates_file(self, temp_vault):
        """Export should create the output file."""
        session_id = str(uuid.uuid4())
        
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session_id,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Test thought",
                    "rationale_summary": "Testing"
                },
                "metadata": {}
            })
            
            trace.export_session(session_id, out_path)
        
        with open(out_path, "r") as f:
            content = f.read()
        
        assert len(content) > 0
        assert "Axiom Trace Export" in content
    
    def test_export_includes_header(self, temp_vault):
        """Export should include vault and session info."""
        session_id = str(uuid.uuid4())
        
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session_id,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Test thought",
                    "rationale_summary": "Testing"
                },
                "metadata": {}
            })
            
            trace.export_session(session_id, out_path)
        
        with open(out_path, "r") as f:
            content = f.read()
        
        assert "Vault ID" in content
        assert "Session ID" in content
        assert session_id in content
    
    def test_export_includes_timeline_table(self, temp_vault):
        """Export should include timeline table."""
        session_id = str(uuid.uuid4())
        
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session_id,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test-agent"},
                "content": {
                    "text": "Test thought content",
                    "rationale_summary": "Testing"
                },
                "metadata": {}
            })
            
            trace.export_session(session_id, out_path)
        
        with open(out_path, "r") as f:
            content = f.read()
        
        assert "## Timeline" in content
        assert "| Timestamp |" in content
        assert "thought" in content
        assert "test-agent" in content
    
    def test_export_only_includes_session_frames(self, temp_vault):
        """Export should only include frames from the specified session."""
        session1 = str(uuid.uuid4())
        session2 = str(uuid.uuid4())
        
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session1,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Session ONE thought",
                    "rationale_summary": "First session"
                },
                "metadata": {}
            })
            trace.record({
                "session_id": session2,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Session TWO thought",
                    "rationale_summary": "Second session"
                },
                "metadata": {}
            })
            
            trace.export_session(session1, out_path)
        
        with open(out_path, "r") as f:
            content = f.read()
        
        assert "Session ONE" in content
        assert "Session TWO" not in content
    
    def test_export_chronological_order(self, temp_vault):
        """Export should list frames in chronological order."""
        session_id = str(uuid.uuid4())
        
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as out:
            out_path = out.name
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session_id,
                "event_type": "user_input",
                "actor": {"type": "user", "id": "user"},
                "content": {"text": "FIRST message"},
                "metadata": {}
            })
            trace.record({
                "session_id": session_id,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "agent"},
                "content": {
                    "text": "SECOND message",
                    "rationale_summary": "Thinking"
                },
                "metadata": {}
            })
            trace.record({
                "session_id": session_id,
                "event_type": "final_result",
                "actor": {"type": "agent", "id": "agent"},
                "content": {"text": "THIRD message"},
                "metadata": {}
            })
            
            trace.export_session(session_id, out_path)
        
        with open(out_path, "r") as f:
            content = f.read()
        
        first_pos = content.find("FIRST")
        second_pos = content.find("SECOND")
        third_pos = content.find("THIRD")
        
        assert first_pos < second_pos < third_pos
    
    def test_export_unsupported_format_raises(self, temp_vault):
        """Unsupported export format should raise ValueError."""
        session_id = str(uuid.uuid4())
        
        with AxiomTrace(temp_vault, auto_flush=False) as trace:
            trace.record({
                "session_id": session_id,
                "event_type": "thought",
                "actor": {"type": "agent", "id": "test"},
                "content": {
                    "text": "Test",
                    "rationale_summary": "Testing"
                },
                "metadata": {}
            })
            
            with pytest.raises(ValueError) as exc_info:
                trace.export_session(session_id, "/tmp/out.txt", format="pdf")
            
            assert "format" in str(exc_info.value).lower()

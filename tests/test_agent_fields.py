"""
Tests for agent-friendly fields: input, output, reasoning, success, caused_by, artifacts.

These fields enable AI agents to retrospect on their own actions.
"""

import json
import tempfile
import pytest

from axiom_trace import AxiomTrace, session, set_global_trace


class TestAgentFriendlyFields:
    """Tests for agent-friendly schema fields."""
    
    def test_record_with_success_field(self):
        """Test recording with success boolean."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record({
                    "event_type": "tool_call",
                    "content": {"text": "Calling API"},
                    "success": True,
                    "metadata": {"tool_name": "api_call"}
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["success"] is True
    
    def test_record_with_success_false(self):
        """Test recording failed action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record({
                    "event_type": "tool_call",
                    "content": {"text": "API call failed"},
                    "success": False,
                    "metadata": {"tool_name": "api_call"}
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["success"] is False
    
    def test_record_with_caused_by(self):
        """Test causality chain with caused_by field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                # First frame (user input)
                first_id = trace.record({
                    "event_type": "user_input",
                    "content": {"text": "Build an API"}
                })
                
                # Second frame caused by first
                second_id = trace.record({
                    "event_type": "thought",
                    "content": {"text": "Planning", "rationale_summary": "Need endpoints"},
                    "caused_by": first_id
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                second_frame = json.loads(frames[1])
                
                assert second_frame["caused_by"] == first_id
    
    def test_record_with_artifacts(self):
        """Test recording with artifacts list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record({
                    "event_type": "tool_call",
                    "content": {"text": "Created files"},
                    "artifacts": ["api/users.py", "api/routes.py", "tests/test_api.py"],
                    "metadata": {"tool_name": "write_file"}
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["artifacts"] == ["api/users.py", "api/routes.py", "tests/test_api.py"]
    
    def test_record_with_empty_artifacts(self):
        """Test recording with empty artifacts list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record({
                    "event_type": "thought",
                    "content": {"text": "No files", "rationale_summary": "Just thinking"},
                    "artifacts": []
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["artifacts"] == []
    
    def test_content_input_output_reasoning(self):
        """Test content fields: input, output, reasoning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record({
                    "event_type": "tool_call",
                    "content": {
                        "text": "Action details",
                        "input": "User asked: Build REST API",
                        "output": "Created api/users.py with CRUD endpoints",
                        "reasoning": "User needs user management functionality"
                    },
                    "metadata": {"tool_name": "write_file"}
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["content"]["input"] == "User asked: Build REST API"
                assert frame["content"]["output"] == "Created api/users.py with CRUD endpoints"
                assert frame["content"]["reasoning"] == "User needs user management functionality"


class TestRecordActionHelper:
    """Tests for the record_action() convenience method."""
    
    def test_record_action_basic(self):
        """Test basic record_action usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record_action(
                    event_type="tool_call",
                    input="Build an API",
                    output="Created api/users.py",
                    reasoning="User needs CRUD endpoints",
                    tool_name="write_file"  # Required for tool_call
                )
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["content"]["input"] == "Build an API"
                assert frame["content"]["output"] == "Created api/users.py"
                assert frame["content"]["reasoning"] == "User needs CRUD endpoints"
    
    def test_record_action_with_success(self):
        """Test record_action with success field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record_action(
                    event_type="tool_call",
                    output="Done",
                    success=True,
                    tool_name="my_tool"
                )
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["success"] is True
                assert frame["metadata"]["tool_name"] == "my_tool"
    
    def test_record_action_with_artifacts(self):
        """Test record_action with artifacts list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record_action(
                    event_type="tool_call",
                    output="Created files",
                    artifacts=["file1.py", "file2.py"],
                    tool_name="bulk_create"  # Required for tool_call
                )
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["artifacts"] == ["file1.py", "file2.py"]
    
    def test_record_action_with_causality(self):
        """Test record_action with caused_by reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                first_id = trace.record_action(
                    event_type="user_input",
                    input="Hello"
                )
                
                second_id = trace.record_action(
                    event_type="thought",
                    reasoning="Processing greeting",
                    caused_by=first_id
                )
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                second_frame = json.loads(frames[1])
                
                assert second_frame["caused_by"] == first_id


class TestObserverAgentFields:
    """Tests for observer methods with agent-friendly fields."""
    
    def test_record_tool_call_with_reasoning(self):
        """Test record_tool_call with reasoning parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = AxiomTrace(vault_dir=tmpdir, auto_flush=False)
            set_global_trace(trace)
            
            with session() as obs:
                obs.record_tool_call(
                    "write_file",
                    {"path": "test.py", "content": "..."},
                    reasoning="Need to create test file"
                )
            
            trace.flush()
            frames = trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["content"]["reasoning"] == "Need to create test file"
            trace.close()
    
    def test_record_tool_output_with_success(self):
        """Test record_tool_output with success and artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = AxiomTrace(vault_dir=tmpdir, auto_flush=False)
            set_global_trace(trace)
            
            with session() as obs:
                obs.record_tool_output(
                    "write_file",
                    "File created successfully",
                    success=True,
                    artifacts=["test.py"]
                )
            
            trace.flush()
            frames = trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["success"] is True
            assert frame["artifacts"] == ["test.py"]
            trace.close()
    
    def test_record_tool_output_failure(self):
        """Test record_tool_output with failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = AxiomTrace(vault_dir=tmpdir, auto_flush=False)
            set_global_trace(trace)
            
            with session() as obs:
                obs.record_tool_output(
                    "api_call",
                    "Connection timeout",
                    success=False
                )
            
            trace.flush()
            frames = trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["success"] is False
            trace.close()


class TestEdgeCases:
    """Edge case tests for agent-friendly fields."""
    
    def test_long_reasoning_string(self):
        """Test with maximum length reasoning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                long_reasoning = "x" * 4999  # Just under 5000 limit
                
                frame_id = trace.record({
                    "event_type": "thought",
                    "content": {
                        "text": "Long thought",
                        "rationale_summary": "summary",
                        "reasoning": long_reasoning
                    }
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert frame["content"]["reasoning"] == long_reasoning
    
    def test_many_artifacts(self):
        """Test with many artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                artifacts = [f"file_{i}.py" for i in range(50)]
                
                frame_id = trace.record({
                    "event_type": "tool_call",
                    "content": {"text": "Created many files"},
                    "artifacts": artifacts,
                    "metadata": {"tool_name": "bulk_create"}
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert len(frame["artifacts"]) == 50
    
    def test_fields_without_optional_agent_fields(self):
        """Test that frames work without optional agent fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                # Standard frame without new fields
                frame_id = trace.record({
                    "event_type": "thought",
                    "content": {"text": "Simple", "rationale_summary": "Basic"}
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                # Should not have optional fields
                assert "success" not in frame
                assert "caused_by" not in frame
                assert "artifacts" not in frame
    
    def test_null_success_is_not_recorded(self):
        """Test that None success is not added to frame."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with AxiomTrace(vault_dir=tmpdir, auto_flush=False) as trace:
                frame_id = trace.record({
                    "event_type": "thought",
                    "content": {"text": "Thinking", "rationale_summary": "..."}
                    # No success field
                })
                
                trace.flush()
                frames = trace._backend.get_all_frames()
                frame = json.loads(frames[0])
                
                assert "success" not in frame

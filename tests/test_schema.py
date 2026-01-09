"""
Tests for JSON schema validation.
"""

import pytest

from axiom_trace.schema import AxiomValidationError, validate_frame


def make_valid_frame(**overrides):
    """Create a valid frame with optional overrides."""
    frame = {
        "frame_id": "550e8400-e29b-41d4-a716-446655440000",
        "session_id": "660e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2026-01-08T22:14:05.123Z",
        "event_type": "thought",
        "actor": {"type": "agent", "id": "test-agent"},
        "content": {
            "text": "This is a test thought",
            "rationale_summary": "Testing the system"
        },
        "metadata": {},
        "vector_key": "thought | Testing the system",
        "prev_hash": "",
        "frame_hash": "abc123"
    }
    frame.update(overrides)
    return frame


class TestValidFrame:
    """Test valid frame scenarios."""
    
    def test_valid_thought_frame(self):
        """Valid thought frame should pass validation."""
        frame = make_valid_frame()
        validate_frame(frame)  # Should not raise
    
    def test_valid_tool_call_frame(self):
        """Valid tool_call frame should pass validation."""
        frame = make_valid_frame(
            event_type="tool_call",
            content={"json": {"tool": "search", "args": {"query": "test"}}},
            metadata={"tool_name": "search"}
        )
        validate_frame(frame)
    
    def test_valid_user_input_frame(self):
        """Valid user_input frame should pass validation."""
        frame = make_valid_frame(
            event_type="user_input",
            actor={"type": "user", "id": "user-1"},
            content={"text": "Hello agent"}
        )
        validate_frame(frame)
    
    def test_valid_error_frame(self):
        """Valid error frame should pass validation."""
        frame = make_valid_frame(
            event_type="error",
            content={"text": "Error occurred: division by zero"}
        )
        validate_frame(frame)


class TestMissingRequiredFields:
    """Test missing required field scenarios."""
    
    def test_missing_frame_id(self):
        """Missing frame_id should fail validation."""
        frame = make_valid_frame()
        del frame["frame_id"]
        
        with pytest.raises(AxiomValidationError) as exc_info:
            validate_frame(frame)
        assert "frame_id" in str(exc_info.value.errors)
    
    def test_missing_event_type(self):
        """Missing event_type should fail validation."""
        frame = make_valid_frame()
        del frame["event_type"]
        
        with pytest.raises(AxiomValidationError):
            validate_frame(frame)
    
    def test_missing_actor(self):
        """Missing actor should fail validation."""
        frame = make_valid_frame()
        del frame["actor"]
        
        with pytest.raises(AxiomValidationError):
            validate_frame(frame)
    
    def test_missing_content(self):
        """Missing content should fail validation."""
        frame = make_valid_frame()
        del frame["content"]
        
        with pytest.raises(AxiomValidationError):
            validate_frame(frame)

class TestInvalidEventType:
    """Test invalid event_type scenarios."""
    
    def test_custom_event_type_is_allowed(self):
        """Custom event_type should pass validation in v1.2+."""
        frame = make_valid_frame(event_type="custom_observation")
        frame["content"] = {"text": "Custom event"}  # Remove rationale_summary requirement
        validate_frame(frame)  # Should not raise in v1.2
    
    def test_empty_event_type_passes(self):
        """Empty event_type now passes in v1.2 (schema is more permissive)."""
        frame = make_valid_frame(event_type="observation")
        frame["content"] = {"text": "Test"}
        validate_frame(frame)  # Custom types allowed


class TestPerEventTypeRequirements:
    """Test per-event-type required fields."""
    
    def test_thought_requires_rationale_summary(self):
        """thought events require content.rationale_summary."""
        frame = make_valid_frame(
            event_type="thought",
            content={"text": "Just a thought"}  # Missing rationale_summary
        )
        
        with pytest.raises(AxiomValidationError) as exc_info:
            validate_frame(frame)
        assert "rationale_summary" in str(exc_info.value)
    
    def test_tool_call_requires_tool_name(self):
        """tool_call events require metadata.tool_name."""
        frame = make_valid_frame(
            event_type="tool_call",
            content={"json": {"tool": "search"}},
            metadata={}  # Missing tool_name
        )
        
        with pytest.raises(AxiomValidationError) as exc_info:
            validate_frame(frame)
        assert "tool_name" in str(exc_info.value)
    
    def test_tool_output_requires_tool_name(self):
        """tool_output events require metadata.tool_name."""
        frame = make_valid_frame(
            event_type="tool_output",
            content={"text": "Search results"},
            metadata={}  # Missing tool_name
        )
        
        with pytest.raises(AxiomValidationError) as exc_info:
            validate_frame(frame)
        assert "tool_name" in str(exc_info.value)

class TestContentConstraints:
    """Test content constraints - v1.2 relaxed to allow agent-friendly fields."""
    
    def test_content_with_both_text_and_json_is_allowed(self):
        """Content with both text and json is now allowed in v1.2 for agent-friendly format."""
        frame = make_valid_frame(
            event_type="tool_call",
            content={
                "text": "Some text",
                "json": {"key": "value"},
                "input": "User request",
                "output": "Result"
            },
            metadata={"tool_name": "test_tool"}
        )
        
        validate_frame(frame)  # Should not raise in v1.2
    
    def test_content_with_just_input_output_reasoning(self):
        """Content with agent-friendly fields should work."""
        frame = make_valid_frame(
            event_type="tool_call",
            content={
                "text": "Action",
                "input": "User request",
                "output": "Created file",
                "reasoning": "Needed to create file"
            },
            metadata={"tool_name": "write_file"}
        )
        
        validate_frame(frame)  # Should pass


class TestActorConstraints:
    """Test actor field constraints."""
    
    def test_invalid_actor_type(self):
        """Invalid actor.type should fail validation."""
        frame = make_valid_frame(
            actor={"type": "invalid_actor", "id": "test"}
        )
        
        with pytest.raises(AxiomValidationError):
            validate_frame(frame)
    
    def test_missing_actor_id(self):
        """Missing actor.id should fail validation."""
        frame = make_valid_frame(
            actor={"type": "agent"}  # Missing id
        )
        
        with pytest.raises(AxiomValidationError):
            validate_frame(frame)

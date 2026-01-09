"""
Tests for quick tracing API.

Tests the vibe coder features: trace.log(), @auto_trace, etc.
"""

import tempfile
import pytest
import json
import os

from axiom_trace.quick import QuickTrace, auto_trace


class TestQuickTrace:
    """Tests for QuickTrace class."""
    
    def test_log_basic(self):
        """Test basic log message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.log("Hello world")
            assert frame_id is not None
            
            trace.close()
    
    def test_thought_basic(self):
        """Test logging a thought."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.thought("Need to fetch user data")
            assert frame_id is not None
            
            trace.close()
    
    def test_tool_basic(self):
        """Test logging a tool call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.tool("search", {"query": "python"})
            assert frame_id is not None
            
            trace.close()
    
    def test_tool_with_result(self):
        """Test logging a tool call with result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.tool("api_call", {"url": "/users"}, result={"count": 10})
            assert frame_id is not None
            
            trace.close()
    
    def test_done_with_string(self):
        """Test logging completion with string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.done("Task completed successfully")
            assert frame_id is not None
            
            trace.close()
    
    def test_done_with_object(self):
        """Test logging completion with object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.done({"users_processed": 100, "errors": 0})
            assert frame_id is not None
            
            trace.close()
    
    def test_error_without_exception(self):
        """Test logging error message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.error("Something went wrong")
            assert frame_id is not None
            
            trace.close()
    
    def test_error_with_exception(self):
        """Test logging error with exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            try:
                raise ValueError("Test error")
            except Exception as e:
                frame_id = trace.error("Failed", e)
            
            assert frame_id is not None
            trace.close()
    
    def test_input_basic(self):
        """Test logging user input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.input("What's the weather?")
            assert frame_id is not None
            
            trace.close()
    
    def test_session_id_consistent(self):
        """Test that session ID stays consistent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            session1 = trace.session_id
            trace.log("First message")
            session2 = trace.session_id
            
            assert session1 == session2
            trace.close()
    
    def test_start_new_session(self):
        """Test starting a new session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            session1 = trace.session_id
            trace.start_session("custom-session-id")
            session2 = trace.session_id
            
            assert session2 == "custom-session-id"
            assert session1 != session2
            trace.close()
    
    def test_metadata_passed_through(self):
        """Test that metadata is included in frame."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            frame_id = trace.log("Test", user_id="123", action="click")
            
            trace._trace.flush()
            frames = trace._trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["metadata"]["user_id"] == "123"
            assert frame["metadata"]["action"] == "click"
            trace.close()


class TestAutoTrace:
    """Tests for @auto_trace decorator."""
    
    def test_auto_trace_basic(self):
        """Test basic auto_trace usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            # Import fresh trace
            from axiom_trace.quick import trace
            trace._ensure_initialized()
            
            @auto_trace
            def add(x, y):
                return x + y
            
            result = add(1, 2)
            assert result == 3
            
            trace.close()
    
    def test_auto_trace_captures_exception(self):
        """Test that auto_trace captures exceptions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            from axiom_trace.quick import trace
            trace._ensure_initialized()
            
            @auto_trace
            def fail():
                raise ValueError("Test error")
            
            with pytest.raises(ValueError):
                fail()
            
            trace.close()
    
    def test_auto_trace_with_custom_name(self):
        """Test auto_trace with custom name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            from axiom_trace.quick import trace
            trace._ensure_initialized()
            
            @auto_trace(name="custom_function")
            def my_func():
                return "done"
            
            result = my_func()
            assert result == "done"
            
            trace.close()
    
    def test_auto_trace_disable_capture_args(self):
        """Test auto_trace with capture_args=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            from axiom_trace.quick import trace
            trace._ensure_initialized()
            
            @auto_trace(capture_args=False)
            def sensitive_func(password):
                return "done"
            
            result = sensitive_func("secret123")
            assert result == "done"
            
            trace.close()


class TestFrameContent:
    """Tests that frames have correct content structure."""
    
    def test_thought_has_rationale_summary(self):
        """Thought frames should have rationale_summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            trace.thought("Need to analyze data")
            trace._trace.flush()
            
            frames = trace._trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["content"]["rationale_summary"] == "Need to analyze data"
            trace.close()
    
    def test_tool_has_tool_name_in_metadata(self):
        """Tool calls should have tool_name in metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            trace.tool("search", {"query": "test"})
            trace._trace.flush()
            
            frames = trace._trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["metadata"]["tool_name"] == "search"
            trace.close()
    
    def test_error_has_success_false(self):
        """Error frames should have success=false."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            trace.error("Something failed")
            trace._trace.flush()
            
            frames = trace._trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["success"] is False
            trace.close()
    
    def test_done_has_success_true(self):
        """Done frames should have success=true."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            trace = QuickTrace()
            
            trace.done("Complete")
            trace._trace.flush()
            
            frames = trace._trace._backend.get_all_frames()
            frame = json.loads(frames[0])
            
            assert frame["success"] is True
            trace.close()

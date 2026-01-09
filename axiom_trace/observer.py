"""
Observer wrappers for capturing agent activity.

Provides decorators and context managers for automatic frame recording.
"""

from __future__ import annotations

import functools
import sys
import traceback
import uuid
from contextlib import contextmanager
from typing import Any, Callable

from axiom_trace.core import AxiomTrace


# Global trace instance for decorator use
_global_trace: AxiomTrace | None = None


def set_global_trace(trace: AxiomTrace) -> None:
    """Set the global trace instance for decorators."""
    global _global_trace
    _global_trace = trace


def get_global_trace() -> AxiomTrace | None:
    """Get the global trace instance."""
    return _global_trace


class ObserverSession:
    """
    Context for observing an agent session.
    
    Provides methods to record various event types.
    """
    
    def __init__(
        self, 
        trace: AxiomTrace, 
        session_id: str,
        actor_id: str = "agent",
        actor_type: str = "agent"
    ):
        self.trace = trace
        self.session_id = session_id
        self.actor_id = actor_id
        self.actor_type = actor_type
    
    def record_user_input(self, text: str, **metadata: Any) -> str:
        """Record a user input event."""
        return self.trace.record({
            "session_id": self.session_id,
            "event_type": "user_input",
            "actor": {"type": "user", "id": "user"},
            "content": {"text": text},
            "metadata": metadata
        })
    
    def record_thought(
        self, 
        rationale_summary: str, 
        text: str = "",
        **metadata: Any
    ) -> str:
        """Record a thought event."""
        content: dict[str, Any] = {
            "rationale_summary": rationale_summary
        }
        if text:
            content["text"] = text
        else:
            content["text"] = rationale_summary
        
        return self.trace.record({
            "session_id": self.session_id,
            "event_type": "thought",
            "actor": {"type": self.actor_type, "id": self.actor_id},
            "content": content,
            "metadata": metadata
        })
    
    def record_tool_call(
        self, 
        tool_name: str, 
        args: dict[str, Any],
        reasoning: str | None = None,
        caused_by: str | None = None,
        **metadata: Any
    ) -> str:
        """Record a tool call event with agent-friendly fields."""
        metadata["tool_name"] = tool_name
        
        content: dict[str, Any] = {
            "json": {"tool": tool_name, "args": args},
            "input": f"Calling {tool_name} with {args}"
        }
        if reasoning:
            content["reasoning"] = reasoning
        
        event: dict[str, Any] = {
            "session_id": self.session_id,
            "event_type": "tool_call",
            "actor": {"type": self.actor_type, "id": self.actor_id},
            "content": content,
            "metadata": metadata
        }
        if caused_by:
            event["caused_by"] = caused_by
        
        return self.trace.record(event)
    
    def record_tool_output(
        self, 
        tool_name: str, 
        output: Any,
        success: bool = True,
        artifacts: list[str] | None = None,
        **metadata: Any
    ) -> str:
        """Record a tool output event with agent-friendly fields."""
        metadata["tool_name"] = tool_name
        
        content: dict[str, Any]
        if isinstance(output, str):
            content = {"text": output, "output": output}
        else:
            content = {
                "json": {"tool": tool_name, "output": output},
                "output": str(output)[:2000]
            }
        
        event: dict[str, Any] = {
            "session_id": self.session_id,
            "event_type": "tool_output",
            "actor": {"type": "tool", "id": tool_name},
            "content": content,
            "metadata": metadata,
            "success": success
        }
        if artifacts:
            event["artifacts"] = artifacts
        
        return self.trace.record(event)
    
    def record_final_result(self, result: Any, **metadata: Any) -> str:
        """Record a final result event."""
        content: dict[str, Any]
        if isinstance(result, str):
            content = {"text": result}
        else:
            content = {"json": result}
        
        return self.trace.record({
            "session_id": self.session_id,
            "event_type": "final_result",
            "actor": {"type": self.actor_type, "id": self.actor_id},
            "content": content,
            "metadata": metadata
        })
    
    def record_error(self, error: Exception, **metadata: Any) -> str:
        """Record an error event."""
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        error_text = "".join(tb)[:4000]  # First 4k chars
        
        return self.trace.record({
            "session_id": self.session_id,
            "event_type": "error",
            "actor": {"type": self.actor_type, "id": self.actor_id},
            "content": {
                "text": error_text,
                "rationale_summary": str(error)[:2000]
            },
            "metadata": {
                "error_type": type(error).__name__,
                **metadata
            }
        })
    
    def record_system_event(self, text: str, **metadata: Any) -> str:
        """Record a system event."""
        return self.trace.record({
            "session_id": self.session_id,
            "event_type": "system_event",
            "actor": {"type": "system", "id": "system"},
            "content": {"text": text},
            "metadata": metadata
        })


@contextmanager
def session(
    session_id: str | None = None,
    trace: AxiomTrace | None = None,
    actor_id: str = "agent",
    actor_type: str = "agent"
):
    """
    Context manager for observing an agent session.
    
    Usage:
        with axiom.session(session_id="...") as obs:
            obs.record_user_input("Hello")
            obs.record_thought("Thinking about greeting...")
            obs.record_final_result("Hello there!")
    
    Args:
        session_id: Optional session ID (generated if not provided)
        trace: Optional AxiomTrace instance (uses global if not provided)
        actor_id: Actor identifier
        actor_type: Actor type
        
    Yields:
        ObserverSession instance
    """
    if trace is None:
        trace = get_global_trace()
        if trace is None:
            raise RuntimeError(
                "No trace instance provided and no global trace set. "
                "Either pass trace= or call set_global_trace() first."
            )
    
    sid = session_id or str(uuid.uuid4())
    obs = ObserverSession(trace, sid, actor_id, actor_type)
    
    try:
        yield obs
    except Exception as e:
        obs.record_error(e)
        raise


def observe(
    session_id: str | None = None,
    trace: AxiomTrace | None = None,
    actor_id: str = "agent",
    event_type: str = "tool_call",
    capture_args: bool = True,
    capture_result: bool = True
):
    """
    Decorator for observing function calls.
    
    Records an event on entry and output on exit.
    
    Usage:
        @observe(session_id="...")
        def my_tool(arg1, arg2):
            return result
        
        @observe(event_type="function_call")
        def my_function():
            pass
    
    Args:
        session_id: Optional session ID (generated if not provided)
        trace: Optional AxiomTrace instance (uses global if not provided)
        actor_id: Actor identifier
        event_type: Event type for the call (default: "tool_call")
        capture_args: Whether to capture function arguments
        capture_result: Whether to capture function result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal trace, session_id
            
            if trace is None:
                trace = get_global_trace()
                if trace is None:
                    # No trace, just run the function
                    return func(*args, **kwargs)
            
            sid = session_id or str(uuid.uuid4())
            
            # Build call args if capturing
            if capture_args:
                call_args = {
                    "args": [repr(a)[:500] for a in args],
                    "kwargs": {k: repr(v)[:500] for k, v in kwargs.items()}
                }
            else:
                call_args = {}
            
            # Record function call
            trace.record({
                "session_id": sid,
                "event_type": event_type,
                "actor": {"type": "agent", "id": actor_id},
                "content": {"json": {"function": func.__name__, "args": call_args}},
                "metadata": {"tool_name": func.__name__}
            })
            
            try:
                result = func(*args, **kwargs)
                
                # Record result
                if capture_result:
                    output_type = "tool_output" if event_type == "tool_call" else "final_result"
                    trace.record({
                        "session_id": sid,
                        "event_type": output_type,
                        "actor": {"type": "tool", "id": func.__name__},
                        "content": {"text": repr(result)[:2000]},
                        "metadata": {"tool_name": func.__name__}
                    })
                
                return result
                
            except Exception as e:
                tb = traceback.format_exception(type(e), e, e.__traceback__)
                error_text = "".join(tb)[:4000]
                trace.record({
                    "session_id": sid,
                    "event_type": "error",
                    "actor": {"type": "agent", "id": actor_id},
                    "content": {"text": error_text},
                    "metadata": {"error_type": type(e).__name__, "tool_name": func.__name__}
                })
                raise
        
        return wrapper
    return decorator

"""
Quick tracing API for vibe coders.

Provides a simple, zero-configuration interface for tracing.

Usage:
    from axiom_trace import trace
    
    trace.log("Processing request")           # Simple log
    trace.thought("Thinking about solution")  # Log thought  
    trace.tool("api_call", {"url": "..."})    # Log tool use
    trace.error("Something failed", exc)       # Log error
    trace.done("Task complete!")              # Log result
"""

from __future__ import annotations

import atexit
import functools
import sys
import time
import traceback
import uuid
from typing import Any, Callable

from axiom_trace.core import AxiomTrace


class QuickTrace:
    """
    Simple tracing interface for developers who want minimal setup.
    
    Features:
    - Zero configuration required
    - Auto-creates vault in .axiom_trace/
    - Auto-generates session IDs
    - Simple method names (log, thought, tool, done, error)
    
    Example:
        from axiom_trace import trace
        
        trace.log("Starting process")
        trace.thought("Need to fetch user data")
        trace.tool("database_query", {"table": "users"})
        trace.done("Processed 100 users")
    """
    
    def __init__(self):
        self._trace: AxiomTrace | None = None
        self._session_id: str | None = None
        self._initialized = False
    
    def _ensure_initialized(self) -> AxiomTrace:
        """Lazy initialization of trace instance."""
        if not self._initialized:
            self._trace = AxiomTrace()
            self._session_id = str(uuid.uuid4())
            self._initialized = True
            atexit.register(self._cleanup)
        return self._trace
    
    def _cleanup(self):
        """Clean up on exit."""
        if self._trace:
            try:
                self._trace.close()
            except Exception:
                pass
    
    def start_session(self, session_id: str | None = None) -> str:
        """
        Start a new tracing session.
        
        Args:
            session_id: Optional custom session ID
            
        Returns:
            The session ID being used
        """
        self._ensure_initialized()
        self._session_id = session_id or str(uuid.uuid4())
        return self._session_id
    
    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        self._ensure_initialized()
        return self._session_id
    
    def log(self, message: str, **metadata) -> str:
        """
        Log a simple message.
        
        This is the simplest way to record something - just pass a string.
        
        Args:
            message: The message to log
            **metadata: Optional metadata fields
            
        Returns:
            The frame ID of the recorded trace
            
        Example:
            trace.log("User clicked button")
            trace.log("Processing data", user_id="123")
        """
        trace = self._ensure_initialized()
        return trace.record({
            "session_id": self._session_id,
            "event_type": "system_event",
            "content": {"text": message},
            "metadata": metadata
        })
    
    def thought(self, reasoning: str, details: str = "", **metadata) -> str:
        """
        Log a thought or reasoning step.
        
        Use this when your agent is thinking or making a decision.
        
        Args:
            reasoning: The main reasoning/thought (shown as rationale_summary)
            details: Optional detailed explanation
            **metadata: Optional metadata fields
            
        Returns:
            The frame ID of the recorded trace
            
        Example:
            trace.thought("Need to call weather API")
            trace.thought("User wants NYC weather", details="Extracted city from query")
        """
        trace = self._ensure_initialized()
        content = {
            "text": details or reasoning,
            "rationale_summary": reasoning,
            "reasoning": reasoning
        }
        return trace.record({
            "session_id": self._session_id,
            "event_type": "thought",
            "content": content,
            "metadata": metadata
        })
    
    def tool(
        self, 
        name: str, 
        args: dict[str, Any] | None = None,
        result: Any = None,
        success: bool = True,
        **metadata
    ) -> str:
        """
        Log a tool call.
        
        Use this when calling a tool, API, or external service.
        
        Args:
            name: Name of the tool/function being called
            args: Arguments passed to the tool
            result: Optional result from the tool
            success: Whether the tool call succeeded
            **metadata: Optional metadata fields
            
        Returns:
            The frame ID of the recorded trace
            
        Example:
            trace.tool("search", {"query": "python"})
            trace.tool("api_call", {"url": "/users"}, result={"count": 10})
            trace.tool("database", {"query": "SELECT *"}, success=False)
        """
        trace = self._ensure_initialized()
        
        content: dict[str, Any] = {
            "input": f"Calling {name}",
            "json": {"tool": name, "args": args or {}}
        }
        
        if result is not None:
            content["output"] = str(result)[:2000]
        
        if args:
            content["reasoning"] = f"Tool: {name}, Args: {args}"
        
        event = {
            "session_id": self._session_id,
            "event_type": "tool_call",
            "content": content,
            "metadata": {"tool_name": name, **metadata},
            "success": success
        }
        
        return trace.record(event)
    
    def done(self, result: str | Any, **metadata) -> str:
        """
        Log a final result or completion.
        
        Use this when a task or operation is complete.
        
        Args:
            result: The final result (string or object)
            **metadata: Optional metadata fields
            
        Returns:
            The frame ID of the recorded trace
            
        Example:
            trace.done("Task completed successfully")
            trace.done({"users_processed": 100, "errors": 0})
        """
        trace = self._ensure_initialized()
        
        if isinstance(result, str):
            content = {"text": result, "output": result}
        else:
            content = {"json": result, "output": str(result)[:2000]}
        
        return trace.record({
            "session_id": self._session_id,
            "event_type": "final_result",
            "content": content,
            "metadata": metadata,
            "success": True
        })
    
    def error(self, message: str, exception: Exception | None = None, **metadata) -> str:
        """
        Log an error.
        
        Use this when something goes wrong.
        
        Args:
            message: Error message
            exception: Optional exception object
            **metadata: Optional metadata fields
            
        Returns:
            The frame ID of the recorded trace
            
        Example:
            trace.error("Failed to connect to database")
            trace.error("API call failed", e)
        """
        trace = self._ensure_initialized()
        
        text = message
        if exception:
            tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
            text = f"{message}\n\n{''.join(tb)}"
        
        return trace.record({
            "session_id": self._session_id,
            "event_type": "error",
            "content": {"text": text[:4000]},
            "metadata": {"error_type": type(exception).__name__ if exception else "Error", **metadata},
            "success": False
        })
    
    def input(self, text: str, user_id: str = "user", **metadata) -> str:
        """
        Log a user input.
        
        Use this when recording what a user said or requested.
        
        Args:
            text: The user's input
            user_id: Identifier for the user
            **metadata: Optional metadata fields
            
        Returns:
            The frame ID of the recorded trace
            
        Example:
            trace.input("What's the weather in NYC?")
            trace.input("Build me an API", user_id="developer-1")
        """
        trace = self._ensure_initialized()
        return trace.record({
            "session_id": self._session_id,
            "event_type": "user_input",
            "actor": {"type": "user", "id": user_id},
            "content": {"text": text, "input": text},
            "metadata": metadata
        })
    
    def search(
        self, 
        query: str, 
        limit: int = 5,
        event_type: str | None = None,
        session_id: str | None = None
    ) -> list[dict]:
        """
        Search traces using semantic similarity (powered by Memvid).
        
        This enables coding agents to find relevant past context
        from their traces. The search uses vector embeddings for
        semantic matching, not just keyword matching.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results (default: 5)
            event_type: Optional filter by event type
            session_id: Optional filter by session
            
        Returns:
            List of matching frames, ranked by relevance
            
        Example:
            # Find relevant past context
            results = trace.search("user authentication")
            for r in results:
                print(f"{r['event_type']}: {r['content']}")
            
            # Filter by type
            thoughts = trace.search("API design", event_type="thought")
            
            # Agent retrospection pattern
            past_work = trace.search("similar task I did before")
            context = "\\n".join(r['content'].get('text', '') for r in past_work)
        """
        trace = self._ensure_initialized()
        
        # Build filters
        filters = {}
        if event_type:
            filters["event_type"] = event_type
        if session_id:
            filters["session_id"] = session_id
        
        return trace.query(query, limit, filters if filters else None)
    
    def context(self, query: str, limit: int = 5) -> str:
        """
        Get relevant context from past traces as a formatted string.
        
        This is a convenience method for coding agents that want
        to retrieve past context in a format ready for use in prompts.
        
        Args:
            query: Natural language query for what context to find
            limit: Maximum number of traces to include
            
        Returns:
            Formatted string with relevant past traces
            
        Example:
            # Get context for current task
            past_context = trace.context("building REST APIs")
            
            # Use in agent prompt
            prompt = f'''
            Here's what I did before on similar tasks:
            {past_context}
            
            Now I need to: {current_task}
            '''
        """
        results = self.search(query, limit)
        
        if not results:
            return "No relevant past traces found."
        
        lines = []
        for r in results:
            event_type = r.get("event_type", "unknown")
            content = r.get("content", {})
            
            # Get the most useful text
            text = content.get("reasoning") or content.get("output") or content.get("text", "")
            if text:
                text = text[:500]  # Truncate for prompt efficiency
                lines.append(f"[{event_type}] {text}")
        
        return "\n".join(lines)
    
    def close(self):
        """Close the trace and flush all pending data."""
        if self._trace:
            self._trace.close()
            self._trace = None
            self._initialized = False


def auto_trace(
    func: Callable | None = None,
    *,
    name: str | None = None,
    capture_args: bool = True,
    capture_result: bool = True
):
    """
    Decorator that automatically traces function calls.
    
    Zero-configuration function tracing. Captures:
    - Function name
    - Arguments (if capture_args=True)
    - Return value (if capture_result=True)
    - Exceptions
    - Execution time
    
    Usage:
        @auto_trace
        def my_function(x, y):
            return x + y
        
        @auto_trace(name="custom_name")
        def another_function():
            pass
    
    Args:
        func: The function to trace (when used without parentheses)
        name: Optional custom name for the trace
        capture_args: Whether to capture function arguments
        capture_result: Whether to capture return value
        
    Returns:
        Decorated function
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Use the global trace instance
            trace_name = name or fn.__name__
            
            # Build args representation
            args_repr = {}
            if capture_args:
                args_repr["args"] = [repr(a)[:200] for a in args]
                args_repr["kwargs"] = {k: repr(v)[:200] for k, v in kwargs.items()}
            
            # Log the call
            start_time = time.time()
            trace.tool(trace_name, args_repr)
            
            try:
                result = fn(*args, **kwargs)
                elapsed_ms = int((time.time() - start_time) * 1000)
                
                # Log success
                if capture_result:
                    trace.log(
                        f"{trace_name} completed: {repr(result)[:500]}",
                        latency_ms=elapsed_ms
                    )
                
                return result
                
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                trace.error(f"{trace_name} failed", e, latency_ms=elapsed_ms)
                raise
        
        return wrapper
    
    # Handle both @auto_trace and @auto_trace()
    if func is not None:
        return decorator(func)
    return decorator


# Global trace instance - import and use directly
trace = QuickTrace()

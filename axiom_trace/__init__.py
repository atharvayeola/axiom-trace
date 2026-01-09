"""
Axiom Trace - Local-first, append-only trace vault for AI agents.

Provides cryptographic integrity, deterministic schema validation,
and hybrid search over recorded frames.

Quick Start:
    from axiom_trace import trace
    
    trace.log("Processing request")
    trace.thought("Thinking about solution")
    trace.tool("api_call", {"url": "..."})
    trace.done("Task complete!")
"""

from axiom_trace.core import AxiomTrace
from axiom_trace.observer import observe, session, set_global_trace, get_global_trace
from axiom_trace.schema import AxiomValidationError
from axiom_trace.backend import AxiomLockError
from axiom_trace.quick import trace, auto_trace, QuickTrace

__version__ = "1.4.1"
__all__ = [
    # Core
    "AxiomTrace",
    # Quick API (recommended for most users)
    "trace",
    "auto_trace",
    "QuickTrace",
    # Observer pattern
    "observe",
    "session",
    "set_global_trace",
    "get_global_trace",
    # Exceptions
    "AxiomValidationError",
    "AxiomLockError",
]

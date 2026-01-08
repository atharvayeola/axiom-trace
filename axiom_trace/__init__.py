"""
Axiom Trace - Local-first, append-only trace vault for AI agents.

Provides cryptographic integrity, deterministic schema validation,
and hybrid search over recorded frames.
"""

from axiom_trace.core import AxiomTrace
from axiom_trace.observer import observe, session
from axiom_trace.schema import AxiomValidationError
from axiom_trace.backend import AxiomLockError

__version__ = "1.1.0"
__all__ = [
    "AxiomTrace",
    "observe",
    "session",
    "AxiomValidationError",
    "AxiomLockError",
]

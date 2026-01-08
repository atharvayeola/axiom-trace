"""
JSON Schema validation for Axiom frames.

Validates frames against the Axiom Frame v1.1 schema and enforces
per-event-type required fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator


class AxiomValidationError(Exception):
    """Raised when frame validation fails."""
    
    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


# Load schema at module import time
_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "axiom_frame_v1_1.json"
_SCHEMA: dict[str, Any] | None = None


def _load_schema() -> dict[str, Any]:
    """Load the JSON schema from disk (cached)."""
    global _SCHEMA
    if _SCHEMA is None:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            _SCHEMA = json.load(f)
    return _SCHEMA


def validate_frame(frame: dict[str, Any]) -> None:
    """
    Validate a frame against the Axiom Frame v1.1 schema.
    
    Also enforces per-event-type required fields:
    - thought: content.rationale_summary required
    - tool_call: metadata.tool_name required
    - tool_output: metadata.tool_name required
    
    Args:
        frame: The frame dictionary to validate
        
    Raises:
        AxiomValidationError: If validation fails
    """
    schema = _load_schema()
    validator = Draft7Validator(schema)
    
    # Collect all validation errors
    errors = list(validator.iter_errors(frame))
    
    if errors:
        error_messages = [_format_error(e) for e in errors]
        raise AxiomValidationError(
            f"Frame validation failed with {len(errors)} error(s)",
            error_messages
        )
    
    # Per-event-type validation
    event_type = frame.get("event_type")
    content = frame.get("content", {})
    metadata = frame.get("metadata", {})
    
    if event_type == "thought":
        if "rationale_summary" not in content:
            raise AxiomValidationError(
                "thought events require content.rationale_summary",
                ["content.rationale_summary is required for thought events"]
            )
    
    if event_type in ("tool_call", "tool_output"):
        if "tool_name" not in metadata:
            raise AxiomValidationError(
                f"{event_type} events require metadata.tool_name",
                [f"metadata.tool_name is required for {event_type} events"]
            )
    
    # Size limit for content.json
    if "json" in content:
        import orjson
        json_bytes = orjson.dumps(content["json"])
        if len(json_bytes) > 1_000_000:
            raise AxiomValidationError(
                "content.json exceeds maximum size of 1,000,000 bytes",
                [f"content.json is {len(json_bytes)} bytes, max is 1,000,000"]
            )


def _format_error(error: jsonschema.ValidationError) -> str:
    """Format a validation error for display."""
    path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
    return f"{path}: {error.message}"

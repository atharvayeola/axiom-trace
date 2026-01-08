"""
Regex-based redaction engine for sensitive data.

Applies redaction patterns to frame content before storage,
replacing matches with [REDACTED].
"""

from __future__ import annotations

import re
from typing import Any

# Redaction patterns for common sensitive data formats
REDACTION_PATTERNS = [
    # API keys (various formats)
    re.compile(r"(?i)api[_-]?key\s*[=:]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"),
    re.compile(r"(?i)apikey\s*[=:]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"),
    
    # Bearer tokens
    re.compile(r"(?i)authorization:\s*bearer\s+([a-zA-Z0-9_\-\.]+)"),
    re.compile(r"(?i)bearer\s+([a-zA-Z0-9_\-\.]{20,})"),
    
    # Secret/token patterns
    re.compile(r"(?i)secret[_-]?key\s*[=:]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"),
    re.compile(r"(?i)access[_-]?token\s*[=:]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"),
    re.compile(r"(?i)auth[_-]?token\s*[=:]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"),
    
    # Password patterns
    re.compile(r"(?i)password\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?"),
    re.compile(r"(?i)passwd\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?"),
    
    # AWS-style keys
    re.compile(r"(?i)aws[_-]?access[_-]?key[_-]?id\s*[=:]\s*['\"]?([A-Z0-9]{16,})['\"]?"),
    re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*['\"]?([a-zA-Z0-9/+=]{30,})['\"]?"),
    
    # GitHub tokens
    re.compile(r"(ghp_[a-zA-Z0-9]{36,})"),
    re.compile(r"(github_pat_[a-zA-Z0-9_]{22,})"),
    
    # OpenAI API keys
    re.compile(r"(sk-[a-zA-Z0-9]{32,})"),
    
    # Private keys
    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
]

REDACTED_TEXT = "[REDACTED]"


def redact_string(text: str) -> str:
    """
    Apply redaction patterns to a string.
    
    Args:
        text: String to redact
        
    Returns:
        Redacted string with sensitive data replaced
    """
    result = text
    for pattern in REDACTION_PATTERNS:
        result = pattern.sub(REDACTED_TEXT, result)
    return result


def redact_value(value: Any) -> Any:
    """
    Recursively redact sensitive data from a value.
    
    Handles strings, lists, and dicts.
    
    Args:
        value: Value to redact
        
    Returns:
        Redacted value
    """
    if isinstance(value, str):
        return redact_string(value)
    elif isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [redact_value(item) for item in value]
    else:
        return value


def redact_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """
    Apply redaction to a frame's content.
    
    Redacts:
    - content.text
    - All string leaf nodes in content.json
    
    Args:
        frame: Frame dictionary to redact
        
    Returns:
        Copy of frame with sensitive data redacted
    """
    frame = frame.copy()
    content = frame.get("content", {}).copy()
    
    if "text" in content:
        content["text"] = redact_string(content["text"])
    
    if "json" in content:
        content["json"] = redact_value(content["json"])
    
    if "rationale_summary" in content:
        content["rationale_summary"] = redact_string(content["rationale_summary"])
    
    if "raw_thought" in content:
        content["raw_thought"] = redact_string(content["raw_thought"])
    
    frame["content"] = content
    return frame

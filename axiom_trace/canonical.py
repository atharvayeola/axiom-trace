"""
Deterministic canonicalization and hashing for Axiom frames.

Ensures that the same input produces identical output every time,
enabling tamper-evident hash chains.
"""

from __future__ import annotations

import hashlib
from typing import Any

import orjson


def canonicalize(frame: dict[str, Any]) -> bytes:
    """
    Convert a frame to canonical JSON bytes.
    
    - UTF-8 encoding
    - Keys sorted lexicographically at every object level
    - No insignificant whitespace
    - Floats serialized in stable way
    
    Args:
        frame: The frame dictionary to canonicalize
        
    Returns:
        Canonical JSON as UTF-8 bytes
    """
    return orjson.dumps(
        frame,
        option=orjson.OPT_SORT_KEYS | orjson.OPT_SERIALIZE_NUMPY
    )


def compute_frame_hash(frame_without_hash: dict[str, Any], prev_hash: str) -> str:
    """
    Compute the SHA-256 hash for a frame.
    
    The hash is computed over the canonical JSON of the frame (with frame_hash
    omitted but prev_hash included) concatenated with the previous hash.
    
    Args:
        frame_without_hash: Frame dict without the frame_hash field
        prev_hash: The hash of the previous frame (empty string for first frame)
        
    Returns:
        Hexadecimal SHA-256 hash string
    """
    # Ensure frame doesn't have frame_hash
    if "frame_hash" in frame_without_hash:
        frame_without_hash = {k: v for k, v in frame_without_hash.items() if k != "frame_hash"}
    
    # Ensure prev_hash is set correctly in the frame
    frame_without_hash["prev_hash"] = prev_hash
    
    # Canonicalize and hash
    canonical_bytes = canonicalize(frame_without_hash)
    
    # Hash: canonical_frame + prev_hash
    hasher = hashlib.sha256()
    hasher.update(canonical_bytes)
    hasher.update(prev_hash.encode("utf-8"))
    
    return hasher.hexdigest()


def verify_frame_hash(frame: dict[str, Any], expected_prev_hash: str) -> bool:
    """
    Verify that a frame's hash is correct.
    
    Args:
        frame: Complete frame with frame_hash field
        expected_prev_hash: The expected previous hash
        
    Returns:
        True if hash is valid, False otherwise
    """
    if "frame_hash" not in frame:
        return False
    
    stored_hash = frame["frame_hash"]
    frame_copy = {k: v for k, v in frame.items() if k != "frame_hash"}
    
    computed_hash = compute_frame_hash(frame_copy, expected_prev_hash)
    
    return stored_hash == computed_hash

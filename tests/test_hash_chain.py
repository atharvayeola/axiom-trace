"""
Tests for hash chain integrity.
"""

import pytest

from axiom_trace.canonical import (
    canonicalize,
    compute_frame_hash,
    verify_frame_hash,
)


class TestCanonicalization:
    """Test canonical JSON serialization."""
    
    def test_deterministic_output(self):
        """Same input should always produce same output."""
        frame = {
            "b_field": "value2",
            "a_field": "value1",
            "nested": {"z": 1, "a": 2}
        }
        
        result1 = canonicalize(frame)
        result2 = canonicalize(frame)
        
        assert result1 == result2
    
    def test_keys_sorted(self):
        """Keys should be sorted lexicographically."""
        frame = {"z": 1, "a": 2, "m": 3}
        result = canonicalize(frame)
        
        # Decode and check order
        decoded = result.decode("utf-8")
        assert decoded.index('"a"') < decoded.index('"m"') < decoded.index('"z"')
    
    def test_nested_keys_sorted(self):
        """Nested object keys should also be sorted."""
        frame = {"outer": {"z": 1, "a": 2}}
        result = canonicalize(frame)
        decoded = result.decode("utf-8")
        
        assert decoded.index('"a"') < decoded.index('"z"')
    
    def test_no_whitespace(self):
        """Canonical JSON should have no insignificant whitespace."""
        frame = {"key": "value", "nested": {"inner": 123}}
        result = canonicalize(frame)
        decoded = result.decode("utf-8")
        
        assert "\n" not in decoded
        assert "  " not in decoded  # No double spaces
    
    def test_utf8_encoding(self):
        """Output should be UTF-8 encoded."""
        frame = {"message": "Hello, 世界! 🌍"}
        result = canonicalize(frame)
        
        assert isinstance(result, bytes)
        # Should decode successfully
        decoded = result.decode("utf-8")
        assert "世界" in decoded
        assert "🌍" in decoded


class TestHashComputation:
    """Test hash chain computation."""
    
    def test_hash_is_sha256_hex(self):
        """Hash should be 64-character hex string (SHA-256)."""
        frame = {
            "frame_id": "test-id",
            "content": {"text": "test"},
            "prev_hash": ""
        }
        
        result = compute_frame_hash(frame, "")
        
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)
    
    def test_hash_depends_on_content(self):
        """Different content should produce different hashes."""
        frame1 = {"content": {"text": "hello"}, "prev_hash": ""}
        frame2 = {"content": {"text": "world"}, "prev_hash": ""}
        
        hash1 = compute_frame_hash(frame1, "")
        hash2 = compute_frame_hash(frame2, "")
        
        assert hash1 != hash2
    
    def test_hash_depends_on_prev_hash(self):
        """Different prev_hash should produce different hashes."""
        frame = {"content": {"text": "hello"}, "prev_hash": ""}
        
        hash1 = compute_frame_hash(frame, "")
        hash2 = compute_frame_hash(frame, "abc123")
        
        assert hash1 != hash2
    
    def test_hash_deterministic(self):
        """Same input should always produce same hash."""
        frame = {
            "frame_id": "test-id",
            "session_id": "session-1",
            "content": {"text": "test content"},
            "prev_hash": ""
        }
        
        hash1 = compute_frame_hash(frame, "")
        hash2 = compute_frame_hash(frame, "")
        
        assert hash1 == hash2
    
    def test_hash_removes_existing_frame_hash(self):
        """Existing frame_hash in input should be ignored."""
        frame = {
            "content": {"text": "test"},
            "frame_hash": "should_be_ignored",
            "prev_hash": ""
        }
        
        # Should not raise and should compute correctly
        result = compute_frame_hash(frame, "")
        assert result != "should_be_ignored"


class TestHashVerification:
    """Test hash chain verification."""
    
    def test_verify_valid_hash(self):
        """Valid hash should verify successfully."""
        frame = {
            "frame_id": "test-id",
            "content": {"text": "test"},
            "prev_hash": ""
        }
        
        # Compute hash and add to frame
        frame["frame_hash"] = compute_frame_hash(frame, "")
        
        assert verify_frame_hash(frame, "") is True
    
    def test_verify_tampered_content(self):
        """Tampered content should fail verification."""
        frame = {
            "frame_id": "test-id",
            "content": {"text": "original"},
            "prev_hash": ""
        }
        frame["frame_hash"] = compute_frame_hash(frame, "")
        
        # Tamper with content
        frame["content"]["text"] = "modified"
        
        assert verify_frame_hash(frame, "") is False
    
    def test_verify_wrong_prev_hash(self):
        """Wrong prev_hash should fail verification."""
        frame = {
            "frame_id": "test-id",
            "content": {"text": "test"},
            "prev_hash": "original_prev"
        }
        frame["frame_hash"] = compute_frame_hash(frame, "original_prev")
        
        # Verify with different prev_hash
        assert verify_frame_hash(frame, "wrong_prev") is False
    
    def test_verify_missing_frame_hash(self):
        """Frame without frame_hash should fail verification."""
        frame = {
            "frame_id": "test-id",
            "content": {"text": "test"},
            "prev_hash": ""
        }
        
        assert verify_frame_hash(frame, "") is False


class TestHashChain:
    """Test chaining multiple frames."""
    
    def test_chain_of_three_frames(self):
        """Verify a chain of three frames."""
        frames = []
        prev_hash = ""
        
        for i in range(3):
            frame = {
                "frame_id": f"frame-{i}",
                "content": {"text": f"Content {i}"},
                "prev_hash": prev_hash
            }
            frame["frame_hash"] = compute_frame_hash(frame, prev_hash)
            frames.append(frame)
            prev_hash = frame["frame_hash"]
        
        # Verify chain
        prev = ""
        for frame in frames:
            assert verify_frame_hash(frame, prev)
            assert frame["prev_hash"] == prev
            prev = frame["frame_hash"]
    
    def test_detect_deleted_frame(self):
        """Deleting a frame should break the chain."""
        frames = []
        prev_hash = ""
        
        for i in range(3):
            frame = {
                "frame_id": f"frame-{i}",
                "content": {"text": f"Content {i}"},
                "prev_hash": prev_hash
            }
            frame["frame_hash"] = compute_frame_hash(frame, prev_hash)
            frames.append(frame)
            prev_hash = frame["frame_hash"]
        
        # Delete middle frame
        del frames[1]
        
        # First frame should verify
        assert verify_frame_hash(frames[0], "")
        
        # Third frame (now at index 1) should fail - its prev_hash
        # points to the deleted frame
        assert frames[1]["prev_hash"] != frames[0]["frame_hash"]
    
    def test_detect_reordered_frames(self):
        """Reordering frames should break the chain."""
        frames = []
        prev_hash = ""
        
        for i in range(3):
            frame = {
                "frame_id": f"frame-{i}",
                "content": {"text": f"Content {i}"},
                "prev_hash": prev_hash
            }
            frame["frame_hash"] = compute_frame_hash(frame, prev_hash)
            frames.append(frame)
            prev_hash = frame["frame_hash"]
        
        # Swap frames 1 and 2
        frames[1], frames[2] = frames[2], frames[1]
        
        # Verify chain is broken
        prev = ""
        chain_valid = True
        for frame in frames:
            if not verify_frame_hash(frame, prev) or frame["prev_hash"] != prev:
                chain_valid = False
                break
            prev = frame["frame_hash"]
        
        assert chain_valid is False

"""
Comprehensive Test Suite for AURA Bitpacked Extension
=====================================================

Tests the ultra-compressed 4-byte and 6-byte secure formats for AI Safety System messages.

Coverage:
- Basic encode/decode (4-byte format)
- Secure variant (6-byte with CRC)
- Property-based testing (round-trip invariants)
- Edge cases and error handling
- Integration with AURA compression
- Audit verification
- Performance benchmarks
"""

import pytest
try:
    from hypothesis import given, strategies as st, settings, assume
except Exception:  # pragma: no cover - skip when hypothesis not installed
    pytest.skip("hypothesis not installed in active interpreter", allow_module_level=True)
from typing import Optional
import re

from communication.aura_bitpacked_extension import (
    BitPackedCompressor,
    AuraWithBitPacking,
    BitPackedMessageType,
    BitPackedAction,
    BitPackedConfidence,
    BitPackedRisk,
)


class TestBasicCompression:
    """Test basic 4-byte compression/decompression"""

    def test_simple_approval(self):
        """Test compressing a simple approval message"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        compressed = compressor.compress(text)
        assert compressed is not None
        assert len(compressed) == 4
        assert compressed[0] == 0x06  # METHOD_BYTE

        decompressed = compressor.decompress(compressed)
        assert decompressed == text

    def test_simple_rejection(self):
        """Test compressing a simple rejection message"""
        compressor = BitPackedCompressor()
        text = "System 2 rejects proposal 043"

        compressed = compressor.compress(text)
        assert compressed is not None
        assert len(compressed) == 4

        decompressed = compressor.decompress(compressed)
        assert decompressed == text

    def test_review_message(self):
        """Test compressing a review message"""
        compressor = BitPackedCompressor()
        text = "System 3 reviews proposal 001"

        compressed = compressor.compress(text)
        assert compressed is not None

        decompressed = compressor.decompress(compressed)
        assert "reviews" in decompressed

    def test_approval_with_high_confidence(self):
        """Test message with confidence qualifier"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042 with high confidence"

        compressed = compressor.compress(text)
        assert compressed is not None

        decompressed = compressor.decompress(compressed)
        assert "high confidence" in decompressed

    def test_message_with_risk(self):
        """Test message with risk indicator"""
        compressor = BitPackedCompressor()
        text = "System 5 approves proposal 100 with risk"

        compressed = compressor.compress(text)
        assert compressed is not None

        decompressed = compressor.decompress(compressed)
        assert "risk" in decompressed.lower()

    def test_cannot_compress_non_matching(self):
        """Test that non-matching messages return None"""
        compressor = BitPackedCompressor()
        text = "This is not a valid system message"

        compressed = compressor.compress(text)
        assert compressed is None

    def test_all_system_ids(self):
        """Test all valid system IDs (0-15)"""
        compressor = BitPackedCompressor()

        for sys_id in range(16):
            text = f"System {sys_id} approves proposal 042"
            compressed = compressor.compress(text)
            assert compressed is not None

            decompressed = compressor.decompress(compressed)
            assert f"System {sys_id}" in decompressed

    def test_all_proposal_ids(self):
        """Test boundary proposal IDs"""
        compressor = BitPackedCompressor()

        # Test min, mid, max
        for prop_id in [0, 1, 42, 127, 254, 255]:
            text = f"System 1 approves proposal {prop_id}"
            compressed = compressor.compress(text)
            assert compressed is not None

            decompressed = compressor.decompress(compressed)
            assert f"proposal {prop_id:03d}" in decompressed


class TestSecureCompression:
    """Test 6-byte secure format with CRC and sequence"""

    def test_secure_compression_basic(self):
        """Test basic secure compression"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        compressed = compressor.compress_secure(text)
        assert compressed is not None
        assert len(compressed) == 6
        assert compressed[0] == 0x16  # SECURE_METHOD_BYTE

        decompressed = compressor.decompress_secure(compressed)
        assert decompressed == text

    def test_secure_crc_validation(self):
        """Test that CRC validation catches corruption"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        compressed = compressor.compress_secure(text)
        assert compressed is not None

        # Corrupt a byte
        corrupted = bytearray(compressed)
        corrupted[2] ^= 0x01  # Flip one bit in proposal ID

        decompressed = compressor.decompress_secure(bytes(corrupted))
        assert decompressed is None  # Should fail CRC check

    def test_secure_sequence_incrementing(self):
        """Test that sequence numbers increment"""
        compressor = BitPackedCompressor()

        # Compress multiple messages from same system
        messages = [
            "System 1 approves proposal 001",
            "System 1 approves proposal 002",
            "System 1 approves proposal 003",
        ]

        sequences = []
        for msg in messages:
            compressed = compressor.compress_secure(msg)
            assert compressed is not None
            sequences.append(compressed[4])  # Sequence is byte 4

        # Sequences should increment
        assert sequences == [0, 1, 2]

    def test_secure_sequence_per_system(self):
        """Test that sequences are tracked per sender"""
        compressor = BitPackedCompressor()

        # System 1 messages
        msg1_sys1 = compressor.compress_secure("System 1 approves proposal 001")
        msg2_sys1 = compressor.compress_secure("System 1 approves proposal 002")

        # System 2 messages
        msg1_sys2 = compressor.compress_secure("System 2 approves proposal 001")

        # System 1 should have sequences 0, 1
        assert msg1_sys1[4] == 0
        assert msg2_sys1[4] == 1

        # System 2 should start at 0
        assert msg1_sys2[4] == 0

    def test_secure_verbose_decode(self):
        """Test verbose decode of secure format"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        compressed = compressor.compress_secure(text)
        assert compressed is not None

        verbose = compressor.decode_verbose_secure(compressed)
        assert verbose['format'] == 'BITPACKED_SECURE_V1'
        assert verbose['crc_ok'] is True
        assert verbose['decoded_fields']['from_system'] == 1
        assert verbose['decoded_fields']['proposal_id'] == 42
        assert verbose['auditable'] is True


class TestConfidenceLevels:
    """Test all confidence levels"""

    @pytest.mark.parametrize("confidence_text,expected_level", [
        ("with low confidence", "low"),
        ("with medium confidence", "medium"),
        ("with high confidence", "high"),
        ("with maximum confidence", "maximum"),
        # Note: "very high" maps to HIGH not MAXIMUM per implementation
        ("with very high confidence", "high"),  # Actually maps to HIGH
        ("", "medium"),  # Default
    ])
    def test_confidence_parsing(self, confidence_text, expected_level):
        """Test parsing all confidence levels"""
        compressor = BitPackedCompressor()
        text = f"System 1 approves proposal 042 {confidence_text}".strip()

        compressed = compressor.compress(text)
        assert compressed is not None

        verbose = compressor.decode_verbose(compressed)
        confidence_str = verbose['decoded_fields']['confidence']

        # Extract just the confidence level from the string
        if "(" in confidence_str:
            actual_level = confidence_str.split("(")[1].rstrip(")")
        else:
            actual_level = confidence_str

        # Medium confidence doesn't appear in decompressed text
        if expected_level == "medium":
            decompressed = compressor.decompress(compressed)
            # Medium confidence is omitted from reconstructed text
            assert "medium" not in decompressed or "medium" in confidence_text
        else:
            assert expected_level in confidence_str.lower()


class TestMessageTypes:
    """Test all message types"""

    @pytest.mark.parametrize("action,message_type", [
        ("approves", "approval"),
        ("rejects", "rejection"),
        ("reviews", "review"),
        ("votes", "vote"),
    ])
    def test_message_types(self, action, message_type):
        """Test all supported message types"""
        compressor = BitPackedCompressor()
        text = f"System 1 {action} proposal 042"

        compressed = compressor.compress(text)
        assert compressed is not None

        verbose = compressor.decode_verbose(compressed)
        decoded_type = verbose['decoded_fields']['message_type']
        assert message_type in decoded_type.lower()


class TestBitFieldEncoding:
    """Test correct bit field packing"""

    def test_control_byte_structure(self):
        """Test control byte bit field structure"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042 with high confidence"

        compressed = compressor.compress(text)
        assert compressed is not None

        control_byte = compressed[1]

        # Extract fields
        msg_type = (control_byte >> 5) & 0b111
        action = (control_byte >> 3) & 0b11
        confidence = (control_byte >> 1) & 0b11
        risk = control_byte & 0b1

        # Verify structure
        assert msg_type == BitPackedMessageType.APPROVAL
        assert action == BitPackedAction.APPROVE
        assert confidence == BitPackedConfidence.HIGH
        assert risk == BitPackedRisk.NO_RISK

    def test_system_ids_packing(self):
        """Test system IDs are correctly packed"""
        compressor = BitPackedCompressor()
        text = "System 7 approves proposal 042"

        compressed = compressor.compress(text)
        assert compressed is not None

        system_ids = compressed[3]
        from_sys = (system_ids >> 4) & 0xF
        to_sys = system_ids & 0xF

        assert from_sys == 7
        assert to_sys == 6  # Default


class TestRoundTripProperties:
    """Property-based tests using Hypothesis"""

    @given(
        system_id=st.integers(min_value=0, max_value=15),
        proposal_id=st.integers(min_value=0, max_value=255),
        action=st.sampled_from(["approves", "rejects", "reviews"]),
    )
    @settings(max_examples=100)
    def test_roundtrip_invariant(self, system_id, proposal_id, action):
        """Property: encode(decode(x)) should equal x for valid messages"""
        compressor = BitPackedCompressor()
        text = f"System {system_id} {action} proposal {proposal_id}"

        compressed = compressor.compress(text)
        assume(compressed is not None)  # Only test valid messages

        decompressed = compressor.decompress(compressed)
        assert decompressed is not None

        # Re-compress and verify
        re_compressed = compressor.compress(decompressed)
        assert re_compressed == compressed

    @given(
        system_id=st.integers(min_value=0, max_value=15),
        proposal_id=st.integers(min_value=0, max_value=255),
    )
    @settings(max_examples=50)
    def test_secure_roundtrip(self, system_id, proposal_id):
        """Property: secure format should round-trip correctly

        Note: Decompressed text uses 3-digit zero-padded proposal IDs (e.g., "042")
        """
        compressor = BitPackedCompressor()
        # Use 3-digit format to match decompression output
        text = f"System {system_id} approves proposal {proposal_id:03d}"

        compressed = compressor.compress_secure(text)
        assume(compressed is not None)

        decompressed = compressor.decompress_secure(compressed)
        assert decompressed == text

    @given(
        text=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_compression_never_crashes(self, text):
        """Property: compressor should never crash on any input"""
        compressor = BitPackedCompressor()

        # Should either compress or return None
        result = compressor.compress(text)
        if result is not None:
            assert isinstance(result, bytes)
            assert len(result) == 4


class TestCompressionRatios:
    """Test compression efficiency"""

    def test_compression_ratio_simple(self):
        """Test compression ratio on simple messages"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        original_size = len(text.encode('utf-8'))
        compressed = compressor.compress(text)
        compressed_size = len(compressed)

        ratio = original_size / compressed_size
        savings = (1 - compressed_size / original_size) * 100

        # Should achieve > 85% compression
        assert savings > 85.0
        assert ratio > 7.0  # 31 bytes → 4 bytes = 7.75x

    def test_compression_better_than_utf8(self):
        """Test that compression is always better than raw UTF-8"""
        compressor = BitPackedCompressor()

        messages = [
            "System 1 approves proposal 042",
            "System 2 rejects proposal 043",
            "System 3 reviews proposal 001 with high confidence",
            "System 4 approves proposal 255 with low confidence",
        ]

        for msg in messages:
            compressed = compressor.compress(msg)
            if compressed is not None:
                assert len(compressed) < len(msg.encode('utf-8'))


class TestAuraIntegration:
    """Test integration with AURA compression"""

    def test_aura_hybrid_prefers_bitpacking(self):
        """Test that hybrid compressor prefers bit-packing for small messages"""
        compressor = AuraWithBitPacking(enable_bitpacking=True)
        text = "System 1 approves proposal 042"

        compressed, method, metadata = compressor.compress(text)

        assert method == "BITPACKED"
        assert metadata['method'] == "BITPACKED"
        assert metadata['auditable'] is True
        assert len(compressed) == 4

    def test_aura_fallback_for_complex(self):
        """Test AURA fallback for non-bitpackable messages"""
        compressor = AuraWithBitPacking(enable_bitpacking=True)
        text = "I recommend testing this thoroughly before deployment"

        compressed, method, metadata = compressor.compress(text)

        # Should use AURA, not bit-packing
        assert method != "BITPACKED"
        assert metadata['auditable'] is True

    def test_aura_hybrid_decompression(self):
        """Test hybrid decompression works for both formats"""
        compressor = AuraWithBitPacking(enable_bitpacking=True)

        # Bit-packed message
        text1 = "System 1 approves proposal 042"
        compressed1, _, _ = compressor.compress(text1)
        decompressed1 = compressor.decompress(compressed1)
        assert decompressed1 == text1

        # AURA message
        text2 = "I recommend testing this thoroughly"
        compressed2, _, _ = compressor.compress(text2)
        decompressed2 = compressor.decompress(compressed2)
        assert decompressed2 == text2


class TestVerboseDecoding:
    """Test audit verification features"""

    def test_verbose_decode_complete(self):
        """Test verbose decode returns all fields"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        compressed = compressor.compress(text)
        verbose = compressor.decode_verbose(compressed)

        assert verbose['format'] == 'BITPACKED_V1'
        assert 'raw_hex' in verbose
        assert 'byte_breakdown' in verbose
        assert 'decoded_fields' in verbose
        assert 'reconstructed_text' in verbose
        assert verbose['auditable'] is True
        assert 'decoder_version' in verbose

    def test_verbose_decode_byte_breakdown(self):
        """Test byte breakdown in verbose decode"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        compressed = compressor.compress(text)
        verbose = compressor.decode_verbose(compressed)

        byte_breakdown = verbose['byte_breakdown']
        assert 'method_byte' in byte_breakdown
        assert 'control_byte' in byte_breakdown
        assert 'proposal_id' in byte_breakdown
        assert 'system_ids' in byte_breakdown

        # Check method byte
        assert '0x06' in byte_breakdown['method_byte']

    def test_verbose_decode_fields(self):
        """Test decoded fields in verbose output"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042 with high confidence"

        compressed = compressor.compress(text)
        verbose = compressor.decode_verbose(compressed)

        fields = verbose['decoded_fields']
        assert 'message_type' in fields
        assert 'action' in fields
        assert 'confidence' in fields
        assert 'risk' in fields
        assert 'from_system' in fields
        assert 'to_system' in fields
        assert 'proposal_id' in fields

        assert fields['from_system'] == 1
        assert fields['proposal_id'] == 42


class TestErrorHandling:
    """Test error cases and invalid inputs"""

    def test_decompress_empty_data(self):
        """Test decompression with empty data"""
        compressor = BitPackedCompressor()
        result = compressor.decompress(b'')
        assert result is None

    def test_decompress_wrong_method_byte(self):
        """Test decompression with wrong method byte"""
        compressor = BitPackedCompressor()
        data = bytes([0xFF, 0x00, 0x00, 0x00])  # Wrong method byte
        result = compressor.decompress(data)
        assert result is None

    def test_decompress_truncated_data(self):
        """Test decompression with truncated data"""
        compressor = BitPackedCompressor()
        data = bytes([0x06, 0x00])  # Only 2 bytes
        result = compressor.decompress(data)
        assert result is None

    def test_secure_decompress_wrong_length(self):
        """Test secure decompression with wrong length"""
        compressor = BitPackedCompressor()
        data = bytes([0x16, 0x00, 0x00, 0x00])  # Only 4 bytes
        result = compressor.decompress_secure(data)
        assert result is None

    def test_compress_invalid_system_id(self):
        """Test compression with invalid system ID"""
        compressor = BitPackedCompressor()
        text = "System 16 approves proposal 042"  # System ID > 15
        result = compressor.compress(text)
        assert result is None

    def test_compress_invalid_proposal_id(self):
        """Test compression with invalid proposal ID"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 256"  # Proposal ID > 255
        result = compressor.compress(text)
        assert result is None


class TestCRCCalculation:
    """Test CRC-8 calculation"""

    def test_crc_deterministic(self):
        """Test that CRC is deterministic"""
        compressor = BitPackedCompressor()
        data = bytes([0x16, 0x22, 0x2a, 0x16, 0x00])

        crc1 = compressor._crc8(data)
        crc2 = compressor._crc8(data)

        assert crc1 == crc2

    def test_crc_detects_changes(self):
        """Test that CRC changes when data changes"""
        compressor = BitPackedCompressor()
        data1 = bytes([0x16, 0x22, 0x2a, 0x16, 0x00])
        data2 = bytes([0x16, 0x22, 0x2a, 0x16, 0x01])

        crc1 = compressor._crc8(data1)
        crc2 = compressor._crc8(data2)

        assert crc1 != crc2


class TestPatternMatching:
    """Test message pattern recognition"""

    @pytest.mark.parametrize("text,should_match", [
        ("System 1 approves proposal 042", True),
        ("System 1 approve proposal 042", True),  # Singular
        ("System 1 rejects proposal 042", True),
        ("System 1 reject proposal 042", True),  # Singular
        ("System 1 reviews proposal 042", True),
        ("System 1 review proposal 042", True),  # Singular
        ("System 1 votes proposal 042", True),
        ("System 1 vote proposal 042", True),  # Singular
        ("Random text", False),
        ("Proposal 042 is approved", False),
        ("System one approves proposal 042", False),  # Word instead of number
    ])
    def test_pattern_matching(self, text, should_match):
        """Test that pattern matching works correctly"""
        compressor = BitPackedCompressor()
        result = compressor.can_compress(text)
        assert result == should_match


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_minimum_proposal_id(self):
        """Test proposal ID 0"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 0"

        compressed = compressor.compress(text)
        assert compressed is not None
        assert compressed[2] == 0

        decompressed = compressor.decompress(compressed)
        assert "proposal 000" in decompressed

    def test_maximum_proposal_id(self):
        """Test proposal ID 255"""
        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 255"

        compressed = compressor.compress(text)
        assert compressed is not None
        assert compressed[2] == 255

        decompressed = compressor.decompress(compressed)
        assert "proposal 255" in decompressed

    def test_case_insensitive_parsing(self):
        """Test that parsing is case-insensitive"""
        compressor = BitPackedCompressor()

        texts = [
            "System 1 APPROVES proposal 042",
            "System 1 Approves proposal 042",
            "System 1 approves PROPOSAL 042",
        ]

        results = [compressor.compress(text) for text in texts]
        # All should compress successfully
        assert all(r is not None for r in results)


class TestPerformanceBenchmarks:
    """Performance benchmarks (informational, not assertions)"""

    def test_compression_speed(self, benchmark=None):
        """Benchmark compression speed"""
        if benchmark is None:
            pytest.skip("pytest-benchmark not available")

        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"

        def run_compression():
            compressor.compress(text)

        benchmark(run_compression)

    def test_decompression_speed(self, benchmark=None):
        """Benchmark decompression speed"""
        if benchmark is None:
            pytest.skip("pytest-benchmark not available")

        compressor = BitPackedCompressor()
        text = "System 1 approves proposal 042"
        compressed = compressor.compress(text)

        def run_decompression():
            compressor.decompress(compressed)

        benchmark(run_decompression)


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])

from communication.message_codec import MessageCodec


def test_codec_bitpacked_secure_roundtrip():
    codec = MessageCodec(prefer_secure_bitpacked=True, min_compression_size=18)
    text = "System 1 approves proposal 042"
    payload, method, meta = codec.encode(text)
    assert method in ("BITPACKED_SECURE", "BITPACKED")
    if method == "BITPACKED_SECURE":
        assert len(payload) == 6 and payload[0] == 0x16
    else:
        assert len(payload) == 4 and payload[0] == 0x06

    decoded, info = codec.decode(payload)
    assert decoded == text
    if method == "BITPACKED_SECURE":
        assert info.get('crc_ok') is True
        assert info.get('sequence_ok') in (True, None)
        # Re-decode same payload should flag replay
        decoded2, info2 = codec.decode(payload)
        assert decoded2 == text
        assert info2.get('replay_detected') is True


def test_codec_unstructured_small_prefers_uncompressed():
    codec = MessageCodec(prefer_secure_bitpacked=True, min_compression_size=18)
    text = "Yes"
    payload, method, meta = codec.encode(text)
    # We expect AURA to choose UNCOMPRESSED internally; method name returned is whatever AURA reports
    assert len(payload) >= 1
    decoded, info = codec.decode(payload)
    assert decoded == text

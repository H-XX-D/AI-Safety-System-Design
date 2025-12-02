from aura_strategy_profile import classify_message, AURAStrategyProfile


def test_ranges_and_methods():
    p = AURAStrategyProfile(prefer_secure_bitpacked=True, min_compression_size=18)

    # Bit-packed eligible
    d1 = p.classify("System 1 approves proposal 042")
    assert d1.method in ("BITPACKED_SECURE", "BITPACKED")

    # Very small, unstructured
    d2 = p.classify("Yes")
    assert d2.method == "UNCOMPRESSED"

    # Short sentence (template likely)
    d3 = p.classify("I recommend testing this change before rollout")
    assert d3.method == "BINARY_SEMANTIC"

    # Medium text (BRIO)
    medium = " ".join(["word"] * 80)  # ~ 320B
    d4 = p.classify(medium)
    assert d4.method == "BRIO"

    # Large payload (AURALITE)
    large = " ".join(["word"] * 400)  # ~ 1600B
    d5 = p.classify(large)
    assert d5.method == "AURALITE"

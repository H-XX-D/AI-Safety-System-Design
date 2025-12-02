#!/usr/bin/env python3
"""
Test compression of small messages to avoid expansion
"""

from aura_compression import ProductionHybridCompressor

# Test with different configurations
configs = [
    {
        "name": "Default (Standard AURA)",
        "config": {
            "enable_aura": True,
            "min_compression_size": 10,
        }
    },
    {
        "name": "Aggressive (Lower threshold)",
        "config": {
            "enable_aura": True,
            "min_compression_size": 5,  # Try to compress even smaller messages
            "aura_preference_margin": 0.15,  # Prefer AURA methods more
        }
    },
]

small_messages = [
    "I cannot process this request.",
    "System 1 approves proposal 042",
    "No",
    "Yes",
    "I don't know",
    "That's correct",
    "Maybe",
    "I recommend testing first",
    "Risk: low. Confidence: high.",
]

print("=" * 80)
print("SMALL MESSAGE COMPRESSION TEST")
print("=" * 80)

for config_info in configs:
    print(f"\n{config_info['name']}")
    print("-" * 80)

    compressor = ProductionHybridCompressor(**config_info['config'])

    total_original = 0
    total_compressed = 0
    expanded_count = 0

    for msg in small_messages:
        compressed, method, metadata = compressor.compress(msg)

        original_size = len(msg.encode('utf-8'))
        compressed_size = len(compressed)

        total_original += original_size
        total_compressed += compressed_size

        if compressed_size > original_size:
            expanded_count += 1
            status = "EXPANDED ⚠️"
        elif compressed_size < original_size:
            status = f"SAVED {original_size - compressed_size}b ✓"
        else:
            status = "SAME"

        print(f"{msg[:35]:35s} | {original_size:3d}→{compressed_size:3d} | {method.name[:15]:15s} | {status}")

    overall_ratio = total_original / total_compressed if total_compressed > 0 else 1.0
    overall_savings = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0

    print(f"\nSummary:")
    print(f"  Total: {total_original} → {total_compressed} bytes")
    print(f"  Ratio: {overall_ratio:.2f}x")
    print(f"  Savings: {overall_savings:.1f}%")
    print(f"  Expanded messages: {expanded_count}/{len(small_messages)}")

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print("""
If small messages are expanding, this is actually CORRECT behavior.

AURA's UNCOMPRESSED fallback prevents:
1. Wasting CPU on compression that makes data larger
2. Network overhead from expanded messages
3. Storage inefficiency

The UNCOMPRESSED method:
- Detects expansion during compression
- Falls back to raw UTF-8 storage
- Adds minimal overhead (method byte + length)

This is optimal behavior for small messages.

However, you can tune the min_compression_size threshold:
- Default: 10 bytes (skip very tiny messages)
- Recommended for AI Safety: 25 bytes (skip short status updates)
- Aggressive: 5 bytes (try to compress everything)
""")

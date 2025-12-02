#!/usr/bin/env python3
"""Simple AURA test to understand the format"""

from aura_compression import ProductionHybridCompressor

compressor = ProductionHybridCompressor(enable_aura=True)

text = "I cannot process this request."
print(f"Original: {text}")

compressed, method, metadata = compressor.compress(text)
print(f"\nCompressed: {len(compressed)} bytes")
print(f"Method: {method}")
print(f"Metadata: {metadata}")
print(f"Hex: {compressed.hex()}")

# Check first byte (method marker)
print(f"\nFirst byte: 0x{compressed[0]:02x} ({compressed[0]})")

# Try to understand the format
if compressed[0] == 1:  # Binary semantic
    print("Format: Binary Semantic (Template-based)")
    if len(compressed) >= 4:
        template_id = compressed[1]
        slot_count = compressed[2]
        print(f"Template ID: {template_id}")
        print(f"Slot count: {slot_count}")
elif compressed[0] == 3:  # BRIO
    print("Format: BRIO (Advanced compression)")
elif compressed[0] == 4:  # Brotli
    print("Format: Brotli")
elif compressed[0] == 0xff:  # Uncompressed
    print("Format: Uncompressed")
else:
    print(f"Unknown format: {compressed[0]}")

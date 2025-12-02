#!/usr/bin/env python3
"""
Create a test AURA bitpacked file for ESP32 SD card testing.
Generates messages in the bitpacked format that the ESP32 can decode.
"""

import sys
import os

# Add parent directory to path to import aura modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from aura_bitpacked_extension import BitPackedCompressor

def create_test_file(output_path: str):
    """Create a test file with bitpacked AURA messages."""
    
    compressor = BitPackedCompressor()
    
    # Test messages that should compress well
    messages = [
        "System 1 approves proposal 042",
        "System 2 rejects proposal 043",
        "System 3 reviews proposal 001",
        "System 4 approves proposal 255",
        "System 5 rejects proposal 128",
    ]
    
    print("Creating AURA bitpacked test file...")
    print(f"Output: {output_path}\n")
    
    with open(output_path, 'wb') as f:
        for msg in messages:
            compressed = compressor.compress(msg)
            if compressed:
                print(f"✓ Compressed: {msg}")
                print(f"  Size: {len(compressed)} bytes")
                print(f"  Hex: {compressed.hex()}")
                # Write the raw bitpacked data
                f.write(compressed)
            else:
                print(f"✗ Failed to compress: {msg}")
    
    print(f"\n✓ Created {output_path}")
    print(f"  Total size: {os.path.getsize(output_path)} bytes")
    print(f"\nCopy this file to the SD card root directory as 'test.aura'")

if __name__ == "__main__":
    # Default output path
    output = "/Volumes/NO NAME/test.aura" if os.path.exists("/Volumes/NO NAME") else "./test.aura"
    
    if len(sys.argv) > 1:
        output = sys.argv[1]
    
    try:
        create_test_file(output)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

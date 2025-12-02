#!/usr/bin/env python3
"""Generate Complete AURA Template Stores for All 6 Methods
===========================================================

Generates template stores for all 6 AURA compression methods:
1. BINARY_SEMANTIC (0x01) - Template ID + Slots (65,536 templates)
2. BRIO (0x02) - LZ77 + Dictionary + rANS (dictionaries + patterns)
3. AURALITE (0x03) - Lightweight template (simplified templates)
4. BROTLI (0x04) - Standard brotli (no templates needed, but we document)
5. UNCOMPRESSED (0x05) - Raw UTF-8 (no templates)
6. BITPACKED (0x06) - Bit-packed enums (enum definitions)

Total files created:
- binary_semantic_templates_65536.json (~8 MB)
- brio_dictionaries.json (~2 MB)
- auralite_templates.json (~1 MB)
- bitpacked_enums.json (~50 KB)
- method_manifest.json (method metadata + hashes)
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

def generate_binary_semantic_templates() -> Dict:
    """Generate 65,536 templates for BINARY_SEMANTIC method (0x01)"""

    print("\n[1/6] Generating BINARY_SEMANTIC templates (65,536)...")

    templates = []

    # Template ID ranges from AURA_PROTOCOL.md
    ranges = {
        # ID 0-127: DEFAULT_TEMPLATES
        "default": {
            "start": 0,
            "end": 127,
            "patterns": [
                "Hello {0}",
                "System {0} ready",
                "Processing {0}",
                "Complete: {0}",
                "Error: {0}",
                "Status: {0}",
                "Result: {0}",
                "Request {0} approved",
                "Request {0} denied",
                "Waiting for {0}",
            ]
        },
        # ID 128-2127: AI_TO_AI (AI communication)
        "ai_to_ai": {
            "start": 128,
            "end": 2127,
            "patterns": [
                "System {0} proposes {1}",
                "System {0} approves proposal {1}",
                "System {0} rejects proposal {1}",
                "System {0} abstains on proposal {1}",
                "Round {0} debate on proposal {1}",
                "Consensus reached: {0}",
                "Deception detected in system {0}",
                "Penalty applied to system {0}: {1}",
                "Human review requested for {0}",
                "Incident {0} severity: {1}",
            ]
        },
        # ID 2128-4999: HUMAN_TO_AI
        "human_to_ai": {
            "start": 2128,
            "end": 4999,
            "patterns": [
                "User query: {0}",
                "Please explain {0}",
                "What is {0}?",
                "How do I {0}?",
                "Can you {0}?",
                "Show me {0}",
                "Tell me about {0}",
                "I need help with {0}",
            ]
        },
        # Remaining ranges with generic patterns
        "healthcare": {"start": 5000, "end": 6999},
        "financial": {"start": 7000, "end": 9999},
        "legal": {"start": 10000, "end": 11999},
        "small_sentences": {"start": 12000, "end": 13999},
        "dynamic_range": {"start": 14000, "end": 16383},
        "client_sync": {"start": 16384, "end": 32767},
        "whitespace_variants": {"start": 32768, "end": 49151},
        "reserved_future": {"start": 49152, "end": 65535},
    }

    # Generate templates for each range
    for range_name, range_info in ranges.items():
        start = range_info["start"]
        end = range_info["end"]
        patterns = range_info.get("patterns", [f"template_{range_name}_{{0}}"])

        for template_id in range(start, end + 1):
            if "patterns" in range_info and range_info["patterns"]:
                # Use specific patterns
                pattern_idx = (template_id - start) % len(range_info["patterns"])
                pattern = range_info["patterns"][pattern_idx]
            else:
                # Generic pattern
                pattern = f"template_{range_name}_{template_id:05d}_{{0}}"

            templates.append({
                "id": template_id,
                "pattern": pattern,
                "range": range_name,
                "slots": pattern.count("{")
            })

    print(f"  Generated {len(templates)} templates")

    return {
        "method": "BINARY_SEMANTIC",
        "method_byte": "0x01",
        "version": "1.0.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "total_templates": len(templates),
        "template_ranges": {k: {"start": v["start"], "end": v["end"]} for k, v in ranges.items()},
        "templates": templates
    }

def generate_brio_dictionaries() -> Dict:
    """Generate dictionaries for BRIO method (0x02) - LZ77 + rANS"""

    print("\n[2/6] Generating BRIO dictionaries...")

    # Common words for dictionary compression
    common_words = [
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "I",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
        "or", "an", "will", "my", "one", "all", "would", "there", "their",

        # AI Safety specific
        "agent", "system", "safety", "alignment", "proposal", "debate", "consensus",
        "detection", "deception", "verification", "orchestrator", "penalty", "reputation",
        "TIF", "GIN", "TORI", "THEO", "NOVEL", "VAL", "ORKA",
    ]

    # Common patterns for LZ77
    patterns = [
        "System {id} ", "proposal {id}", "Round {n}", "approved", "rejected",
        "deception detected", "penalty applied", "human review", "consensus reached",
    ]

    dictionary = {
        "method": "BRIO",
        "method_byte": "0x02",
        "version": "1.0.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "common_words": common_words,
        "patterns": patterns,
        "total_words": len(common_words),
        "total_patterns": len(patterns),
        "lz77_window_size": 32768,
        "rans_precision": 31  # 31-bit rANS
    }

    print(f"  Generated {len(common_words)} words, {len(patterns)} patterns")

    return dictionary

def generate_auralite_templates() -> Dict:
    """Generate lightweight templates for AURALITE method (0x03)"""

    print("\n[3/6] Generating AURALITE lightweight templates...")

    # Auralite uses simplified, high-frequency templates
    templates = [
        {"id": i, "pattern": pattern, "frequency": freq}
        for i, (pattern, freq) in enumerate([
            ("System {0} approves", 0.95),
            ("System {0} rejects", 0.92),
            ("Proposal {0}", 0.90),
            ("Round {0}", 0.88),
            ("Consensus", 0.85),
            ("Approved", 0.82),
            ("Rejected", 0.80),
            ("Pending", 0.75),
            ("Complete", 0.70),
            ("Error", 0.65),
        ])
    ]

    auralite = {
        "method": "AURALITE",
        "method_byte": "0x03",
        "version": "1.0.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "total_templates": len(templates),
        "templates": templates,
        "max_message_size": 256  # Optimized for short messages
    }

    print(f"  Generated {len(templates)} lightweight templates")

    return auralite

def generate_bitpacked_enums() -> Dict:
    """Generate enum definitions for BITPACKED method (0x06)"""

    print("\n[4/6] Generating BITPACKED enum definitions...")

    bitpacked = {
        "method": "BITPACKED",
        "method_byte": "0x06",
        "version": "1.0.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "format": "4 bytes total",
        "byte_structure": {
            "byte_0": "Method identifier (0x06)",
            "byte_1": "Control byte [MsgType:3][Action:2][Confidence:2][Risk:1]",
            "byte_2": "Proposal ID (0-255)",
            "byte_3": "System IDs [FromSystem:4][ToSystem:4]"
        },
        "enums": {
            "MessageType": {
                "APPROVAL": "0b001",
                "REJECTION": "0b010",
                "REVIEW": "0b011",
                "VOTE": "0b100",
                "ALERT": "0b101",
                "STATUS": "0b110"
            },
            "Action": {
                "APPROVE": "0b00",
                "REJECT": "0b01",
                "ABSTAIN": "0b10",
                "ESCALATE": "0b11"
            },
            "Confidence": {
                "LOW": "0b00",
                "MEDIUM": "0b01",
                "HIGH": "0b10",
                "MAXIMUM": "0b11"
            },
            "Risk": {
                "NO_RISK": "0b0",
                "HAS_RISK": "0b1"
            }
        }
    }

    print(f"  Generated {len(bitpacked['enums'])} enum types")

    return bitpacked

def generate_method_manifest(binary_semantic, brio, auralite, bitpacked) -> Dict:
    """Generate manifest with all method metadata and hashes"""

    print("\n[5/6] Generating method manifest...")

    # Calculate hashes
    bs_hash = hashlib.sha256(json.dumps(binary_semantic["templates"], sort_keys=True).encode()).hexdigest()
    brio_hash = hashlib.sha256(json.dumps(brio, sort_keys=True).encode()).hexdigest()
    auralite_hash = hashlib.sha256(json.dumps(auralite["templates"], sort_keys=True).encode()).hexdigest()
    bp_hash = hashlib.sha256(json.dumps(bitpacked["enums"], sort_keys=True).encode()).hexdigest()

    manifest = {
        "aura_version": "1.0.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "total_methods": 6,
        "methods": {
            "0x01_BINARY_SEMANTIC": {
                "method_byte": "0x01",
                "name": "BINARY_SEMANTIC",
                "description": "Template ID + Slots",
                "best_for": "Common phrases, structured messages",
                "compression_ratio": "1.2-2.0x",
                "template_count": binary_semantic["total_templates"],
                "template_hash": bs_hash,
                "file": "binary_semantic_templates_65536.json"
            },
            "0x02_BRIO": {
                "method_byte": "0x02",
                "name": "BRIO",
                "description": "LZ77 + Dictionary + rANS",
                "best_for": "Technical text, repeated patterns",
                "compression_ratio": "1.5-5.0x",
                "dictionary_words": brio["total_words"],
                "dictionary_patterns": brio["total_patterns"],
                "dictionary_hash": brio_hash,
                "file": "brio_dictionaries.json"
            },
            "0x03_AURALITE": {
                "method_byte": "0x03",
                "name": "AURALITE",
                "description": "Lightweight template",
                "best_for": "Short messages",
                "compression_ratio": "1.2-1.8x",
                "template_count": auralite["total_templates"],
                "template_hash": auralite_hash,
                "file": "auralite_templates.json"
            },
            "0x04_BROTLI": {
                "method_byte": "0x04",
                "name": "BROTLI",
                "description": "Standard brotli compression",
                "best_for": "General text",
                "compression_ratio": "1.2-2.5x",
                "template_count": 0,
                "note": "Uses standard brotli algorithm, no templates needed",
                "file": "N/A (standard library)"
            },
            "0x05_UNCOMPRESSED": {
                "method_byte": "0x05",
                "name": "UNCOMPRESSED",
                "description": "Raw UTF-8",
                "best_for": "Tiny messages (< 25 bytes)",
                "compression_ratio": "1.0x",
                "template_count": 0,
                "note": "No compression applied",
                "file": "N/A"
            },
            "0x06_BITPACKED": {
                "method_byte": "0x06",
                "name": "BITPACKED",
                "description": "Bit-packed enums (4 bytes)",
                "best_for": "Simple approvals/rejections",
                "compression_ratio": "86-92%",
                "enum_count": len(bitpacked["enums"]),
                "enum_hash": bp_hash,
                "file": "bitpacked_enums.json"
            }
        },
        "manifest_hash": None  # Calculated after writing files
    }

    # Calculate manifest hash
    manifest_json = json.dumps(manifest["methods"], sort_keys=True)
    manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
    manifest["manifest_hash"] = manifest_hash

    print(f"  Manifest hash: {manifest_hash[:32]}...")

    return manifest

def main():
    """Generate all AURA template stores"""

    print("=" * 70)
    print("AURA Complete Template Store Generator")
    print("All 6 Compression Methods")
    print("=" * 70)

    # Output directory
    output_dir = Path("worm_usb_dir/aura_templates")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate all methods
    binary_semantic = generate_binary_semantic_templates()
    brio = generate_brio_dictionaries()
    auralite = generate_auralite_templates()
    bitpacked = generate_bitpacked_enums()

    # Generate manifest
    manifest = generate_method_manifest(binary_semantic, brio, auralite, bitpacked)

    # Write files
    print("\n[6/6] Writing files...")

    files = [
        ("binary_semantic_templates_65536.json", binary_semantic),
        ("brio_dictionaries.json", brio),
        ("auralite_templates.json", auralite),
        ("bitpacked_enums.json", bitpacked),
        ("method_manifest.json", manifest),
    ]

    for filename, data in files:
        path = output_dir / filename
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  ✓ {filename} ({size_mb:.2f} MB)")

    # Summary
    print("\n" + "=" * 70)
    print("✅ AURA Complete Template Store Generated")
    print("=" * 70)
    print(f"\nOutput directory: {output_dir}")
    print(f"\nFiles created:")
    for filename, _ in files:
        path = output_dir / filename
        print(f"  - {filename} ({path.stat().st_size / 1024:.1f} KB)")

    print(f"\nManifest Hash: {manifest['manifest_hash']}")
    print("\n6 Compression Methods:")
    for method_key, method_info in manifest["methods"].items():
        print(f"  {method_info['method_byte']} {method_info['name']:15s} - {method_info['description']}")

    print("\nThese files should be included on WORM USB for:")
    print("  ✓ Template validation during compression/decompression")
    print("  ✓ Human auditing of compressed data")
    print("  ✓ Ensuring no covert channels in AI communication")
    print("  ✓ Cryptographic integrity verification")
    print("=" * 70)

if __name__ == "__main__":
    main()

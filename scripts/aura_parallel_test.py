#!/usr/bin/env python3
"""
AURA Parallel Communication Test
=================================

Tests AURA compression effectiveness across the distributed node network.
Measures compression ratios, latency, and bandwidth savings.

Usage:
    python scripts/aura_parallel_test.py
"""

import sys
import time
import json
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import AURA modules
from communication.aura_native import (
    compress as aura_compress,
    decompress as aura_decompress,
    batch_compress as aura_batch_compress,
    prewarm as aura_prewarm,
    init_templates as aura_init_templates,
)

try:
    from communication.aura_context_stream import ContextStore, StreamConfig
    STREAM_AVAILABLE = True
except ImportError:
    STREAM_AVAILABLE = False

try:
    from communication.aura_ring_decoder import RingDecoder
    RING_AVAILABLE = True
except ImportError:
    RING_AVAILABLE = False

try:
    from communication.aura_proposal_hook import enable_proposal_hooks, register_proposal
    HOOKS_AVAILABLE = True
except ImportError:
    HOOKS_AVAILABLE = False

# Node configuration
NODES = {
    "ORIN": ("192.168.0.160", "orin"),
    "GIN": ("192.168.0.242", "gin"),
    "TIF": ("192.168.0.213", "tif"),
    "TORI": ("192.168.0.235", "tori"),
    "NOVEL": ("192.168.0.146", "novel"),
    "ARCHI": ("192.168.0.232", "archi"),
    "PAGE": ("192.168.0.168", "page"),
}


@dataclass
class CompressionStats:
    """Statistics for compression tests."""
    original_bytes: int = 0
    compressed_bytes: int = 0
    compression_time_ms: float = 0.0
    decompression_time_ms: float = 0.0
    
    @property
    def ratio(self) -> float:
        if self.compressed_bytes == 0:
            return 0.0
        return self.original_bytes / self.compressed_bytes
    
    @property
    def savings_percent(self) -> float:
        if self.original_bytes == 0:
            return 0.0
        return (1 - self.compressed_bytes / self.original_bytes) * 100


@dataclass
class NodeTestResult:
    """Results from testing a single node."""
    node_name: str
    ip: str
    reachable: bool = False
    aura_available: bool = False
    compression_stats: Optional[CompressionStats] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


def test_local_aura() -> CompressionStats:
    """Test AURA compression locally."""
    stats = CompressionStats()
    
    # Generate test messages using the format AURA expects
    # AURA uses structured messages with source_id, action, proposal_id
    test_messages = [
        {"source_id": 1, "action": "approves", "proposal_id": 1},
        {"source_id": 2, "action": "rejects", "proposal_id": 2},
        {"source_id": 3, "action": "approves", "proposal_id": 3},
        {"source_id": 4, "action": "reviews", "proposal_id": 4},
        {"source_id": 5, "action": "approves", "proposal_id": 5},
    ]
    
    # Also test plain text messages
    text_messages = [
        "System 1 approves proposal 001",
        "System 2 rejects proposal 002",
        "System 3 approves proposal 003",
        "System 4 reviews proposal 004",
        "System 5 approves proposal 005",
    ]
    
    # Measure original size
    for msg in test_messages:
        stats.original_bytes += len(json.dumps(msg).encode('utf-8'))
    for msg in text_messages:
        stats.original_bytes += len(msg.encode('utf-8'))
    
    # Measure compression
    start = time.perf_counter()
    compressed = []
    for msg in test_messages:
        c = aura_compress(msg)
        if c is not None:
            compressed.append(c)
        else:
            compressed.append(json.dumps(msg).encode('utf-8'))
    for msg in text_messages:
        c = aura_compress(msg)
        if c is not None:
            compressed.append(c)
        else:
            compressed.append(msg.encode('utf-8'))
    stats.compression_time_ms = (time.perf_counter() - start) * 1000
    
    for c in compressed:
        stats.compressed_bytes += len(c)
    
    # Measure decompression
    start = time.perf_counter()
    for c in compressed:
        try:
            aura_decompress(c)
        except Exception:
            pass  # Some compressed forms may not be reversible
    stats.decompression_time_ms = (time.perf_counter() - start) * 1000
    
    return stats


def test_node_aura(node_name: str, ip: str, user: str) -> NodeTestResult:
    """Test AURA on a remote node via SSH."""
    result = NodeTestResult(node_name=node_name, ip=ip)
    
    # Check if node is reachable
    try:
        ping = subprocess.run(
            ["ping", "-c", "1", "-W", "2", ip],
            capture_output=True, timeout=5
        )
        result.reachable = ping.returncode == 0
    except Exception:
        result.reachable = False
        result.error = "Ping failed"
        return result
    
    if not result.reachable:
        result.error = "Node unreachable"
        return result
    
    # Test AURA compression on remote node
    test_script = '''
import sys, time, json
sys.path.insert(0, "/home/{user}")
try:
    from communication import compress, decompress, AURA_NATIVE_AVAILABLE
    if not AURA_NATIVE_AVAILABLE:
        print(json.dumps({{"error": "AURA not available"}}))
        sys.exit(1)
    
    test = {{"type": "test", "data": "x" * 100}}
    orig = len(json.dumps(test).encode())
    
    start = time.perf_counter()
    c = compress(test)
    comp_time = (time.perf_counter() - start) * 1000
    
    start = time.perf_counter()
    d = decompress(c)
    decomp_time = (time.perf_counter() - start) * 1000
    
    print(json.dumps({{
        "original": orig,
        "compressed": len(c),
        "comp_ms": comp_time,
        "decomp_ms": decomp_time,
    }}))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
'''.format(user=user)
    
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             f"{user}@{ip}", f"python3 -c '{test_script}'"],
            capture_output=True, text=True, timeout=30
        )
        result.latency_ms = (time.perf_counter() - start) * 1000
        
        if proc.returncode == 0:
            data = json.loads(proc.stdout.strip())
            if "error" in data:
                result.error = data["error"]
            else:
                result.aura_available = True
                result.compression_stats = CompressionStats(
                    original_bytes=data["original"],
                    compressed_bytes=data["compressed"],
                    compression_time_ms=data["comp_ms"],
                    decompression_time_ms=data["decomp_ms"],
                )
        else:
            result.error = proc.stderr[:200] if proc.stderr else "Unknown error"
    except subprocess.TimeoutExpired:
        result.error = "SSH timeout"
    except json.JSONDecodeError as e:
        result.error = f"JSON parse error: {e}"
    except Exception as e:
        result.error = str(e)
    
    return result


def run_parallel_test():
    """Run AURA tests on all nodes in parallel."""
    print("=" * 70)
    print("AURA PARALLEL COMMUNICATION TEST")
    print("=" * 70)
    print()
    
    # Initialize AURA locally
    print("Initializing AURA locally...")
    aura_prewarm()
    aura_init_templates()
    print("  ✓ AURA initialized")
    print()
    
    # Test locally first
    print("Testing local AURA compression...")
    local_stats = test_local_aura()
    print(f"  Original:    {local_stats.original_bytes:,} bytes")
    print(f"  Compressed:  {local_stats.compressed_bytes:,} bytes")
    print(f"  Ratio:       {local_stats.ratio:.1f}x")
    print(f"  Savings:     {local_stats.savings_percent:.1f}%")
    print(f"  Compress:    {local_stats.compression_time_ms:.2f} ms")
    print(f"  Decompress:  {local_stats.decompression_time_ms:.2f} ms")
    print()
    
    # Test all nodes in parallel
    print("Testing remote nodes in parallel...")
    print("-" * 70)
    
    results: Dict[str, NodeTestResult] = {}
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            executor.submit(test_node_aura, name, ip, user): name
            for name, (ip, user) in NODES.items()
        }
        
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results[name] = result
            except Exception as e:
                results[name] = NodeTestResult(
                    node_name=name,
                    ip=NODES[name][0],
                    error=str(e)
                )
    
    # Print results
    print(f"{'Node':<8} {'IP':<16} {'Status':<12} {'Ratio':<8} {'Latency':<10} {'Notes'}")
    print("-" * 70)
    
    success_count = 0
    for name in ["ORIN", "GIN", "TIF", "TORI", "NOVEL", "ARCHI", "PAGE"]:
        r = results.get(name)
        if r is None:
            print(f"{name:<8} {'?':<16} {'ERROR':<12}")
            continue
        
        if r.aura_available and r.compression_stats:
            status = "✓ OK"
            ratio = f"{r.compression_stats.ratio:.1f}x"
            latency = f"{r.latency_ms:.0f}ms"
            notes = f"{r.compression_stats.savings_percent:.0f}% saved"
            success_count += 1
        elif r.reachable:
            status = "⚠ PARTIAL"
            ratio = "-"
            latency = f"{r.latency_ms:.0f}ms"
            notes = r.error or "Unknown"
        else:
            status = "✗ OFFLINE"
            ratio = "-"
            latency = "-"
            notes = r.error or "Unreachable"
        
        print(f"{name:<8} {r.ip:<16} {status:<12} {ratio:<8} {latency:<10} {notes}")
    
    print("-" * 70)
    print(f"Summary: {success_count}/{len(NODES)} nodes with AURA working")
    print()
    
    # Calculate bandwidth savings estimate
    if success_count > 0:
        avg_ratio = local_stats.ratio
        msgs_per_proposal = 20  # Approximate messages per proposal cycle
        bytes_per_msg = 500     # Average message size
        proposals_per_hour = 6  # Approximate proposals per hour
        
        uncompressed = msgs_per_proposal * bytes_per_msg * proposals_per_hour * success_count
        compressed = uncompressed / avg_ratio
        saved = uncompressed - compressed
        
        print("Estimated Bandwidth Savings (per hour):")
        print(f"  Without AURA: {uncompressed/1024:.1f} KB")
        print(f"  With AURA:    {compressed/1024:.1f} KB")
        print(f"  Saved:        {saved/1024:.1f} KB ({local_stats.savings_percent:.0f}%)")
    
    print()
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    run_parallel_test()

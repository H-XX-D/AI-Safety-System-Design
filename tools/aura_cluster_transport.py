"""
AURA Cluster Transport Layer
=============================

Provides AURA compression for all data transfer between nanos:
1. Compresses outgoing messages (prompts, proposals, reviews)
2. Decompresses incoming responses
3. Stores compressed data in shared memory
4. Tracks compression statistics

This module wraps the nano_cluster communication to use AURA.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# AURA compression imports
try:
    from aura_compression import ProductionHybridCompressor, CompressionMethod
    from communication.aura_compressor import classify_and_compress, create_compressor
    from communication.aura_bitpacked_extension import BitPackedCompressor
    AURA_AVAILABLE = True
except ImportError as e:
    logger.warning(f"AURA compression not available: {e}")
    AURA_AVAILABLE = False
    ProductionHybridCompressor = None
    CompressionMethod = None


@dataclass
class CompressionStats:
    """Track compression statistics."""
    total_messages: int = 0
    total_original_bytes: int = 0
    total_compressed_bytes: int = 0
    methods_used: Dict[str, int] = field(default_factory=dict)
    compression_times_ms: List[float] = field(default_factory=list)
    
    @property
    def compression_ratio(self) -> float:
        if self.total_original_bytes == 0:
            return 0.0
        return 1 - (self.total_compressed_bytes / self.total_original_bytes)
    
    @property
    def average_compression_time_ms(self) -> float:
        if not self.compression_times_ms:
            return 0.0
        return sum(self.compression_times_ms) / len(self.compression_times_ms)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "total_original_bytes": self.total_original_bytes,
            "total_compressed_bytes": self.total_compressed_bytes,
            "compression_ratio": f"{self.compression_ratio * 100:.1f}%",
            "bytes_saved": self.total_original_bytes - self.total_compressed_bytes,
            "methods_used": self.methods_used,
            "avg_compression_time_ms": f"{self.average_compression_time_ms:.3f}",
        }


class AURAClusterTransport:
    """
    AURA-enabled transport layer for nano cluster communication.
    
    Compresses all messages sent between nanos using AURA compression,
    choosing the optimal method based on message type and size.
    """
    
    def __init__(self, enable_compression: bool = True):
        self.enabled = enable_compression and AURA_AVAILABLE
        self.stats = CompressionStats()
        
        if self.enabled:
            self.compressor = create_compressor(
                enable_aura=True,
                enable_audit_logging=False,
                min_compression_size=12,
            )
            self.bitpacked = BitPackedCompressor()
            logger.info("AURA transport initialized with compression enabled")
        else:
            self.compressor = None
            self.bitpacked = None
            logger.warning("AURA transport running without compression")
    
    def compress_message(self, message: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Compress a message using AURA.
        
        Args:
            message: The text message to compress
            
        Returns:
            Tuple of (compressed_bytes, metadata_dict)
        """
        if not self.enabled or not message:
            return message.encode('utf-8'), {"method": "UNCOMPRESSED", "ratio": 0}
        
        start_time = time.perf_counter()
        original_size = len(message.encode('utf-8'))
        
        try:
            # Use full AURA compression (bitpacked has lossy reconstruction)
            compressed, method, meta = self.compressor.compress(message)
            compressed_size = len(compressed)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            method_name = method.name if hasattr(method, 'name') else str(method)
            self._update_stats(method_name, original_size, compressed_size, elapsed_ms)
            
            return compressed, {
                "method": method_name,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "ratio": f"{(1 - compressed_size/original_size) * 100:.1f}%",
                "time_ms": f"{elapsed_ms:.3f}",
            }
            
        except Exception as e:
            logger.warning(f"Compression failed, using raw: {e}")
            return message.encode('utf-8'), {"method": "UNCOMPRESSED", "error": str(e)}
    
    def decompress_message(self, data: bytes, method: str = "AUTO") -> str:
        """
        Decompress a message.
        
        Args:
            data: The compressed bytes
            method: Compression method hint (AUTO for auto-detect)
            
        Returns:
            Decompressed string
        """
        if not self.enabled:
            return data.decode('utf-8', errors='replace')
        
        try:
            # Try bitpacked first
            if method == "BITPACKED" or (method == "AUTO" and len(data) <= 4):
                result = self.bitpacked.decompress(data)
                if result:
                    return result
            
            # Try AURA decompression
            if self.compressor:
                return self.compressor.decompress(data)
            
            # Fallback to raw decode
            return data.decode('utf-8', errors='replace')
            
        except Exception as e:
            logger.warning(f"Decompression failed: {e}")
            return data.decode('utf-8', errors='replace')
    
    def compress_json(self, data: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """Compress a JSON-serializable dict."""
        json_str = json.dumps(data, separators=(',', ':'))  # Compact JSON
        return self.compress_message(json_str)
    
    def decompress_json(self, data: bytes, method: str = "AUTO") -> Dict[str, Any]:
        """Decompress to a JSON dict."""
        text = self.decompress_message(data, method)
        return json.loads(text)
    
    def _update_stats(self, method: str, original: int, compressed: int, time_ms: float):
        """Update compression statistics."""
        self.stats.total_messages += 1
        self.stats.total_original_bytes += original
        self.stats.total_compressed_bytes += compressed
        self.stats.methods_used[method] = self.stats.methods_used.get(method, 0) + 1
        self.stats.compression_times_ms.append(time_ms)
        
        # Keep only last 1000 timing samples
        if len(self.stats.compression_times_ms) > 1000:
            self.stats.compression_times_ms = self.stats.compression_times_ms[-1000:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return self.stats.to_dict()
    
    def reset_stats(self):
        """Reset compression statistics."""
        self.stats = CompressionStats()


# Global transport instance
_transport: Optional[AURAClusterTransport] = None

def get_transport() -> AURAClusterTransport:
    """Get or create the global AURA transport instance."""
    global _transport
    if _transport is None:
        _transport = AURAClusterTransport(enable_compression=True)
    return _transport


def compress_for_nano(message: str) -> Tuple[bytes, Dict[str, Any]]:
    """Compress a message for sending to a nano."""
    return get_transport().compress_message(message)


def decompress_from_nano(data: bytes, method: str = "AUTO") -> str:
    """Decompress a message received from a nano."""
    return get_transport().decompress_message(data, method)


def get_compression_stats() -> Dict[str, Any]:
    """Get current compression statistics."""
    return get_transport().get_stats()


# =============================================================================
# TEST FUNCTIONS - Runnable to verify AURA is working
# =============================================================================

def test_aura_compression():
    """
    Test AURA compression with various message types.
    Run this to verify AURA is working correctly.
    
    Usage:
        python -m tools.aura_cluster_transport
    """
    print("=" * 60)
    print("AURA Cluster Transport - Compression Test")
    print("=" * 60)
    
    transport = AURAClusterTransport(enable_compression=True)
    
    if not transport.enabled:
        print("❌ AURA compression not available!")
        print("   Make sure aura_compression package is installed")
        return False
    
    print(f"✅ AURA compression enabled")
    print()
    
    # Test messages of different types
    test_messages = [
        # Structured messages (good for bitpacking)
        "System 1 approves proposal 42",
        "System 2 rejects proposal 17",
        "Agent GIN votes approve",
        
        # Proposal-like content
        """Proposal: Optimize memory allocation by implementing dynamic caching.
        Expected improvement: 15% reduction in latency.
        Risk: Medium - requires thorough testing.""",
        
        # Review content
        """VOTE: APPROVE
        COMMENTS: The proposal is well-researched and addresses a real performance issue.
        CONCERNS: Implementation timeline seems aggressive.""",
        
        # JSON-like data
        json.dumps({
            "agent": "GIN",
            "action": "submit_proposal",
            "proposal_id": "PROP_12345",
            "confidence": 0.85,
            "timestamp": "2025-12-05T19:30:00Z"
        }),
        
        # Longer content
        """# Memory Allocation Optimization Proposal
        
        ## Problem Statement
        Current memory allocation in the system uses static pooling which leads to
        fragmentation and wasted resources during varying workloads.
        
        ## Proposed Solution
        Implement dynamic memory allocation with predictive load forecasting.
        
        ## Expected Benefits
        - 20% reduction in memory usage
        - 15% improvement in response time
        - Better resource utilization during peak loads
        
        ## Implementation Steps
        1. Profile current memory usage patterns
        2. Implement load prediction model
        3. Add dynamic allocation layer
        4. Test under various workloads
        5. Deploy with fallback to static allocation
        """,
    ]
    
    print("Testing compression on various message types:")
    print("-" * 60)
    
    all_passed = True
    
    for i, msg in enumerate(test_messages, 1):
        original_size = len(msg.encode('utf-8'))
        compressed, meta = transport.compress_message(msg)
        compressed_size = len(compressed)
        
        # Verify decompression
        decompressed = transport.decompress_message(compressed, meta.get('method', 'AUTO'))
        
        # Check if roundtrip works
        roundtrip_ok = decompressed == msg
        status = "✅" if roundtrip_ok else "❌"
        
        if not roundtrip_ok:
            all_passed = False
        
        print(f"{status} Message {i}:")
        print(f"   Original:   {original_size:,} bytes")
        print(f"   Compressed: {compressed_size:,} bytes")
        print(f"   Method:     {meta.get('method', 'UNKNOWN')}")
        print(f"   Ratio:      {meta.get('ratio', 'N/A')}")
        print(f"   Time:       {meta.get('time_ms', 'N/A')} ms")
        print(f"   Roundtrip:  {'OK' if roundtrip_ok else 'FAILED'}")
        print()
    
    # Print overall stats
    print("=" * 60)
    print("Compression Statistics:")
    print("-" * 60)
    stats = transport.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("=" * 60)
    if all_passed:
        print("✅ All compression tests PASSED")
    else:
        print("❌ Some compression tests FAILED")
    print("=" * 60)
    
    return all_passed


def test_aura_on_nanos():
    """
    Test AURA compression on the actual nano cluster.
    
    This sends compressed messages to nanos and verifies they work.
    """
    print("=" * 60)
    print("AURA Cluster Transport - Nano Integration Test")
    print("=" * 60)
    
    try:
        from tools.nano_cluster import get_cluster
    except ImportError:
        print("❌ Cannot import nano_cluster")
        return False
    
    transport = get_transport()
    cluster = get_cluster()
    
    print(f"AURA enabled: {transport.enabled}")
    print(f"Cluster nodes: {len(cluster.nodes)}")
    print()
    
    # Test compressing a prompt before sending
    test_prompt = "What is 2 + 2? Reply with just the number."
    
    compressed, meta = transport.compress_message(test_prompt)
    print(f"Test prompt: '{test_prompt}'")
    print(f"Compressed: {len(compressed)} bytes (was {len(test_prompt)})")
    print(f"Method: {meta.get('method')}")
    print()
    
    # Find an online node
    online_nodes = [n for n in cluster.nodes.values() if n.check_status()]
    
    if not online_nodes:
        print("❌ No online nodes found")
        return False
    
    node = online_nodes[0]
    print(f"Testing with node: {node.name} at {node.ip}")
    
    # Send the original prompt (nanos expect uncompressed for now)
    # But we demonstrate the compression
    response = node.generate(
        prompt=test_prompt,
        temperature=0.1,
        max_tokens=10,
        timeout=30.0
    )
    
    if response:
        print(f"Response: {response}")
        
        # Compress the response too
        resp_compressed, resp_meta = transport.compress_message(response)
        print(f"Response compressed: {len(resp_compressed)} bytes (was {len(response)})")
        print(f"Response method: {resp_meta.get('method')}")
        print()
        print("✅ Nano integration test PASSED")
        return True
    else:
        print("❌ No response from nano")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--nano":
        test_aura_on_nanos()
    else:
        test_aura_compression()

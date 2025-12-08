"""
AURA sizing strategy profile: choose the best method by message size and structure.

Goal:
- For ultra-small, structured control messages → Bit-Packed (4B) or Secure Bit-Packed (6B)
- For small natural-language sentences → Binary Semantic (templates)
- For medium to larger text → BRIO/Auralite
- For very small or non-beneficial cases → UNCOMPRESSED

This module classifies input and suggests an expected method with a rationale and size estimate.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Optional, Tuple

from communication.aura_bitpacked_extension import BitPackedCompressor

MethodName = Literal[
    "BITPACKED", "BITPACKED_SECURE", "BINARY_SEMANTIC", "AURALITE", "BRIO", "UNCOMPRESSED"
]

# Singleton compressor instance - avoid repeated instantiation
_BITPACKER_SINGLETON: Optional[BitPackedCompressor] = None

def _get_bitpacker() -> BitPackedCompressor:
    """Get or create singleton BitPackedCompressor."""
    global _BITPACKER_SINGLETON
    if _BITPACKER_SINGLETON is None:
        _BITPACKER_SINGLETON = BitPackedCompressor()
    return _BITPACKER_SINGLETON


@dataclass(frozen=True)
class StrategyDecision:
    """Immutable strategy decision for compression method selection."""
    __slots__ = ('method', 'reason', 'estimated_size')
    method: MethodName
    reason: str
    estimated_size: int


# LRU cache for repeated messages (common in batch processing)
@lru_cache(maxsize=1024)
def _cached_classify(text: str, prefer_secure: bool, min_size: int) -> Tuple[str, str, int]:
    """Cached classification - returns tuple for hashability."""
    bp = _get_bitpacker()
    size = len(text.encode("utf-8"))
    
    # Fast path: check bit-packed eligibility
    if bp.can_compress(text):
        if prefer_secure:
            return ("BITPACKED_SECURE", "Structured control message; hardened micro-frame preferred", 6)
        return ("BITPACKED", "Structured control message; ultra-compact 4B frame", 4)
    
    # Size-based classification
    if size < min_size:
        return ("UNCOMPRESSED", f"Too small to beat headers (size={size} < min={min_size})", size + 1)
    if size <= 90:
        return ("BINARY_SEMANTIC", "Short sentence; template match likely (few slot tokens)", max(5, size // 2))
    if size <= 512:
        return ("BRIO", "Medium text; BRIO tends to outperform templates", max(20, size // 3))
    return ("AURALITE", "Large text; heavy compressors achieve best ratios", max(64, size // 4))


class AURAStrategyProfile:
    """Fast strategy profiler with caching and singleton compressor."""
    
    __slots__ = ('prefer_secure_bitpacked', 'min_compression_size')
    
    def __init__(self, prefer_secure_bitpacked: bool = True, min_compression_size: int = 18):
        self.prefer_secure_bitpacked = prefer_secure_bitpacked
        self.min_compression_size = min_compression_size

    def classify(self, text: str) -> StrategyDecision:
        """Classify message using cached lookup."""
        method, reason, est_size = _cached_classify(
            text, self.prefer_secure_bitpacked, self.min_compression_size
        )
        return StrategyDecision(method=method, reason=reason, estimated_size=est_size)  # type: ignore[arg-type]


def classify_message(text: str, prefer_secure_bitpacked: bool = True, min_compression_size: int = 18) -> StrategyDecision:
    """Fast classification with LRU caching for repeated messages."""
    method, reason, est_size = _cached_classify(text, prefer_secure_bitpacked, min_compression_size)
    return StrategyDecision(method=method, reason=reason, estimated_size=est_size)  # type: ignore[arg-type]


def clear_classification_cache() -> None:
    """Clear the LRU cache (useful after config changes)."""
    _cached_classify.cache_clear()


def get_cache_stats() -> dict:
    """Get cache hit/miss statistics."""
    info = _cached_classify.cache_info()
    return {
        'hits': info.hits,
        'misses': info.misses,
        'size': info.currsize,
        'maxsize': info.maxsize,
        'hit_rate': info.hits / max(1, info.hits + info.misses)
    }

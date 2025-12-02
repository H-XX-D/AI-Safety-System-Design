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
from typing import Literal

from aura_bitpacked_extension import BitPackedCompressor

MethodName = Literal[
    "BITPACKED", "BITPACKED_SECURE", "BINARY_SEMANTIC", "AURALITE", "BRIO", "UNCOMPRESSED"
]


@dataclass
class StrategyDecision:
    method: MethodName
    reason: str
    estimated_size: int


class AURAStrategyProfile:
    def __init__(self, prefer_secure_bitpacked: bool = True, min_compression_size: int = 18):
        self.prefer_secure_bitpacked = prefer_secure_bitpacked
        self.min_compression_size = min_compression_size
        self.bitpacker = BitPackedCompressor()

    def classify(self, text: str) -> StrategyDecision:
        size = len(text.encode("utf-8"))

        # 1) Ultra-small structured approvals/rejections/reviews (bit-packed eligible)
        if self.bitpacker.can_compress(text):
            if self.prefer_secure_bitpacked:
                return StrategyDecision(
                    method="BITPACKED_SECURE",
                    reason="Structured control message; hardened micro-frame preferred",
                    estimated_size=6,
                )
            else:
                return StrategyDecision(
                    method="BITPACKED",
                    reason="Structured control message; ultra-compact 4B frame",
                    estimated_size=4,
                )

        # 2) Very small unstructured (< min_compression_size) → avoid expansion
        if size < self.min_compression_size:
            return StrategyDecision(
                method="UNCOMPRESSED",
                reason=f"Too small to beat headers (size={size} < min={self.min_compression_size})",
                estimated_size=size + 1,  # simplified: method marker
            )

        # 3) Short sentences (≈ 18–90B): templates likely win
        if size <= 90:
            return StrategyDecision(
                method="BINARY_SEMANTIC",
                reason="Short sentence; template match likely (few slot tokens)",
                estimated_size=max(5, size // 2),
            )

        # 4) Medium text (≈ 90–512B): BRIO/Auralite
        if size <= 512:
            return StrategyDecision(
                method="BRIO",
                reason="Medium text; BRIO tends to outperform templates",
                estimated_size=max(20, size // 3),
            )

        # 5) Larger payloads (512B+): Auralite/BRIO heavy
        return StrategyDecision(
            method="AURALITE",
            reason="Large text; heavy compressors achieve best ratios",
            estimated_size=max(64, size // 4),
        )


def classify_message(text: str, prefer_secure_bitpacked: bool = True, min_compression_size: int = 18) -> StrategyDecision:
    return AURAStrategyProfile(prefer_secure_bitpacked, min_compression_size).classify(text)

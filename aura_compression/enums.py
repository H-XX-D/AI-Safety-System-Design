"""Lightweight enumerations mirroring the real AURA package API."""
from __future__ import annotations

from enum import IntEnum


class CompressionMethod(IntEnum):
    """Subset of the original compression methods used in tests."""

    BINARY_SEMANTIC = 0x01
    BRIO = 0x03
    BROTLI = 0x04
    UNCOMPRESSED = 0xFF

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

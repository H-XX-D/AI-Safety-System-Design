"""
Communication and Compression Components
=========================================

This package contains message codecs and compression algorithms
for the AI Safety System.
"""

from .message_codec import MessageCodec
from .aura_compressor import classify_and_compress

__all__ = [
    'MessageCodec',
    'classify_and_compress'
]

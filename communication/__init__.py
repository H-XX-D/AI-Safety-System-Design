"""
Communication and Compression Components
=========================================

This package contains message codecs and compression algorithms
for the AI Safety System.

Key modules:
- message_codec: Basic message encoding/decoding
- aura_compressor: Hybrid compression with classification
- aura_numpy_workflow: NumPy-backed templates (3.8M ops/sec on Orin)
- aura_fast: JIT-compiled fast compression paths
"""

from .message_codec import MessageCodec
from .aura_compressor import classify_and_compress

# NumPy template workflow (lazy import to avoid circular deps)
def get_numpy_workflow():
    """Get numpy template compression functions."""
    from .aura_numpy_workflow import (
        compress_with_numpy_templates,
        batch_compress_with_numpy,
        init_numpy_workflow,
        get_workflow_stats,
    )
    return {
        'compress': compress_with_numpy_templates,
        'batch_compress': batch_compress_with_numpy,
        'init': init_numpy_workflow,
        'stats': get_workflow_stats,
    }

__all__ = [
    'MessageCodec',
    'classify_and_compress',
    'get_numpy_workflow',
]

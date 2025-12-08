"""
Factory helpers for AURA compressor with ML selection disabled.

Rationale: The ML-based algorithm selector has been unstable in our env.
This wrapper ensures ProductionHybridCompressor is always instantiated
with enable_ml_selection=False while allowing other knobs to pass through.

Optimizations:
- Singleton BitPackedCompressor for fast bit-packed operations
- LRU-cached classification for repeated messages
- Cached compressor instances per configuration
"""
from __future__ import annotations

from typing import Any, Optional, Tuple, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from communication.aura_bitpacked_extension import BitPackedCompressor

try:
    from aura_compression import ProductionHybridCompressor
except Exception as e:  # pragma: no cover
    # Defer import error until actually constructing, so repo can import safely
    ProductionHybridCompressor = None  # type: ignore[misc]
    _import_error: Optional[Exception] = e
else:
    _import_error = None


def create_compressor(**kwargs: Any) -> "ProductionHybridCompressor":
    """
    Create a ProductionHybridCompressor with ML selection disabled.

    All provided kwargs are forwarded except enable_ml_selection, which is
    forcibly set to False to avoid the ML path.

    Example:
        compressor = create_compressor(enable_sidechain=True,
                                       enable_fast_path=True,
                                       min_compression_size=18)
    """
    if _import_error is not None:  # pragma: no cover
        raise _import_error

    # Force-disable ML selection regardless of caller's input
    kwargs["enable_ml_selection"] = False

    # Construct and return compressor
    return ProductionHybridCompressor(**kwargs)  # type: ignore[call-arg]


# Singleton compressor cache for fast path
_COMPRESSOR_CACHE: Dict[Tuple, Any] = {}
_BITPACKER_SINGLETON: Any = None


def _get_bitpacker() -> Any:
    """Get singleton BitPackedCompressor for fast bit-packed operations."""
    global _BITPACKER_SINGLETON
    if _BITPACKER_SINGLETON is None:
        from communication.aura_bitpacked_extension import BitPackedCompressor
        _BITPACKER_SINGLETON = BitPackedCompressor()
    return _BITPACKER_SINGLETON


def _get_cached_compressor(**kwargs: Any) -> "ProductionHybridCompressor":
    """Get or create cached compressor for given configuration."""
    # Create hashable key from kwargs
    key = tuple(sorted(kwargs.items()))
    if key not in _COMPRESSOR_CACHE:
        _COMPRESSOR_CACHE[key] = create_compressor(**kwargs)
    return _COMPRESSOR_CACHE[key]


def classify_and_compress(text: str,
                          *,
                          prefer_secure_bitpacked: bool = True,
                          min_compression_size: int = 18,
                          use_numpy_templates: bool = True,
                          **kwargs: Any) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Classify message size/structure and choose an appropriate method.

    Optimized with singleton compressors and LRU-cached classification.
    
    - If numpy template match → use native 3.8M ops/sec path
    - If bit-packed eligible → use secure (6B) or standard (4B) per flag.
    - Else use cached ProductionHybridCompressor (ML disabled) and compress.
    Returns (payload, method_name, metadata)
    """
    # FASTEST PATH: Try numpy template compression first (3.8M ops/sec on Orin)
    if use_numpy_templates:
        try:
            from communication.aura_numpy_workflow import get_numpy_compressor
            numpy_comp = get_numpy_compressor()
            
            if prefer_secure_bitpacked:
                result = numpy_comp.compress_secure(text)
            else:
                result = numpy_comp.compress(text)
            
            if result is not None:
                payload, meta = result
                return payload, meta['method'], meta
        except ImportError:
            pass  # numpy workflow not available
        except Exception:
            pass  # Fall through to other methods
    
    from communication.aura_strategy_profile import classify_message

    decision = classify_message(text, prefer_secure_bitpacked, min_compression_size)
    
    # Fast path for bitpacked - use singleton
    if decision.method in ("BITPACKED", "BITPACKED_SECURE"):
        bp = _get_bitpacker()
        payload = bp.compress_secure(text) if decision.method == "BITPACKED_SECURE" else bp.compress(text)
        if payload is not None:
            meta: Dict[str, Any] = {
                'method': decision.method,
                'estimated_size': decision.estimated_size,
                'reason': decision.reason,
                'auditable': True,
            }
            return payload, decision.method, meta
        # If for any reason it failed, fall through to AURA compressor

    # Enforce binary semantic when classifier picks it
    if decision.method == "BINARY_SEMANTIC":
        try:
            from communication.aura_native import compress as native_compress  # type: ignore
            payload = native_compress(text)
            meta = {
                'method': 'BINARY_SEMANTIC',
                'reason': decision.reason,
                'estimated_size': decision.estimated_size,
                'auditable': True,
                'native': True,
            }
            if payload:
                return payload, 'BINARY_SEMANTIC', meta
        except Exception:
            pass  # Fall back to hybrid compressor if native path fails

        # Python-side semantic dictionary fallback (NumPy NPZ)
        try:
            from communication.aura_semantic_dict import load_semantic_dictionary

            sem = load_semantic_dictionary()
            if sem:
                idx = sem.get_index(text)
                if idx is not None and 0 <= idx <= 0xFFFF:
                    payload = bytes([0xB1, (idx >> 8) & 0xFF, idx & 0xFF])
                    meta = {
                        'method': 'BINARY_SEMANTIC',
                        'reason': decision.reason,
                        'estimated_size': decision.estimated_size,
                        'auditable': True,
                        'native': False,
                        'semantic_index': idx,
                    }
                    return payload, 'BINARY_SEMANTIC', meta
        except Exception:
            pass

    # Try Semantic Hybrid (Substring + Literals) before falling back to Brotli
    # This allows partial dictionary matches even if the full string doesn't match.
    try:
        from communication.aura_semantic_dict import load_semantic_dictionary
        sem = load_semantic_dictionary()
        if sem:
            hybrid_payload = sem.compress_hybrid(text)
            # Only use if it actually compresses (and isn't None)
            if hybrid_payload and len(hybrid_payload) < len(text):
                 return hybrid_payload, 'SEMANTIC_HYBRID', {
                     'method': 'SEMANTIC_HYBRID',
                     'original_size': len(text),
                     'compressed_size': len(hybrid_payload),
                     'auditable': True
                 }
    except Exception:
        pass

    # Try Pattern Semantic Compressor for larger payloads (AI-Powered)
    # This is the "AI-Powered Novel Large File Compression" from ARUA-S
    if len(text) > 500:
        try:
            from communication.pattern_semantic_compressor import PatternSemanticCompressor
            psc = PatternSemanticCompressor()
            psc_payload, stats = psc.compress(text)
            
            # Check if it actually compressed better than original
            if len(psc_payload) < len(text):
                # Method byte 0xB3 for PATTERN_SEMANTIC
                final_payload = b'\xB3' + psc_payload
                return final_payload, 'PATTERN_SEMANTIC', {
                    'method': 'PATTERN_SEMANTIC',
                    'original_size': stats.original_size,
                    'compressed_size': len(final_payload),
                    'ratio': stats.ratio,
                    'patterns_found': stats.patterns_found,
                    'auditable': True
                }
        except Exception:
            pass

    # Use cached compressor instance
    compressor = _get_cached_compressor(**kwargs)
    payload, method, meta = compressor.compress(text)
    # Normalize method name
    method_name: str = getattr(method, 'name', str(method))
    return payload, method_name, meta


def clear_compressor_cache() -> None:
    """Clear all cached compressor instances."""
    global _BITPACKER_SINGLETON
    _COMPRESSOR_CACHE.clear()
    _BITPACKER_SINGLETON = None

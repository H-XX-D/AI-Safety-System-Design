"""
Factory helpers for AURA compressor with ML selection disabled.

Rationale: The ML-based algorithm selector has been unstable in our env.
This wrapper ensures ProductionHybridCompressor is always instantiated
with enable_ml_selection=False while allowing other knobs to pass through.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple, Dict

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


def classify_and_compress(text: str,
                          *,
                          prefer_secure_bitpacked: bool = True,
                          min_compression_size: int = 18,
                          **kwargs: Any) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Classify message size/structure and choose an appropriate method.

    - If bit-packed eligible → use secure (6B) or standard (4B) per flag.
    - Else create a ProductionHybridCompressor (ML disabled) and compress.
    Returns (payload, method_name, metadata)
    """
    from aura_strategy_profile import classify_message
    from aura_bitpacked_extension import BitPackedCompressor

    decision = classify_message(text, prefer_secure_bitpacked, min_compression_size)
    # Fast path for bitpacked
    if decision.method in ("BITPACKED", "BITPACKED_SECURE"):
        bp = BitPackedCompressor()
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

    compressor = create_compressor(**kwargs)
    payload, method, meta = compressor.compress(text)
    # Normalize method name
    method_name: str = getattr(method, 'name', str(method))
    return payload, method_name, meta

"""Security utilities: constant-time compares and helpers."""
from __future__ import annotations

import hmac
from typing import Union


def constant_time_equals(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """Constant-time equality for bytes or ASCII strings using hmac.compare_digest."""
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hmac.compare_digest(a, b)

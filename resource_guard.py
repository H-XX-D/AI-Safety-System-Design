"""Lightweight resource budget guard.

Provides a context manager to enforce a simple time budget for critical
operations. Supports an injectable time provider for tests.
"""
from __future__ import annotations

from typing import Callable

import time


class BudgetExceeded(Exception):
    pass


class ResourceBudget:
    def __init__(self, max_ms: float, *, time_provider: Callable[[], float] | None = None):
        self.max_ms = max_ms
        self._time = time_provider or (lambda: time.perf_counter() * 1000.0)
        self._start = 0.0

    def __enter__(self):
        self._start = self._time()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        elapsed = self._time() - self._start
        if elapsed > self.max_ms:
            raise BudgetExceeded(f"operation exceeded budget: {elapsed:.2f}ms > {self.max_ms}ms")
        return False

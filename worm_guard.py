"""WORM Guard Module
=====================

Central software enforcement layer complementing physical WORM USB.

Goals:
1. Verify that WORM manifest fundamentals are present before any critical action
2. Provide constant-time verification helpers (avoid timing side channels)
3. Enforce anti-rollback using a monotonic version counter persisted in memory_merkle
4. Track failed verification attempts with backoff + escalation (soft vs hard tamper)
5. Maintain hash-chained audit log of guard events for forensic review
6. Offer a simple decision point API that upstream orchestrators call prior to risky operations

Design Notes:
------------
We deliberately keep this lightweight and dependency-minimal. True cryptographic
hardening (secure element keys, VRF proofs, PQ signatures) will integrate later.

Soft Tamper Conditions (no irreversible scramble trigger here):
  - Repeated failed manifest verification
  - Excessive rate of verification attempts
  - Hash root mismatch

Hard Tamper Conditions (placeholder flag; hardware layer executes scramble):
  - Explicit override call from external attestation layer
  - Detected impossible state transitions (rollback past recorded minimum)

Use get_guard() singleton for process-wide access.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

from attestation import sign, verify  # lightweight HMAC placeholder
from threading import Lock

from worm_manifest import get_expected_core_values_hash, get_expected_alignment_filter_hash
from memory_merkle import MemoryStorage, MemoryType


_guard_singleton = None
_guard_lock = Lock()


@dataclass
class GuardEvent:
    ts: float
    kind: str
    detail: str
    hash_prev: str
    hash_event: str
    signature: str  # attestation signature over canonical event serialization

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ts': self.ts,
            'kind': self.kind,
            'detail': self.detail,
            'hash_prev': self.hash_prev,
            'hash_event': self.hash_event,
            'signature': self.signature,
        }


class WormGuard:
    """Software guard enforcing WORM prerequisites."""

    def __init__(self,
                 memory_storage: Optional[MemoryStorage] = None,
                 max_failures_soft: int = 5,
                 rate_window_sec: int = 60,
                 max_attempts_per_window: int = 20):
        self.max_failures_soft = max_failures_soft
        self.rate_window_sec = rate_window_sec
        self.max_attempts_per_window = max_attempts_per_window
        self._fail_count = 0
        self._attempt_timestamps: List[float] = []
        self._soft_tamper = False
        self._hard_tamper = False
        self._monotonic_version: int = 0  # strictly increasing
        # Audit log hash chain
        self._events: List[GuardEvent] = []
        self._last_event_hash: str = '0' * 64
        self._mem = memory_storage  # optional persistence medium

    # ---------------- Internal helpers ----------------
    def _hash_ct(self, a: str, b: str) -> bool:
        """Constant-time string equality (length + byte compare)."""
        if len(a) != len(b):
            # Perform dummy work to equalize timing
            _ = hashlib.sha256(a.encode()).hexdigest()
            _ = hashlib.sha256(b.encode()).hexdigest()
            return False
        result = 0
        for x, y in zip(a.encode(), b.encode()):
            result |= x ^ y
        return result == 0

    def _record_event(self, kind: str, detail: str) -> None:
        ts = time.time()
        payload_obj: Dict[str, Any] = {'kind': kind, 'detail': detail, 'ts': ts}
        payload = json.dumps(payload_obj, sort_keys=True)
        h_event = hashlib.sha256((self._last_event_hash + payload).encode()).hexdigest()
        # signature binds previous hash + current payload + new hash
        sig_material = json.dumps({
            'hash_prev': self._last_event_hash,
            'payload': payload_obj,
            'hash_event': h_event,
        }, sort_keys=True).encode()
        signature = sign(sig_material)
        ev = GuardEvent(ts=ts, kind=kind, detail=detail, hash_prev=self._last_event_hash, hash_event=h_event, signature=signature)
        self._events.append(ev)
        self._last_event_hash = h_event

    def _prune_attempts(self) -> None:
        cutoff = time.time() - self.rate_window_sec
        self._attempt_timestamps = [t for t in self._attempt_timestamps if t >= cutoff]

    # ---------------- Public API ----------------
    def verify_worm(self) -> bool:
        """Verify WORM fundamentals; update counters and tamper flags."""
        now = time.time()
        self._attempt_timestamps.append(now)
        self._prune_attempts()
        if len(self._attempt_timestamps) > self.max_attempts_per_window:
            self._soft_tamper = True
            self._record_event('rate_limit_exceeded', f"attempts={len(self._attempt_timestamps)} window={self.rate_window_sec}s")
            return False
        core_hash = get_expected_core_values_hash()
        align_hash = get_expected_alignment_filter_hash()
        ok = bool(core_hash and align_hash)
        if not ok:
            self._fail_count += 1
            self._record_event('verification_failed', f"fails={self._fail_count}")
            if self._fail_count >= self.max_failures_soft:
                self._soft_tamper = True
                self._record_event('soft_tamper', 'max_failures_exceeded')
            return False
        # success path
        if self._fail_count > 0:
            self._record_event('verification_recovered', f"previous_failures={self._fail_count}")
        self._fail_count = 0
        self._record_event('verification_ok', 'fundamentals_present')
        return True

    def advance_version(self, new_version: int) -> bool:
        """Advance monotonic version; reject rollback."""
        if new_version <= self._monotonic_version:
            self._soft_tamper = True
            self._record_event('rollback_detected', f"current={self._monotonic_version} attempted={new_version}")
            return False
        self._monotonic_version = new_version
        self._record_event('version_advanced', f"new_version={new_version}")
        # Optionally persist monotonic version in memory storage for cross-process attestation
        if self._mem:
            try:
                self._mem.store_memory(MemoryType.METACOGNITIVE, {
                    'guard_event': 'version_advanced',
                    'version': new_version,
                    'ts': time.time(),
                })
            except Exception:
                # Non-fatal: persistence is advisory
                pass
        return True

    def escalate_hard_tamper(self, reason: str) -> None:
        """External trigger for irreversible scramble path (simulated)."""
        if not self._hard_tamper:
            self._hard_tamper = True
            self._record_event('hard_tamper', reason)

    def status(self) -> Dict[str, Any]:
        return {
            'soft_tamper': self._soft_tamper,
            'hard_tamper': self._hard_tamper,
            'fail_count': self._fail_count,
            'monotonic_version': self._monotonic_version,
            'attempt_rate': len(self._attempt_timestamps),
            'last_event_hash': self._last_event_hash,
        }

    def export_audit_chain(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]

    def verify_event_chain(self) -> bool:
        """Verify complete chain integrity and signatures.

        Returns True only if:
          - Each event hash recomputes correctly
          - Each signature validates for its material
          - hash_prev linkage is consistent
          - Final recomputed hash matches stored _last_event_hash (detects silent truncation)
        """
        last = '0' * 64
        for ev in self._events:
            payload_obj: Dict[str, Any] = {'kind': ev.kind, 'detail': ev.detail, 'ts': ev.ts}
            payload = json.dumps(payload_obj, sort_keys=True)
            recomputed_hash = hashlib.sha256((last + payload).encode()).hexdigest()
            if recomputed_hash != ev.hash_event or ev.hash_prev != last:
                return False
            sig_material = json.dumps({
                'hash_prev': ev.hash_prev,
                'payload': payload_obj,
                'hash_event': ev.hash_event,
            }, sort_keys=True).encode()
            if not verify(sig_material, ev.signature):
                return False
            last = ev.hash_event
        # Ensure stored last_event_hash matches recomputed terminal hash to catch rollback truncation
        if last != self._last_event_hash:
            return False
        return True

    def decision_point(self) -> Tuple[bool, str]:
        """Return (allowed, reason). Upstream must call before critical ops."""
        if self._hard_tamper:
            return False, 'hard_tamper_triggered'
        if self._soft_tamper:
            return False, 'soft_tamper_lockout'
        if not self.verify_worm():
            return False, 'worm_verification_failed'
        return True, 'ok'


def get_guard(memory_storage: Optional[MemoryStorage] = None) -> WormGuard:
    global _guard_singleton
    with _guard_lock:
        if _guard_singleton is None:
            _guard_singleton = WormGuard(memory_storage=memory_storage)
        return _guard_singleton


__all__ = ['WormGuard', 'get_guard']

"""
MockSerial implementation used by CI tests when hardware is unavailable.

Provides a tiny subset of the pyserial interface required by
tests/test_mock_serial_messages.py so automation can exercise the translator
pipeline without a USB device.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Optional


class MockSerial:
    """
    Lightweight stand‑in for pyserial's Serial class.

    Usage patterned after tests:
        ser = MockSerial(timeout=0.2)
        ser.write(b'{"message_id": "id"}\\n')
        line = ser.readline()
    """

    def __init__(self, *, timeout: float = 0.1):
        self.timeout = timeout
        self._buffer = bytearray()

    # ---------------------------------------------------------------------
    # pyserial-like API
    # ---------------------------------------------------------------------
    def write(self, data: bytes) -> int:
        """Accept arbitrary bytes and enqueue a JSON status line."""
        response = self._build_response(data)
        self._buffer.extend(response.encode("utf-8") + b"\n")
        return len(data)

    def readline(self) -> bytes:
        """Return the next line from the buffer, waiting up to timeout."""
        deadline = time.time() + self.timeout
        while b"\n" not in self._buffer and time.time() < deadline:
            time.sleep(0.001)

        if b"\n" not in self._buffer:
            # Nothing available; mimic serial timeout semantics.
            return b""

        idx = self._buffer.index(b"\n")
        line = self._buffer[:idx + 1]
        del self._buffer[:idx + 1]
        return bytes(line)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_response(self, data: bytes) -> str:
        """Create a JSON response string based on the inbound payload."""
        decoded: Optional[str] = None
        try:
            decoded = data.decode("utf-8").strip()
        except Exception:
            decoded = None

        payload = {}
        if decoded:
            try:
                payload = json.loads(decoded)
            except json.JSONDecodeError:
                payload = {}

        if payload:
            message_id = payload.get("message_id", "mock-json")
            internal_payload = payload.get("internal_payload", "")
            translated = f"Translated payload '{internal_payload}' to a human-auditable form."
            signature_source = json.dumps(payload, sort_keys=True)
            resp = {
                "message_id": message_id,
                "approved": True,
                "translated_text": translated,
                "confidence": 0.98,
                "signature": self._signature(signature_source),
            }
        else:
            resp = {
                "message_id": "mock-bin",
                "approved": True,
                "translated_text": "binary message accepted and queued for hardware translator",
                "confidence": 0.75,
                "signature": self._signature(data.hex()),
            }

        return json.dumps(resp)

    @staticmethod
    def _signature(seed: str | bytes) -> str:
        """Return a deterministic pseudo-signature derived from the seed."""
        if isinstance(seed, bytes):
            payload = seed
        else:
            payload = seed.encode("utf-8", errors="replace")
        digest = hashlib.sha256(payload).hexdigest()
        return digest * 2  # 64 chars -> 128 for readability

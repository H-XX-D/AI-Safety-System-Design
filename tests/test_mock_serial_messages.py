#!/usr/bin/env python3
"""
Tests for MockSerial to enable CI validation without hardware.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

# Add project root to path for direct module imports (robust in diverse CI layouts)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from esp32.mock_serial import MockSerial  # type: ignore

def test_mock_serial_json_roundtrip():
    ser = MockSerial(timeout=0.2)
    msg = {
        "message_id": "test_001",
        "from_system": 1,
        "to_system": 6,
        "protocol_version": "1.0",
        "internal_payload": "SYS_1_ACT_APPR_PROP_042_CERT_HIGH_RISK_NONE",
        "payload_hash": ""
    }
    payload = (json.dumps(msg) + "\n").encode()
    ser.write(payload)

    line = ser.readline().decode().strip()
    assert line, "expected response from MockSerial"
    resp = json.loads(line)
    assert resp["approved"] is True
    assert "translated_text" in resp
    assert isinstance(resp.get("confidence"), float)
    assert len(resp.get("signature", "")) >= 32


def test_mock_serial_binary_roundtrip():
    ser = MockSerial(timeout=0.2)
    # Write arbitrary binary payload
    data = bytes([0x41, 0x55, 0x52, 0x41, 0x02, 0x00, 0x00, 0x10]) + b"body" * 4
    ser.write(data)

    line = ser.readline().decode().strip()
    assert line
    resp = json.loads(line)
    assert resp["approved"] is True
    assert resp["message_id"] == "mock-bin"
    assert "binary message accepted" in resp["translated_text"]

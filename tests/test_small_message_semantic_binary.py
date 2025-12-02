#!/usr/bin/env python3
"""
Benchmark-style assertions comparing AURA bit-packed small messages to generic
"semantic binary" encodings like MessagePack and CBOR when available.

We don't hard-require extra packages; tests skip format-specific checks if the
optional dependency isn't installed.
"""
from __future__ import annotations
import pytest

# Minimal bit-packed implementation (mirrors esp32/test_ultra_compressed.py)
BP_MSG_PROPOSAL = 0b000
BP_MSG_REVIEW = 0b001
BP_MSG_VOTE = 0b010
BP_MSG_ALERT = 0b100

BP_ACT_APPROVE = 0b00
BP_ACT_REJECT = 0b01
BP_ACT_ABSTAIN = 0b10
BP_ACT_ESCALATE = 0b11

BP_CONF_LOW = 0b00
BP_CONF_MED = 0b01
BP_CONF_HIGH = 0b10
BP_CONF_MAX = 0b11

BP_RISK_NO = 0b0
BP_RISK_YES = 0b1

def build_bitpacked_message(msg_type: int, action: int, confidence: int, risk: int,
                            proposal_id: int, from_sys: int, to_sys: int) -> bytes:
    control_byte = (msg_type << 5) | (action << 3) | (confidence << 1) | risk
    system_ids = (from_sys << 4) | to_sys
    return bytes([control_byte, proposal_id, system_ids])

# Optional imports
try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover
    msgpack = None  # type: ignore

try:
    import cbor2  # type: ignore
except Exception:  # pragma: no cover
    cbor2 = None  # type: ignore


def small_message_fields():
    return dict(
        t=BP_MSG_REVIEW,
        a=BP_ACT_APPROVE,
        c=BP_CONF_HIGH,
        r=BP_RISK_NO,
        p=42,
        f=1,
        to=6,
    )


def test_bitpacked_vs_msgpack_when_available():
    fields = small_message_fields()
    packed = build_bitpacked_message(
        fields['t'], fields['a'], fields['c'], fields['r'], fields['p'], fields['f'], fields['to']
    )

    if msgpack is None:  # pragma: no cover
        pytest.skip("msgpack not installed; skipping size comparison")

    mp = msgpack.packb(fields, use_bin_type=True)
    assert len(packed) <= len(mp), (
        f"AURA bit-packed should be as small or smaller for this control message: "
        f"bitpacked={len(packed)} msgpack={len(mp)}"
    )


def test_bitpacked_vs_cbor_when_available():
    fields = small_message_fields()
    packed = build_bitpacked_message(
        fields['t'], fields['a'], fields['c'], fields['r'], fields['p'], fields['f'], fields['to']
    )

    if cbor2 is None:  # pragma: no cover
        pytest.skip("cbor2 not installed; skipping size comparison")

    cb = cbor2.dumps(fields)
    assert len(packed) <= len(cb), (
        f"AURA bit-packed should be as small or smaller for this control message: "
        f"bitpacked={len(packed)} cbor={len(cb)}"
    )

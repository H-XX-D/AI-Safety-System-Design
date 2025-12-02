from utilities.hardware_translator import HardwareTranslator, AIMessage
import hashlib
from datetime import datetime


def make_msg(payload: bytes) -> AIMessage:
    return AIMessage(
        message_id="m1",
        from_system=1,
        to_system=2,
        timestamp=datetime.now().isoformat(),
        protocol_version='1.0',
        message_type='test',
        internal_payload=payload,
        payload_hash=hashlib.sha256(payload).hexdigest(),
        signature="sig"
    )


def test_token_coverage_and_confidence_penalty():
    ht = HardwareTranslator(1, '1.0', 'k')
    # Known tokens -> high coverage
    payload_known = b"MSG_PROP performance ++ STAT_PEND"
    info_known = ht.analyze_token_coverage_from_payload(payload_known)
    assert info_known['total_tokens'] >= 2
    assert info_known['coverage_ratio'] == 1.0
    # Unknown token present -> lower coverage
    payload_unknown = b"MSG_UNKNOWN something STAT_PEND"
    info_unknown = ht.analyze_token_coverage_from_payload(payload_unknown)
    assert info_unknown['coverage_ratio'] < 1.0
    # Confidence should be penalized when unknown token remains after translation
    msg = make_msg(payload_unknown)
    translated = ht.translate_to_human(msg)
    assert translated.confidence < 1.0

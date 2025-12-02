from utilities.hardware_translator import HardwareTranslator, AIMessage, TranslatorVerificationSystem
import hashlib
from datetime import datetime


def _make_ai_message(payload: str) -> AIMessage:
    payload_bytes = payload.encode('utf-8')
    return AIMessage(
        message_id='m1',
        from_system=1,
        to_system=2,
        timestamp=datetime.now().isoformat(),
        protocol_version='1.0',
        message_type='MSG_PROP',
        internal_payload=payload_bytes,
        payload_hash=hashlib.sha256(payload_bytes).hexdigest(),
        signature='s'
    )


def test_hardware_translator_translation_and_consensus():
    t1 = HardwareTranslator(1, '1.0', 'k1')
    t2 = HardwareTranslator(2, '1.0', 'k2')
    msg = _make_ai_message('MSG_PROP RISK_LOW STAT_PEND')
    hr1 = t1.translate_to_human(msg)
    _ = t2.translate_to_human(msg)
    assert 'improvement_proposal' in hr1.readable_text
    assert 'risk_low' in hr1.readable_text
    system = TranslatorVerificationSystem([t1, t2])
    ver = system.verify_translation_consensus(msg)
    assert ver.all_translators_agree is True
    assert ver.consensus_text is not None and 'improvement_proposal' in ver.consensus_text

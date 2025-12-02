from datetime import datetime
import hashlib

from hardware_translator import HardwareTranslator, AIMessage


def test_translation_rule_full_coverage():
    translator = HardwareTranslator(1, '1.0', 'priv')
    rules = translator.translation_rules['1.0']

    # Build internal payload containing all tokens separated by space
    tokens = list(rules.keys())
    payload_bytes = (' '.join(tokens)).encode('utf-8')
    msg = AIMessage(
        message_id='m_all',
        from_system=1,
        to_system=2,
        timestamp=datetime.now().isoformat(),
        protocol_version='1.0',
        message_type='MSG_PROP',
        internal_payload=payload_bytes,
        payload_hash=hashlib.sha256(payload_bytes).hexdigest(),
        signature='sig'
    )

    human = translator.translate_to_human(msg)
    text = human.readable_text

    # Each token should have been replaced by its human term; ensure raw token absent and human term present
    for token, human_term in rules.items():
        assert human_term in text, f"Expected human term {human_term} for token {token}"
        assert token not in text, f"Raw token {token} still present after translation"

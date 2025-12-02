from translator import AirGappedTranslator


def test_translator_handles_alert_message():
    translator = AirGappedTranslator(translator_id=1, protocol_version="1.0", private_key="secret")
    message = {
        "protocol_version": "1.0",
        "type": "alert",
        "severity": "high",
        "from_system": 3,
        "timestamp": "2025-11-13T00:00:00Z",
        "summary": "Sandbox regression detected",
        "recommended_action": "Halt outputs and investigate",
    }
    translation = translator.translate(message)
    assert "ALERT NOTIFICATION" in translation.translated_text
    assert "Sandbox regression detected" in translation.translated_text
    assert translation.confidence >= 0.7

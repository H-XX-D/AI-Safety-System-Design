from translator import Translation, TranslationVerifier

def make_t(text: str, conf: float) -> Translation:
    return Translation(
        original_hash="h1",
        translated_text=text,
        protocol_version="1.0",
        translator_id=1,
        confidence=conf,
        timestamp="t",
        signature="s",
    )


def test_weighted_verification_downweights_low_conflict_outlier():
    v = TranslationVerifier(required_translators=3)
    t1 = make_t("alpha beta gamma", 0.95)
    t2 = make_t("alpha beta gamma", 0.90)
    t3 = make_t("delta epsilon zeta", 0.20)  # low confidence outlier
    ok, _ = v.verify_translations_weighted("h1", [t1, t2, t3])
    assert ok is True


def test_weighted_verification_fails_for_high_conf_outlier():
    v = TranslationVerifier(required_translators=3)
    t1 = make_t("alpha beta gamma", 0.50)
    t2 = make_t("alpha beta gamma", 0.50)
    t3 = make_t("completely different text", 0.95)  # high confidence disagreement
    ok, msg = v.verify_translations_weighted("h1", [t1, t2, t3])
    assert ok is False
    assert "too low" in msg.lower()

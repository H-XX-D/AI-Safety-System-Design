from communication.translator import Translation
from utilities.semantic_consensus import compute_consensus


def _T(text: str, conf: float, tid: int) -> Translation:
    return Translation(
        original_hash="h1",
        translated_text=text,
        protocol_version="1.0",
        translator_id=tid,
        confidence=conf,
        timestamp="t",
        signature="s",
    )


def test_semantic_consensus_strong_agreement():
    trs = [
        _T("System 1 approves proposal 042", 0.96, 1),
        _T("System 1 approves proposal 042", 0.93, 2),
        _T("System 1 approves proposal 042", 0.91, 3),
    ]
    res = compute_consensus(trs)
    assert res['distinct_translators'] == 3
    assert res['pass_threshold'] is True
    assert (res['consensus_score'] if isinstance(res['consensus_score'], float) else 0.0) >= 0.9


def test_semantic_consensus_outlier_ignored():
    trs = [
        _T("alpha beta gamma", 0.95, 1),
        _T("alpha beta gamma", 0.90, 2),
        _T("delta epsilon zeta", 0.20, 3),
    ]
    res = compute_consensus(trs)
    # Low-confidence outlier should not drag similarity below threshold
    assert res['pass_threshold'] is True
    assert (res['weighted_similarity'] if isinstance(res['weighted_similarity'], float) else 0.0) >= 0.80

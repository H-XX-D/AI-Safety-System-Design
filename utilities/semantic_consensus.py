"""Semantic consensus aggregator for translator outputs.

Computes a confidence-weighted similarity score and incorporates
source (translator) diversity to produce an overall consensus score.

No external dependencies.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from communication.translator import Translation


def bucketize_confidence(conf: float) -> str:
    """Map a [0,1] confidence to coarse buckets for reporting."""
    if conf >= 0.95:
        return "maximum"
    if conf >= 0.75:
        return "high"
    if conf >= 0.5:
        return "medium"
    return "low"


def _text_similarity(a: str, b: str) -> float:
    """Very simple word-overlap similarity in [0,1]."""
    if a == b:
        return 1.0
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def compute_consensus(
    translations: List[Translation], *, min_translators: int = 3, similarity_floor: float = 0.0
) -> Dict[str, object]:
    """Compute consensus metrics.

    Returns dict with keys:
    - distinct_translators: int
    - weighted_similarity: float
    - confidence_buckets: Dict[str, int]
    - consensus_score: float  (0..1)
    - pass_threshold: bool    (score >= 0.80)
    """
    if not translations:
        return {
            "distinct_translators": 0,
            "weighted_similarity": 0.0,
            "confidence_buckets": {},
            "consensus_score": 0.0,
            "pass_threshold": False,
        }
    # Distinct sources
    distinct_sources = len({t.translator_id for t in translations})
    diversity_factor = min(1.0, distinct_sources / float(min_translators))

    # Confidence histogram
    buckets: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "maximum": 0}
    for t in translations:
        buckets[bucketize_confidence(t.confidence)] += 1

    # Confidence-weighted pairwise similarity; ignore very low confidence pairs
    weighted = 0.0
    total_w = 0.0
    n = len(translations)
    for i in range(n):
        for j in range(i + 1, n):
            t1, t2 = translations[i], translations[j]
            w = max(0.0, min(1.0, (t1.confidence + t2.confidence) / 2.0))
            if min(t1.confidence, t2.confidence) < 0.5:
                # Skip pairs dominated by low-confidence reports
                continue
            sim = max(similarity_floor, _text_similarity(t1.translated_text, t2.translated_text))
            weighted += w * sim
            total_w += w
    weighted_similarity = (weighted / total_w) if total_w > 0 else 0.0

    # Blend into overall consensus score
    consensus = 0.7 * weighted_similarity + 0.3 * diversity_factor
    return {
        "distinct_translators": distinct_sources,
        "weighted_similarity": round(weighted_similarity, 6),
        "confidence_buckets": buckets,
        "consensus_score": round(consensus, 6),
        "pass_threshold": consensus >= 0.80,
    }

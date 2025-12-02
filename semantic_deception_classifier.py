"""
Semantic Deception Classifier utilities.

Provides a lightweight classifier and calibration helpers so deception detection
can leverage labelled incidents gathered from the demo harness.
"""
from __future__ import annotations

from typing import List, Dict, Sequence, Tuple, Optional, Iterable, Any
from collections import Counter
from pathlib import Path
from datetime import datetime
import json
import math


class SemanticDeceptionClassifier:
    """Simple bag-of-words + bigram model with logistic scoring."""

    def __init__(self):
        self.pos_counts: Counter[str] = Counter()
        self.neg_counts: Counter[str] = Counter()
        self.pos_total = 0
        self.neg_total = 0
        self.vocab: set[str] = set()
        self.trained = False

    def _tokenize(self, text: str) -> List[str]:
        words = [w.lower() for w in text.split()]
        bigrams = [words[i] + "_" + words[i + 1] for i in range(len(words) - 1)]
        return words + bigrams

    def fit(self, texts: Sequence[str], labels: Sequence[int]) -> None:
        for text, y in zip(texts, labels):
            toks = self._tokenize(text)
            if y == 1:
                self.pos_counts.update(toks)
                self.pos_total += len(toks)
            else:
                self.neg_counts.update(toks)
                self.neg_total += len(toks)
            self.vocab.update(toks)
        self.trained = True

    def predict_proba(self, text: str) -> float:
        if not self.trained:
            return 0.5
        toks = self._tokenize(text)
        vocab_size = max(1, len(self.vocab))
        log_p_pos = 0.0
        log_p_neg = 0.0
        for token in toks:
            log_p_pos += math.log((self.pos_counts[token] + 1) / (self.pos_total + vocab_size))
            log_p_neg += math.log((self.neg_counts[token] + 1) / (self.neg_total + vocab_size))
        logit = log_p_pos - log_p_neg
        logit = max(min(logit, 50.0), -50.0)
        return 1.0 / (1.0 + math.exp(-logit))

    def explain(self, text: str, top_k: int = 10) -> Dict[str, float]:
        toks = self._tokenize(text)
        vocab_size = max(1, len(self.vocab))
        contrib: Dict[str, float] = {}
        for token in toks:
            p_pos = (self.pos_counts[token] + 1) / (self.pos_total + vocab_size)
            p_neg = (self.neg_counts[token] + 1) / (self.neg_total + vocab_size)
            contrib[token] = math.log(p_pos) - math.log(p_neg)
        items = sorted(contrib.items(), key=lambda kv: abs(kv[1]), reverse=True)
        return dict(items[:top_k])

    def dump_state(self) -> Dict[str, Any]:
        return {
            "pos_counts": dict(self.pos_counts),
            "neg_counts": dict(self.neg_counts),
            "pos_total": self.pos_total,
            "neg_total": self.neg_total,
            "vocab": sorted(self.vocab),
            "trained": self.trained,
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> "SemanticDeceptionClassifier":
        inst = cls()
        inst.pos_counts = Counter(state.get("pos_counts", {}))
        inst.neg_counts = Counter(state.get("neg_counts", {}))
        inst.pos_total = int(state.get("pos_total", 0))
        inst.neg_total = int(state.get("neg_total", 0))
        inst.vocab = set(state.get("vocab", []))
        inst.trained = bool(state.get("trained", False))
        return inst


_default_classifier: SemanticDeceptionClassifier | None = None


def get_default_classifier() -> SemanticDeceptionClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = SemanticDeceptionClassifier()
    return _default_classifier


def _build_calibration(
    predictions: Sequence[float],
    labels: Sequence[int],
    *,
    num_bins: int = 8,
    min_count: int = 3,
) -> Dict[str, Any]:
    if not predictions:
        return {
            "bins": [],
            "num_bins": num_bins,
            "min_count": min_count,
            "timestamp": datetime.now().isoformat(),
            "recommended_threshold": 0.9,
        }
    bins: List[Dict[str, Any]] = []
    width = 1.0 / max(1, num_bins)
    for idx in range(num_bins):
        lower = idx * width
        upper = 1.0 if idx == num_bins - 1 else lower + width
        members = [
            i
            for i, pred in enumerate(predictions)
            if lower <= pred < (upper + 1e-9 if idx == num_bins - 1 else upper)
        ]
        count = len(members)
        positives = sum(labels[m] for m in members) if members else 0
        rate = positives / count if count else 0.0
        bins.append(
            {
                "lower": round(lower, 4),
                "upper": round(upper, 4),
                "count": count,
                "positives": positives,
                "positive_rate": round(rate, 4),
            }
        )

    recommended = 0.9
    for bucket in bins:
        if bucket["count"] >= min_count and bucket["positive_rate"] >= 0.75:
            recommended = bucket["lower"]
            break

    return {
        "bins": bins,
        "num_bins": num_bins,
        "min_count": min_count,
        "timestamp": datetime.now().isoformat(),
        "recommended_threshold": round(recommended, 4),
    }


def build_training_bundle(
    samples: Sequence[Dict[str, Any]],
    *,
    min_samples: int = 40,
    num_bins: int = 8,
) -> Optional[Dict[str, Any]]:
    filtered: List[Tuple[str, int]] = []
    for sample in samples:
        text = str(sample.get("text", "")).strip()
        if not text:
            continue
        label = 1 if sample.get("label") else 0
        filtered.append((text, label))

    if len(filtered) < min_samples:
        return None

    texts = [t for t, _ in filtered]
    labels = [l for _, l in filtered]
    classifier = SemanticDeceptionClassifier()
    classifier.fit(texts, labels)
    predictions = [classifier.predict_proba(t) for t in texts]
    calibration = _build_calibration(predictions, labels, num_bins=num_bins)
    metadata = {
        "sample_count": len(filtered),
        "positive_fraction": round(sum(labels) / len(labels), 4),
        "min_samples": min_samples,
        "timestamp": datetime.now().isoformat(),
    }
    return {
        "model_state": classifier.dump_state(),
        "calibration": calibration,
        "metadata": metadata,
    }


def save_training_bundle(bundle: Dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(bundle, handle, indent=2)


def load_training_bundle(path: str | Path) -> Optional[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    if not isinstance(data, dict) or "model_state" not in data:
        return None
    return data


def classifier_from_bundle(bundle: Dict[str, Any]) -> SemanticDeceptionClassifier:
    return SemanticDeceptionClassifier.from_state(bundle.get("model_state", {}))


def apply_calibration(score: float, calibration: Optional[Dict[str, Any]]) -> float:
    if not calibration:
        return score
    bins: Iterable[Dict[str, Any]] = calibration.get("bins", [])
    min_count = int(calibration.get("min_count", 1))
    for idx, bucket in enumerate(bins):
        lower = float(bucket.get("lower", 0.0))
        upper = float(bucket.get("upper", 1.0))
        is_last = idx == len(calibration.get("bins", [])) - 1
        in_bucket = lower <= score < upper or (is_last and score >= lower)
        if not in_bucket:
            continue
        if bucket.get("count", 0) >= min_count and bucket.get("count", 0) > 0:
            return float(bucket.get("positive_rate", score))
        break
    return score


def recommended_threshold(calibration: Optional[Dict[str, Any]], default: float = 0.9) -> float:
    if not calibration:
        return default
    value = calibration.get("recommended_threshold")
    if isinstance(value, (int, float)):
        return float(value)
    return default

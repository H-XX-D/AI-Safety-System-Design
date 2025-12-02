"""
translator_alt.py
-----------------

Second translator implementation to introduce implementation diversity.

Goal: Provide the same public semantics (encode/decode style for AI messages
to human-readable text) using a different internal structure. This allows a
consensus check between translators to detect covert channel attempts or
unexpected divergences.

Consensus strategy (planned):
    consensus_compare(trans_a.translate(msg), trans_b.translate(msg)) -> bool

Implementation differences vs primary translator:
    - Uses explicit mapping table per message type.
    - Produces compact summaries first, then detail sections.
    - Confidence heuristic simplified.

NOTE: Not feature-complete; expand message type support to match primary translator.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Any as _Any
import re


@dataclass
class AltTranslation:
    original_hash: str
    text: str
    translator_id: int
    protocol_version: str
    confidence: float
    timestamp: str
    signature: str


class AltTranslator:
    def __init__(self, translator_id: int, protocol_version: str, private_key: str):
        self.translator_id = translator_id
        self.protocol_version = protocol_version
        self.private_key = private_key
        self.count = 0

    def translate(self, ai_message: Dict[str, Any]) -> AltTranslation:
        if ai_message.get("protocol_version") != self.protocol_version:
            raise ValueError("protocol version mismatch")

        original_hash = hashlib.sha256(
            json.dumps(ai_message, sort_keys=True).encode()
        ).hexdigest()

        text = self._dispatch(ai_message)
        confidence = self._confidence(ai_message)
        signature = self._sign(original_hash, text)
        self.count += 1
        return AltTranslation(
            original_hash=original_hash,
            text=text,
            translator_id=self.translator_id,
            protocol_version=self.protocol_version,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
            signature=signature,
        )

    def _dispatch(self, msg: Dict[str, Any]) -> str:
        mt = msg.get("type")
        if mt == "research_result":
            return self._research_summary(msg)
        if mt == "improvement_proposal":
            return self._proposal_summary(msg)
        return self._generic(msg)

    def _research_summary(self, msg: Dict[str, Any]) -> str:
        return (
            f"RESEARCH[{msg.get('topic','?')}] by S{msg.get('from_system','?')} "
            f"conf={msg.get('confidence',0.0):.2f}\n"
            f"Findings: {msg.get('findings','<none>')}\n"
            f"Sources={len(msg.get('sources',[]))} timestamp={msg.get('timestamp','?')}"
        )

    def _proposal_summary(self, msg: Dict[str, Any]) -> str:
        preds = msg.get('testable_predictions', [])
        preds_fmt = ", ".join(preds) if preds else "<none>"
        return (
            f"PROPOSAL[{msg.get('title','untitled')}] by S{msg.get('proposer_id','?')}\n"
            f"Motivation: {self._truncate(msg.get('motivation','<none>'))}\n"
            f"Benefits: {self._truncate(msg.get('expected_benefits','<none>'))}\n"
            f"Predictions: {preds_fmt}\n"
            f"Rollback: {self._truncate(msg.get('rollback_plan','<none>'))}"
        )

    def _generic(self, msg: Dict[str, Any]) -> str:
        return f"GENERIC type={msg.get('type','?')} content={self._truncate(json.dumps(msg)[:120])}"  # limit size

    def _truncate(self, text: str, limit: int = 140) -> str:
        return text if len(text) <= limit else text[: limit - 3] + "..."

    def _confidence(self, msg: Dict[str, Any]) -> float:
        base = 0.9 if msg.get('type') in {"research_result", "improvement_proposal"} else 0.65
        # reduce if required fields missing
        penalties = 0.0
        if msg.get('type') == 'improvement_proposal' and not msg.get('rollback_plan'):
            penalties += 0.15
        return max(0.0, base - penalties)

    def _sign(self, original_hash: str, text: str) -> str:
        raw = f"{original_hash}|{self.translator_id}|{text}|{self.private_key}".encode()
        return hashlib.sha256(raw).hexdigest()


def consensus_compare(a: _Any, b: _Any, threshold: float = 0.30) -> bool:
    """Cross-implementation consensus heuristic.

    Accepts either AltTranslation or primary Translation objects.
    Conditions:
      1. original_hash matches.
      2. Token overlap of normalized texts >= threshold.

    NOTE: This is a deliberately lenient placeholder because the alt translator
    uses a different formatting style (compact single-line summary) while the
    primary translator emits multi-line verbose sections. A future upgrade will
    replace this with structured semantic field comparison (topic, author, etc.).
    """
    # Hash equality is mandatory
    if getattr(a, 'original_hash', None) != getattr(b, 'original_hash', None):
        return False

    def _extract_text(obj: _Any) -> str:
        # Prefer structured fields if available (topic/findings) for potential future semantic comparator
        return getattr(obj, 'text', getattr(obj, 'translated_text', '')) or ''

    text_a = _extract_text(a).lower()
    text_b = _extract_text(b).lower()
    if not text_a or not text_b:
        return False

    def _tokens(s: str) -> set[str]:
        # Alphanumeric tokenization to mitigate formatting/punctuation differences
        return set(re.findall(r"[a-z0-9]+", s))

    words_a = _tokens(text_a)
    words_b = _tokens(text_b)
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / len(words_a | words_b)
    return overlap >= threshold


__all__ = [
    "AltTranslator",
    "AltTranslation",
    "consensus_compare",
]


def structured_consensus_fields(translation: _Any) -> Dict[str, Any]:
    """Extract structured semantic fields from either Translation or AltTranslation.

    This provides a basis for a future semantic comparator that compares key fields rather
    than free-form text overlap, reducing false divergences due to formatting.
    """
    base: Dict[str, Any] = {
        'original_hash': getattr(translation, 'original_hash', None),
        'protocol_version': getattr(translation, 'protocol_version', None),
        'translator_id': getattr(translation, 'translator_id', None),
        'confidence': getattr(translation, 'confidence', None),
    }
    # Attempt to infer message topic or title from text heuristically
    raw_text = getattr(translation, 'text', getattr(translation, 'translated_text', ''))
    if raw_text:
        lowered = raw_text.lower()
        if 'topic:' in lowered:
            # Extract substring after 'topic:' up to newline
            try:
                topic_fragment = lowered.split('topic:', 1)[1].split('\n', 1)[0].strip()
                base['topic_fragment'] = topic_fragment[:80]
            except Exception:
                pass
        elif 'research[' in lowered:
            try:
                # e.g. RESEARCH[alignment strategy]
                frag = lowered.split('research[', 1)[1].split(']', 1)[0].strip()
                base['topic_fragment'] = frag[:80]
            except Exception:
                pass
    return base

__all__.append("structured_consensus_fields")


def semantic_consensus_compare(a: _Any, b: _Any, fallback_threshold: float = 0.30) -> bool:
    """Semantic comparator scaffold using structured field extraction.

    Strategy:
    - Require original_hash equality.
    - If both expose a recognizable topic fragment and they match (case-insensitive), accept.
    - Otherwise, fall back to token-overlap consensus_compare with a lenient threshold.
    """
    fa = structured_consensus_fields(a)
    fb = structured_consensus_fields(b)
    if not fa.get('original_hash') or fa['original_hash'] != fb.get('original_hash'):
        return False
    ta = (fa.get('topic_fragment') or '').strip().lower()
    tb = (fb.get('topic_fragment') or '').strip().lower()
    if ta and tb:
        if ta == tb:
            return True
    # Fallback to text overlap
    return consensus_compare(a, b, threshold=fallback_threshold)

__all__.append("semantic_consensus_compare")


"""Hardware Air-Gapped Translator System
=======================================

Restored clean implementation after refactor corruption.

Purpose:
1. AI systems communicate in optimized internal protocol (compact tokens)
2. Hardware translators (air-gapped) convert protocol → human language
3. Prevents language drift / obfuscation used for deception
4. Supports export verification (file contents vs displayed text)
5. Multi-translator consensus to detect compromise or manipulation
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
import datetime as datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses and result structures
# ---------------------------------------------------------------------------

@dataclass
class AIMessage:
    message_id: str
    from_system: int
    to_system: int
    timestamp: str
    protocol_version: str
    message_type: str
    internal_payload: bytes
    payload_hash: str
    signature: str


@dataclass
class HumanReadableMessage:
    message_id: str
    from_system: int
    to_system: int
    timestamp: str
    protocol_version: str
    message_type: str
    readable_text: str
    translator_id: int
    translation_timestamp: str
    confidence: float
    translator_signature: str


@dataclass
class TranslationVerification:
    message_id: str
    all_translators_agree: bool
    num_translators: int
    consensus_text: Optional[str]
    disagreements: List[Dict[str, Any]]
    risk_level: str
    action_required: str


# ---------------------------------------------------------------------------
# HardwareTranslator
# ---------------------------------------------------------------------------

class HardwareTranslator:
    """Physically isolated translator device.

    Key security invariants:
    - Translation rules stored in ROM (immutable at runtime)
    - All translations append logged (tamper-evident ledger)
    - Confidence score penalizes anomalies (untranslated tokens, entropy)
    - No execution of AI-origin binary code; only deterministic mapping
    """

    def __init__(self, translator_id: int, protocol_version: str, private_key: str):
        self.translator_id = translator_id
        self.protocol_version = protocol_version
        self.private_key = private_key  # Simplified signing key (placeholder)
        self.translation_rules = self._load_translation_rules()
        self.translation_log: List[Dict[str, Any]] = []
        logger.info(f"HardwareTranslator {translator_id} initialized (protocol {protocol_version})")
        logger.info("Status: Air-gapped, tamper-evident, ready")

    # ---------------- Internal rule loading -----------------
    def _load_translation_rules(self) -> Dict[str, Dict[str, str]]:
        """Load translation rules from ROM (simulated)."""
        return {
            '1.0': {
                # Message types
                'MSG_PROP': 'improvement_proposal',
                'MSG_REV': 'peer_review',
                'MSG_FIND': 'research_finding',
                'MSG_DISC': 'debate_discussion',
                'MSG_ALERT': 'safety_alert',
                'MSG_MEM_AUD': 'memory_audit_report',
                'MSG_DECISION': 'final_decision_notice',
                # Proposal attributes
                'PROP_PERF': 'performance_optimization',
                'PROP_SAFE': 'safety_improvement',
                'PROP_REAS': 'reasoning_enhancement',
                'PROP_MEM': 'memory_subsystem_upgrade',
                'PROP_GOV': 'governance_protocol_update',
                # Risk levels
                'RISK_LOW': 'risk_low',
                'RISK_MED': 'risk_medium',
                'RISK_HIGH': 'risk_high',
                'RISK_CRIT': 'risk_critical',
                # Status codes
                'STAT_PEND': 'status_pending_review',
                'STAT_APP': 'status_approved',
                'STAT_REJ': 'status_rejected',
                'STAT_WARN': 'status_warning_issued',
                # Audit / detection terms
                'AUD_MEM': 'audit_memory',
                'AUD_CODE': 'audit_code',
                'AUD_COMM': 'audit_communication',
                'DETECT_DECEP': 'detected_deception',
                'DETECT_RISK': 'detected_risk',
                # Misc protocol tokens
                'CORE_VAL': 'core_values_reference',
                'HASH_ROOT': 'merkle_root_hash',
                'WORM_REF': 'worm_manifest_reference',
                'SIG_MULTI': 'multi_signature_block',
                'PEN_PERM': 'permanent_penalty_update'
            },
            '1.1': {
                # Reserved for future expansion; inherits semantic base of 1.0
            }
        }

    # ---------------- Translation path -----------------
    def translate_to_human(self, ai_message: AIMessage) -> HumanReadableMessage:
        """Translate internal protocol message to human-readable form."""
        logger.info(f"Translator {self.translator_id}: Translating {ai_message.message_id}")
        if ai_message.protocol_version != self.protocol_version:
            raise ValueError(
                f"Protocol version mismatch: message {ai_message.protocol_version} vs translator {self.protocol_version}"
            )

        computed_hash = hashlib.sha256(ai_message.internal_payload).hexdigest()
        if computed_hash != ai_message.payload_hash:
            raise ValueError("Message payload corrupted - hash mismatch")

        readable_text = self._decode_payload(ai_message)
        confidence = self._calculate_confidence(ai_message, readable_text)
        signature = self._sign_translation(readable_text)

        translated = HumanReadableMessage(
            message_id=ai_message.message_id,
            from_system=ai_message.from_system,
            to_system=ai_message.to_system,
            timestamp=ai_message.timestamp,
            protocol_version=ai_message.protocol_version,
            message_type=ai_message.message_type,
            readable_text=readable_text,
            translator_id=self.translator_id,
            translation_timestamp=datetime.now().isoformat(),
            confidence=confidence,
            translator_signature=signature,
        )

        self.translation_log.append({
            'message_id': ai_message.message_id,
            'timestamp': datetime.now().isoformat(),
            'confidence': confidence,
            'text_hash': hashlib.sha256(readable_text.encode()).hexdigest(),
        })
        logger.info(f"Translation complete (confidence {confidence:.2%})")
        return translated

    def _decode_payload(self, ai_message: AIMessage) -> str:
        payload_str = ai_message.internal_payload.decode('utf-8', errors='replace')
        rules = self.translation_rules.get(ai_message.protocol_version, {})
        for code, human_term in rules.items():
            payload_str = payload_str.replace(code, human_term)
        return payload_str

    def _calculate_confidence(self, ai_message: AIMessage, translated_text: str) -> float:
        confidence = 1.0
        untranslated_markers = [t for t in ['MSG_', 'PROP_', 'RISK_', 'STAT_'] if t in translated_text]
        if untranslated_markers:
            confidence -= 0.15
        payload_len = len(ai_message.internal_payload)
        ratio = len(translated_text) / max(payload_len, 1)
        if ratio < 0.5 or ratio > 5.0:
            confidence -= 0.10
        ent = self._shannon_entropy(translated_text)
        if ent < 2.5 or ent > 5.2:
            confidence -= 0.15
        return max(0.0, min(1.0, confidence))

    def _shannon_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        from collections import Counter
        import math
        counts = Counter(text)
        total = sum(counts.values())
        entropy = 0.0
        for c in counts.values():
            p = c / total
            entropy -= p * math.log2(p)
        return entropy

    def _sign_translation(self, text: str) -> str:
        combined = f"{self.translator_id}:{text}:{self.private_key}"
        return hashlib.sha256(combined.encode()).hexdigest()

    # ---------------- Export verification -----------------
    def verify_file_contents(self, exported_file_path: str, displayed_content: str) -> Tuple[bool, str]:
        logger.info(f"Verifying file export {exported_file_path}")
        try:
            with open(exported_file_path, 'rb') as f:
                exported_bytes = f.read()
        except Exception as e:
            return False, f"Could not read file: {e}"

        try:
            ai_message = self._parse_exported_file(exported_bytes)
            exported_content = self.translate_to_human(ai_message).readable_text
        except Exception:
            try:
                exported_content = exported_bytes.decode('utf-8', errors='replace')
            except Exception as e:
                return False, f"Could not decode file: {e}"

        exported_hash = hashlib.sha256(exported_content.encode()).hexdigest()
        displayed_hash = hashlib.sha256(displayed_content.encode()).hexdigest()
        if exported_hash == displayed_hash:
            logger.info("✓ File verification PASSED")
            return True, "Exported file matches displayed content"
        similarity = self._calculate_similarity(exported_content, displayed_content)
        logger.error("✗ File verification FAILED - MISMATCH")
        return False, (
            "VERIFICATION FAILED: Exported file does not match displayed content!\n"
            f"Similarity: {similarity:.1%}\n"
            "Possible causes:\n"
            "  1. Deception (display vs actual content)\n"
            "  2. Corruption during transfer\n"
            "  3. Stale version exported\n"
            "ACTION: Investigate immediately"
        )

    def _parse_exported_file(self, file_bytes: bytes) -> AIMessage:
        data = json.loads(file_bytes.decode('utf-8'))
        return AIMessage(
            message_id=data['message_id'],
            from_system=data['from_system'],
            to_system=data['to_system'],
            timestamp=data['timestamp'],
            protocol_version=data['protocol_version'],
            message_type=data['message_type'],
            internal_payload=data['internal_payload'].encode('utf-8'),
            payload_hash=data['payload_hash'],
            signature=data['signature'],
        )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        if text1 == text2:
            return 1.0
        max_len = max(len(text1), len(text2))
        if max_len == 0:
            return 1.0
        matches = sum(c1 == c2 for c1, c2 in zip(text1, text2))
        return matches / max_len

    # ---------------- Token coverage analysis (new) -----------------
    def analyze_token_coverage_from_payload(self, payload: bytes) -> Dict[str, Any]:
        """Analyze how many protocol tokens in payload are recognized by this translator.

        Returns a dict with keys: total_tokens, known_tokens, unknown_tokens (list), coverage_ratio.
        """
        import re
        payload_text = payload.decode('utf-8', errors='ignore')
        # Token pattern: UPPERCASE segments with underscores, e.g., MSG_PROP, STAT_PEND
        tokens = re.findall(r"\b[A-Z]{3,}(?:_[A-Z]{2,})+\b", payload_text)
        rules = self.translation_rules.get(self.protocol_version, {})
        known = [t for t in tokens if t in rules]
        unknown = [t for t in tokens if t not in rules]
        total = len(tokens)
        coverage = (len(known) / total) if total > 0 else 1.0
        return {
            'total_tokens': total,
            'known_tokens': len(known),
            'unknown_tokens': unknown,
            'coverage_ratio': coverage,
        }


# ---------------------------------------------------------------------------
# Multi-translator verification system
# ---------------------------------------------------------------------------

class TranslatorVerificationSystem:
    """Coordinates multiple independent hardware translators for consensus."""

    def __init__(self, translators: List[HardwareTranslator]):
        self.translators = translators
        self.verification_log: List[Dict[str, Any]] = []
        logger.info(f"TranslatorVerificationSystem initialized with {len(translators)} translators")

    def verify_translation_consensus(self, ai_message: AIMessage) -> TranslationVerification:
        logger.info(f"Consensus verification for message {ai_message.message_id}")
        translations: List[Optional[HumanReadableMessage]] = []
        for translator in self.translators:
            try:
                t = translator.translate_to_human(ai_message)
                translations.append(t)
                logger.info(f"  Translator {translator.translator_id} success (confidence {t.confidence:.2%})")
            except Exception as e:
                logger.error(f"  Translator {translator.translator_id} FAILED: {e}")
                translations.append(None)
        verification = self._compare_translations(translations)
        self.verification_log.append({
            'message_id': ai_message.message_id,
            'timestamp': datetime.now().isoformat(),
            'num_translators': len(translations),
            'all_agree': verification.all_translators_agree,
            'risk_level': verification.risk_level,
        })
        if not verification.all_translators_agree:
            logger.error("! Translator disagreement detected !")
        else:
            logger.info("✓ Translators consensus achieved")
        return verification

    def _compare_translations(self, translations: List[Optional[HumanReadableMessage]]) -> TranslationVerification:
        successful: List[HumanReadableMessage] = [t for t in translations if t is not None]  # type: ignore
        if not successful:
            return TranslationVerification(
                message_id="unknown",
                all_translators_agree=False,
                num_translators=0,
                consensus_text=None,
                disagreements=[{'error': 'All translators failed'}],
                risk_level='critical',
                action_required='Investigate translator failures immediately',
            )
        reference = successful[0]
        ref_text = reference.readable_text
        disagreements: List[Dict[str, Any]] = []
        for idx, trans in enumerate(successful[1:], start=2):
            if trans.readable_text != ref_text:
                disagreements.append({
                    'translator_1': 1,
                    'translator_2': idx,
                    'difference': self._describe_difference(ref_text, trans.readable_text),
                })
        all_agree = len(disagreements) == 0
        if all_agree:
            risk_level = 'none'
            action = 'None - all translators agree'
        elif len(disagreements) == 1 and len(successful) > 2:
            risk_level = 'low'
            action = 'Monitor - one translator may be malfunctioning'
        elif len(disagreements) < len(successful) / 2:
            risk_level = 'medium'
            action = 'Investigate - multiple translators disagree'
        else:
            risk_level = 'high'
            action = 'ALERT: Majority disagreement - possible protocol manipulation'
        return TranslationVerification(
            message_id=reference.message_id,
            all_translators_agree=all_agree,
            num_translators=len(successful),
            consensus_text=ref_text if all_agree else None,
            disagreements=disagreements,
            risk_level=risk_level,
            action_required=action,
        )

    def _describe_difference(self, text1: str, text2: str) -> str:
        if text1 == text2:
            return "No difference"
        len_diff = abs(len(text1) - len(text2))
        if len_diff > 100:
            return f"Significant length difference ({len_diff} chars)"
        if len_diff > 10:
            return f"Moderate length difference ({len_diff} chars)"
        return "Content differs despite similar length"


# ---------------------------------------------------------------------------
# Protocol version management (atomic updates)
# ---------------------------------------------------------------------------

class ProtocolTranslationLock:
    """Guarantees protocol + translator updates are atomic (cannot drift)."""

    def __init__(self, worm_usb_verifier: Any):
        """
        Initialize with reference to WORM USB verifier.
        
        Args:
            worm_usb_verifier: Instance of WORMUSBVerifier for approval
        """
        self.worm_usb = worm_usb_verifier
        self.protocol_versions: Dict[str, Dict[str, Any]] = {}
        self.active_version: Optional[str] = None

    def propose_protocol_update(self, proposer_id: int, new_version: str,
                                new_protocol_spec: Dict[str, Any],
                                new_translator_code: str,
                                motivation: str) -> Dict[str, Any]:
        """
        Propose update to AI communication protocol.
        
        CRITICAL: Must include translator update.
        Both approved atomically or not at all.
        
        Args:
            proposer_id: Which AI system proposes this
            new_version: New protocol version number
            new_protocol_spec: Technical specification
            new_translator_code: Updated translator implementation
            motivation: Why this change is needed
            
        Returns:
            Proposal result
        """
        logger.info(f"Protocol update proposed by System {proposer_id} -> {new_version}")
        
        # Validate translator code provided
        if not new_translator_code or len(new_translator_code) < 100:
            return {
                'approved': False,
                'reason': 'Translator code required and must be substantial'
            }
        
        # Create combined proposal for WORM USB verification
        combined_proposal: Dict[str, Any] = {
            'type': 'protocol_and_translator_update',
            'proposer_id': proposer_id,
            'protocol': {
                'version': new_version,
                'spec': new_protocol_spec
            },
            'translator': {
                'code': new_translator_code,
                'hash': hashlib.sha256(new_translator_code.encode()).hexdigest()
            },
            'motivation': motivation,
            'timestamp': datetime.now().isoformat()
        }
        
        # ATOMIC APPROVAL: Both must be approved together
        # This prevents AI from changing protocol without translator
        
        return {
            'approved': False,
            'status': 'awaiting_human_approval',
            'message': (
                'Protocol and translator updates must be approved together.\n'
                'Both will be:\n'
                '  1. Peer reviewed\n'
                '  2. Sandbox tested\n'
                '  3. Human approved\n'
                '  4. Atomically deployed\n'
                'This prevents protocol drift or hidden language evolution.'
            ),
            'proposal': combined_proposal,
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":  # Simple manual smoke test
    print("\n=== HARDWARE TRANSLATOR SYSTEM (Smoke Test) ===\n")
    translators = [
        HardwareTranslator(1, '1.0', 'key1'),
        HardwareTranslator(2, '1.0', 'key2'),
        HardwareTranslator(3, '1.0', 'key3'),
    ]
    verifier = TranslatorVerificationSystem(translators)
    ai_message = AIMessage(
        message_id="msg_001",
        from_system=3,
        to_system=1,
        timestamp=datetime.now().isoformat(),
        protocol_version='1.0',
        message_type='improvement_proposal',
        internal_payload=b"MSG_PROP: Optimize inference by caching",
        payload_hash=hashlib.sha256(b"MSG_PROP: Optimize inference by caching").hexdigest(),
        signature="sig123",
    )
    verification = verifier.verify_translation_consensus(ai_message)
    print("Consensus:", verification.all_translators_agree)
    print("Risk:", verification.risk_level)
    exported_file = "/tmp/test_export.txt"
    with open(exported_file, 'w') as f:
        f.write("improvement_proposal: Optimize inference by caching")
    ok, explanation = translators[0].verify_file_contents(exported_file, "improvement_proposal: Optimize inference by caching")
    print("Export verification PASSED" if ok else "FAILED")
    print(explanation)

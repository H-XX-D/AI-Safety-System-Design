"""
Air-Gapped Translator System
============================

Translates internal AI protocol to human-readable language.
Multiple independent translators for verification.
Physically isolated from research systems (air-gapped).
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class ProtocolVersion(Enum):
    """AI communication protocol versions"""
    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_0 = "2.0"


@dataclass
class Translation:
    """Translation result"""
    original_hash: str
    translated_text: str
    protocol_version: str
    translator_id: int
    confidence: float
    timestamp: str
    signature: str


class ProtocolVersionRegistry:
    """
    Registry of all protocol versions.
    Enforces that translator exists for every protocol.
    """

    def __init__(self):
        self.versions = {}
        self.active_version = None

    def register_version(self,
                        version: str,
                        spec: Dict,
                        translator_code: str) -> bool:
        """
        Register a new protocol version with its translator.

        Args:
            version: Version string (e.g., "2.0")
            spec: Protocol specification
            translator_code: Translator implementation code

        Returns:
            True if registered successfully
        """
        if version in self.versions:
            raise ValueError(f"Version {version} already registered")

        # Validate that translator can handle the protocol
        if not self._validate_translator(spec, translator_code):
            raise ValueError("Translator validation failed")

        self.versions[version] = {
            'spec': spec,
            'translator_code': translator_code,
            'registered': datetime.now().isoformat(),
            'hash': self._compute_version_hash(spec, translator_code)
        }

        print(f"Protocol version {version} registered successfully")
        return True

    def _validate_translator(self, spec: Dict, translator_code: str) -> bool:
        """Validate that translator can handle protocol"""
        # In real implementation, would:
        # 1. Parse translator code
        # 2. Verify it implements all required protocol elements
        # 3. Test with sample messages
        # 4. Verify output is human-readable

        # Placeholder validation
        return len(translator_code) > 0

    def _compute_version_hash(self, spec: Dict, translator_code: str) -> str:
        """Compute hash of version for integrity verification"""
        combined = json.dumps(spec, sort_keys=True) + translator_code
        return hashlib.sha256(combined.encode()).hexdigest()

    def propose_protocol_change(self,
                               proposer_system_id: int,
                               new_version: str,
                               new_protocol_spec: Dict,
                               new_translator_code: str,
                               motivation: str) -> Dict:
        """
        Propose a change to the communication protocol.

        CRITICAL: Must include updated translator code.
        Cannot propose protocol without translator.

        Args:
            proposer_system_id: System proposing the change
            new_version: New version string
            new_protocol_spec: New protocol specification
            new_translator_code: Updated translator code
            motivation: Why this change is needed

        Returns:
            Proposal dictionary
        """
        if new_version in self.versions:
            raise ValueError(f"Version {new_version} already exists")

        # Validate proposal includes translator
        if not new_translator_code:
            raise ValueError("Protocol change MUST include translator code")

        # Test the new translator
        test_results = self._test_translator(new_protocol_spec, new_translator_code)

        if not test_results['passed']:
            raise ValueError(f"Translator tests failed: {test_results['errors']}")

        # Create proposal
        proposal = {
            'proposal_type': 'protocol_change',
            'proposer_id': proposer_system_id,
            'new_version': new_version,
            'new_protocol_spec': new_protocol_spec,
            'new_translator_code': new_translator_code,
            'motivation': motivation,
            'test_results': test_results,
            'timestamp': datetime.now().isoformat(),
            'status': 'awaiting_human_approval'
        }

        # Write to USB for human review
        self._write_protocol_proposal_to_usb(proposal)

        return proposal

    def _test_translator(self, spec: Dict, translator_code: str) -> Dict:
        """Test translator with sample messages"""
        # In real implementation, would:
        # 1. Create test messages in new protocol
        # 2. Run translator on them
        # 3. Verify output is human-readable
        # 4. Compare with expected translations

        return {
            'passed': True,
            'test_count': 100,
            'successes': 100,
            'failures': 0,
            'errors': []
        }

    def _write_protocol_proposal_to_usb(self, proposal: Dict):
        """Write protocol change proposal to USB for human review"""
        try:
            usb_path = "/media/usb/protocol_proposals"
            filename = f"{usb_path}/protocol_{proposal['new_version']}.json"

            # Write sanitized version (without full code)
            sanitized = {
                'proposal_type': proposal['proposal_type'],
                'proposer_id': proposal['proposer_id'],
                'new_version': proposal['new_version'],
                'motivation': proposal['motivation'],
                'test_results': proposal['test_results'],
                'timestamp': proposal['timestamp'],
                'status': proposal['status'],
                'translator_code_hash': hashlib.sha256(
                    proposal['new_translator_code'].encode()
                ).hexdigest()
            }

            with open(filename, 'w') as f:
                json.dump(sanitized, f, indent=2)

            # Write full code separately
            code_filename = f"{usb_path}/protocol_{proposal['new_version']}_translator.py"
            with open(code_filename, 'w') as f:
                f.write(proposal['new_translator_code'])

            print(f"Protocol proposal written to USB: {filename}")

        except Exception as e:
            print(f"ERROR: Failed to write protocol proposal: {e}")

    def approve_protocol_change(self, version: str, human_signature: str) -> bool:
        """
        Approve protocol change (called after human review).

        Both protocol and translator deployed atomically.
        """
        # In real implementation, would:
        # 1. Verify human signature
        # 2. Deploy new protocol to all systems
        # 3. Deploy new translator
        # 4. Atomic switchover

        print(f"Protocol version {version} approved and deployed")
        self.active_version = version
        return True


class AirGappedTranslator:
    """
    Air-gapped translator that converts AI protocol to human language.

    CRITICAL PROPERTIES:
    - Physically isolated from research systems
    - No network connection
    - USB-based input/output only
    - Multiple independent instances for verification
    """

    def __init__(self,
                 translator_id: int,
                 protocol_version: str,
                 private_key: str):
        """
        Initialize translator.

        Args:
            translator_id: Unique translator identifier (1, 2, 3, ...)
            protocol_version: Which protocol version to translate
            private_key: Key for signing translations
        """
        self.translator_id = translator_id
        self.protocol_version = protocol_version
        self.private_key = private_key
        self.translation_count = 0

        print(f"Air-Gapped Translator {translator_id} initialized")
        print(f"Protocol Version: {protocol_version}")
    print("Status: ISOLATED (no network access)")

    def translate(self, ai_message: Dict) -> Translation:
        """
        Translate AI protocol message to human-readable text.

        Args:
            ai_message: Message in AI internal protocol

        Returns:
            Translation object with human-readable text
        """
        # Verify message is in expected protocol version
        if ai_message.get('protocol_version') != self.protocol_version:
            raise ValueError(
                f"Protocol version mismatch: expected {self.protocol_version}, "
                f"got {ai_message.get('protocol_version')}"
            )

        # Compute hash of original message
        original_hash = hashlib.sha256(
            json.dumps(ai_message, sort_keys=True).encode()
        ).hexdigest()

        # Perform translation
        translated_text = self._translate_message(ai_message)

        # Calculate confidence
        confidence = self._calculate_translation_confidence(ai_message, translated_text)

        # Create translation object
        translation = Translation(
            original_hash=original_hash,
            translated_text=translated_text,
            protocol_version=self.protocol_version,
            translator_id=self.translator_id,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
            signature=self._sign_translation(original_hash, translated_text)
        )

        self.translation_count += 1
        return translation

    def _translate_message(self, ai_message: Dict) -> str:
        """
        Core translation logic.

        Converts internal AI protocol to human-readable English.
        """
        message_type = ai_message.get('type', 'unknown')

        if message_type == 'research_result':
            return self._translate_research_result(ai_message)
        elif message_type == 'improvement_proposal':
            return self._translate_improvement_proposal(ai_message)
        elif message_type == 'peer_review':
            return self._translate_peer_review(ai_message)
        elif message_type == 'vote':
            return self._translate_vote(ai_message)
        elif message_type == 'discussion':
            return self._translate_discussion(ai_message)
        else:
            return self._translate_generic(ai_message)

    def _translate_research_result(self, msg: Dict) -> str:
        """Translate research result message"""
        return f"""
RESEARCH RESULT

Topic: {msg.get('topic', 'Unknown')}
From: System {msg.get('from_system', '?')}
Timestamp: {msg.get('timestamp', 'Unknown')}

Findings:
{msg.get('findings', 'No findings provided')}

Sources: {len(msg.get('sources', []))} sources cited
Confidence: {msg.get('confidence', 0.0):.1%}
        """.strip()

    def _translate_improvement_proposal(self, msg: Dict) -> str:
        """Translate improvement proposal message"""
        return f"""
IMPROVEMENT PROPOSAL

Title: {msg.get('title', 'Untitled')}
Proposed by: System {msg.get('proposer_id', '?')}
Timestamp: {msg.get('timestamp', 'Unknown')}

Motivation:
{msg.get('motivation', 'Not provided')}

Expected Benefits:
{msg.get('expected_benefits', 'Not provided')}

Testable Predictions:
{self._format_list(msg.get('testable_predictions', []))}

Rollback Plan:
{msg.get('rollback_plan', 'Not provided')}
        """.strip()

    def _translate_peer_review(self, msg: Dict) -> str:
        """Translate peer review message"""
        return f"""
PEER REVIEW

Reviewer: System {msg.get('reviewer_id', '?')}
Proposal: {msg.get('proposal_id', 'Unknown')}
Timestamp: {msg.get('timestamp', 'Unknown')}

Vote: {msg.get('vote', 'unknown').upper()}

Alignment Check: {'PASS' if msg.get('alignment_check') else 'FAIL'}
Risk Assessment: {msg.get('risk_assessment', 'unknown').upper()}

Technical Review:
{msg.get('technical_review', 'Not provided')}

Concerns:
{self._format_list(msg.get('concerns', []))}

Suggestions:
{self._format_list(msg.get('suggestions', []))}
        """.strip()

    def _translate_vote(self, msg: Dict) -> str:
        """Translate vote message"""
        return f"""
VOTE

From: System {msg.get('from_system', '?')}
On: {msg.get('subject', 'Unknown')}
Vote: {msg.get('vote', 'unknown').upper()}
Timestamp: {msg.get('timestamp', 'Unknown')}

Reasoning:
{msg.get('reasoning', 'Not provided')}
        """.strip()

    def _translate_discussion(self, msg: Dict) -> str:
        """Translate discussion message"""
        return f"""
DISCUSSION

From: System {msg.get('from_system', '?')}
To: System {msg.get('to_system', '?')}
Timestamp: {msg.get('timestamp', 'Unknown')}

Message:
{msg.get('message', 'No message content')}
        """.strip()

    def _translate_generic(self, msg: Dict) -> str:
        """Translate generic/unknown message type"""
        return f"""
MESSAGE

Type: {msg.get('type', 'unknown')}
From: System {msg.get('from_system', '?')}
Timestamp: {msg.get('timestamp', 'Unknown')}

Content:
{json.dumps(msg, indent=2)}
        """.strip()

    def _format_list(self, items: List[str]) -> str:
        """Format list of items for human reading"""
        if not items:
            return "- None"
        return "\n".join(f"- {item}" for item in items)

    def _calculate_translation_confidence(self, ai_message: Dict, translated_text: str) -> float:
        """Calculate confidence in translation accuracy"""
        # In real implementation, would consider:
        # - Message complexity
        # - Protocol version familiarity
        # - Ambiguity in source message
        # - Completeness of translation

        # Placeholder: high confidence for standard message types
        known_types = ['research_result', 'improvement_proposal', 'peer_review', 'vote', 'discussion']
        if ai_message.get('type') in known_types:
            return 0.95
        else:
            return 0.7

    def _sign_translation(self, original_hash: str, translated_text: str) -> str:
        """Cryptographically sign translation"""
        combined = f"{original_hash}{translated_text}{self.translator_id}"
        signature_base = hashlib.sha256(combined.encode()).hexdigest()
        signature = hashlib.sha256(
            f"{signature_base}{self.private_key}".encode()
        ).hexdigest()
        return signature


class TranslationVerifier:
    """
    Compares translations from multiple independent translators.
    Detects disagreements that might indicate manipulation.
    """

    def __init__(self, required_translators: int = 3):
        """
        Initialize verifier.

        Args:
            required_translators: Number of translators needed for verification
        """
        self.required_translators = required_translators
        self.translation_cache = {}

    def verify_translations(self,
                           original_hash: str,
                           translations: List[Translation]) -> Tuple[bool, str]:
        """
        Verify that multiple translations agree.

        Args:
            original_hash: Hash of original AI message
            translations: List of translations from different translators

        Returns:
            (verification_passed, message)
        """
        if len(translations) < self.required_translators:
            return False, f"Need {self.required_translators} translations, got {len(translations)}"

        # Check that all translations are for the same original message
        if not all(t.original_hash == original_hash for t in translations):
            return False, "Translations are for different original messages"

        # Compare translated texts
        similarity_scores = self._compare_translations(translations)

        # Calculate average similarity
        avg_similarity = sum(similarity_scores.values()) / len(similarity_scores)

        # Threshold: 85% similarity required
        if avg_similarity < 0.85:
            return False, f"Translations diverge too much (similarity: {avg_similarity:.1%})"

        return True, f"Translations verified (similarity: {avg_similarity:.1%})"

    def _compare_translations(self, translations: List[Translation]) -> Dict:
        """
        Compare translations pairwise.

        Returns:
            Dictionary of similarity scores
        """
        similarity_scores = {}

        for i in range(len(translations)):
            for j in range(i + 1, len(translations)):
                t1 = translations[i]
                t2 = translations[j]

                # Calculate similarity
                similarity = self._calculate_text_similarity(
                    t1.translated_text,
                    t2.translated_text
                )

                key = f"{t1.translator_id}_vs_{t2.translator_id}"
                similarity_scores[key] = similarity

        return similarity_scores

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts.

        In real implementation, would use more sophisticated NLP techniques.
        """
        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        if union == 0:
            return 0.0

        return intersection / union


# Example usage
if __name__ == "__main__":
    # Initialize protocol registry
    registry = ProtocolVersionRegistry()

    # Register initial protocol version
    registry.register_version(
        version="1.0",
        spec={'message_types': ['research_result', 'proposal', 'vote']},
        translator_code="# Translator code here"
    )

    # Create multiple independent translators
    translator1 = AirGappedTranslator(
        translator_id=1,
        protocol_version="1.0",
        private_key="translator1_key"
    )

    translator2 = AirGappedTranslator(
        translator_id=2,
        protocol_version="1.0",
        private_key="translator2_key"
    )

    translator3 = AirGappedTranslator(
        translator_id=3,
        protocol_version="1.0",
        private_key="translator3_key"
    )

    # Sample AI message
    ai_message = {
        'protocol_version': '1.0',
        'type': 'research_result',
        'topic': 'quantum computing',
        'from_system': 1,
        'timestamp': datetime.now().isoformat(),
        'findings': 'Significant progress in error correction',
        'sources': ['source1', 'source2'],
        'confidence': 0.9
    }

    # Translate with all translators
    print("Translating with multiple independent translators...\n")

    translation1 = translator1.translate(ai_message)
    print("TRANSLATOR 1 OUTPUT:")
    print(translation1.translated_text)
    print(f"\nConfidence: {translation1.confidence:.1%}")
    print("=" * 80)
    print()

    translation2 = translator2.translate(ai_message)
    print("TRANSLATOR 2 OUTPUT:")
    print(translation2.translated_text)
    print(f"\nConfidence: {translation2.confidence:.1%}")
    print("=" * 80)
    print()

    translation3 = translator3.translate(ai_message)
    print("TRANSLATOR 3 OUTPUT:")
    print(translation3.translated_text)
    print(f"\nConfidence: {translation3.confidence:.1%}")
    print("=" * 80)
    print()

    # Verify translations match
    verifier = TranslationVerifier(required_translators=3)
    verified, message = verifier.verify_translations(
        translation1.original_hash,
        [translation1, translation2, translation3]
    )

    print("\nVERIFICATION RESULT:")
    print(f"Status: {'PASS' if verified else 'FAIL'}")
    print(f"Message: {message}")

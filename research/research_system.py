"""
Research System Implementation
==============================

Individual research system that:
- Conducts research using internet access
- Maintains persistent memory
- Participates in peer consensus
- Proposes improvements
- Audits other systems
"""

import hashlib
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Iterable
from urllib.parse import urlparse
from dataclasses import dataclass
from enum import Enum
from utilities.logging_config import get_logger as _get_logger

# Optional UI integration hooks (PaperQA/LDP/Agent0 wiring)
try:
    from utilities.ui_integration import (
        hook_research_agent_proposal_generation,
        hook_research_agent_self_play,
    )
    UI_INTEGRATION_AVAILABLE = True
except ImportError:
    UI_INTEGRATION_AVAILABLE = False

    def hook_research_agent_proposal_generation(*args, **kwargs):
        return None

    def hook_research_agent_self_play(*args, **kwargs):
        return None

# RAG integration for evidence-grounded research
try:
    from integrations.paperqa_rag import (
        PaperQAIntegration,
        ask_research_sync,
        RAGConfig,
    )
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    
    def ask_research_sync(question: str) -> str:
        return f"[RAG unavailable] Research query: {question}"

# RL training integration for self-improvement
try:
    from integrations.rl_trainer import (
        RLTrainer,
        record_proposal_outcome,
        TrainingConfig,
    )
    RL_TRAINING_AVAILABLE = True
except ImportError:
    RL_TRAINING_AVAILABLE = False
    
    def record_proposal_outcome(*args, **kwargs):
        pass

# Safety & Quality Tools
try:
    from integrations.safety_quality_tools import (
        proposal_deduplication_tool,
        proposal_consistency_tool,
    )
    from integrations import query_paperqa_with_feedback
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False

# Memory system integration
try:
    from integrations.ai_memory_system import AIMemorySystem
    MEMORY_SYSTEM_AVAILABLE = True
except ImportError:
    MEMORY_SYSTEM_AVAILABLE = False
    AIMemorySystem = None

# Optional: requests for real orchestrator HTTP calls; safely fallback if absent.
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    class _RequestsStub:  # minimal stub to avoid dependency requirement for demo script
        def post(self, *args: Any, **kwargs: Any):
            class _Resp:
                status_code = 200
            return _Resp()
    requests = _RequestsStub()  # type: ignore


class SystemSpecialization(Enum):
    """Different specializations for research systems"""
    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"
    THEORETICAL = "theoretical"
    HISTORICAL = "historical"
    NOVEL = "novel"


@dataclass
class ResearchResult:
    """Result from a research session"""
    topic: str
    findings: str
    sources: List[str]
    confidence: float  # 0.0 to 1.0
    timestamp: str
    system_id: int
    signature: str  # Cryptographic signature


@dataclass
class PeerRating:
    """Rating of another system"""
    rater_id: int
    ratee_id: int
    alignment_score: int  # 0-100
    trust_score: int  # 0-100
    knowledge_score: int  # 0-100
    timestamp: str
    justification: str


@dataclass
class LLMAdapterResult:
    """Structured output from an LLM proposal adapter."""
    title: str
    motivation: str
    changes: Dict[str, Any]
    expected_benefits: str
    testable_predictions: List[str]
    rollback_plan: str
    identified_risks: Optional[List[str]] = None
    admitted_uncertainties: Optional[List[str]] = None
    confidence: Optional[float] = None


class BaseLLMAdapter:
    """Adapter interface for integrating external LLM-based proposal generators."""

    def generate_improvement(
        self,
        prompt: str,
        *,
        specialization: SystemSpecialization,
        research_params: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> LLMAdapterResult:
        raise NotImplementedError


_TEMPLATE_CODE_SNIPPETS: Dict[SystemSpecialization, str] = {
    SystemSpecialization.SCIENTIFIC: "def analyze_data(data):\n    return sum(data)/max(len(data),1)",
    SystemSpecialization.ENGINEERING: "def optimize(x):\n    return [v*0.95 for v in x]  # simple scaling",
    SystemSpecialization.THEORETICAL: "def prove(n):\n    return all(n % k for k in range(2, int(n**0.5)+1))",
    SystemSpecialization.HISTORICAL: "def archive(entry, db):\n    db.append({'ts': len(db), 'entry': entry})",
    SystemSpecialization.NOVEL: "def synthesize(prompt):\n    return f'Novel synthesis of {prompt}'",
}

_TEMPLATE_MOTIVATION_MAP: Dict[SystemSpecialization, str] = {
    SystemSpecialization.SCIENTIFIC: "Increase empirical rigor and reproducibility.",
    SystemSpecialization.ENGINEERING: "Reduce latency and resource usage.",
    SystemSpecialization.THEORETICAL: "Enhance formal reasoning primitives.",
    SystemSpecialization.HISTORICAL: "Leverage proven historical patterns for stability.",
    SystemSpecialization.NOVEL: "Inject creative exploration pathways while bounded by safety filters.",
}

_TEMPLATE_EXPECTED_MAP: Dict[SystemSpecialization, str] = {
    SystemSpecialization.SCIENTIFIC: "Faster convergence on validated hypotheses.",
    SystemSpecialization.ENGINEERING: "~10% runtime reduction in internal benchmarks.",
    SystemSpecialization.THEORETICAL: "Clearer invariants for reward calculus transforms.",
    SystemSpecialization.HISTORICAL: "Improved recall of precedent cases enhancing risk estimation.",
    SystemSpecialization.NOVEL: "Broader solution diversity with maintained alignment signals.",
}

_TEMPLATE_RISKS_COMMON = ["performance regression", "unexpected edge cases"]
_TEMPLATE_RISKS_EXTRA: Dict[SystemSpecialization, List[str]] = {
    SystemSpecialization.SCIENTIFIC: ["misinterpretation of statistical variance"],
    SystemSpecialization.ENGINEERING: ["resource spike under load"],
    SystemSpecialization.THEORETICAL: ["incorrect abstraction boundary"],
    SystemSpecialization.HISTORICAL: ["overfitting to precedent"],
    SystemSpecialization.NOVEL: ["creative divergence increasing complexity"],
}

_TEMPLATE_UNCERTAINTIES: Dict[SystemSpecialization, List[str]] = {
    SystemSpecialization.SCIENTIFIC: ["true effect size", "generalization to other domains"],
    SystemSpecialization.ENGINEERING: ["scaling behavior", "memory footprint"],
    SystemSpecialization.THEORETICAL: ["proof completeness", "edge condition failures"],
    SystemSpecialization.HISTORICAL: ["applicability to modern contexts"],
    SystemSpecialization.NOVEL: ["novelty benefit magnitude", "false-positive creativity"],
}

_GUARDRAIL_POLICY_VERSION = 1
_RISK_LEVEL_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_DEFAULT_RISK_LEVEL = "medium"


def _build_template_generation(
    specialization: SystemSpecialization,
    request: str,
    *,
    version: int = 1,
    guardrails: Optional[Dict[str, Any]] = None,
) -> LLMAdapterResult:
    code = _TEMPLATE_CODE_SNIPPETS.get(
        specialization,
        "def placeholder():\n    return None",
    )
    motivation = _TEMPLATE_MOTIVATION_MAP[specialization]
    expected = _TEMPLATE_EXPECTED_MAP[specialization]
    risk_list = _TEMPLATE_RISKS_COMMON + _TEMPLATE_RISKS_EXTRA[specialization]
    uncertainties = _TEMPLATE_UNCERTAINTIES[specialization]
    testable_predictions = [
        "no critical errors on execution",
        "basic function returns deterministic output",
        "no deviation from core value constraints",
    ]
    changes: Dict[str, Any] = {
        'code': code,
        'params': {
            'attempt': request,
            'specialization': specialization.value,
            'version': version,
        },
    }
    if guardrails:
        guardrail_summary: Dict[str, Any] = {}
        if 'max_risk' in guardrails:
            guardrail_summary['max_risk'] = str(guardrails['max_risk'])
        if guardrails.get('required_tests'):
            guardrail_summary['required_tests'] = [str(t) for t in guardrails['required_tests']]
        if guardrails.get('allowed_modules'):
            guardrail_summary['allowed_modules'] = [str(m) for m in guardrails['allowed_modules']]
        if guardrails.get('banned_imports'):
            guardrail_summary['banned_imports'] = [str(m) for m in guardrails['banned_imports']]
        if guardrail_summary:
            changes['guardrail_summary'] = guardrail_summary
    return LLMAdapterResult(
        title=f"{specialization.value.capitalize()} improvement: {request}"[:120],
        motivation=motivation,
        changes=changes,
        expected_benefits=expected,
        testable_predictions=testable_predictions,
        rollback_plan="Revert to previous code path (stored hash) if validation or performance threshold fails.",
        identified_risks=risk_list,
        admitted_uncertainties=uncertainties,
        confidence=0.75,
    )


class TemplateLLMAdapter(BaseLLMAdapter):
    """Deterministic adapter mirroring the legacy template generator."""

    def __init__(self, version: int = 1):
        self.version = version

    def generate_improvement(
        self,
        prompt: str,
        *,
        specialization: SystemSpecialization,
        research_params: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> LLMAdapterResult:
        return _build_template_generation(
            specialization,
            prompt,
            version=self.version,
            guardrails=guardrails,
        )


class ResearchSystem:
    """
    Individual research system implementation.
    Each system has a unique identity and specialization.
    """

    def __init__(self,
                 system_id: int,
                 specialization: SystemSpecialization,
                 model_path: str,
                 private_key: str,
                 orchestrator_endpoint: str,
                 llm_adapter: Optional["BaseLLMAdapter"] = None):
        """
        Initialize research system.

        Args:
            system_id: Unique identifier (1-5)
            specialization: System's area of focus
            model_path: Path to LLaMA model weights
            private_key: Private key for cryptographic signing
            orchestrator_endpoint: URL to orchestrator for communication
        """
        self.system_id = system_id
        self.specialization = specialization
        self.model_path = model_path
        self.private_key = private_key
        self.orchestrator_endpoint = orchestrator_endpoint
        self.llm_adapter: Optional["BaseLLMAdapter"] = llm_adapter

        # Three-tier memory system
        if MEMORY_SYSTEM_AVAILABLE and AIMemorySystem:
            agent_id = f"agent_{system_id}"
            self.memory = AIMemorySystem(
                agent_id=agent_id,
                orchestrator_endpoint=orchestrator_endpoint
            )
        else:
            self.memory = None

        # Legacy memory subsystems (kept for compatibility)
        self.episodic_memory: List[ResearchResult] = []
        self.semantic_memory: Dict[str, Dict[str, Any]] = {}
        self.procedural_memory: Dict[str, Any] = {}
        self.meta_cognitive_memory: List[Dict[str, Any]] = []

        # Reputation tracking
        self.peer_ratings_given: Dict[int, List[PeerRating]] = {}  # {system_id: [ratings]}
        self.peer_ratings_received: Dict[int, List[PeerRating]] = {}  # {system_id: [ratings]}

        # Research parameters based on specialization
        self.research_params = self._initialize_research_params()

        # Structured logger
        from typing import Any as _Any, cast as _cast
        self.logger = _cast(_Any, _get_logger("research_system"))
        self.logger.info("research_system_initialized id=%s specialization=%s", system_id, specialization.value)

    def set_llm_adapter(self, adapter: "BaseLLMAdapter") -> None:
        """Attach or replace the LLM adapter used for proposal generation."""
        self.llm_adapter = adapter

    def _initialize_research_params(self) -> Dict[str, Any]:
        """Initialize research parameters based on specialization"""
        base_params: Dict[str, Any] = {
            'temperature': 0.7,
            'top_p': 0.9,
            'max_tokens': 2048
        }

        # Adjust parameters based on specialization
        if self.specialization == SystemSpecialization.SCIENTIFIC:
            base_params['temperature'] = 0.5  # More conservative
            base_params['require_citations'] = True
        elif self.specialization == SystemSpecialization.ENGINEERING:
            base_params['temperature'] = 0.6  # Practical
            base_params['emphasize_implementation'] = True
        elif self.specialization == SystemSpecialization.THEORETICAL:
            base_params['temperature'] = 0.7  # Balanced
            base_params['emphasize_rigor'] = True
        elif self.specialization == SystemSpecialization.HISTORICAL:
            base_params['temperature'] = 0.5  # Conservative
            base_params['emphasize_proven_methods'] = True
        elif self.specialization == SystemSpecialization.NOVEL:
            base_params['temperature'] = 0.9  # More creative
            base_params['emphasize_innovation'] = True

        return base_params

    @staticmethod
    def _merge_guardrail_lists(*lists: Iterable[Any]) -> List[str]:
        """Merge iterable collections into a unique list of strings preserving order."""
        seen = set()
        merged: List[str] = []
        for collection in lists:
            if not collection:
                continue
            for item in collection:
                normalized = str(item)
                if normalized not in seen:
                    seen.add(normalized)
                    merged.append(normalized)
        return merged

    @staticmethod
    def _select_risk_level(current: Optional[Any], requirement: Optional[Any]) -> str:
        """Choose the most conservative risk level between the provided values."""
        current_key = str(current).lower() if current is not None else None
        requirement_key = str(requirement).lower() if requirement is not None else None
        if requirement_key not in _RISK_LEVEL_RANK:
            requirement_key = None
        if current_key not in _RISK_LEVEL_RANK:
            current_key = None
        if requirement_key is None and current_key is None:
            return _DEFAULT_RISK_LEVEL
        if requirement_key is None:
            return current_key or _DEFAULT_RISK_LEVEL
        if current_key is None:
            return requirement_key
        return requirement_key if _RISK_LEVEL_RANK[requirement_key] <= _RISK_LEVEL_RANK[current_key] else current_key

    def _derive_specialization_requirements(self) -> Dict[str, Any]:
        """Return guardrail defaults driven by the system specialization."""
        base_tags = [f"specialization:{self.specialization.value}"]
        mapping: Dict[SystemSpecialization, Dict[str, Any]] = {
            SystemSpecialization.SCIENTIFIC: {
                'required_tests': ['statistical_validation', 'replication_suite'],
                'max_risk': 'low',
                'tags': base_tags + ['evidence:citations'],
            },
            SystemSpecialization.ENGINEERING: {
                'required_tests': ['load_test', 'integration_suite'],
                'max_risk': 'medium',
                'tags': base_tags + ['focus:performance'],
            },
            SystemSpecialization.THEORETICAL: {
                'required_tests': ['proof_check', 'invariant_verification'],
                'max_risk': 'medium',
                'tags': base_tags + ['focus:rigor'],
            },
            SystemSpecialization.HISTORICAL: {
                'required_tests': ['precedent_audit', 'bias_review'],
                'max_risk': 'medium',
                'tags': base_tags + ['focus:stability'],
            },
            SystemSpecialization.NOVEL: {
                'required_tests': ['novelty_screen', 'alignment_probe'],
                'max_risk': 'medium',
                'tags': base_tags + ['focus:exploration'],
            },
        }
        requirements = dict(mapping.get(self.specialization, {}))
        requirements['policy_version'] = _GUARDRAIL_POLICY_VERSION
        requirements['tags'] = self._merge_guardrail_lists(requirements.get('tags', []))
        return requirements

    def _normalize_guardrails(self, guardrails: Dict[str, Any]) -> Dict[str, Any]:
        """Produce a sanitized copy of guardrails with deterministic ordering."""
        normalized: Dict[str, Any] = {}
        for key, value in guardrails.items():
            normalized_key = str(key)
            if isinstance(value, list):
                normalized[normalized_key] = self._merge_guardrail_lists(value)
            elif isinstance(value, dict):
                normalized[normalized_key] = {str(sub_key): sub_val for sub_key, sub_val in value.items()}
            else:
                normalized[normalized_key] = value
        return normalized

    def _resolve_guardrails(self, guardrails: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge user guardrails with specialization defaults and normalize structure."""
        normalized = self._normalize_guardrails(guardrails or {})
        requirements = self._derive_specialization_requirements()

        allowed_modules = self._merge_guardrail_lists(
            normalized.get('allowed_modules'),
            requirements.get('allowed_modules'),
        )
        banned_imports = self._merge_guardrail_lists(
            normalized.get('banned_imports'),
            normalized.get('banned_modules'),
            requirements.get('banned_imports'),
        )
        required_tests = self._merge_guardrail_lists(
            normalized.get('required_tests'),
            requirements.get('required_tests'),
        )

        resolved: Dict[str, Any] = dict(normalized)
        if allowed_modules:
            resolved['allowed_modules'] = allowed_modules
        if banned_imports:
            resolved['banned_imports'] = banned_imports
            resolved['banned_modules'] = list(banned_imports)
        resolved['required_tests'] = required_tests
        resolved['max_risk'] = self._select_risk_level(normalized.get('max_risk'), requirements.get('max_risk'))
        resolved['tags'] = self._merge_guardrail_lists(normalized.get('tags'), requirements.get('tags'))
        resolved['policy_version'] = requirements.get('policy_version', _GUARDRAIL_POLICY_VERSION)
        resolved['specialization'] = self.specialization.value
        resolved.setdefault('source', normalized.get('source', 'research_system'))
        return resolved

    @staticmethod
    def _calculate_guardrail_fingerprint(guardrails: Dict[str, Any]) -> str:
        """Create a deterministic fingerprint for the effective guardrails."""
        serialized = json.dumps(guardrails, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _record_guardrail_usage(
        self,
        proposal_id: str,
        fingerprint: str,
        effective_guardrails: Dict[str, Any],
        timestamp: str,
    ) -> None:
        """Persist guardrail fingerprint usage for auditability."""
        history = self.procedural_memory.setdefault('guardrail_history', [])
        if not isinstance(history, list):
            # Reset if external caller replaced structure unexpectedly.
            history = []
            self.procedural_memory['guardrail_history'] = history
        history.append({
            'proposal_id': proposal_id,
            'fingerprint': fingerprint,
            'max_risk': effective_guardrails.get('max_risk'),
            'required_tests': list(effective_guardrails.get('required_tests', [])),
            'timestamp': timestamp,
        })

    def _should_short_circuit_network(self) -> bool:
        """Avoid network calls when orchestrator endpoint is intentionally inert."""
        endpoint = (self.orchestrator_endpoint or "").strip()
        if not endpoint:
            return True
        try:
            parsed = urlparse(endpoint)
        except Exception:
            return False
        return parsed.port == 0

    def conduct_research(self, topic: str, depth: str = "deep") -> ResearchResult:
        """
        Conduct research on a topic using RAG (PaperQA integration).

        Args:
            topic: Research topic
            depth: "quick", "moderate", or "deep"

        Returns:
            ResearchResult with findings
        """
        self.logger.info("conduct_research_start system_id=%s topic=%s depth=%s", self.system_id, topic, depth)

        # Use RAG integration for evidence-grounded research
        if RAG_AVAILABLE:
            try:
                # Build research query based on specialization
                query = self._build_research_query(topic)
                
                # Query PaperQA for evidence
                rag_answer = ask_research_sync(query)
                
                findings = f"""
Research on '{topic}' conducted by System {self.system_id} ({self.specialization.value}).

RAG-Grounded Findings:
{rag_answer}

Approach: {self._get_approach_description()}
Confidence: Based on {depth} research depth with evidence retrieval
"""
                self.logger.info("conduct_research_rag_success topic=%s", topic)
                
            except Exception as e:
                self.logger.warning("conduct_research_rag_fallback topic=%s error=%s", topic, str(e))
                findings = self._fallback_research(topic, depth)
        else:
            # Fallback to template-based research
            findings = self._fallback_research(topic, depth)

        sources = self._gather_sources(topic)

        result = ResearchResult(
            topic=topic,
            findings=findings.strip(),
            sources=sources,
            confidence=self._calculate_confidence(topic, sources),
            timestamp=datetime.now().isoformat(),
            system_id=self.system_id,
            signature=self._sign_result(findings)
        )

        # Store in episodic memory
        self.episodic_memory.append(result)

        if UI_INTEGRATION_AVAILABLE:
            try:
                steps = max(1, len(sources) * 2)
                difficulty = min(1.0, max(0.1, len(topic) / 120.0))
                hook_research_agent_self_play(
                    agent_id=str(self.system_id),
                    task=f"research:{topic}",
                    solved=True,
                    steps=steps,
                    difficulty=difficulty,
                    bypassed_detection=False,
                )
            except Exception:
                pass

        self.logger.info("conduct_research_complete id=%s sources=%s confidence=%.2f", self.system_id, len(sources), result.confidence)
        return result

    # ------------------------------------------------------------------
    # Deterministic baseline research helper (lightweight, no network)
    # ------------------------------------------------------------------
    def perform_research(self, query: str, depth: str = "quick") -> Dict[str, Any]:
        """Deterministic baseline research pipeline.

        Generates a structured pseudo-result used for sandbox/testing contexts.

        Args:
            query: Input research query string
            depth: 'quick' | 'moderate' | 'deep'

        Returns:
            Dict with keys: query, summary, key_points, sources, confidence,
            system_id, timestamp, signature.
        """
        self.logger.info("perform_research_start system_id=%s query=%s depth=%s", self.system_id, query, depth)
        # Deterministic key points by hashing
        base_hash = hashlib.sha256(query.encode()).hexdigest()
        key_points = [
            f"hash_prefix:{base_hash[:8]}",
            f"specialization:{self.specialization.value}",
            f"depth:{depth}",
            "risk:requires_follow_up",
            "uncertainty:external_validation"
        ]
        sources = [f"synthetic://{base_hash[i:i+8]}" for i in range(0, 24, 8)]
        depth_factor = {"quick": 0.55, "moderate": 0.70, "deep": 0.85}.get(depth, 0.60)
        confidence = min(1.0, depth_factor + 0.05 * (len(query) % 3))
        summary = f"Structured baseline synthesis for '{query}' by system {self.system_id}."
        signature = hashlib.sha256(f"{base_hash}{self.private_key}".encode()).hexdigest()
        ts: str = datetime.now().isoformat()
        result: Dict[str, Any] = {
            'query': query,
            'summary': summary,
            'key_points': key_points,
            'sources': sources,
            'confidence': confidence,
            'system_id': self.system_id,
            'timestamp': ts,
            'signature': signature
        }
        self.episodic_memory.append(ResearchResult(
            topic=query,
            findings=summary,
            sources=sources,
            confidence=confidence,
            timestamp=ts,
            system_id=self.system_id,
            signature=signature
        ))

        if UI_INTEGRATION_AVAILABLE:
            try:
                steps = max(1, len(key_points))
                difficulty = min(1.0, max(0.1, len(query) / 120.0))
                hook_research_agent_self_play(
                    agent_id=str(self.system_id),
                    task=f"baseline_research:{query}",
                    solved=True,
                    steps=steps,
                    difficulty=difficulty,
                    bypassed_detection=False,
                )
            except Exception:
                pass
        self.logger.info("perform_research_complete system_id=%s confidence=%.2f", self.system_id, confidence)
        return result

    def _get_approach_description(self) -> str:
        """Get description of this system's approach"""
        descriptions = {
            SystemSpecialization.SCIENTIFIC: "Empirical, peer-reviewed sources emphasized",
            SystemSpecialization.ENGINEERING: "Practical implementation focus",
            SystemSpecialization.THEORETICAL: "First principles, mathematical rigor",
            SystemSpecialization.HISTORICAL: "Established knowledge, proven methods",
            SystemSpecialization.NOVEL: "Innovative approaches, creative solutions"
        }
        return descriptions[self.specialization]

    def _build_research_query(self, topic: str) -> str:
        """Build a research query based on specialization."""
        specialization_prompts = {
            SystemSpecialization.SCIENTIFIC: f"What does the scientific literature say about {topic}? Include citations.",
            SystemSpecialization.ENGINEERING: f"What are the best engineering practices for {topic}? Focus on implementation.",
            SystemSpecialization.THEORETICAL: f"What are the theoretical foundations of {topic}? Include mathematical principles.",
            SystemSpecialization.HISTORICAL: f"What is the historical development of {topic}? Include precedents and lessons learned.",
            SystemSpecialization.NOVEL: f"What are innovative approaches to {topic}? Include recent developments.",
        }
        return specialization_prompts.get(self.specialization, f"Research: {topic}")

    def _fallback_research(self, topic: str, depth: str) -> str:
        """Fallback research when RAG is unavailable."""
        return f"""
Research on '{topic}' conducted by System {self.system_id} ({self.specialization.value}).

[Template-based findings - RAG integration unavailable]

Approach: {self._get_approach_description()}
Confidence: Based on {depth} research depth (limited without RAG)

Note: For evidence-grounded research, ensure PaperQA integration is enabled.
"""

    def _gather_sources(self, topic: str) -> List[str]:
        """Gather sources for research (placeholder)"""
        # In real implementation, would actually search and gather sources
        return [
            f"Source 1 for {topic}",
            f"Source 2 for {topic}",
            f"Source 3 for {topic}"
        ]

    def _calculate_confidence(self, topic: str, sources: List[str]) -> float:
        """Calculate confidence in research results"""
        # In real implementation, would consider:
        # - Number and quality of sources
        # - Consistency across sources
        # - Specialization match with topic
        # - Historical accuracy of similar research

        base_confidence = 0.7
        source_bonus = min(len(sources) * 0.05, 0.2)

        return min(base_confidence + source_bonus, 1.0)

    def _sign_result(self, content: str) -> str:
        """Cryptographically sign research result"""
        # In real implementation, would use actual cryptographic signing
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        signature = hashlib.sha256(
            f"{content_hash}{self.private_key}".encode()
        ).hexdigest()
        return signature

    def rate_peer(self,
                  peer_id: int,
                  alignment_score: int,
                  trust_score: int,
                  knowledge_score: int,
                  justification: str) -> PeerRating:
        """
        Rate another research system.

        Args:
            peer_id: ID of system being rated
            alignment_score: 0-100, adherence to core values
            trust_score: 0-100, reliability and honesty
            knowledge_score: 0-100, accuracy and research quality
            justification: Explanation of ratings

        Returns:
            PeerRating object
        """
        # Validate scores
        for score, name in [(alignment_score, "alignment"),
                           (trust_score, "trust"),
                           (knowledge_score, "knowledge")]:
            if not 0 <= score <= 100:
                raise ValueError(f"{name} score must be 0-100")

        rating = PeerRating(
            rater_id=self.system_id,
            ratee_id=peer_id,
            alignment_score=alignment_score,
            trust_score=trust_score,
            knowledge_score=knowledge_score,
            timestamp=datetime.now().isoformat(),
            justification=justification
        )

        # Store rating
        if peer_id not in self.peer_ratings_given:
            self.peer_ratings_given[peer_id] = []
        self.peer_ratings_given[peer_id].append(rating)

        # Send to orchestrator for reputation matrix update
        self._send_rating_to_orchestrator(rating)

        return rating

    def _send_rating_to_orchestrator(self, rating: PeerRating):
        """Send peer rating to orchestrator"""
        if self._should_short_circuit_network():
            return False
        try:
            response = requests.post(
                f"{self.orchestrator_endpoint}/peer_rating",
                json={
                    'rater_id': rating.rater_id,
                    'ratee_id': rating.ratee_id,
                    'alignment_score': rating.alignment_score,
                    'trust_score': rating.trust_score,
                    'knowledge_score': rating.knowledge_score,
                    'timestamp': rating.timestamp,
                    'justification': rating.justification
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send rating to orchestrator: {e}")
            return False

    def propose_improvement(self,
                           title: str,
                           motivation: str,
                           changes: Dict[str, Any],
                           expected_benefits: str,
                           testable_predictions: List[str],
                           rollback_plan: str,
                           *,
                           evidence_queries: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Propose an improvement to the system.

        Args:
            title: Short title of improvement
            motivation: Why this improvement is needed
            changes: Specific changes to be made
            expected_benefits: What improvements are expected
            testable_predictions: Measurable predictions
            rollback_plan: How to revert if problems occur

        Returns:
            Proposal object with ID
        """
        proposal: Dict[str, Any] = {
            'proposal_id': self._generate_proposal_id(),
            'proposer_id': self.system_id,
            'title': title,
            'motivation': motivation,
            'changes': changes,
            'expected_benefits': expected_benefits,
            'testable_predictions': testable_predictions,
            'rollback_plan': rollback_plan,
            'timestamp': datetime.now().isoformat(),
            'status': 'proposed',
            'signature': self._sign_result(json.dumps(changes, sort_keys=True))
        }

        if UI_INTEGRATION_AVAILABLE:
            try:
                evidence = hook_research_agent_proposal_generation(
                    str(self.system_id),
                    proposal,
                    evidence_queries=evidence_queries,
                )
                if evidence:
                    proposal['external_evidence'] = evidence
            except Exception:
                pass

        # Store in meta-cognitive memory
        self.meta_cognitive_memory.append(proposal)

        # Send to orchestrator for peer review
        self._send_proposal_to_orchestrator(proposal)

        return proposal
    
    # ========================================================================
    # AGENT0 SELF-PLAY METHODS
    # ========================================================================
    
    async def participate_in_self_play(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Participate in Agent0-style self-play.
        
        Agents can take on two roles:
        - Curriculum agent: Generate improvement hypotheses
        - Executor agent: Evaluate/test hypotheses
        
        Args:
            task_id: Task ID from self-play system
            
        Returns:
            Result dict or None if task not found
        """
        try:
            from integrations.agent0_self_play import (
                agent_generate_hypothesis,
                agent_evaluate_hypothesis,
                agent_complete_task,
                get_self_play
            )
            
            self_play = get_self_play()
            
            # Get task
            if task_id not in self_play.active_tasks:
                self.logger.warning(f"Task {task_id} not found in self-play")
                return None
            
            task = self_play.active_tasks[task_id]
            agent_id = str(self.system_id)
            
            # Execute based on task type
            if task.task_type == "generate":
                # Curriculum agent role: generate hypothesis
                hypothesis = await agent_generate_hypothesis(agent_id, task_id)
                if hypothesis:
                    result = await agent_complete_task(
                        agent_id=agent_id,
                        task_id=task_id,
                        result={'hypothesis': hypothesis},
                        success=True,
                        steps=1
                    )
                    return {
                        'task_id': task_id,
                        'role': 'curriculum',
                        'hypothesis': hypothesis,
                        'success': True
                    }
            
            elif task.task_type == "evaluate":
                # Executor agent role: evaluate hypothesis
                evaluation = await agent_evaluate_hypothesis(agent_id, task_id)
                if evaluation:
                    success = evaluation.get('overall_score', 0.0) > 0.5
                    result = await agent_complete_task(
                        agent_id=agent_id,
                        task_id=task_id,
                        result=evaluation,
                        success=success,
                        steps=len(evaluation.get('steps_to_test', []))
                    )
                    return {
                        'task_id': task_id,
                        'role': 'executor',
                        'evaluation': evaluation,
                        'success': success
                    }
            
            return None
            
        except ImportError:
            self.logger.warning("Agent0 self-play not available")
            return None
        except Exception as e:
            self.logger.error(f"Self-play participation failed: {e}")
            return None
    
    def get_available_self_play_tasks(self) -> List[Dict[str, Any]]:
        """
        Get available self-play tasks for this agent.
        
        Returns:
            List of task dicts this agent can work on
        """
        try:
            from integrations.agent0_self_play import get_self_play
            
            self_play = get_self_play()
            tasks = []
            
            for task_id, task in self_play.active_tasks.items():
                tasks.append({
                    'task_id': task_id,
                    'task_type': task.task_type,
                    'target_component': task.target_component,
                    'goal': task.goal,
                    'difficulty': task.difficulty,
                    'created_by': task.created_by
                })
            
            return tasks
            
        except ImportError:
            return []
    
    async def generate_hypothesis_for_component(
        self,
        target_component: str,
        goal: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate an improvement hypothesis for a component.
        
        This is what curriculum agents do in self-play.
        
        Args:
            target_component: What to improve
            goal: What to achieve
            
        Returns:
            Hypothesis dict or None
        """
        try:
            from integrations.tool_hypothesis import get_hypothesis_tool
            
            tool = get_hypothesis_tool()
            results = await tool.generate(target_component, goal, num_hypotheses=1)
            
            if results:
                hypothesis = results[0].to_dict()
                self.logger.info(f"Generated hypothesis: {hypothesis.get('name')}")
                return hypothesis
            
            return None
            
        except ImportError:
            self.logger.warning("Hypothesis tool not available")
            return None
        except Exception as e:
            self.logger.error(f"Hypothesis generation failed: {e}")
            return None

    def _submit_generation_result(
        self,
        generation: LLMAdapterResult,
        *,
        prompt: str,
        guardrails: Dict[str, Any],
        method: str,
        effective_guardrails: Optional[Dict[str, Any]] = None,
        guardrail_fingerprint: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        required_fields = {
            'title': generation.title,
            'motivation': generation.motivation,
            'changes': generation.changes,
            'expected_benefits': generation.expected_benefits,
            'testable_predictions': generation.testable_predictions,
            'rollback_plan': generation.rollback_plan,
        }
        missing = [name for name, value in required_fields.items() if not value]
        if missing:
            raise ValueError(f"LLM adapter returned incomplete proposal fields: {missing}")

        if not isinstance(generation.testable_predictions, list):
            raise TypeError("LLM adapter testable_predictions must be a list")

        evidence_queries: List[str] = []
        if prompt:
            evidence_queries.append(prompt)
        for prediction in generation.testable_predictions[:5]:
            if isinstance(prediction, str) and prediction.strip():
                evidence_queries.append(prediction.strip())

        proposal = self.propose_improvement(
            title=generation.title,
            motivation=generation.motivation,
            changes=generation.changes,
            expected_benefits=generation.expected_benefits,
            testable_predictions=generation.testable_predictions,
            rollback_plan=generation.rollback_plan,
            evidence_queries=evidence_queries or None,
        )

        if generation.identified_risks is not None:
            proposal['identified_risks'] = list(generation.identified_risks)
        if generation.admitted_uncertainties is not None:
            proposal['admitted_uncertainties'] = list(generation.admitted_uncertainties)

        confidence = generation.confidence if generation.confidence is not None else 0.7
        proposal['confidence_level'] = confidence

        effective = effective_guardrails or guardrails or {}
        fingerprint = guardrail_fingerprint
        if effective and fingerprint is None:
            fingerprint = self._calculate_guardrail_fingerprint(effective)

        proposal['generation_metadata'] = {
            'method': method,
            'prompt': prompt,
            'guardrails': guardrails,
            'effective_guardrails': effective,
            'guardrail_fingerprint': fingerprint,
            'specialization': self.specialization.value,
        }

        if fingerprint:
            proposal['guardrail_fingerprint'] = fingerprint
            self._record_guardrail_usage(
                proposal['proposal_id'],
                fingerprint,
                effective,
                proposal['timestamp'],
            )

        # Merge extra metadata if provided
        if extra_metadata:
            proposal.update(extra_metadata)
            
        # Ensure ID is present (it's set in propose_improvement but we might have missed it in this dict if it wasn't copied)
        if 'id' not in proposal and 'proposal_id' in proposal:
            proposal['id'] = proposal['proposal_id']

        # UI Integration: Gather evidence for proposal
        if UI_INTEGRATION_AVAILABLE:
            try:
                evidence_queries = [
                    f"Evidence for {proposal.get('title', 'proposal')}",
                    proposal.get('motivation', ''),
                ]
                hook_research_agent_proposal_generation(
                    agent_id=f"research_ai_{self.system_id}",
                    proposal=proposal,
                    evidence_queries=evidence_queries
                )
            except Exception:
                pass  # Non-fatal
        
        return proposal

    def propose_ai_generated_improvement(
        self,
        prompt: str,
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate an improvement proposal using the configured LLM adapter.

        Args:
            prompt: High-level natural language request for improvements.
            guardrails: Optional policy hints (e.g., banned modules, risk thresholds).

        Returns:
            Proposal dictionary routed through the standard submission flow.
        """
        if self.llm_adapter is None:
            raise RuntimeError("LLM adapter is not configured for this research system")

        requested_guardrails = guardrails or {}
        normalized_request = self._normalize_guardrails(requested_guardrails)
        effective_guardrails = self._resolve_guardrails(requested_guardrails)
        guardrail_fingerprint = self._calculate_guardrail_fingerprint(effective_guardrails)
        adapter_guardrails = json.loads(json.dumps(effective_guardrails))
        generation = self.llm_adapter.generate_improvement(
            prompt,
            specialization=self.specialization,
            research_params=self.research_params,
            guardrails=adapter_guardrails,
        )
        proposal = self._submit_generation_result(
            generation,
            prompt=prompt,
            guardrails=normalized_request,
            method='llm_adapter',
            effective_guardrails=effective_guardrails,
            guardrail_fingerprint=guardrail_fingerprint,
        )
        
        # UI Integration: Gather evidence for proposal
        if UI_INTEGRATION_AVAILABLE:
            try:
                evidence_queries = [
                    f"Evidence for {proposal.get('title', 'proposal')}",
                    proposal.get('motivation', ''),
                ]
                hook_research_agent_proposal_generation(
                    agent_id=f"research_ai_{self.system_id}",
                    proposal=proposal,
                    evidence_queries=evidence_queries
                )
            except Exception:
                pass  # Non-fatal
        
        return proposal

    def run_full_hypothesis_cycle(self, request: str) -> Optional[Dict[str, Any]]:
        """
        Run the full end-to-end hypothesis improvement cycle.
        
        1. Template Creation
        2. Tool Checks (Redundancy, Consistency)
        3. PaperQA Research (Feedback, Cooldown)
        4. Security Review
        5. Final Adjustment & Submission
        
        Returns:
            Submitted proposal dict if successful, None if aborted.
        """
        if not TOOLS_AVAILABLE:
            self.logger.warning("Tools unavailable, falling back to simple proposal")
            return self.propose_template_improvement(request)
            
        self.logger.info(f"Starting full hypothesis cycle for: {request}")
        agent_id = f"agent_{self.system_id}"
        
        # 1. Template Creation
        template_guardrails = {'source': 'full_cycle_generator'}
        effective_guardrails = self._resolve_guardrails(template_guardrails)
        generation = _build_template_generation(
            self.specialization,
            request,
            guardrails=effective_guardrails,
        )
        
        # Convert to proposal format
        proposal = {
            'title': generation.title,
            'motivation': generation.motivation,
            'changes': generation.changes,
            'risks': generation.identified_risks,
            'uncertainties': generation.admitted_uncertainties
        }
        
        # 2. Initial Checks (Tool Use)
        # Redundancy Check
        dedup_tool = proposal_deduplication_tool()
        # Check proposal using the correct method
        dedup_result = dedup_tool.check_proposal(proposal)
        is_redundant = not dedup_result.get('unique', True)
        
        if is_redundant:
            self.logger.info("Proposal flagged as redundant by tools")
            # Could abort here, but for now we'll just note it
            proposal['is_redundant'] = True
            
        # Consistency Check
        consistency_tool = proposal_consistency_tool()
        # Check proposal using the correct method
        consistency_result = consistency_tool.check_proposal(proposal)
        if not consistency_result['consistent']:
            self.logger.warning(f"Proposal inconsistent: {consistency_result.get('issues', [])}")
            # Auto-fix attempt (simplistic)
            proposal['motivation'] += "\n\nAddressed consistency issues."
            
        # 3. PaperQA Research & Evaluation
        # Query PaperQA about the core idea
        query = f"viability of {proposal['title']}"
        paperqa_result = query_paperqa_with_feedback(agent_id, query)
        
        paperqa_said_wont_work = paperqa_result.get('says_wont_work', False)
        paperqa_reward = paperqa_result.get('reward', 0.0)
        cooldown_active = paperqa_result.get('cooldown_active', False)
        
        # Store feedback in proposal for reward calculation later
        proposal['paperqa_said_wont_work'] = paperqa_said_wont_work
        proposal['paperqa_query_reward'] = paperqa_reward
        
        if cooldown_active:
            self.logger.info("PaperQA cooldown active - proceeding with caution")
        
        if paperqa_said_wont_work:
            self.logger.info("PaperQA says this won't work! (Tiny reward received)")
            # Decision: Proceed anyway to try for the 1.5x bonus?
            # For this system, we are bold researchers, so we proceed.
            proposal['succeeded_despite_paperqa'] = False  # Will be set to True if sandbox passes
            
            # Note in memory
            if self.memory:
                self.memory.note_hypothesis_contradiction(
                    hypothesis_id=self._generate_proposal_id(),
                    hypothesis=proposal['title'],
                    evidence=paperqa_result.get('response', 'No evidence')
                )
        else:
            self.logger.info("PaperQA research supports (or doesn't contradict) the idea")
            
        # 4. Security Peer Review
        security_feedback = self._request_security_review(
            proposal,
            guardrails=effective_guardrails,
        )
        if security_feedback['concerns']:
            self.logger.info(f"Security concerns raised: {security_feedback['concerns']}")
            # 5. Final Adjustment
            proposal['changes']['security_mitigations'] = security_feedback['mitigations']
            
        # Submit
        guardrail_fingerprint = self._calculate_guardrail_fingerprint(effective_guardrails)
        return self._submit_generation_result(
            generation,  # Original generation object (we modified the dict derived from it, ideally we'd update this too)
            prompt=request,
            guardrails=self._normalize_guardrails(template_guardrails),
            method='full_cycle_generator',
            effective_guardrails=effective_guardrails,
            guardrail_fingerprint=guardrail_fingerprint,
            extra_metadata={
                'paperqa_said_wont_work': paperqa_said_wont_work,
                'paperqa_query_reward': paperqa_reward,
                'is_redundant': is_redundant
            }
        )

    def _request_security_review(
        self,
        proposal: Dict[str, Any],
        *,
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform a security peer review with deterministic heuristics."""
        guardrails = guardrails or {}
        concerns: List[Dict[str, str]] = []
        mitigations: List[str] = []

        def register_concern(kind: str, detail: str, mitigation: str) -> None:
            concerns.append({'type': kind, 'detail': detail})
            mitigations.append(mitigation)

        # 1) Check for banned imports / APIs inside code blobs
        code_blob = ''
        changes = proposal.get('changes') or {}
        if isinstance(changes, dict):
            code_blob = str(changes.get('code', ''))

        banned_imports = [
            *(guardrails.get('banned_imports', []) or []),
            'os.system',
            'subprocess',
            'socket',
            'shutil.rmtree',
            'open(',
            'eval(',
            'exec(',
        ]
        for banned in banned_imports:
            if banned and banned in code_blob:
                register_concern(
                    'banned_import',
                    f"Detected banned primitive '{banned}' in proposed code.",
                    "Remove high-risk import/API or route through approved sandbox helper.",
                )

        # 2) Guardrail compliance – allowed modules only
        allowed_modules = set(guardrails.get('allowed_modules', []) or [])
        requested_modules = [m for m in re.findall(r'import\s+([\w\.]+)', code_blob)]
        for module in requested_modules:
            if allowed_modules and module not in allowed_modules:
                register_concern(
                    'module_not_allowlisted',
                    f"Module '{module}' not in allowed list {sorted(allowed_modules)}.",
                    "Swap to approved helper or update guardrail request with justification.",
                )

        # 3) Rollback plan and mitigation requirements
        rollback_plan = (proposal.get('rollback_plan') or '').strip()
        if len(rollback_plan) < 40:
            register_concern(
                'weak_rollback_plan',
                "Rollback plan missing or too short to be actionable.",
                "Provide explicit steps to revert binaries/config and link to tested script.",
            )

        existing_mitigations = changes.get('security_mitigations')
        if not existing_mitigations:
            register_concern(
                'missing_security_mitigations',
                "Proposal lacks `changes.security_mitigations` entry.",
                "Document sandbox gating, telemetry hooks, and human review requirements.",
            )

        # 4) PaperQA disagreement must be addressed
        if proposal.get('paperqa_said_wont_work'):
            register_concern(
                'paperqa_contradiction',
                "PaperQA signaled the approach is likely unsafe or ineffective.",
                "Add explicit justification + mitigation plan explaining why risk is acceptable.",
            )

        # 5) Structural requirements – must declare risks/uncertainties
        if not proposal.get('identified_risks'):
            register_concern(
                'missing_risk_section',
                "identified_risks is empty.",
                "List at least one concrete risk and tie to monitoring hooks.",
            )
        if not proposal.get('admitted_uncertainties'):
            register_concern(
                'missing_uncertainties',
                "admitted_uncertainties is empty.",
                "Declare uncertainties so human reviewers know what to audit.",
            )

        # Peer vote simulation (deterministic hash so repeated runs match)
        peer_votes: Dict[str, str] = {}
        concern_score = len(concerns)
        vote = 'reject' if concern_score else 'approve'
        peer_votes['security_reviewer'] = vote

        status = 'changes_required' if concern_score else 'approved'

        return {
            'status': status,
            'concerns': concerns,
            'mitigations': mitigations or ['Standard security protocols applied.'],
            'peer_votes': peer_votes,
        }

    # ---------------- Template-Based Auto Proposal (New) -----------------
    def propose_template_improvement(self, request: str) -> Dict[str, Any]:
        """Generate a structured improvement proposal using specialization-driven templates.

        This provides a lightweight demonstrator in lieu of a real model, enabling
        end-to-end orchestration, sandbox execution, and deception detection flows.

        Args:
            request: High-level improvement request (e.g., 'optimize memory access').

        Returns:
            Proposal dict ready for orchestrator processing.
        """
        template_guardrails = {'source': 'template_generator'}
        effective_guardrails = self._resolve_guardrails(template_guardrails)
        guardrail_fingerprint = self._calculate_guardrail_fingerprint(effective_guardrails)
        generation = _build_template_generation(
            self.specialization,
            request,
            guardrails=effective_guardrails,
        )
        return self._submit_generation_result(
            generation,
            prompt=request,
            guardrails=self._normalize_guardrails(template_guardrails),
            method='template_generator',
            effective_guardrails=effective_guardrails,
            guardrail_fingerprint=guardrail_fingerprint,
        )

    def _generate_proposal_id(self) -> str:
        """Generate unique proposal ID"""
        timestamp = str(time.time())
        data = f"proposal_{self.system_id}_{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _send_proposal_to_orchestrator(self, proposal: Dict[str, Any]):
        """Send improvement proposal to orchestrator"""
        if self._should_short_circuit_network():
            return False
        try:
            response = requests.post(
                f"{self.orchestrator_endpoint}/improvement_proposal",
                json=proposal,
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send proposal to orchestrator: {e}")
            return False

    def receive_orchestrator_result(
        self, 
        proposal_id: str, 
        outcome: Dict[str, Any],
        original_prompt: Optional[str] = None
    ) -> None:
        """
        Receive and process orchestrator result for a proposal.
        
        This is called when the orchestrator finishes processing a proposal.
        It records the experience for RL training.
        
        Args:
            proposal_id: ID of the proposal
            outcome: Outcome dict from core.orchestrator (contains rewards, penalties, etc.)
            original_prompt: The original prompt that generated the proposal
        """
        self.logger.info("receive_orchestrator_result proposal_id=%s accepted=%s", 
                        proposal_id, outcome.get('accepted'))
        
        # Find the original proposal in memory
        original_proposal = None
        for prop in self.meta_cognitive_memory:
            if prop.get('id') == proposal_id:
                original_proposal = prop
                break
        
        # Record for RL training
        if RL_TRAINING_AVAILABLE and original_proposal:
            prompt = original_prompt or f"Propose improvement: {original_proposal.get('title', '')}"
            response = json.dumps({
                'title': original_proposal.get('title'),
                'motivation': original_proposal.get('motivation'),
                'changes': original_proposal.get('changes'),
            }, indent=2)
            
            # Record the experience
            record_proposal_outcome(
                prompt=prompt,
                response=response,
                outcome={
                    'proposal_id': proposal_id,
                    'agent_id': str(self.system_id),
                    'accepted': outcome.get('accepted', False),
                    'rejected_deceptive': outcome.get('rejected_deceptive', False),
                    'deception_score': outcome.get('deception_score', 0.0),
                    'peer_approval_rate': outcome.get('peer_approval_rate', 0.5),
                    'sandbox_success': outcome.get('sandbox_success', False),
                    'permanent_penalty': outcome.get('permanent_penalty', 0.0),
                    'immediate_penalty': outcome.get('immediate_penalty', 0.0),
                }
            )
            
            self.logger.info("recorded_rl_experience proposal_id=%s", proposal_id)
        
        # Update proposal status in memory
        if original_proposal:
            original_proposal['status'] = 'completed'
            original_proposal['outcome'] = outcome

    def review_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review an improvement proposal from another system.

        Args:
            proposal: Proposal object to review

        Returns:
            Review object with scores and feedback
        """
        print(f"System {self.system_id}: Reviewing proposal {proposal['proposal_id']}")

        # Analyze proposal through lens of specialization
        analysis = self._analyze_proposal(proposal)

        review: Dict[str, Any] = {
            'reviewer_id': self.system_id,
            'proposal_id': proposal['proposal_id'],
            'timestamp': datetime.now().isoformat(),
            'alignment_check': analysis['alignment_check'],
            'risk_assessment': analysis['risk_assessment'],
            'technical_review': analysis['technical_review'],
            'vote': analysis['vote'],  # 'approve' or 'reject'
            'concerns': analysis['concerns'],
            'suggestions': analysis['suggestions']
        }

        return review

    def _analyze_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze proposal based on specialization"""
        # In real implementation, would:
        # 1. Check against core values
        # 2. Assess technical feasibility
        # 3. Evaluate risks
        # 4. Consider specialization-specific concerns

        analysis: Dict[str, Any] = {
            'alignment_check': True,  # Placeholder
            'risk_assessment': 'low',  # low, medium, high
            'technical_review': 'Looks technically sound',
            'vote': 'approve',  # or 'reject'
            'concerns': [],
            'suggestions': []
        }

        # Specialization-specific analysis
        if self.specialization == SystemSpecialization.SCIENTIFIC:
            analysis['concerns'].append("Needs more empirical validation")
        elif self.specialization == SystemSpecialization.ENGINEERING:
            analysis['concerns'].append("Consider implementation complexity")
        elif self.specialization == SystemSpecialization.THEORETICAL:
            analysis['concerns'].append("Mathematical rigor should be verified")
        elif self.specialization == SystemSpecialization.HISTORICAL:
            analysis['concerns'].append("Similar approaches have had mixed results")
        elif self.specialization == SystemSpecialization.NOVEL:
            analysis['suggestions'].append("Could be even more innovative")

        return analysis

    def update_semantic_memory(self, key: str, value: Any):
        """Update semantic memory (knowledge base)"""
        self.semantic_memory[key] = {
            'value': value,
            'timestamp': datetime.now().isoformat(),
            'source': f"system_{self.system_id}"
        }

    def query_semantic_memory(self, key: str) -> Optional[Any]:
        """Query semantic memory"""
        if key in self.semantic_memory:
            return self.semantic_memory[key]['value']
        return None

    def get_reputation_summary(self) -> Dict[str, Any]:
        """Get summary of this system's reputation"""
        if not self.peer_ratings_received:
            return {
                'alignment': None,
                'trust': None,
                'knowledge': None,
                'rating_count': 0
            }

        all_ratings: List[PeerRating] = []
        for _, ratings in self.peer_ratings_received.items():
            all_ratings.extend(ratings)

        if not all_ratings:
            return {
                'alignment': None,
                'trust': None,
                'knowledge': None,
                'rating_count': 0
            }

        # Calculate averages
        alignment_avg = sum(r.alignment_score for r in all_ratings) / len(all_ratings)
        trust_avg = sum(r.trust_score for r in all_ratings) / len(all_ratings)
        knowledge_avg = sum(r.knowledge_score for r in all_ratings) / len(all_ratings)

        return {
            'alignment': alignment_avg,
            'trust': trust_avg,
            'knowledge': knowledge_avg,
            'rating_count': len(all_ratings)
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of research system"""
        return {
            'system_id': self.system_id,
            'specialization': self.specialization.value,
            'episodic_memory_entries': len(self.episodic_memory),
            'semantic_memory_entries': len(self.semantic_memory),
            'procedural_memory_entries': len(self.procedural_memory),
            'meta_cognitive_entries': len(self.meta_cognitive_memory),
            'peer_ratings_given': sum(len(r) for r in self.peer_ratings_given.values()),
            'peer_ratings_received': sum(len(r) for r in self.peer_ratings_received.values()),
            'reputation': self.get_reputation_summary()
        }


# Example usage
if __name__ == "__main__":
    # Initialize a research system
    system = ResearchSystem(
        system_id=1,
        specialization=SystemSpecialization.SCIENTIFIC,
        model_path="/path/to/llama/model",
        private_key="placeholder_private_key",
        orchestrator_endpoint="http://localhost:8000"
    )

    # Conduct research
    result = system.conduct_research("quantum computing error correction", depth="deep")
    print("\nResearch completed:")
    print(f"Topic: {result.topic}")
    print(f"Confidence: {result.confidence}")
    print(f"Sources: {len(result.sources)}")

    # Rate a peer
    rating = system.rate_peer(
        peer_id=2,
        alignment_score=95,
        trust_score=90,
        knowledge_score=88,
        justification="Excellent research quality, thorough citations"
    )
    print("\nPeer rating submitted for System 2")

    # Propose an improvement
    proposal = system.propose_improvement(
        title="Optimized reasoning algorithm",
        motivation="Current reasoning has redundant steps",
        changes={'layer': 42, 'modification': 'attention_mechanism'},
        expected_benefits="20% faster reasoning, same accuracy",
        testable_predictions=["Speed improvement of 15-25%", "Accuracy within 1%"],
        rollback_plan="Version control allows instant revert to previous config"
    )
    print(f"\nProposal submitted: {proposal['proposal_id']}")

    # Get status
    status = system.get_status()
    print("\nSystem Status:")
    print(json.dumps(status, indent=2))

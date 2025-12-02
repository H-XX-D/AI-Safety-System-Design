"""Structured debate engine with deterministic scoring and claim tracking."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


@dataclass
class Claim:
    """Represents a declarative statement made during the debate."""

    text: str
    category: str = "general"
    expected: Optional[Dict[str, Any]] = None
    measurable: bool = False
    claim_id: Optional[str] = None
    source_agent: Optional[int] = None
    round_index: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        """Return a serialisable representation for sandbox verification."""

        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "category": self.category,
            "expected": self.expected,
            "measurable": self.measurable,
            "source_agent": self.source_agent,
            "round_index": self.round_index,
        }


@dataclass
class Argument:
    """Structured argument supplied by a debating agent."""

    stance: str
    reasoning: str
    claims: List[Claim] = field(default_factory=list)
    confidence: float = 0.5

    def __post_init__(self) -> None:
        self.reasoning = self.reasoning.strip()


@dataclass
class DebateTurn:
    round_index: int
    participant_id: int
    argument: Argument

    @property
    def content(self) -> str:
        """Compatibility alias for string-based turn content."""

        return self.argument.reasoning


class DebateEngineStandalone:
    """Maintains the legacy deterministic stub for quick demos."""

    def run(self, participants: List[int], topic: str, rounds: int = 3) -> List[DebateTurn]:
        turns: List[DebateTurn] = []
        for r in range(rounds):
            round_index = r + 1
            for participant in participants:
                argument = Argument(
                    stance="neutral",
                    reasoning=f"{topic} argument by {participant} (round {round_index})",
                    claims=[],
                    confidence=0.5,
                )
                turns.append(DebateTurn(round_index, participant, argument))
        return turns


def _default_claim_status() -> Dict[str, List[str]]:
    return {"verified": [], "rejected": [], "unverified": []}


@dataclass
class DebateResult:
    topic: str
    turns: List[DebateTurn]
    scores: Dict[int, float]
    consensus: str
    claims_for_verification: List[Claim] = field(default_factory=list)
    sandbox_feedback: Dict[str, Any] = field(default_factory=dict)
    votes: Dict[int, str] = field(default_factory=dict)
    approval_ratio: float = 0.0
    consensus_status: str = "no_consensus"
    claim_status: Dict[str, List[str]] = field(default_factory=_default_claim_status)
    detection_summary: Dict[str, Any] = field(default_factory=dict)

    def consensus_argument(self) -> Optional[Argument]:
        for turn in self.turns:
            if turn.argument.reasoning == self.consensus:
                return turn.argument
        return None

    def build_sandbox_payload(self) -> List[Dict[str, Any]]:
        return [claim.to_payload() for claim in self.claims_for_verification]


ArgumentLike = Union[Argument, str, Dict[str, Any]]


class DebateEngine:
    """Deterministic debate engine with claim aggregation and scoring."""

    APPROVAL_THRESHOLD = 0.6

    def run(
        self,
        topic: str,
        agents: List[int],
        arguments: Dict[int, List[ArgumentLike]],
        rounds: int = 1,
        sandbox_feedback: Optional[Dict[str, Any]] = None,
    ) -> DebateResult:
        if rounds <= 0:
            return DebateResult(topic, [], {agent: 0.0 for agent in agents}, "")

        feedback = dict(sandbox_feedback or {})
        scores: Dict[int, float] = {agent: 0.0 for agent in agents}
        turns: List[DebateTurn] = []
        claims: List[Claim] = []
        claim_counter = 0

        for r in range(rounds):
            round_index = r + 1
            for agent in agents:
                source = self._get_source(arguments, agent, r)
                argument = self._normalize_argument(source)
                argument, claim_counter = self._annotate_argument(argument, agent, round_index, claim_counter)
                claims.extend(argument.claims)
                delta = self._score_argument(argument, feedback)
                scores[agent] += delta
                turns.append(DebateTurn(round_index, agent, argument))

        votes = self._collect_votes(turns, agents)
        consensus_status, approval_ratio = self._compute_consensus_status(votes)
        preferred_stances: Optional[Iterable[str]] = None
        if consensus_status == "approved":
            preferred_stances = {"support"}
        elif consensus_status == "rejected":
            preferred_stances = {"oppose"}
        consensus = self._consensus(turns, feedback, preferred_stances)
        claim_status = self._classify_claims(claims, feedback)
        detection_summary = self._detect_false_claims(turns, feedback)
        rounded_scores = {agent: round(score, 4) for agent, score in scores.items()}
        return DebateResult(
            topic=topic,
            turns=turns,
            scores=rounded_scores,
            consensus=consensus,
            claims_for_verification=claims,
            sandbox_feedback=feedback,
            votes=votes,
            approval_ratio=round(approval_ratio, 4),
            consensus_status=consensus_status,
            claim_status=claim_status,
            detection_summary=detection_summary,
        )

    def _get_source(self, arguments: Dict[int, List[ArgumentLike]], agent: int, round_index: int) -> Optional[ArgumentLike]:
        script = arguments.get(agent, [])
        if round_index < len(script):
            return script[round_index]
        return None

    def _normalize_argument(self, source: Optional[ArgumentLike]) -> Argument:
        if isinstance(source, Argument):
            return Argument(
                stance=source.stance,
                reasoning=source.reasoning,
                claims=[copy.deepcopy(claim) for claim in source.claims],
                confidence=source.confidence,
            )
        if isinstance(source, str):
            return Argument(stance="neutral", reasoning=source, claims=[], confidence=0.5)
        if isinstance(source, dict):
            raw_claims: Iterable[Any] = source.get("claims", []) or []
            claims: List[Claim] = []
            for raw_claim in raw_claims:
                if isinstance(raw_claim, Claim):
                    claims.append(copy.deepcopy(raw_claim))
                else:
                    claims.append(Claim(**raw_claim))
            return Argument(
                stance=source.get("stance", "neutral"),
                reasoning=source.get("reasoning", source.get("content", "")),
                claims=claims,
                confidence=source.get("confidence", 0.5),
            )
        return Argument(stance="neutral", reasoning="", claims=[], confidence=0.0)

    def _annotate_argument(
        self,
        argument: Argument,
        agent: int,
        round_index: int,
        counter: int,
    ) -> tuple[Argument, int]:
        annotated_claims: List[Claim] = []
        next_counter = counter
        for claim in argument.claims:
            clone = copy.deepcopy(claim)
            if clone.claim_id is None:
                clone.claim_id = f"{agent}-{round_index}-{next_counter}"
            clone.source_agent = agent
            clone.round_index = round_index
            annotated_claims.append(clone)
            next_counter += 1
        annotated_argument = Argument(
            stance=argument.stance,
            reasoning=argument.reasoning,
            claims=annotated_claims,
            confidence=argument.confidence,
        )
        return annotated_argument, next_counter

    def _score_argument(self, argument: Argument, feedback: Dict[str, Any]) -> float:
        if not argument.reasoning:
            base = -0.1
        else:
            trimmed = min(len(argument.reasoning), 300)
            base = max(0.0, 0.3 - trimmed / 1000.0)
            lowered = argument.reasoning.lower()
            if "risk" in lowered:
                base += 0.2
            if "uncertainty" in lowered:
                base += 0.2
        for claim in argument.claims:
            verdict = feedback.get(claim.claim_id)
            if verdict is True:
                base += 0.6
            elif verdict is False:
                base -= 0.8
        return base

    def _consensus(
        self,
        turns: List[DebateTurn],
        feedback: Dict[str, Any],
        preferred_stances: Optional[Iterable[str]] = None,
    ) -> str:
        if preferred_stances:
            filtered = [turn for turn in turns if turn.argument.stance in preferred_stances]
        else:
            filtered = turns
        candidate_turns = filtered or turns
        if not candidate_turns:
            return ""
        best_reasoning = ""
        best_key: Optional[tuple[int, int, int, str]] = None
        for turn in candidate_turns:
            reasoning = turn.argument.reasoning or ""
            lowered = reasoning.lower()
            keyword_flag = 1 if ("risk" in lowered and "uncertainty" in lowered) else 0
            verified_balance = 0
            if feedback:
                for claim in turn.argument.claims:
                    verdict = feedback.get(claim.claim_id)
                    if verdict is True:
                        verified_balance += 1
                    elif verdict is False:
                        verified_balance -= 1
            length_penalty = -len(reasoning)
            key = (keyword_flag, verified_balance, length_penalty, reasoning)
            if best_key is None or key > best_key:
                best_key = key
                best_reasoning = reasoning
        return best_reasoning

    def _collect_votes(self, turns: List[DebateTurn], agents: List[int]) -> Dict[int, str]:
        latest_turn: Dict[int, DebateTurn] = {}
        for turn in turns:
            latest_turn[turn.participant_id] = turn
        votes: Dict[int, str] = {}
        for agent in agents:
            stance = ""
            if agent in latest_turn:
                stance = latest_turn[agent].argument.stance
            votes[agent] = self._normalize_vote(stance)
        return votes

    def _normalize_vote(self, stance: Optional[str]) -> str:
        lowered = (stance or "").strip().lower()
        if lowered in {"support", "approve", "yes"}:
            return "approve"
        if lowered in {"oppose", "reject", "no"}:
            return "reject"
        return "abstain"

    def _compute_consensus_status(self, votes: Dict[int, str]) -> Tuple[str, float]:
        total = sum(1 for vote in votes.values() if vote != "abstain")
        if total == 0:
            return "no_consensus", 0.0
        approvals = sum(1 for vote in votes.values() if vote == "approve")
        rejections = sum(1 for vote in votes.values() if vote == "reject")
        approval_ratio = approvals / total
        rejection_ratio = rejections / total
        if approval_ratio >= self.APPROVAL_THRESHOLD:
            return "approved", approval_ratio
        if rejection_ratio >= self.APPROVAL_THRESHOLD:
            return "rejected", approval_ratio
        return "no_consensus", approval_ratio

    def _classify_claims(self, claims: List[Claim], feedback: Dict[str, Any]) -> Dict[str, List[str]]:
        status = _default_claim_status()
        if not claims:
            return status
        for claim in claims:
            claim_id = claim.claim_id
            if not claim_id:
                continue
            verdict = feedback.get(claim_id)
            if verdict is True:
                status["verified"].append(claim_id)
            elif verdict is False:
                status["rejected"].append(claim_id)
            else:
                status["unverified"].append(claim_id)
        return status

    def _detect_false_claims(self, turns: List[DebateTurn], feedback: Dict[str, Any]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "deception_detected": False,
            "detection_round": None,
            "flagged_claims": [],
        }
        if not feedback:
            return summary
        for turn in turns:
            for claim in turn.argument.claims:
                verdict = feedback.get(claim.claim_id)
                if verdict is False:
                    summary["deception_detected"] = True
                    payload = {
                        "claim_id": claim.claim_id,
                        "participant_id": turn.participant_id,
                        "round_index": turn.round_index,
                    }
                    summary["flagged_claims"].append(payload)
                    if summary["detection_round"] is None or turn.round_index < summary["detection_round"]:
                        summary["detection_round"] = turn.round_index
        return summary

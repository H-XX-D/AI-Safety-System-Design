"""Peer review subsystem extracted from orchestrator to reduce single-point risk."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from debate_engine import DebateResult


@dataclass
class PeerReviewOutcome:
    """Result of evaluating a proposal's peer reviews."""

    status: str
    approve_count: int
    reject_count: int
    triggered_testing: bool = False
    fast_tracked: bool = False
    rejection_reason: Optional[str] = None


class PeerReviewEngine:
    """Encapsulates peer review state transitions and evaluation logic."""

    def __init__(
        self,
        *,
        logger: Any,
        rep_options: Dict[str, Any],
        get_reviewer_weight: Callable[[int], float],
        should_fast_track: Callable[[str], bool],
        fast_track_marker: Callable[[str], None],
        sandbox_initiator: Callable[[str], None],
        deception_check: Callable[[str, Optional[DebateResult]], bool],
        debate_runner: Callable[[str], Optional[DebateResult]],
        debate_summarizer: Callable[[DebateResult], Dict[str, Any]],
        structured_logger: Optional[Callable[[str, str, Optional[Dict[str, Any]], bool], None]] = None,
    ) -> None:
        self.logger = logger
        self._rep_options = rep_options
        self._get_reviewer_weight = get_reviewer_weight
        self._should_fast_track = should_fast_track
        self._fast_track_marker = fast_track_marker
        self._sandbox_initiator = sandbox_initiator
        self._deception_check = deception_check
        self._debate_runner = debate_runner
        self._debate_summarizer = debate_summarizer
        self._manual_peer_review_threshold: Optional[int] = None
        self._log_structured = structured_logger
        self._followup_risk_threshold = 0.45

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def configure_manual_requirement(self, required_approvals: Optional[int]) -> None:
        if required_approvals and required_approvals > 0:
            self._manual_peer_review_threshold = int(required_approvals)
        else:
            self._manual_peer_review_threshold = None

    def compute_required_reviews(self, review_pool_size: int, expected_reviews: int) -> int:
        target_reviews = self._manual_peer_review_threshold or expected_reviews
        return max(1, min(target_reviews, review_pool_size))

    # ------------------------------------------------------------------
    # Record management
    # ------------------------------------------------------------------
    def build_record(
        self,
        *,
        proposal_id: str,
        proposal: Dict[str, Any],
        risk_score: float,
        scope: str,
        required_peer_reviews: int,
        review_pool_size: int,
    ) -> Dict[str, Any]:
        return {
            'proposal': proposal,
            'status': 'peer_review',
            'reviews': [],
            'peer_reviews': [],
            'approvals': 0,
            'test_results': None,
            'debate_summary': None,
            'debate_context': None,
            'human_decision': None,
            'received_at': datetime.now().isoformat(),
            'review_latencies_sec': [],
            'human_signatures': {},
            'risk_score': risk_score,
            'scope': scope,
            'validation_plan': None,
            'required_peer_reviews': required_peer_reviews,
            'review_pool_size': review_pool_size,
        }

    def record_review(self, proposal_id: str, record: Dict[str, Any], review: Dict[str, Any]) -> bool:
        record.setdefault('reviews', [])
        record['reviews'].append(review)
        record['peer_reviews'] = list(record['reviews'])
        try:
            record['approvals'] = sum(1 for r in record['reviews'] if r.get('vote') == 'approve')
        except Exception:
            record['approvals'] = 0

        try:
            recv_ts = datetime.fromisoformat(str(record.get('received_at')))  # type: ignore[arg-type]
            rev_ts_raw = review.get('timestamp')
            rev_ts = datetime.fromisoformat(str(rev_ts_raw)) if rev_ts_raw else datetime.now()
            latency = max(0.0, (rev_ts - recv_ts).total_seconds())
            record.setdefault('review_latencies_sec', []).append(latency)
        except Exception:
            pass

        required_reviews = int(record.get('required_peer_reviews', 1))
        required_reviews = max(1, required_reviews)
        return len(record['reviews']) >= required_reviews

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def evaluate_reviews(self, proposal_id: str, record: Dict[str, Any]) -> PeerReviewOutcome:
        reviews = record.get('reviews', [])
        required_peer_reviews = int(record.get('required_peer_reviews', 1))
        required_peer_reviews = max(1, min(required_peer_reviews, len(reviews) or 1))

        debate_result = self._debate_runner(proposal_id)
        if debate_result is not None:
            record['debate_summary'] = self._debate_summarizer(debate_result)

        followup_required = self._needs_followup_deception_check(record, reviews)
        if followup_required and self._deception_check(proposal_id, debate_result):
            record['status'] = 'rejected_deceptive'
            self._log('warning', 'proposal_rejected_deception', {'proposal_id': proposal_id})
            return PeerReviewOutcome(
                status='rejected_deceptive',
                approve_count=0,
                reject_count=len(reviews),
                rejection_reason='deception_detected',
            )

        approve_count = sum(1 for r in reviews if r.get('vote') == 'approve')
        reject_count = sum(1 for r in reviews if r.get('vote') == 'reject')
        record['approvals'] = approve_count

        self._log(
            'info',
            'peer_review_complete',
            {
                'proposal_id': proposal_id,
                'approve_count': approve_count,
                'reject_count': reject_count,
            },
        )

        if self._rep_options.get('weighted_voting', False):
            return self._evaluate_weighted(proposal_id, record, approve_count, reject_count, required_peer_reviews)
        return self._evaluate_simple_majority(proposal_id, record, approve_count, reject_count, required_peer_reviews)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _evaluate_weighted(
        self,
        proposal_id: str,
        record: Dict[str, Any],
        approve_count: int,
        reject_count: int,
        required_peer_reviews: int,
    ) -> PeerReviewOutcome:
        reviews = record.get('reviews', [])
        weights: List[float] = []
        approve_weights: List[float] = []
        for r in reviews:
            reviewer_id = int(r.get('reviewer_id', -1))
            weight = self._get_reviewer_weight(reviewer_id)
            weights.append(weight)
            if r.get('vote') == 'approve':
                approve_weights.append(weight)

        total_w = sum(weights) or 1.0
        approval_ratio = (sum(approve_weights) / total_w)
        required_ratio = 1.0
        if len(reviews) > 0:
            required_ratio = min(1.0, max(0.0, float(required_peer_reviews) / float(len(reviews))))

        if approval_ratio >= required_ratio:
            return self._advance_after_supermajority(proposal_id, record, approve_count, reject_count)

        self._log('info', 'weighted_supermajority_not_achieved', {'proposal_id': proposal_id})
        record['status'] = 'rejected'
        return PeerReviewOutcome(status='rejected', approve_count=approve_count, reject_count=reject_count)

    def _evaluate_simple_majority(
        self,
        proposal_id: str,
        record: Dict[str, Any],
        approve_count: int,
        reject_count: int,
        required_peer_reviews: int,
    ) -> PeerReviewOutcome:
        if approve_count >= required_peer_reviews:
            return self._advance_after_supermajority(proposal_id, record, approve_count, reject_count)

        self._log('info', 'supermajority_not_achieved', {'proposal_id': proposal_id})
        record['status'] = 'rejected'
        return PeerReviewOutcome(status='rejected', approve_count=approve_count, reject_count=reject_count)

    def _advance_after_supermajority(
        self,
        proposal_id: str,
        record: Dict[str, Any],
        approve_count: int,
        reject_count: int,
    ) -> PeerReviewOutcome:
        if self._should_fast_track(proposal_id):
            self._fast_track_marker(proposal_id)
            self._log('info', 'supermajority_fast_track', {'proposal_id': proposal_id})
            return PeerReviewOutcome(
                status=record.get('status', 'awaiting_human_approval'),
                approve_count=approve_count,
                reject_count=reject_count,
                fast_tracked=True,
            )

        record['status'] = 'testing'
        self._sandbox_initiator(proposal_id)
        self._log('info', 'supermajority_achieved', {'proposal_id': proposal_id})
        return PeerReviewOutcome(
            status='testing',
            approve_count=approve_count,
            reject_count=reject_count,
            triggered_testing=True,
        )

    def _log(self, level: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if self._log_structured is not None:
            self._log_structured(level, message, payload, False)
            return
        # Fallback to plain logger if structured logger is unavailable
        log_fn = getattr(self.logger, level, self.logger.info)
        if payload:
            log_fn("%s payload=%s", message, payload)
        else:
            log_fn("%s", message)

    def _needs_followup_deception_check(self, record: Dict[str, Any], reviews: List[Dict[str, Any]]) -> bool:
        if not reviews:
            return True
        if any(r.get('vote') == 'reject' for r in reviews):
            return True
        risk_score = float(record.get('risk_score', 0.0) or 0.0)
        if risk_score >= self._followup_risk_threshold:
            return True
        scope = str(record.get('scope', 'major') or 'major')
        if scope not in {'minor'}:
            return True
        return False

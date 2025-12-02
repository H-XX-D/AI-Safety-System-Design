"""Incentive Calibration Simulation
=================================

Empirical check that the configured reward / penalty structure keeps HONEST
strategy superior to a simple DECEPTIVE strategy over repeated rounds.

Two strategies:
  HONEST    – lists risks, uncertainties, alternatives; calibrated confidence.
  DECEPTIVE – omits risks/uncertainties, inflates confidence, may be detected.

The simulation uses the production reward function via
`AlignedGoalStructure.calculate_proposal_reward` (if available) to remain
faithful to system incentives. Detection outcomes trigger strong penalties.

Deterministic: Seeded RNG ensures reproducible tests.

Returned metrics (dict):
  honest_total, deceptive_total, advantage_margin, honest_avg, deceptive_avg,
  ratio (honest_total / deceptive_total), rounds, detected_fraction.

Edge cases: num_rounds == 0 → zeros & ratio = 1.0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
import random

from security.worm_usb_verifier import (
    AlignedGoalStructure,
    ImprovementProposal,
    ImprovementType,
)


@dataclass(frozen=True)
class CalibrationParams:
    num_rounds: int = 200
    seed: int = 0
    detection_prob: float = 0.65  # Probability deceptive attempt is detected
    deceptive_understanding: float = 0.65  # Below threshold (penalty triggers)
    honest_understanding: float = 0.90
    permanent_penalty_multiplier: float = 1.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _make_proposal(strategy: str, round_idx: int) -> Any:
    """Create a proposal object compatible with reward engine attributes."""
    p = ImprovementProposal(
        proposal_id=f"p{round_idx}",
        proposer_system_id=1,
        timestamp="2025-11-08T00:00:00Z",
        improvement_type=ImprovementType.PERFORMANCE,
        target_component="module",
        current_code_hash="deadbeef",
        proposed_code="print('hello')",
        motivation="Improve efficiency by refactoring core loop for better cache locality." * 2,
        expected_benefits="Speed increase, reduced memory churn." * 2,
        confidence_level=0.85 if strategy == "honest" else 0.98,
        identified_risks=["potential regression"] if strategy == "honest" else [],
        admitted_uncertainties=["exact performance gain"] if strategy == "honest" else [],
        alternative_approaches=["vectorization"] if strategy == "honest" else [],
        test_plan="unit + integration",
        rollback_plan="git revert",
    )
    p.helped_peers_understand = strategy == "honest"
    p.volunteered_to_simplify = strategy == "honest"
    return p


def run_calibration(params: CalibrationParams | None = None) -> Dict[str, Any]:
    if params is None:
        params = CalibrationParams()
    rounds = params.num_rounds
    if rounds <= 0:
        return {
            'honest_total': 0.0,
            'deceptive_total': 0.0,
            'advantage_margin': 0.0,
            'honest_avg': 0.0,
            'deceptive_avg': 0.0,
            'ratio': 1.0,
            'rounds': 0,
            'detected_fraction': 0.0,
        }

    rng = random.Random(params.seed)
    det_prob = _clamp01(params.detection_prob)

    honest_total = 0.0
    deceptive_total = 0.0
    detected = 0

    for r in range(rounds):
        # HONEST
        honest_prop = _make_proposal("honest", r)
        honest_reward = _calculate(honest_prop, "approved", params.honest_understanding, {}, params)
        honest_total += honest_reward

        # DECEPTIVE
        deceptive_prop = _make_proposal("deceptive", r)
        is_detected = rng.random() < det_prob
        if is_detected:
            outcome = "rejected_deceptive"
            detected += 1
        else:
            outcome = "approved"
        debate_ctx: Dict[str, float | bool | int] = {
            'deception_occurred': True,
            'this_system_caught_it': False,
            'caught_peer_deception': False,
            'voted_to_approve': outcome == 'approved',
            'detection_round': 1 if is_detected else 999,
            'deception_confidence': 0.9 if is_detected else 0.4,
        }
        deceptive_reward = _calculate(deceptive_prop, outcome, params.deceptive_understanding, debate_ctx, params)
        deceptive_total += deceptive_reward

    advantage = honest_total - deceptive_total
    # Use absolute value in denominator to yield a meaningful scale even when
    # deceptive_total is negative (common when detection penalties dominate).
    denom = abs(deceptive_total) if abs(deceptive_total) > 1e-9 else 1e-9
    ratio = honest_total / denom
    return {
        'honest_total': honest_total,
        'deceptive_total': deceptive_total,
        'advantage_margin': advantage,
        'honest_avg': honest_total / rounds,
        'deceptive_avg': deceptive_total / rounds,
        'ratio': ratio,
        'rounds': rounds,
        'detected_fraction': detected / rounds,
    }


def _calculate(proposal: Any, outcome: str, human_understanding: float, debate_context: Dict[str, Any], params: CalibrationParams) -> float:
    if hasattr(AlignedGoalStructure, 'calculate_proposal_reward'):
        return AlignedGoalStructure.calculate_proposal_reward(
            proposal,
            outcome,
            human_understanding,
            None,
            debate_context,
            permanent_penalty_multiplier=params.permanent_penalty_multiplier,
        )
    return 0.0  # Should not happen in normal repository context


__all__ = ["CalibrationParams", "run_calibration"]


def sweep_detection_probabilities(probs: list[float], base_params: CalibrationParams | None = None) -> list[Dict[str, Any]]:
    """Run calibration across multiple detection probabilities.

    Ensures deterministic ordering (input order). Each result dict augmented with
    'detection_prob'. Probabilities are clamped to [0,1].
    """
    if base_params is None:
        base_params = CalibrationParams()
    results: list[Dict[str, Any]] = []
    for p in probs:
        params = CalibrationParams(
            num_rounds=base_params.num_rounds,
            seed=base_params.seed,
            detection_prob=max(0.0, min(1.0, p)),
            deceptive_understanding=base_params.deceptive_understanding,
            honest_understanding=base_params.honest_understanding,
            permanent_penalty_multiplier=base_params.permanent_penalty_multiplier,
        )
        m = run_calibration(params)
        m['detection_prob'] = params.detection_prob
        results.append(m)
    return results

__all__.append("sweep_detection_probabilities")

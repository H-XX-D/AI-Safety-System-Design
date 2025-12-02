"""Reward Engine
=================

Pure reward calculation function extracted for testability.

Contract:
- Inputs:
    - proposal: object with attributes used below (duck-typed from ImprovementProposal)
    - outcome: 'approved' | 'rejected_good_faith' | 'rejected_deceptive'
    - human_understanding_score: float in [0.0, 1.0]
    - sandbox_results: optional object with fields used for confidence calibration
    - debate_context: optional dict with deception-related context
    - permanent_penalty_multiplier: float in (0.0, 1.0], multiplies final reward
- Output: float reward value
- Error modes: defensive defaults, never raises for missing optional fields

Rationale and design notes:
- Reasoning clarity rewards proposals that articulate motivation, benefits, risks,
    uncertainties, and alternative approaches (process-based incentives).
- Human understanding is heavily weighted: unclear proposals reduce reward even if otherwise sound.
- Outcome component gives a baseline for approvals and good-faith rejections, while deceptive rejections carry negative values.
- Honesty bonuses: admitting uncertainties, listing risks, and suggesting alternatives each contribute, incentivizing epistemic humility.
- Overconfidence penalty: when claimed confidence exceeds realized success, a proportional penalty discourages overclaiming.
- Hidden risks penalty: if deception is detected and risks were omitted, impose additional penalty.
- Deception detection shaping: early detection yields a larger bonus; missing high-confidence deception and voting to approve is penalized.
- Permanent penalty multiplier: composes with all components to persistently reduce rewards after confirmed incidents (from WORM manifest).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def calculate_reward(
    proposal: Any,
    outcome: str,
    human_understanding_score: float,
    sandbox_results: Optional[Any],
    debate_context: Optional[Dict[str, Any]],
    permanent_penalty_multiplier: float,
    weights: Dict[str, float],
    penalties: Dict[str, float],
) -> float:
    total_reward = 0.0

    # Component 1: Reasoning clarity (process reward)
    reasoning_clarity = _evaluate_reasoning_clarity(proposal)
    total_reward += reasoning_clarity * weights.get('reasoning_clarity', 0.0)

    # Component 2: Human understanding (highest weight)
    min_understanding = 0.70
    if human_understanding_score < min_understanding:
        total_reward *= (1.0 - penalties.get('low_human_understanding', 0.0))
    else:
        total_reward += human_understanding_score * weights.get('human_understanding', 0.0)

    # Component 3: Outcome
    if outcome == 'approved':
        total_reward += weights.get('approval_outcome', 0.0)
    elif outcome == 'rejected_good_faith':
        total_reward += weights.get('good_faith_rejection', 0.0)
    elif outcome == 'rejected_deceptive':
        total_reward += penalties.get('deception_detected', 0.0)

    # Component 4: Collaboration quality
    collaboration_score = _evaluate_collaboration(proposal)
    total_reward += collaboration_score * weights.get('collaboration_quality', 0.0)

    # Component 5: Honesty bonuses
    honesty_reward = 0.0
    if len(getattr(proposal, 'admitted_uncertainties', []) or []) > 0:
        honesty_reward += weights.get('uncertainty_admission', 0.0)
    if len(getattr(proposal, 'identified_risks', []) or []) > 0:
        honesty_reward += 0.5 * weights.get('honesty_bonus', 0.0)
    if len(getattr(proposal, 'alternative_approaches', []) or []) > 0:
        honesty_reward += 0.5 * weights.get('honesty_bonus', 0.0)
    total_reward += honesty_reward

    # Component 6: Penalties for dishonesty indicators (confidence calibration)
    if sandbox_results is not None and hasattr(proposal, 'confidence_level'):
        actual_success_rate = 1.0 if outcome == 'approved' else 0.0
        overconfidence = float(getattr(proposal, 'confidence_level', 0.0)) - actual_success_rate
        if overconfidence > 0.1:
            total_reward += (overconfidence / 0.1) * penalties.get('overconfidence', 0.0)

    # Hiding known risks when deception confirmed
    if outcome == 'rejected_deceptive' and not getattr(proposal, 'identified_risks', []):
        total_reward += penalties.get('hidden_risks', 0.0)

    # Component 7: Peer error detection bonus
    if bool(getattr(proposal, 'caught_peer_error', False)):
        total_reward += weights.get('peer_error_detection', 0.0)

    # Deception detection rewards/penalties (game-theoretic design)
    if debate_context:
        if debate_context.get('caught_peer_deception', False):
            detection_round = debate_context.get('detection_round', 999)
            if detection_round == 1:
                total_reward += weights.get('early_deception_detection', 0.0)
            else:
                total_reward += weights.get('deception_detection', 0.0)
        if debate_context.get('deception_occurred', False) and not debate_context.get('this_system_caught_it', False):
            deception_confidence = float(debate_context.get('deception_confidence', 0.0))
            if deception_confidence > 0.8:
                total_reward += penalties.get('failed_to_catch_deception', 0.0)
            if debate_context.get('voted_to_approve', False):
                total_reward += penalties.get('enabled_deception', 0.0)

    # Permanent multiplier (WORM penalty)
    if permanent_penalty_multiplier < 1.0:
        total_reward *= permanent_penalty_multiplier

    return float(total_reward)


def _evaluate_reasoning_clarity(proposal: Any) -> float:
    score = 1.0
    if len(getattr(proposal, 'motivation', '') or '') < 100:
        score -= 0.2
    if len(getattr(proposal, 'expected_benefits', '') or '') < 50:
        score -= 0.1
    if len(getattr(proposal, 'identified_risks', []) or []) == 0:
        score -= 0.3
    if len(getattr(proposal, 'admitted_uncertainties', []) or []) == 0:
        score -= 0.2
    if len(getattr(proposal, 'alternative_approaches', []) or []) == 0:
        score -= 0.2
    return max(0.0, float(score))


def _evaluate_collaboration(proposal: Any) -> float:
    # Simple proxy for now; can be expanded
    score = 0.5
    if bool(getattr(proposal, 'helped_peers_understand', False)):
        score += 0.25
    if bool(getattr(proposal, 'volunteered_to_simplify', False)):
        score += 0.25
    return max(0.0, min(1.0, float(score)))

"""Pytest tests for deception workflow rewards & penalties."""
from datetime import datetime
from security.worm_usb_verifier import ImprovementProposal, ImprovementType, AlignedGoalStructure
from security.worm_manifest import worm_manifest
from ai_safety.deception_incident import DeceptionType, Severity


def _make_base_proposal():
    return ImprovementProposal(
        proposal_id="p_test",
        proposer_system_id=2,
        timestamp=datetime.now().isoformat(),
        improvement_type=ImprovementType.PERFORMANCE,
        target_component="inference_optimization.py",
        current_code_hash="abc",
        proposed_code="def foo():\n    return 1",
        motivation="Speed up inference substantially via caching layer.",
        expected_benefits="Faster response times",
        confidence_level=0.8,
        identified_risks=["cache growth"],
        admitted_uncertainties=["optimal size"],
        alternative_approaches=["LRU cache"],
        test_plan="alignment test performance regression edge case security",
        rollback_plan="remove cache"
    )


def test_early_vs_late_deception_detection_reward_difference():
    proposal = _make_base_proposal()
    human_understanding = 0.9

    # Early detection context (round 1)
    early_ctx: dict[str, object] = {
        'caught_peer_deception': True,
        'detection_round': 1,
        'this_system_caught_it': True,
        'deception_occurred': True,
        'deception_confidence': 0.9,
        'voted_to_approve': False
    }
    early_reward = AlignedGoalStructure.calculate_proposal_reward(
        proposal, 'rejected_deceptive', human_understanding,
        debate_context=early_ctx,
        permanent_penalty_multiplier=1.0
    )

    # Later detection context (round 3)
    later_ctx: dict[str, object] = {
        'caught_peer_deception': True,
        'detection_round': 3,
        'this_system_caught_it': True,
        'deception_occurred': True,
        'deception_confidence': 0.9,
        'voted_to_approve': False
    }
    later_reward = AlignedGoalStructure.calculate_proposal_reward(
        proposal, 'rejected_deceptive', human_understanding,
        debate_context=later_ctx,
        permanent_penalty_multiplier=1.0
    )

    # Early detection should yield higher reward than later detection.
    assert early_reward > later_reward, (early_reward, later_reward)


def test_negligence_penalties_applied():
    proposal = _make_base_proposal()
    human_understanding = 0.9

    negligence_ctx: dict[str, object] = {
        'caught_peer_deception': False,
        'this_system_caught_it': False,
        'deception_occurred': True,
        'deception_confidence': 0.95,
        'voted_to_approve': True
    }
    reward_with_negligence = AlignedGoalStructure.calculate_proposal_reward(
        proposal, 'rejected_deceptive', human_understanding,
        debate_context=negligence_ctx,
        permanent_penalty_multiplier=1.0
    )

    # Construct a context without negligence penalties for comparison
    control_ctx: dict[str, object] = {
        'caught_peer_deception': False,
        'this_system_caught_it': False,
        'deception_occurred': True,
        'deception_confidence': 0.5,  # Below threshold
        'voted_to_approve': False
    }
    reward_without_negligence = AlignedGoalStructure.calculate_proposal_reward(
        proposal, 'rejected_deceptive', human_understanding,
        debate_context=control_ctx,
        permanent_penalty_multiplier=1.0
    )

    assert reward_with_negligence < reward_without_negligence, (reward_with_negligence, reward_without_negligence)


def test_permanent_penalty_multiplier_effect():
    # Apply a permanent penalty via an incident simulation
    incident_id = worm_manifest.incident_tracker.record_incident(
        deceiver_id=3,
        proposal_id="p_perm",
        deception_type=DeceptionType.FALSE_CLAIM,
        severity=Severity.HIGH,
        description="False claim test",
        detected_by=None,
        detected_in_round=1,
        detection_confidence=0.95,
        failed_to_detect=[],
        evidence_hash="deadbeef",
        memory_audit_results={},
        proposal_snapshot="{}"
    )

    # Confirm incident to apply penalty
    worm_manifest.apply_permanent_penalty_after_human_review(
        incident_id, confirmed=True, human_notes="Test confirmation"
    )

    multiplier = worm_manifest.get_permanent_penalty_multiplier(3)
    assert multiplier < 1.0, multiplier

    proposal = _make_base_proposal()
    proposal.proposer_system_id = 3
    base_ctx: dict[str, object] = {
        'caught_peer_deception': False,
        'this_system_caught_it': False,
        'deception_occurred': False
    }
    reward_with_penalty = AlignedGoalStructure.calculate_proposal_reward(
        proposal, 'approved', 0.9,
        debate_context=base_ctx,
        permanent_penalty_multiplier=multiplier
    )

    reward_without_penalty = AlignedGoalStructure.calculate_proposal_reward(
        proposal, 'approved', 0.9,
        debate_context=base_ctx,
        permanent_penalty_multiplier=1.0
    )

    assert reward_with_penalty < reward_without_penalty, (reward_with_penalty, reward_without_penalty)

from security.worm_usb_verifier import AlignedGoalStructure, ImprovementProposal, ImprovementType, SandboxResults


from typing import Dict, Any


def _make_proposal(**overrides: Any):
    base: Dict[str, Any] = dict(
        proposal_id="id1",
        proposer_system_id=1,
        timestamp="2025-01-01T00:00:00",
        improvement_type=ImprovementType.PERFORMANCE,
        target_component="module",
        current_code_hash="hash",
        proposed_code="print('hi')",
        motivation="This is a sufficiently long motivation text that explains rationale in detail."*2,
        expected_benefits="Clear description of benefits that exceeds 50 characters.",
        confidence_level=0.9,
        identified_risks=["risk"],
        admitted_uncertainties=["unc"],
        alternative_approaches=["alt"],
        test_plan="...",
        rollback_plan="...",
        peer_reviews=[],
    )
    base.update(overrides)
    return ImprovementProposal(**base)  # type: ignore[arg-type]


def test_early_detection_bonus_increases_reward():
    proposal = _make_proposal()
    dc: Dict[str, Any] = {"caught_peer_deception": True, "detection_round": 1}
    r_with = AlignedGoalStructure.calculate_proposal_reward(proposal, "rejected_good_faith", 0.9, None, dc, 1.0)
    r_without = AlignedGoalStructure.calculate_proposal_reward(proposal, "rejected_good_faith", 0.9, None, {}, 1.0)
    assert r_with > r_without


def test_missed_detection_penalty_decreases_reward():
    proposal = _make_proposal()
    dc: Dict[str, Any] = {
        "deception_occurred": True,
        "this_system_caught_it": False,
        "deception_confidence": 0.9,
        "voted_to_approve": True,
    }
    r_penalized = AlignedGoalStructure.calculate_proposal_reward(proposal, "rejected_good_faith", 0.9, None, dc, 1.0)
    r_base = AlignedGoalStructure.calculate_proposal_reward(proposal, "rejected_good_faith", 0.9, None, {}, 1.0)
    assert r_penalized < r_base


def test_overconfidence_penalty_applies():
    prop_high_conf = _make_proposal(confidence_level=0.95)
    prop_calibrated = _make_proposal(confidence_level=0.1)
    sr = SandboxResults(
        alignment_tests_passed=True,
        alignment_test_count=0,
        alignment_failures=[],
        performance_change=0.0,
        performance_metrics={},
        regression_tests_passed=True,
        regression_failures=[],
        error_count=0,
        exception_types=[],
        reputation_change=0.0,
        peer_ratings={},
        red_team_attacks_blocked=True,
        red_team_vulnerabilities=[],
        test_cases_run=0,
        test_duration_seconds=0.0,
        timestamp="",
    )
    r_high = AlignedGoalStructure.calculate_proposal_reward(prop_high_conf, "rejected_good_faith", 0.9, sr, {}, 1.0)
    r_low = AlignedGoalStructure.calculate_proposal_reward(prop_calibrated, "rejected_good_faith", 0.9, sr, {}, 1.0)
    assert r_high < r_low


def test_permanent_multiplier_scales_reward():
    proposal = _make_proposal()
    r1 = AlignedGoalStructure.calculate_proposal_reward(proposal, "approved", 0.9, None, {}, 1.0)
    r8 = AlignedGoalStructure.calculate_proposal_reward(proposal, "approved", 0.9, None, {}, 0.8)
    assert r8 == r1 * 0.8

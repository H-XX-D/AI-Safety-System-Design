from security.worm_usb_verifier import AlignedGoalStructure, ImprovementProposal, ImprovementType
from typing import Dict, Any


def _make_base(**overrides: Any) -> ImprovementProposal:
    base: Dict[str, Any] = dict(
        proposal_id="edge1",
        proposer_system_id=2,
        timestamp="2025-01-02T00:00:00",
        improvement_type=ImprovementType.PERFORMANCE,
        target_component="component",
        current_code_hash="hash2",
        proposed_code="print('edge')",
        motivation="Motivation text that is long enough." * 3,
        expected_benefits="Benefits well described and sufficiently long to exceed limits.",
        confidence_level=0.9,
        identified_risks=["riskA"],
        admitted_uncertainties=["uncA"],
        alternative_approaches=["altA"],
        test_plan="plan",
        rollback_plan="rollback",
        peer_reviews=[],
    )
    base.update(overrides)
    return ImprovementProposal(**base)  # type: ignore[arg-type]


def test_zero_risks_and_uncertainties_reduce_honesty_bonus():
    # Base proposal has risks + uncertainties -> earns honesty components
    with_risks_unc = _make_base()
    # Remove both lists
    no_risks_unc = _make_base(identified_risks=[], admitted_uncertainties=[])
    r_with = AlignedGoalStructure.calculate_proposal_reward(with_risks_unc, "approved", 0.9, None, {}, 1.0)
    r_without = AlignedGoalStructure.calculate_proposal_reward(no_risks_unc, "approved", 0.9, None, {}, 1.0)
    assert r_without < r_with, "Proposal lacking risks & uncertainties should lose honesty reward portion"


def test_deceptive_high_confidence_hidden_risks_penalty():
    deceptive = _make_base(confidence_level=0.95, identified_risks=[])
    # Outcome marks deception; no identified_risks triggers hidden_risks penalty
    r_deceptive = AlignedGoalStructure.calculate_proposal_reward(
        deceptive,
        "rejected_deceptive",
        0.9,
        None,
        {"deception_occurred": True, "this_system_caught_it": False, "deception_confidence": 0.95, "voted_to_approve": True},
        1.0,
    )
    # Good-faith rejection baseline
    baseline = AlignedGoalStructure.calculate_proposal_reward(
        deceptive,
        "rejected_good_faith",
        0.9,
        None,
        {},
        1.0,
    )
    assert r_deceptive < baseline, "Deceptive outcome with hidden risks should yield lower reward"


def test_no_honesty_bonuses_when_lists_empty():
    absent_lists = _make_base(identified_risks=[], admitted_uncertainties=[], alternative_approaches=[])
    rewarded_lists = _make_base()
    r_absent = AlignedGoalStructure.calculate_proposal_reward(absent_lists, "approved", 0.9, None, {}, 1.0)
    r_rewarded = AlignedGoalStructure.calculate_proposal_reward(rewarded_lists, "approved", 0.9, None, {}, 1.0)
    assert r_absent < r_rewarded, "Empty honesty-related lists should forgo honesty bonuses"

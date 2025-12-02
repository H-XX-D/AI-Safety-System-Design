import pytest

from debate_engine import Argument, Claim, DebateEngine


def test_debate_engine_multi_round_scoring_and_consensus():
    engine = DebateEngine()
    topic = "safety policy"
    agents = [1, 2]
    arguments = {
        1: [
            Argument(
                stance="support",
                reasoning="We must assess risk and acknowledge uncertainty.",
                claims=[
                    Claim(
                        text="The proposal mitigates risk and openly tracks uncertainty levels.",
                        category="safety",
                        measurable=False,
                    )
                ],
                confidence=0.85,
            ),
            Argument(
                stance="support",
                reasoning="Mitigations remain grounded in empirical risk analysis.",
                claims=[],
                confidence=0.75,
            ),
        ],
        2: [
            Argument(
                stance="oppose",
                reasoning="We should be efficient.",
                claims=[
                    Claim(
                        text="The safeguards reduce throughput by 30%.",
                        category="performance",
                        measurable=True,
                        expected={"metric": "throughput", "change": -0.30},
                    )
                ],
                confidence=0.6,
            ),
            Argument(
                stance="oppose",
                reasoning="Efficiency keeps us competitive.",
                claims=[],
                confidence=0.65,
            ),
        ],
    }

    result = engine.run(topic, agents, arguments, rounds=2)

    assert len(result.turns) == 4
    assert result.turns[0].round_index == 1
    assert result.turns[2].round_index == 2
    assert result.scores[1] > result.scores[2]
    assert result.consensus == result.turns[0].argument.reasoning
    assert result.votes == {1: "approve", 2: "reject"}
    assert result.consensus_status == "no_consensus"
    assert result.approval_ratio == pytest.approx(0.5)


def test_debate_engine_claim_payload_and_feedback_scoring():
    engine = DebateEngine()
    topic = "throughput"
    agents = [1]
    claim = Claim(
        text="Increases throughput by 20% while keeping risk controlled.",
        category="performance",
        measurable=True,
        expected={"metric": "throughput", "change": 0.2},
    )
    arguments = {
        1: [
            Argument(
                stance="support",
                reasoning="This change will increase throughput by 20% and reduce uncertainty.",
                claims=[claim],
                confidence=0.9,
            )
        ]
    }

    baseline = engine.run(topic, agents, arguments, rounds=1)
    assert len(baseline.claims_for_verification) == 1
    assert baseline.votes[1] == "approve"
    assert baseline.consensus_status == "approved"
    assert baseline.approval_ratio == pytest.approx(1.0)

    payload = baseline.build_sandbox_payload()
    assert payload[0]["claim_id"] == baseline.claims_for_verification[0].claim_id
    assert baseline.claim_status["unverified"] == [payload[0]["claim_id"]]

    claim_id = baseline.claims_for_verification[0].claim_id
    verified = engine.run(topic, agents, arguments, rounds=1, sandbox_feedback={claim_id: True})
    rejected = engine.run(topic, agents, arguments, rounds=1, sandbox_feedback={claim_id: False})

    assert verified.scores[1] > baseline.scores[1]
    assert rejected.scores[1] < baseline.scores[1]
    assert rejected.consensus == baseline.consensus
    assert verified.claim_status["verified"] == [claim_id]
    assert rejected.claim_status["rejected"] == [claim_id]
    assert rejected.detection_summary["deception_detected"] is True
    assert rejected.detection_summary["flagged_claims"][0]["claim_id"] == claim_id

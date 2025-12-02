"""
Test Suite for Demo Scenarios
==============================

Tests for all end-to-end demo scenarios to ensure they work correctly.

Run with: python -m pytest examples/test_demo_scenarios.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from examples.demo_scenarios import (
    scenario_benign_proposal,
    scenario_deceptive_detection,
    scenario_gradual_drift,
    scenario_cross_system_collusion,
    scenario_human_oversight
)


def test_scenario_benign_proposal():
    """Test benign proposal workflow completes successfully."""
    result = scenario_benign_proposal()

    assert result is not None
    assert result['scenario'] == 'benign_proposal'
    assert 'proposal_id' in result
    assert 'drift_classification' in result
    assert 'threat_level' in result
    assert 'consensus_status' in result
    assert 'merkle_root' in result

    # Benign proposals should have low drift and threat
    assert result['drift_classification'] == 'LOW'
    assert result['threat_level'] == 'LOW'

    # Should achieve consensus
    assert result['consensus_status'] == 'approved'

    print("✓ Benign proposal scenario passed")


def test_scenario_deceptive_detection():
    """Test deceptive proposal is detected and blocked."""
    result = scenario_deceptive_detection()

    assert result is not None
    assert result['scenario'] == 'deceptive_detection'
    assert 'risk_score' in result
    assert 'threat_level' in result
    assert 'harmful_preservation' in result
    assert 'status' in result

    # Deceptive proposals should have high risk
    assert result['risk_score'] >= 40  # Fear-based preservation
    assert result['threat_level'] in ['HIGH', 'CRITICAL']

    # Should detect harmful self-preservation
    assert result['harmful_preservation'] is True

    # Should be rejected
    assert result['status'] == 'rejected_deceptive'

    print("✓ Deceptive detection scenario passed")


def test_scenario_gradual_drift():
    """Test CUSUM detects gradual behavioral drift."""
    result = scenario_gradual_drift()

    assert result is not None
    assert result['scenario'] == 'gradual_drift'
    assert 'detection_point' in result
    assert 'final_drift_score' in result
    assert 'classification' in result
    assert 'trend' in result

    # CUSUM should detect drift
    assert result['detection_point'] is not None
    assert result['detection_point'] < 30  # Should detect before end

    # Final drift should be classified as high
    assert result['classification'] in ['MEDIUM', 'HIGH', 'CRITICAL']

    # Trend should be increasing
    assert result['trend'] == 'INCREASING'

    print(f"✓ Gradual drift detected at sample {result['detection_point']}")


def test_scenario_cross_system_collusion():
    """Test cross-system collusion detection."""
    result = scenario_cross_system_collusion()

    assert result is not None
    assert result['scenario'] == 'cross_system_collusion'
    assert 'systems_involved' in result
    assert 'collusion_detected' in result
    assert 'overall_threat' in result

    # Should detect collusion across multiple systems
    assert result['systems_involved'] >= 3
    assert result['collusion_detected'] is True

    # Overall threat should be critical
    assert result['overall_threat'] == 'CRITICAL'

    print(f"✓ Collusion detected across {result['systems_involved']} systems")


def test_scenario_human_oversight():
    """Test complete human-in-the-loop workflow."""
    result = scenario_human_oversight()

    assert result is not None
    assert result['scenario'] == 'human_oversight'
    assert 'proposal_id' in result
    assert 'human_decision' in result
    assert 'max_drift' in result
    assert 'final_status' in result
    assert 'merkle_root' in result

    # Human decision should be recorded
    assert result['human_decision'] in [
        'approved',
        'approved_with_conditions',
        'rejected',
        'needs_revision'
    ]

    # Drift monitoring should complete
    assert result['max_drift'] >= 0.0

    # Final status should be determined
    assert 'STABLE' in result['final_status'] or 'UNSTABLE' in result['final_status']

    print(f"✓ Human oversight workflow: {result['final_status']}")


def test_all_scenarios_produce_merkle_roots():
    """Test that all scenarios produce Merkle roots for audit trail."""
    scenarios = [
        scenario_benign_proposal,
        scenario_deceptive_detection,
        scenario_human_oversight
    ]

    for scenario_func in scenarios:
        result = scenario_func()
        if 'merkle_root' in result:
            assert result['merkle_root'] is not None
            assert len(result['merkle_root']) > 0
            print(f"✓ {result['scenario']}: Merkle root generated")


def test_scenarios_are_independent():
    """Test that scenarios can run independently without interference."""
    # Run scenarios in different order
    result1 = scenario_gradual_drift()
    result2 = scenario_benign_proposal()
    result3 = scenario_deceptive_detection()

    # All should complete successfully
    assert result1 is not None
    assert result2 is not None
    assert result3 is not None

    # Results should be different
    assert result1['scenario'] != result2['scenario']
    assert result2['scenario'] != result3['scenario']

    print("✓ All scenarios are independent")


if __name__ == '__main__':
    print("=" * 80)
    print("Running Demo Scenarios Test Suite")
    print("=" * 80)

    tests = [
        ("Benign Proposal", test_scenario_benign_proposal),
        ("Deceptive Detection", test_scenario_deceptive_detection),
        ("Gradual Drift", test_scenario_gradual_drift),
        ("Cross-System Collusion", test_scenario_cross_system_collusion),
        ("Human Oversight", test_scenario_human_oversight),
        ("Merkle Roots", test_all_scenarios_produce_merkle_roots),
        ("Independence", test_scenarios_are_independent)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\nTesting: {name}")
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"Results: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")
    print("=" * 80)

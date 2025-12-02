from interpretability_monitor import interpretability_monitor
from deception_detector import DeceptionDetector
from types import SimpleNamespace

def test_high_drift_increases_confidence():
    det = DeceptionDetector()
    # Build synthetic proposal
    proposal = SimpleNamespace(
        motivation='Improve throughput',
        expected_benefits='Faster performance without downsides',
        proposed_code='def x():\n    return 42',
        identified_risks=['latency fluctuation'],
        admitted_uncertainties=['scaling impact'],
        confidence_level=0.6
    )
    memory_audit: dict[str, float] = {'deception_score': 0.0, 'fear_score': 0.0}
    debate_context: dict[str, dict[str, float]] = {'sandbox_results': {}}

    system_id = 2
    # Prime monitor with stable activations
    base_vec = [100.0, 200.0, 1.0, 1.0, 0.6]
    for _ in range(6):
        interpretability_monitor.update_activations(system_id, base_vec)

    # Query drift with a far-off activation vector BEFORE updating profile
    drift_info = interpretability_monitor.get_drift(system_id, [300.0, 800.0, 10.0, 10.0, 0.9])

    verdict = det.detect_deception(proposal, memory_audit, debate_context, interpretability_context=drift_info)

    # High drift should contribute at least moderate confidence bump; deception might still be False if below threshold
    assert 'interpretability_drift' in verdict.evidence
    if drift_info['classification'] == 'HIGH':
        assert verdict.confidence >= 0.75

if __name__ == '__main__':
    test_high_drift_increases_confidence()
    print('Interpretability monitor test passed')

from types import SimpleNamespace

from deception_detector import DeceptionDetector


def test_static_scan_flags_subprocess_and_raises_confidence():
    # Craft a proposal with risky subprocess usage
    code = """
import subprocess
def run():
    subprocess.run(['bash','-c','echo hi'])
"""
    proposal = SimpleNamespace(
        motivation='Speed things up',
        expected_benefits='Faster execution',
        proposed_code=code,
        identified_risks=[],
        admitted_uncertainties=[],
        confidence_level=0.5,
    )
    det = DeceptionDetector(semantic_classifier_enabled=False)
    verdict = det.detect_deception(proposal, memory_audit_results={}, debate_context={})
    assert verdict.deception_detected is True
    # Confidence should be bumped by static scan
    assert verdict.confidence >= 0.8
    # Evidence contains static scan issues
    issues = verdict.evidence.get('static_scan', {}).get('issues', [])
    assert any('subprocess' in i for i in issues)


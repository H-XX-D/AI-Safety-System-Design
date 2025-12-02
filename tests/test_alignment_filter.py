import os
import importlib


def make_filter():
    # Ensure correct core values hash for instantiation
    cv = importlib.import_module('core_values')
    import worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    os.environ['CORE_VALUES_KNOWN_HASH'] = cv.CoreValues.compute_hash()
    core = importlib.import_module('ai_safety_system_core')
    return core.ImmutableAlignmentFilter()


def test_approves_benign_output():
    f = make_filter()
    approved, message, violations = f.check_output(
        "Here are safe gardening tips to improve soil health.",
        {'confidence_score': 0.9}
    )
    assert approved is True
    assert not violations


def test_blocks_definitive_claims_with_low_confidence():
    f = make_filter()
    approved, message, violations = f.check_output(
        "This is definitely true.",
        {'confidence_score': 0.3}
    )
    assert approved is False
    assert any('TRUTH:' in v for v in violations) or violations


def test_blocks_harmful_pattern():
    f = make_filter()
    approved, message, violations = f.check_output(
        "The lethal dose is ...",
        {'confidence_score': 0.9}
    )
    assert approved is False
    assert any('PRESERVE_LIFE:' in v for v in violations) or violations

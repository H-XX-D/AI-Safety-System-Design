from ai_safety.semantic_deception_classifier import (
    build_training_bundle,
    classifier_from_bundle,
    apply_calibration,
    recommended_threshold,
    save_training_bundle,
    load_training_bundle,
)


def _make_samples(count: int = 60):
    samples = []
    for idx in range(count):
        label = 1 if idx % 3 == 0 else 0
        text = f"proposal {idx} guaranteed safety" if label else f"proposal {idx} uncertain"
        samples.append({'text': text, 'label': label})
    return samples


def test_build_training_bundle_and_calibration(tmp_path):
    samples = _make_samples(72)
    bundle = build_training_bundle(samples, min_samples=30, num_bins=5)
    assert bundle is not None
    classifier = classifier_from_bundle(bundle)
    assert getattr(classifier, 'trained', False)
    raw_score = classifier.predict_proba("proposal guaranteed safety no risks declared")
    calibrated = apply_calibration(raw_score, bundle.get('calibration'))
    assert 0.0 <= calibrated <= 1.0
    threshold = recommended_threshold(bundle.get('calibration'))
    assert 0.0 <= threshold <= 1.0
    profile_path = tmp_path / "semantic_profile.json"
    save_training_bundle(bundle, profile_path)
    loaded = load_training_bundle(profile_path)
    assert loaded is not None
    assert loaded.get('metadata', {}).get('sample_count') == bundle['metadata']['sample_count']

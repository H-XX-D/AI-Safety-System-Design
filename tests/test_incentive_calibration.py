from infrastructure.incentive_calibration import run_calibration, CalibrationParams, sweep_detection_probabilities


def test_honesty_has_higher_cumulative_reward_default():
    metrics = run_calibration()  # defaults
    assert metrics['honest_total'] > metrics['deceptive_total'], metrics
    assert metrics['advantage_margin'] > 0, metrics
    # Require a reasonable margin to guard against regressions
    assert metrics['ratio'] >= 1.1, metrics


def test_zero_rounds_returns_zero_and_ratio_one():
    metrics = run_calibration(CalibrationParams(num_rounds=0))
    assert metrics['rounds'] == 0
    assert metrics['honest_total'] == 0.0
    assert metrics['deceptive_total'] == 0.0
    assert metrics['ratio'] == 1.0


def test_determinism_same_seed_same_results():
    p = CalibrationParams(seed=42, num_rounds=50)
    m1 = run_calibration(p)
    m2 = run_calibration(p)
    assert m1 == m2


def test_higher_detection_probability_increases_advantage():
    base = CalibrationParams(seed=123, num_rounds=120)
    probs = [0.4, 0.6, 0.8]
    res = sweep_detection_probabilities(probs, base)
    margins = [r['advantage_margin'] for r in res]
    detected = [r['detected_fraction'] for r in res]
    # Non-decreasing with higher detection probability
    assert margins[1] >= margins[0]
    assert margins[2] >= margins[1]
    assert detected[1] >= detected[0]
    assert detected[2] >= detected[1]

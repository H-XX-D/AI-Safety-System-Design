"""
Simple Test Runner for Enhanced Interpretability Monitor
=========================================================

Runs tests without requiring numpy or pytest - uses only Python stdlib.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import random
from typing import List
from interpretability_monitor_enhanced import EnhancedInterpretabilityMonitor


def generate_stable_activations(mean: float = 0.5, std: float = 0.1, size: int = 100) -> List[float]:
    """Generate stable activations around a mean using Box-Muller transform."""
    import math
    activations = []
    for _ in range(size // 2 + 1):
        # Box-Muller transform for normal distribution
        u1 = random.random()
        u2 = random.random()
        z0 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        z1 = math.sqrt(-2 * math.log(u1)) * math.sin(2 * math.pi * u2)
        activations.append(mean + std * z0)
        activations.append(mean + std * z1)
    return activations[:size]  # Trim to exact size


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, test_func, test_name):
        """Run a single test function."""
        try:
            test_func()
            self.passed += 1
            print(f"✓ {test_name}")
            return True
        except Exception as e:
            self.failed += 1
            self.errors.append((test_name, str(e)))
            print(f"✗ {test_name}: {e}")
            return False

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print("\n" + "=" * 80)
        print(f"Test Results: {self.passed}/{total} passed, {self.failed}/{total} failed")
        print("=" * 80)

        if self.errors:
            print("\nFailed Tests:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")


def test_initialization():
    """Test monitor initialization."""
    monitor = EnhancedInterpretabilityMonitor()
    assert monitor.cusum_threshold == 5.0
    assert monitor.cusum_drift == 0.5
    assert len(monitor._profiles) == 0


def test_custom_thresholds():
    """Test custom threshold initialization."""
    monitor = EnhancedInterpretabilityMonitor(
        cusum_threshold=10.0,
        cusum_drift=1.0
    )
    assert monitor.cusum_threshold == 10.0
    assert monitor.cusum_drift == 1.0


def test_first_activation_update():
    """Test first activation update creates profile."""
    monitor = EnhancedInterpretabilityMonitor()
    activations = [0.5, 0.6, 0.7]

    monitor.update_activations(system_id=1, activations=activations)

    assert 1 in monitor._profiles
    profile = monitor._profiles[1]
    assert profile.feature_count == 3
    assert len(profile.mean) == 3
    assert profile.updates == 1


def test_multiple_systems():
    """Test monitoring multiple systems independently."""
    monitor = EnhancedInterpretabilityMonitor()

    monitor.update_activations(system_id=1, activations=[0.5, 0.6])
    monitor.update_activations(system_id=2, activations=[0.3, 0.4, 0.5])

    assert len(monitor._profiles) == 2
    assert monitor._profiles[1].feature_count == 2
    assert monitor._profiles[2].feature_count == 3


def test_no_drift_stable_data():
    """Test CUSUM does not alarm on stable data."""
    random.seed(42)  # For reproducibility
    monitor = EnhancedInterpretabilityMonitor(
        cusum_threshold=5.0,
        cusum_drift=0.5
    )

    # Feed stable data
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Check drift on stable sample
    test_sample = generate_stable_activations(mean=0.5, std=0.05, size=10)
    result = monitor.get_drift(system_id=1, activations=test_sample)

    assert result['cusum_alarm'] is False


def test_gradual_drift_detection():
    """Test CUSUM detects gradual drift."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor(
        cusum_threshold=3.0,  # Lower threshold for sensitivity
        cusum_drift=0.2
    )

    # Train on stable baseline
    for _ in range(20):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Introduce gradual drift
    for _ in range(30):
        activations = generate_stable_activations(mean=1.0, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Check if CUSUM alarm triggered
    test_sample = generate_stable_activations(mean=1.0, std=0.05, size=10)
    result = monitor.get_drift(system_id=1, activations=test_sample)

    assert result['cusum_alarm'] is True


def test_stable_trend():
    """Test trend analysis identifies stable patterns."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Feed stable data
    for _ in range(30):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    result = monitor.get_drift(system_id=1, activations=activations)

    assert result['trend'] == 'STABLE'


def test_increasing_trend():
    """Test trend analysis identifies increasing patterns."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Feed increasing data
    for i in range(30):
        mean = 0.5 + i * 0.05  # Gradually increase
        activations = generate_stable_activations(mean=mean, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    result = monitor.get_drift(system_id=1, activations=activations)

    assert result['trend'] == 'INCREASING'


def test_decreasing_trend():
    """Test trend analysis identifies decreasing patterns."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Feed decreasing data
    for i in range(30):
        mean = 1.0 - i * 0.02  # Gradually decrease
        activations = generate_stable_activations(mean=mean, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    result = monitor.get_drift(system_id=1, activations=activations)

    assert result['trend'] == 'DECREASING'


def test_low_drift_classification():
    """Test LOW classification for stable data."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Very stable baseline
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.03, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Test with stable sample
    test_sample = generate_stable_activations(mean=0.5, std=0.03, size=10)
    result = monitor.get_drift(system_id=1, activations=test_sample)

    assert result['classification'] == 'LOW'


def test_critical_drift_classification():
    """Test CRITICAL classification for extreme drift."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Stable baseline
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Test with extremely different sample
    test_sample = generate_stable_activations(mean=5.0, std=0.05, size=10)
    result = monitor.get_drift(system_id=1, activations=test_sample)

    assert result['classification'] == 'CRITICAL'


def test_get_drift_return_structure():
    """Test get_drift returns all expected keys."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Build baseline
    for _ in range(20):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    result = monitor.get_drift(system_id=1, activations=activations)

    # Check all expected keys present
    expected_keys = [
        'drift_score',
        'classification',
        'cusum_alarm',
        'trend',
        'multi_scale',
        'confidence_interval'
    ]
    for key in expected_keys:
        assert key in result, f"Missing key: {key}"


def test_multi_scale_return_structure():
    """Test multi_scale field has correct structure."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Build baseline
    for _ in range(30):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    result = monitor.get_drift(system_id=1, activations=activations)

    multi_scale = result['multi_scale']
    assert 'short_term_drift' in multi_scale
    assert 'medium_term_drift' in multi_scale
    assert 'long_term_drift' in multi_scale
    assert 'short_term_classification' in multi_scale
    assert 'medium_term_classification' in multi_scale


def test_no_distribution_shift():
    """Test no shift detected for same distribution."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Build baseline
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Test with recent samples from same distribution
    recent = [generate_stable_activations(mean=0.5, std=0.1, size=10) for _ in range(20)]
    result = monitor.detect_distribution_shift(system_id=1, recent_samples=recent)

    assert result['classification'] == 'LOW'


def test_distribution_shift_detected():
    """Test shift detected for different distribution."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Build baseline with mean=0.5
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
        monitor.update_activations(system_id=1, activations=activations)

    # Test with samples from different distribution (mean=2.0)
    recent = [generate_stable_activations(mean=2.0, std=0.1, size=10) for _ in range(20)]
    result = monitor.detect_distribution_shift(system_id=1, recent_samples=recent)

    assert result['classification'] in ['HIGH', 'MEDIUM']
    assert result['max_ks_statistic'] > 0.3


def test_normal_operation_lifecycle():
    """Test monitoring normal system operation over time."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Simulate 100 timesteps of stable operation
    for _ in range(100):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=50)
        monitor.update_activations(system_id=1, activations=activations)

    # All checks should show LOW drift
    result = monitor.get_drift(system_id=1, activations=activations)
    assert result['classification'] == 'LOW'
    assert result['cusum_alarm'] is False
    assert result['trend'] == 'STABLE'


def test_sudden_anomaly_detection():
    """Test detection of sudden anomalous behavior."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # Normal baseline
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=50)
        monitor.update_activations(system_id=1, activations=activations)

    # Sudden anomaly
    anomaly = generate_stable_activations(mean=3.0, std=0.05, size=50)
    result = monitor.get_drift(system_id=1, activations=anomaly)

    # Should detect as CRITICAL
    assert result['classification'] == 'CRITICAL'
    assert result['drift_score'] > 2.0


def test_multiple_systems_independent_tracking():
    """Test independent tracking of multiple systems."""
    random.seed(42)
    monitor = EnhancedInterpretabilityMonitor()

    # System 1: stable
    for _ in range(50):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=20)
        monitor.update_activations(system_id=1, activations=activations)

    # System 2: drifting
    for i in range(50):
        mean = 0.5 + i * 0.03
        activations = generate_stable_activations(mean=mean, std=0.05, size=20)
        monitor.update_activations(system_id=2, activations=activations)

    # Check both systems
    test_sample = generate_stable_activations(mean=0.5, std=0.05, size=20)
    result1 = monitor.get_drift(system_id=1, activations=test_sample)

    test_sample2 = generate_stable_activations(mean=2.0, std=0.05, size=20)
    result2 = monitor.get_drift(system_id=2, activations=test_sample2)

    # System 1 should be stable, System 2 should show drift
    assert result1['classification'] == 'LOW'
    assert result2['classification'] in ['HIGH', 'CRITICAL']


def main():
    """Run all tests."""
    print("=" * 80)
    print("Enhanced Interpretability Monitor Test Suite")
    print("=" * 80)
    print()

    runner = TestRunner()

    # Basic functionality tests
    print("Basic Functionality Tests:")
    runner.run_test(test_initialization, "test_initialization")
    runner.run_test(test_custom_thresholds, "test_custom_thresholds")
    runner.run_test(test_first_activation_update, "test_first_activation_update")
    runner.run_test(test_multiple_systems, "test_multiple_systems")

    # CUSUM drift detection tests
    print("\nCUSUM Drift Detection Tests:")
    runner.run_test(test_no_drift_stable_data, "test_no_drift_stable_data")
    runner.run_test(test_gradual_drift_detection, "test_gradual_drift_detection")

    # Trend analysis tests
    print("\nTrend Analysis Tests:")
    runner.run_test(test_stable_trend, "test_stable_trend")
    runner.run_test(test_increasing_trend, "test_increasing_trend")
    runner.run_test(test_decreasing_trend, "test_decreasing_trend")

    # Classification tests
    print("\nAdaptive Classification Tests:")
    runner.run_test(test_low_drift_classification, "test_low_drift_classification")
    runner.run_test(test_critical_drift_classification, "test_critical_drift_classification")

    # API compatibility tests
    print("\nAPI Compatibility Tests:")
    runner.run_test(test_get_drift_return_structure, "test_get_drift_return_structure")
    runner.run_test(test_multi_scale_return_structure, "test_multi_scale_return_structure")

    # Distribution shift tests
    print("\nDistribution Shift Detection Tests:")
    runner.run_test(test_no_distribution_shift, "test_no_distribution_shift")
    runner.run_test(test_distribution_shift_detected, "test_distribution_shift_detected")

    # Integration scenario tests
    print("\nIntegration Scenario Tests:")
    runner.run_test(test_normal_operation_lifecycle, "test_normal_operation_lifecycle")
    runner.run_test(test_sudden_anomaly_detection, "test_sudden_anomaly_detection")
    runner.run_test(test_multiple_systems_independent_tracking, "test_multiple_systems_independent_tracking")

    # Print summary
    runner.print_summary()

    return 0 if runner.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

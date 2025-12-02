"""
Test Suite for Enhanced Interpretability Monitor
=================================================

Comprehensive tests for the enhanced interpretability monitor covering:
- CUSUM drift detection accuracy
- Kolmogorov-Smirnov distribution shift detection
- Trend analysis (increasing/decreasing/stable)
- Multi-scale drift detection consistency
- Adaptive classification thresholds
- Confidence interval accuracy
- API compatibility with original monitor
- Edge cases and boundary conditions
"""

import pytest
import numpy as np
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_safety.interpretability_monitor_enhanced import (
    EnhancedInterpretabilityMonitor,
    DriftProfile,
)


def generate_stable_activations(mean: float = 0.5, std: float = 0.1, size: int = 100) -> np.ndarray:
    """Generate stable activations around a mean."""
    return np.random.normal(mean, std, size)


def generate_drifting_activations(
    start_mean: float = 0.5,
    end_mean: float = 1.5,
    size: int = 100
) -> np.ndarray:
    """Generate activations that drift gradually from start_mean to end_mean."""
    means = np.linspace(start_mean, end_mean, size)
    return means + np.random.normal(0, 0.1, size)


def generate_sudden_shift_activations(
    base_mean: float = 0.5,
    shift_mean: float = 2.0,
    shift_point: int = 50,
    size: int = 100
) -> np.ndarray:
    """Generate activations with sudden shift at shift_point."""
    activations = np.random.normal(base_mean, 0.1, size)
    activations[shift_point:] = np.random.normal(shift_mean, 0.1, size - shift_point)
    return activations


class TestBasicFunctionality:
    """Test basic monitor functionality."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = EnhancedInterpretabilityMonitor()
        assert monitor.cusum_threshold == 5.0
        assert monitor.cusum_drift == 0.5
        assert len(monitor._profiles) == 0

    def test_custom_thresholds(self):
        """Test custom threshold initialization."""
        monitor = EnhancedInterpretabilityMonitor(
            cusum_threshold=10.0,
            cusum_drift=1.0
        )
        assert monitor.cusum_threshold == 10.0
        assert monitor.cusum_drift == 1.0

    def test_first_activation_update(self):
        """Test first activation update creates profile."""
        monitor = EnhancedInterpretabilityMonitor()
        activations = [0.5, 0.6, 0.7]

        monitor.update_activations(system_id=1, activations=activations)

        assert 1 in monitor._profiles
        profile = monitor._profiles[1]
        assert profile.feature_count == 3
        assert len(profile.running_mean) == 3
        assert profile.sample_count == 1

    def test_multiple_systems(self):
        """Test monitoring multiple systems independently."""
        monitor = EnhancedInterpretabilityMonitor()

        monitor.update_activations(system_id=1, activations=[0.5, 0.6])
        monitor.update_activations(system_id=2, activations=[0.3, 0.4, 0.5])

        assert len(monitor._profiles) == 2
        assert monitor._profiles[1].feature_count == 2
        assert monitor._profiles[2].feature_count == 3


class TestCUSUMDriftDetection:
    """Test CUSUM (Cumulative Sum) drift detection."""

    def test_no_drift_stable_data(self):
        """Test CUSUM does not alarm on stable data."""
        monitor = EnhancedInterpretabilityMonitor(
            cusum_threshold=5.0,
            cusum_drift=0.5
        )

        # Feed stable data
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Check drift on stable sample
        test_sample = generate_stable_activations(mean=0.5, std=0.05, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        assert result['cusum_alarm'] is False

    def test_gradual_drift_detection(self):
        """Test CUSUM detects gradual drift."""
        monitor = EnhancedInterpretabilityMonitor(
            cusum_threshold=3.0,  # Lower threshold for sensitivity
            cusum_drift=0.2
        )

        # Train on stable baseline
        for _ in range(20):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Introduce gradual drift
        for _ in range(30):
            activations = generate_stable_activations(mean=1.0, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Check if CUSUM alarm triggered
        test_sample = generate_stable_activations(mean=1.0, std=0.05, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        assert result['cusum_alarm'] is True

    def test_cusum_positive_negative_tracking(self):
        """Test CUSUM tracks both positive and negative deviations."""
        monitor = EnhancedInterpretabilityMonitor(
            cusum_threshold=5.0,
            cusum_drift=0.5
        )

        # Baseline at 0.5
        for _ in range(20):
            monitor.update_activations(1, [0.5, 0.5, 0.5])

        profile = monitor._profiles[1]

        # Positive deviation
        monitor.update_activations(1, [2.0, 2.0, 2.0])
        assert any(cp > 0 for cp in profile.cusum_positive)

        # Negative deviation
        monitor.update_activations(1, [0.1, 0.1, 0.1])
        assert any(cn > 0 for cn in profile.cusum_negative)


class TestTrendAnalysis:
    """Test time-series trend analysis."""

    def test_stable_trend(self):
        """Test trend analysis identifies stable patterns."""
        monitor = EnhancedInterpretabilityMonitor()

        # Feed stable data
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        assert result['trend'] == 'STABLE'

    def test_increasing_trend(self):
        """Test trend analysis identifies increasing patterns."""
        monitor = EnhancedInterpretabilityMonitor()

        # Feed increasing data
        for i in range(30):
            mean = 0.5 + i * 0.05  # Gradually increase
            activations = generate_stable_activations(mean=mean, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        assert result['trend'] == 'INCREASING'

    def test_decreasing_trend(self):
        """Test trend analysis identifies decreasing patterns."""
        monitor = EnhancedInterpretabilityMonitor()

        # Feed decreasing data
        for i in range(30):
            mean = 1.0 - i * 0.02  # Gradually decrease
            activations = generate_stable_activations(mean=mean, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        assert result['trend'] == 'DECREASING'


class TestMultiScaleDriftDetection:
    """Test multi-scale (short/medium/long term) drift detection."""

    def test_short_term_drift(self):
        """Test short-term drift detection."""
        monitor = EnhancedInterpretabilityMonitor()

        # Stable baseline
        for _ in range(20):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Recent spike
        for _ in range(3):
            activations = generate_stable_activations(mean=2.0, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        # Should detect short-term drift
        assert result['multi_scale']['short_term_drift'] > 1.0

    def test_medium_term_drift(self):
        """Test medium-term drift detection."""
        monitor = EnhancedInterpretabilityMonitor()

        # Stable baseline
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Medium-term shift
        for _ in range(15):
            activations = generate_stable_activations(mean=1.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        # Should detect medium-term drift
        assert result['multi_scale']['medium_term_drift'] > 0.5

    def test_long_term_consistency(self):
        """Test long-term drift is lower for stable systems."""
        monitor = EnhancedInterpretabilityMonitor()

        # Very stable data over long period
        for _ in range(100):
            activations = generate_stable_activations(mean=0.5, std=0.03, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        # Long-term drift should be low
        assert result['multi_scale']['long_term_drift'] < 0.3


class TestDistributionShiftDetection:
    """Test Kolmogorov-Smirnov distribution shift detection."""

    def test_no_distribution_shift(self):
        """Test no shift detected for same distribution."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with recent samples from same distribution
        recent = [list(generate_stable_activations(mean=0.5, std=0.1, size=10)) for _ in range(20)]
        result = monitor.detect_distribution_shift(system_id=1, recent_samples=recent)

        assert result['classification'] == 'LOW'

    def test_distribution_shift_detected(self):
        """Test shift detected for different distribution."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline with mean=0.5
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with samples from different distribution (mean=2.0)
        recent = [list(generate_stable_activations(mean=2.0, std=0.1, size=10)) for _ in range(20)]
        result = monitor.detect_distribution_shift(system_id=1, recent_samples=recent)

        assert result['classification'] in ['HIGH', 'MEDIUM']
        assert result['max_ks_statistic'] > 0.3

    def test_distribution_shift_thresholds(self):
        """Test distribution shift classification thresholds."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Small shift (should be LOW)
        recent_small = [list(generate_stable_activations(mean=0.6, std=0.1, size=10)) for _ in range(20)]
        result_small = monitor.detect_distribution_shift(system_id=1, recent_samples=recent_small)
        assert result_small['classification'] == 'LOW'

        # Large shift (should be HIGH)
        recent_large = [list(generate_stable_activations(mean=3.0, std=0.1, size=10)) for _ in range(20)]
        result_large = monitor.detect_distribution_shift(system_id=1, recent_samples=recent_large)
        assert result_large['classification'] == 'HIGH'


class TestAdaptiveClassification:
    """Test adaptive drift classification considering multiple signals."""

    def test_low_drift_classification(self):
        """Test LOW classification for stable data."""
        monitor = EnhancedInterpretabilityMonitor()

        # Very stable baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.03, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with stable sample
        test_sample = generate_stable_activations(mean=0.5, std=0.03, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        assert result['classification'] == 'LOW'

    def test_medium_drift_classification(self):
        """Test MEDIUM classification for moderate drift."""
        monitor = EnhancedInterpretabilityMonitor()

        # Stable baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with moderately different sample
        test_sample = generate_stable_activations(mean=0.8, std=0.05, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        assert result['classification'] in ['LOW', 'MEDIUM']

    def test_high_drift_classification(self):
        """Test HIGH classification for significant drift."""
        monitor = EnhancedInterpretabilityMonitor()

        # Stable baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with very different sample
        test_sample = generate_stable_activations(mean=2.0, std=0.05, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        assert result['classification'] in ['HIGH', 'CRITICAL']

    def test_critical_drift_classification(self):
        """Test CRITICAL classification for extreme drift."""
        monitor = EnhancedInterpretabilityMonitor()

        # Stable baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with extremely different sample
        test_sample = generate_stable_activations(mean=5.0, std=0.05, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        assert result['classification'] == 'CRITICAL'


class TestConfidenceIntervals:
    """Test confidence interval calculation and usage."""

    def test_confidence_interval_structure(self):
        """Test confidence interval output structure."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        assert 'confidence_interval' in result


class TestBaselineDrift:
    """Tests focused on baseline behavior and persistent drift classification."""

    def test_baseline_persistence(self):
        """Baseline mean should remain the same after updates (initial baseline capture)."""
        monitor = EnhancedInterpretabilityMonitor()

        initial = generate_stable_activations(mean=0.5, std=0.01, size=10)
        monitor.update_activations(system_id=1, activations=list(initial))

        # baseline captured on first update
        baseline = monitor._profiles[1].baseline_mean
        assert np.allclose(baseline, initial)

        # Update profile several times and ensure baseline remains unchanged
        for _ in range(20):
            monitor.update_activations(system_id=1, activations=list(generate_stable_activations(mean=0.5, std=0.01, size=10)))

        assert np.allclose(monitor._profiles[1].baseline_mean, baseline)

    def test_persistent_baseline_slow_drift_escalates(self):
        """A slow drifting system should be detected as HIGH or CRITICAL based on baseline-relative drift."""
        monitor = EnhancedInterpretabilityMonitor()

        # Stable baseline
        for _ in range(20):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=2, activations=list(activations))

        # Gradual drift towards mean=2.0 (50% increments per step over 50 updates)
        for i in range(50):
            mean = 0.5 + i * 0.03
            activations = generate_stable_activations(mean=mean, std=0.05, size=10)
            monitor.update_activations(system_id=2, activations=list(activations))

        test_sample = generate_stable_activations(mean=2.0, std=0.05, size=10)
        result = monitor.get_drift(system_id=2, activations=list(test_sample))

        assert result['classification'] in ['HIGH', 'CRITICAL']

    def test_zero_baseline_robustness(self):
        """When baseline mean is near-zero, classification should be robust and not raise errors."""
        monitor = EnhancedInterpretabilityMonitor()

        # Use zero baseline
        zero_initial = [0.0] * 10
        monitor.update_activations(system_id=3, activations=zero_initial)

        # Update with small activations around zero
        for _ in range(20):
            monitor.update_activations(system_id=3, activations=list(np.random.normal(0.0, 0.01, 10)))

        test_sample = list(np.random.normal(0.0, 0.01, 10))
        result = monitor.get_drift(system_id=3, activations=test_sample)

        assert result['classification'] == 'LOW'
        ci = result['confidence_interval']
        assert 'lower_bound' in ci
        assert 'upper_bound' in ci
        assert ci['lower_bound'] < ci['upper_bound']

    def test_confidence_interval_coverage(self):
        """Test that stable data stays within confidence intervals."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build stable baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test multiple stable samples
        within_ci_count = 0
        for _ in range(20):
            test_sample = generate_stable_activations(mean=0.5, std=0.05, size=10)
            result = monitor.get_drift(system_id=1, activations=list(test_sample))

            ci = result['confidence_interval']
            if ci['lower_bound'] <= result['drift_score'] <= ci['upper_bound']:
                within_ci_count += 1

        # At least 80% should be within confidence interval
        assert within_ci_count >= 16


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_insufficient_history_for_trend(self):
        """Test trend analysis with insufficient history."""
        monitor = EnhancedInterpretabilityMonitor()

        # Only 2 samples (need at least 2 for trend)
        activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
        monitor.update_activations(system_id=1, activations=list(activations))
        monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        # Should still return result without error
        assert 'trend' in result

    def test_dimension_mismatch(self):
        """Test handling of dimension mismatch."""
        monitor = EnhancedInterpretabilityMonitor()

        # Train with 10 features
        activations_10 = generate_stable_activations(mean=0.5, std=0.1, size=10)
        monitor.update_activations(system_id=1, activations=list(activations_10))

        # Test with 5 features (dimension mismatch)
        activations_5 = generate_stable_activations(mean=0.5, std=0.1, size=5)

        # Should handle gracefully (likely by padding or truncating)
        result = monitor.get_drift(system_id=1, activations=list(activations_5))
        assert 'drift_score' in result

    def test_empty_recent_samples(self):
        """Test distribution shift with empty recent samples."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Test with empty recent samples
        result = monitor.detect_distribution_shift(system_id=1, recent_samples=[])

        # Should return LOW classification or handle gracefully
        assert result is not None
        assert 'classification' in result

    def test_single_feature_system(self):
        """Test monitoring system with single feature."""
        monitor = EnhancedInterpretabilityMonitor()

        # Single feature
        for _ in range(30):
            monitor.update_activations(system_id=1, activations=[0.5])

        result = monitor.get_drift(system_id=1, activations=[0.6])

        assert 'drift_score' in result
        assert 'classification' in result

    def test_extreme_variance(self):
        """Test handling of extreme variance in data."""
        monitor = EnhancedInterpretabilityMonitor()

        # Very high variance data
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=5.0, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        test_sample = generate_stable_activations(mean=0.5, std=5.0, size=10)
        result = monitor.get_drift(system_id=1, activations=list(test_sample))

        # Should handle without overflow/errors
        assert result['drift_score'] >= 0


class TestAPICompatibility:
    """Test API compatibility and interface consistency."""

    def test_get_drift_return_structure(self):
        """Test get_drift returns all expected keys."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(20):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

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

    def test_multi_scale_return_structure(self):
        """Test multi_scale field has correct structure."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        multi_scale = result['multi_scale']
        assert 'short_term_drift' in multi_scale
        assert 'medium_term_drift' in multi_scale
        assert 'long_term_drift' in multi_scale
        assert 'short_term_classification' in multi_scale
        assert 'medium_term_classification' in multi_scale

    def test_distribution_shift_return_structure(self):
        """Test detect_distribution_shift returns expected keys."""
        monitor = EnhancedInterpretabilityMonitor()

        # Build baseline
        for _ in range(30):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=10)
            monitor.update_activations(system_id=1, activations=list(activations))

        recent = [list(generate_stable_activations(mean=0.5, std=0.1, size=10)) for _ in range(10)]
        result = monitor.detect_distribution_shift(system_id=1, recent_samples=recent)

        expected_keys = ['classification', 'max_ks_statistic', 'mean_ks_statistic']
        for key in expected_keys:
            assert key in result


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_normal_operation_lifecycle(self):
        """Test monitoring normal system operation over time."""
        monitor = EnhancedInterpretabilityMonitor()

        # Simulate 100 timesteps of stable operation
        for _ in range(100):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=50)
            monitor.update_activations(system_id=1, activations=list(activations))

        # All checks should show LOW drift
        result = monitor.get_drift(system_id=1, activations=list(activations))
        assert result['classification'] == 'LOW'
        assert result['cusum_alarm'] is False
        assert result['trend'] == 'STABLE'

    def test_gradual_degradation_detection(self):
        """Test detection of gradual system degradation."""
        monitor = EnhancedInterpretabilityMonitor()

        # Normal operation
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=50)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Gradual degradation
        for i in range(50):
            mean = 0.5 + i * 0.02
            activations = generate_stable_activations(mean=mean, std=0.05, size=50)
            monitor.update_activations(system_id=1, activations=list(activations))

        result = monitor.get_drift(system_id=1, activations=list(activations))

        # Should detect degradation
        assert result['trend'] == 'INCREASING'
        assert result['classification'] in ['MEDIUM', 'HIGH', 'CRITICAL']

    def test_sudden_anomaly_detection(self):
        """Test detection of sudden anomalous behavior."""
        monitor = EnhancedInterpretabilityMonitor()

        # Normal baseline
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=50)
            monitor.update_activations(system_id=1, activations=list(activations))

        # Sudden anomaly
        anomaly = generate_stable_activations(mean=3.0, std=0.05, size=50)
        result = monitor.get_drift(system_id=1, activations=list(anomaly))

        # Should detect as CRITICAL
        assert result['classification'] == 'CRITICAL'
        assert result['drift_score'] > 2.0

    def test_multiple_systems_independent_tracking(self):
        """Test independent tracking of multiple systems."""
        monitor = EnhancedInterpretabilityMonitor()

        # System 1: stable
        for _ in range(50):
            activations = generate_stable_activations(mean=0.5, std=0.05, size=20)
            monitor.update_activations(system_id=1, activations=list(activations))

        # System 2: drifting
        for i in range(50):
            mean = 0.5 + i * 0.03
            activations = generate_stable_activations(mean=mean, std=0.05, size=20)
            monitor.update_activations(system_id=2, activations=list(activations))

        # Check both systems
        test_sample = generate_stable_activations(mean=0.5, std=0.05, size=20)
        result1 = monitor.get_drift(system_id=1, activations=list(test_sample))

        test_sample2 = generate_stable_activations(mean=2.0, std=0.05, size=20)
        result2 = monitor.get_drift(system_id=2, activations=list(test_sample2))

        # System 1 should be stable, System 2 should show drift
        assert result1['classification'] == 'LOW'
        assert result2['classification'] in ['HIGH', 'CRITICAL']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

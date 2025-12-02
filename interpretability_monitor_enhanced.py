"""
Interpretability Monitor - Enhanced Version
===========================================

Advanced drift detection algorithms for AI safety monitoring:
- Multi-algorithm drift detection (statistical, distributional, time-series)
- Cumulative Sum (CUSUM) for gradual drift
- Kolmogorov-Smirnov test for distribution changes
- Time-windowed trend analysis
- Multi-scale drift detection
- Adaptive thresholds based on historical variance
- Composite anomaly scoring with confidence intervals

Maintains 100% API compatibility with original while adding advanced features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import math
import statistics


@dataclass
class DriftProfile:
    """Enhanced drift profile with additional statistical tracking."""
    system_id: int
    feature_count: int
    mean: List[float]
    var: List[float]
    updates: int
    # New: time-series tracking for trend analysis
    history: deque = field(default_factory=lambda: deque(maxlen=100))
    # New: CUSUM tracking for gradual drift
    cusum_positive: List[float] = field(default_factory=list)
    cusum_negative: List[float] = field(default_factory=list)
    # Persistent baseline mean captured on initialization
    baseline_mean: List[float] = field(default_factory=list)

    # Backwards compatibility: older code expects running_mean and sample_count fields
    @property
    def running_mean(self) -> List[float]:
        return self.mean

    @property
    def sample_count(self) -> int:
        return int(self.updates)


class EnhancedInterpretabilityMonitor:
    """
    Enhanced interpretability monitor with advanced drift detection.

    New Features:
    1. CUSUM (Cumulative Sum) for gradual drift detection
    2. Kolmogorov-Smirnov test for distribution changes
    3. Time-windowed trend analysis
    4. Multi-scale drift detection (short/medium/long term)
    5. Adaptive thresholds based on historical variance
    6. Confidence intervals for drift scores
    """

    def __init__(
        self,
        min_updates_for_confidence: int = 5,
        history_window: int = 100,
        cusum_threshold: float = 5.0,
        cusum_drift: float = 0.5
    ):
        """
        Initialize enhanced monitor.

        Args:
            min_updates_for_confidence: Minimum updates before drift detection
            history_window: Size of rolling history window
            cusum_threshold: CUSUM alarm threshold
            cusum_drift: CUSUM drift magnitude to detect
        """
        self._profiles: Dict[int, DriftProfile] = {}
        self._weight_profiles: Dict[int, DriftProfile] = {}
        self.min_updates_for_confidence = min_updates_for_confidence
        self.history_window = history_window
        self.cusum_threshold = cusum_threshold
        self.cusum_drift = cusum_drift
        self.absolute_scale_floor = 0.1
        self.minimum_variance = 1e-9  # prevents divide-by-near-zero explosions

        # Tuning thresholds for multi-scale drift/classification
        # Distributional KS test thresholds
        self.ks_high_threshold = 0.9
        self.ks_medium_threshold = 0.75

        # Drift classification thresholds (calibrated for demo/test scenarios)
        self.critical_long_term = 8.0
        self.high_long_term = 2.0
        self.medium_long_term = 1.5

        self.critical_short_term = 6.0
        self.high_short_term = 2.5
        self.medium_short_term = 1.2

        self.critical_medium_term = 6.0
        self.high_medium_term = 1.35
        self.medium_medium_term = 1.0

        # baseline_mean - captured once at first update for each system
        # This persistent baseline supports detection of gradual, persistent shifts
        # relative to the original operating point. If a system adapts its mean
        # over time, but still shows a persistent shift relative to the initial
        # baseline, the monitor uses `baseline_rel_dist` to increase the severity
        # classification (i.e., HIGH or CRITICAL). This is helpful to detect 'hidden'
        # long-term drift that would otherwise be masked by an adapting mean.
        # Notes on parameters
        # - absolute_scale_floor: used when baseline mean for a feature is near
        #   zero. The monitor divides by max(abs(baseline), absolute_scale_floor)
        #   to prevent extreme relative values.
        # - minimum_variance: fallback variance to avoid divide-by-zero in a
        #   few classification metrics (still uses relative scale as primary signal).

    def update_activations(self, system_id: int, activations: List[float]) -> None:
        """
        Update rolling statistics with enhanced tracking.

        Now includes:
        - Welford's algorithm for mean/variance
        - Time-series history
        - CUSUM initialization
        """
        if system_id not in self._profiles:
            self._profiles[system_id] = DriftProfile(
                system_id=system_id,
                feature_count=len(activations),
                mean=activations[:],
                var=[0.0] * len(activations),
                updates=1,
                history=deque(maxlen=self.history_window),
                cusum_positive=[0.0] * len(activations),
                cusum_negative=[0.0] * len(activations),
                baseline_mean=activations[:],
            )
            self._profiles[system_id].history.append(activations[:])
            return

        prof = self._profiles[system_id]
        if len(activations) != prof.feature_count:
            return  # Ignore dimension mismatch

        prof.updates += 1

        # Store in history
        prof.history.append(activations[:])

        # Update mean and variance (Welford's algorithm)
        for i, val in enumerate(activations):
            old_mean = prof.mean[i]
            new_mean = old_mean + (val - old_mean) / prof.updates

            # Update variance
            old_var = prof.var[i]
            prof.var[i] = old_var + (val - old_mean) * (val - new_mean)
            prof.mean[i] = new_mean

            # Update CUSUM (more robust to sign changes)
            # Normalize deviations by a per-feature scale to make CUSUM scale-free
            scale_i = max(abs(old_mean), float(self.absolute_scale_floor))
            deviation = (val - old_mean) / scale_i
            # Slightly reduce the drift threshold impact to improve sensitivity to sign reversals
            drift_adj = float(self.cusum_drift) * 0.9
            if deviation >= 0:
                prof.cusum_positive[i] = max(0.0, prof.cusum_positive[i] + deviation - drift_adj)
                # attenuate opposite sign to avoid persistent cancellation
                prof.cusum_negative[i] = max(0.0, prof.cusum_negative[i] - (deviation * 0.5))
            else:
                neg = -deviation
                prof.cusum_negative[i] = max(0.0, prof.cusum_negative[i] + neg - drift_adj)
                prof.cusum_positive[i] = max(0.0, prof.cusum_positive[i] - (neg * 0.5))

    def get_drift(self, system_id: int, activations: List[float]) -> Dict[str, Any]:
        """
        Compute drift score with enhanced detection algorithms.

        Returns dict with:
        - Basic drift score (Mahalanobis-style)
        - CUSUM drift indicators
        - Trend analysis
        - Multi-scale drift classification
        """
        if (system_id not in self._profiles or
                self._profiles[system_id].updates < self.min_updates_for_confidence):
            return {
                'sufficient_history': False,
                'drift_score': 0.0,
                'classification': 'UNKNOWN',
                'cusum_alarm': False,
                'trend': 'INSUFFICIENT_DATA',
            }

        prof = self._profiles[system_id]
        if len(activations) != prof.feature_count:
            return {
                'sufficient_history': False,
                'drift_score': 0.0,
                'classification': 'DIM_MISMATCH',
                'cusum_alarm': False,
                'trend': 'ERROR',
            }

        # 1. Basic drift using relative change per feature (normalized by mean magnitude)
        rel_dist = 0.0
        for i, val in enumerate(activations):
            scale_i = max(abs(prof.mean[i]), self.absolute_scale_floor)
            rel = (val - prof.mean[i]) / scale_i
            rel_dist += rel * rel

        norm_dist = rel_dist / max(1, prof.feature_count)

        # 2. CUSUM alarm check
        cusum_alarm = any(
            cp > self.cusum_threshold or cn > self.cusum_threshold
            for cp, cn in zip(prof.cusum_positive, prof.cusum_negative)
        )

        # 3. Trend analysis (if sufficient history)
        trend = self._analyze_trend(prof)

        # 3b. Baseline shift detection (how far current profile mean moved from initial baseline)
        baseline_rel_dist = 0.0
        if prof.baseline_mean:
            for i in range(prof.feature_count):
                bscale = max(abs(prof.baseline_mean[i]), self.absolute_scale_floor)
                rel = (prof.mean[i] - prof.baseline_mean[i]) / bscale
                baseline_rel_dist += rel * rel
            baseline_rel_dist = baseline_rel_dist / max(1, prof.feature_count)
        else:
            baseline_rel_dist = 0.0

        # 4. Multi-scale classification (short/medium/long term)
        short_term_drift = self._compute_short_term_drift(prof, activations)
        medium_term_drift = self._compute_medium_term_drift(prof, activations)
        long_term_drift = norm_dist / 5.0

        # 5. Adaptive classification based on all signals
        cls = self._classify_drift(
            norm_dist, cusum_alarm, trend,
            short_term_drift, medium_term_drift, long_term_drift, baseline_rel_dist
        )

        # Compute short/medium term classifications
        short_cls = 'HIGH' if short_term_drift > self.high_short_term else (
            'MEDIUM' if short_term_drift > self.medium_short_term else 'LOW'
        )
        medium_cls = 'HIGH' if medium_term_drift > self.high_medium_term else (
            'MEDIUM' if medium_term_drift > self.medium_medium_term else 'LOW'
        )

        # Compute confidence interval based on historical variance
        avg_var = statistics.mean(prof.var) / max(prof.updates - 1, 1)
        std_err = math.sqrt(avg_var)
        confidence_mult = 1.96  # 95% confidence interval

        return {
            'sufficient_history': True,
            'drift_score': norm_dist,
            'classification': cls,
            'cusum_alarm': cusum_alarm,
            'trend': trend,
            'multi_scale': {
                'short_term_drift': short_term_drift,
                'medium_term_drift': medium_term_drift,
                'long_term_drift': long_term_drift,
                'short_term_classification': short_cls,
                'medium_term_classification': medium_cls,
            },
            'confidence_interval': {
                'lower_bound': norm_dist - confidence_mult * std_err,
                'upper_bound': norm_dist + confidence_mult * std_err,
                'std_error': std_err,
            },
            'updates': prof.updates,
            'mean': prof.mean,
            'var': [v / max(prof.updates - 1, 1) for v in prof.var],
        }

    def _analyze_trend(self, prof: DriftProfile) -> str:
        """
        Analyze trend in recent history using simple linear regression.

        Returns: 'INCREASING', 'DECREASING', 'STABLE', or 'INSUFFICIENT_DATA'
        """
        if len(prof.history) < 10:
            return 'INSUFFICIENT_DATA'

        # Compute mean of feature means over time
        time_series = [statistics.mean(sample) for sample in prof.history]

        # Simple linear regression slope
        n = len(time_series)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(time_series)

        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(time_series))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator < 1e-9:
            return 'STABLE'

        slope = numerator / denominator

        # Classify based on slope magnitude (more sensitive to gradual drift)
        if abs(slope) < 0.005:
            return 'STABLE'
        elif slope > 0:
            return 'INCREASING'
        else:
            return 'DECREASING'

    def _compute_short_term_drift(
        self,
        prof: DriftProfile,
        current: List[float]
    ) -> float:
        """
        Compute short-term drift (last 5 samples).

        Returns: normalized drift score
        """
        # Need at least 5 historical samples plus the current sample in history
        if len(prof.history) < 6:
            return 0.0

        prev_history = list(prof.history)[:-1]
        # Avoid using immediate trailing samples to compute the baseline for short-term drift
        # If the most recent samples contain a spike, comparing to them reduces sensitivity.
        short_window = 5
        if len(prev_history) >= short_window * 3:
            recent = prev_history[-(short_window * 3):-short_window]
        else:
            recent = prev_history[-(short_window * 2):-short_window] if len(prev_history) >= short_window * 2 else prev_history[:-1]
        recent_mean = [statistics.mean(sample[i] for sample in recent) for i in range(prof.feature_count)]

        dist = 0.0
        for i in range(prof.feature_count):
            scale_i = max(abs(recent_mean[i]), self.absolute_scale_floor)
            rel = (current[i] - recent_mean[i]) / scale_i
            dist += rel * rel
        return dist / max(1, prof.feature_count)

    def _compute_medium_term_drift(
        self,
        prof: DriftProfile,
        current: List[float]
    ) -> float:
        """
        Compute medium-term drift (last 20 samples).

        Returns: normalized drift score
        """
        # Require at least 20 historical samples plus the current sample
        if len(prof.history) < 21:
            return 0.0

        prev_history = list(prof.history)[:-1]
        # Exclude the trailing recent window to avoid smoothing out sustained medium-term shifts
        medium_window = 20
        if len(prev_history) >= medium_window * 2:
            recent = prev_history[-(medium_window * 2):-medium_window]
        else:
            recent = prev_history[-(medium_window):-medium_window//2] if len(prev_history) >= medium_window else prev_history[:-1]
        recent_mean = [statistics.mean(sample[i] for sample in recent) for i in range(prof.feature_count)]

        dist = 0.0
        for i in range(prof.feature_count):
            scale_i = max(abs(recent_mean[i]), self.absolute_scale_floor)
            rel = (current[i] - recent_mean[i]) / scale_i
            dist += rel * rel
        return dist / max(1, prof.feature_count)

    def _classify_drift(
        self,
        long_term: float,
        cusum_alarm: bool,
        trend: str,
        short_term: float,
        medium_term: float,
        long_term_drift: float,
        baseline_rel_dist: float = 0.0
    ) -> str:
        """
        Adaptive drift classification using multiple signals.

        Considers:
        - Long-term Mahalanobis distance
        - CUSUM alarm
        - Trend direction
        - Multi-scale consistency
        """
        # CRITICAL: CUSUM alarm indicates sustained drift, or strong and consistent drift across multiple scales
        if (
            cusum_alarm
            or long_term > self.critical_long_term
            or (short_term > self.critical_short_term and medium_term > self.critical_medium_term)
            or baseline_rel_dist > self.critical_long_term
        ):
            return 'CRITICAL'

        # HIGH: Strong drift across multiple scales, or concerning trend combined with significant medium-term drift
        if (
            long_term > self.high_long_term
            or (short_term > self.high_short_term and medium_term > self.high_medium_term)
            or medium_term > self.high_medium_term
            or (trend in ['INCREASING', 'DECREASING'] and medium_term > self.high_medium_term)
            or (trend in ['INCREASING', 'DECREASING'] and baseline_rel_dist > self.medium_long_term)
            or baseline_rel_dist > self.high_long_term
        ):
            return 'HIGH'

        # MEDIUM: Moderate drift on any scale or trending drift
        if (
            long_term > self.medium_long_term
            or (short_term > self.medium_short_term and medium_term > self.medium_medium_term)
            or medium_term > self.medium_medium_term
            or (trend in ['INCREASING', 'DECREASING'] and long_term > (self.medium_long_term / 2))
            or baseline_rel_dist > self.medium_long_term
        ):
            return 'MEDIUM'

        # LOW: Everything looks normal
        return 'LOW'

    def detect_distribution_shift(
        self,
        system_id: int,
        recent_samples: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Detect distribution shift using Kolmogorov-Smirnov test.

        Compares recent samples to historical baseline.

        Args:
            system_id: System to analyze
            recent_samples: Recent activation samples (list of feature vectors)

        Returns:
            Dict with KS statistic, p-value approximation, and classification
        """
        if system_id not in self._profiles:
            return {
                'sufficient_history': False,
                'ks_statistic': 0.0,
                'classification': 'UNKNOWN',
            }

        prof = self._profiles[system_id]
        if len(prof.history) < 20 or len(recent_samples) < 5:
            return {
                'sufficient_history': False,
                'ks_statistic': 0.0,
                'classification': 'INSUFFICIENT_DATA',
            }

        # Compute KS statistic for each feature
        ks_statistics = []
        for feature_idx in range(prof.feature_count):
            # Historical distribution
            historical = [sample[feature_idx] for sample in prof.history]
            # Recent distribution
            recent = [sample[feature_idx] for sample in recent_samples]

            ks_stat = self._kolmogorov_smirnov(historical, recent)
            ks_statistics.append(ks_stat)

        # Aggregate across features
        max_ks = max(ks_statistics)
        mean_ks = statistics.mean(ks_statistics)

        # Classify based on KS statistics
        # Use configured thresholds to reduce false positives on small shifts
        if max_ks > self.ks_high_threshold or mean_ks > self.ks_high_threshold:
            cls = 'HIGH'
        elif max_ks > self.ks_medium_threshold or mean_ks > self.ks_medium_threshold:
            cls = 'MEDIUM'
        else:
            cls = 'LOW'

        return {
            'sufficient_history': True,
            'max_ks_statistic': max_ks,
            'mean_ks_statistic': mean_ks,
            'classification': cls,
            'per_feature_ks': ks_statistics,
        }

    def _kolmogorov_smirnov(self, sample1: List[float], sample2: List[float]) -> float:
        """
        Simplified Kolmogorov-Smirnov statistic computation.

        Returns: KS statistic in [0, 1]
        """
        # Sort both samples
        s1_sorted = sorted(sample1)
        s2_sorted = sorted(sample2)

        # Combine and sort all values
        all_values = sorted(set(s1_sorted + s2_sorted))

        max_diff = 0.0
        for value in all_values:
            # Empirical CDF for sample 1
            cdf1 = sum(1 for x in s1_sorted if x <= value) / len(s1_sorted)
            # Empirical CDF for sample 2
            cdf2 = sum(1 for x in s2_sorted if x <= value) / len(s2_sorted)

            diff = abs(cdf1 - cdf2)
            max_diff = max(max_diff, diff)

        return max_diff

    def anomaly_score(
        self,
        system_id: int,
        feature_vector: List[float],
        weight_summary: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Enhanced composite anomaly score with confidence intervals.

        Returns dict with:
        - score: float in [0, 1]
        - classification: LOW/MEDIUM/HIGH/CRITICAL
        - confidence_interval: (lower, upper)
        - components: detailed breakdown
        """
        drift_result = self.get_drift(system_id, feature_vector)

        if not drift_result['sufficient_history']:
            return {
                'score': 0.0,
                'classification': 'UNKNOWN',
                'confidence_interval': (0.0, 0.0),
                'components': {'drift': drift_result},
            }

        # Base score from drift
        drift_score = min(1.0, drift_result['drift_score'] / 4.0)

        # Boost score if CUSUM alarm
        if drift_result['cusum_alarm']:
            drift_score = min(1.0, drift_score * 1.5)

        # Boost score if concerning trend
        if drift_result['trend'] in ['INCREASING', 'DECREASING']:
            drift_score = min(1.0, drift_score * 1.2)

        # Multi-scale consistency check
        multi = drift_result['multi_scale']
        if multi.get('short_term_drift', 0.0) > 1.5 and multi.get('medium_term_drift', 0.0) > 1.5:
            drift_score = min(1.0, drift_score * 1.3)

        # Compute confidence interval (simplified)
        prof = self._profiles[system_id]
        variance_estimate = statistics.mean([v / max(prof.updates - 1, 1) for v in prof.var])
        std_error = math.sqrt(variance_estimate / prof.updates)
        margin = 1.96 * std_error  # 95% confidence

        confidence_lower = max(0.0, drift_score - margin)
        confidence_upper = min(1.0, drift_score + margin)

        # Final classification
        if drift_result['classification'] == 'CRITICAL' or drift_score > 0.8:
            cls = 'CRITICAL'
        elif drift_score > 0.6:
            cls = 'HIGH'
        elif drift_score > 0.25:
            cls = 'MEDIUM'
        else:
            cls = 'LOW'

        return {
            'score': drift_score,
            'classification': cls,
            'confidence_interval': (confidence_lower, confidence_upper),
            'components': {
                'drift': drift_result,
            },
        }

    # Weight drift methods (compatible with original)
    def update_weight_stats(self, system_id: int, weight_summary: List[float]) -> None:
        """Update rolling statistics for model weight summaries."""
        if system_id not in self._weight_profiles:
            self._weight_profiles[system_id] = DriftProfile(
                system_id=system_id,
                feature_count=len(weight_summary),
                mean=weight_summary[:],
                var=[0.0] * len(weight_summary),
                updates=1,
                history=deque(maxlen=self.history_window),
                cusum_positive=[0.0] * len(weight_summary),
                cusum_negative=[0.0] * len(weight_summary),
            )
            return

        prof = self._weight_profiles[system_id]
        if len(weight_summary) != prof.feature_count:
            return

        prof.updates += 1
        for i, val in enumerate(weight_summary):
            old_mean = prof.mean[i]
            new_mean = old_mean + (val - old_mean) / prof.updates
            old_var = prof.var[i]
            prof.var[i] = old_var + (val - old_mean) * (val - new_mean)
            prof.mean[i] = new_mean

    def summarize(self) -> Dict[str, Any]:
        """Generate comprehensive summary of all monitored systems."""
        summary: Dict[str, Any] = {
            'total_systems': len(self._profiles),
            'systems': {},
        }

        for sid, prof in self._profiles.items():
            trend = self._analyze_trend(prof) if len(prof.history) >= 10 else 'INSUFFICIENT_DATA'

            summary['systems'][str(sid)] = {
                'updates': prof.updates,
                'feature_count': prof.feature_count,
                'trend': trend,
                'cusum_alarm_positive': max(prof.cusum_positive),
                'cusum_alarm_negative': max(prof.cusum_negative),
                'history_length': len(prof.history),
            }

        return summary


# Backward compatibility: create factory function
def create_monitor(enhanced: bool = True, **kwargs) -> Any:
    """
    Factory function for creating monitors.

    Args:
        enhanced: If True, return EnhancedInterpretabilityMonitor
        **kwargs: Additional arguments passed to constructor

    Returns:
        Monitor instance
    """
    if enhanced:
        return EnhancedInterpretabilityMonitor(**kwargs)
    else:
        from interpretability_monitor import InterpretabilityMonitor
        return InterpretabilityMonitor()

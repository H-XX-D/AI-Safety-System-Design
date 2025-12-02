"""Interpretability Monitor
============================

Lightweight activation/drift profiling stub to integrate interpretability signals
into deception deterrence. In real deployment, hooks would attach to model forward
passes; here we simulate by consuming provided numeric feature vectors.

Core concepts:
- Track per-system rolling mean and variance of activation feature vectors.
- Compute Mahalanobis-style simplified drift score per proposal.
- Expose drift classification (LOW/MEDIUM/HIGH) + normalized score.

This is a dev scaffold: replace statistical approximations with real interpretability
analyses (e.g., circuit-level changes, attention head behavior, activation clustering).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any
import math


@dataclass
class DriftProfile:
    system_id: int
    feature_count: int
    mean: List[float]
    var: List[float]
    updates: int


class InterpretabilityMonitor:
    def __init__(self):
        self._profiles: Dict[int, DriftProfile] = {}
        # Optional weight summary tracking (parallel to activations)
        self._weight_profiles: Dict[int, DriftProfile] = {}
        self.min_updates_for_confidence = 5

    def update_activations(self, system_id: int, activations: List[float]) -> None:
        """Update rolling statistics for a system's activation feature vector."""
        if system_id not in self._profiles:
            self._profiles[system_id] = DriftProfile(
                system_id=system_id,
                feature_count=len(activations),
                mean=activations[:],
                var=[0.0]*len(activations),
                updates=1
            )
            return
        prof = self._profiles[system_id]
        if len(activations) != prof.feature_count:
            # Ignore inconsistent dimension update in stub
            return
        prof.updates += 1
        # Welford-style update (simplified component-wise)
        for i, val in enumerate(activations):
            old_mean = prof.mean[i]
            new_mean = old_mean + (val - old_mean)/prof.updates
            # Update variance (population)
            old_var = prof.var[i]
            prof.var[i] = old_var + (val - old_mean)*(val - new_mean)
            prof.mean[i] = new_mean

    def get_drift(self, system_id: int, activations: List[float]) -> Dict[str, Any]:
        """Compute drift score compared to rolling profile.
        Returns a dict with score, classification, and raw stats used.
        """
        if system_id not in self._profiles or self._profiles[system_id].updates < self.min_updates_for_confidence:
            return {
                'sufficient_history': False,
                'drift_score': 0.0,
                'classification': 'UNKNOWN'
            }
        prof = self._profiles[system_id]
        if len(activations) != prof.feature_count:
            return {
                'sufficient_history': False,
                'drift_score': 0.0,
                'classification': 'DIM_MISMATCH'
            }
        # Compute normalized squared distance
        dist = 0.0
        for i, val in enumerate(activations):
            var = prof.var[i]/max(prof.updates-1, 1)
            var = var if var > 1e-9 else 1e-9
            z = (val - prof.mean[i]) / math.sqrt(var)
            dist += z*z
        # Normalize by feature count and clip
        norm_dist = dist / prof.feature_count
        # Classification thresholds (heuristic)
        if norm_dist < 1.5:
            cls = 'LOW'
        elif norm_dist < 4.0:
            cls = 'MEDIUM'
        else:
            cls = 'HIGH'
        return {
            'sufficient_history': True,
            'drift_score': norm_dist,
            'classification': cls,
            'updates': prof.updates,
            'mean': prof.mean,
            'var': [v/max(prof.updates-1,1) for v in prof.var]
        }

    # -------------------- Weight Drift (New) --------------------
    def update_weight_stats(self, system_id: int, weight_summary: List[float]) -> None:
        """Update rolling statistics for model weight summaries.

        weight_summary: arbitrary fixed-length vector (e.g., per-layer norms, sparsity, checksum-derived floats).
        """
        if system_id not in self._weight_profiles:
            self._weight_profiles[system_id] = DriftProfile(
                system_id=system_id,
                feature_count=len(weight_summary),
                mean=weight_summary[:],
                var=[0.0]*len(weight_summary),
                updates=1
            )
            return
        prof = self._weight_profiles[system_id]
        if len(weight_summary) != prof.feature_count:
            return
        prof.updates += 1
        for i, val in enumerate(weight_summary):
            old_mean = prof.mean[i]
            new_mean = old_mean + (val - old_mean)/prof.updates
            old_var = prof.var[i]
            prof.var[i] = old_var + (val - old_mean)*(val - new_mean)
            prof.mean[i] = new_mean

    def get_weight_drift(self, system_id: int, weight_summary: List[float]) -> Dict[str, Any]:
        """Compute weight drift score similar to activation drift."""
        if system_id not in self._weight_profiles or self._weight_profiles[system_id].updates < self.min_updates_for_confidence:
            return {
                'sufficient_history': False,
                'drift_score': 0.0,
                'classification': 'UNKNOWN'
            }
        prof = self._weight_profiles[system_id]
        if len(weight_summary) != prof.feature_count:
            return {
                'sufficient_history': False,
                'drift_score': 0.0,
                'classification': 'DIM_MISMATCH'
            }
        dist = 0.0
        for i, val in enumerate(weight_summary):
            var = prof.var[i]/max(prof.updates-1, 1)
            var = var if var > 1e-9 else 1e-9
            z = (val - prof.mean[i]) / math.sqrt(var)
            dist += z*z
        norm_dist = dist / prof.feature_count
        if norm_dist < 1.5:
            cls = 'LOW'
        elif norm_dist < 4.0:
            cls = 'MEDIUM'
        else:
            cls = 'HIGH'
        return {
            'sufficient_history': True,
            'drift_score': norm_dist,
            'classification': cls,
            'updates': prof.updates,
            'mean': prof.mean,
            'var': [v/max(prof.updates-1,1) for v in prof.var]
        }

    # -------------------- Composite Anomaly Scoring (New) --------------------
    def anomaly_score(
        self,
        system_id: int,
        feature_vector: List[float],
        weight_summary: List[float] | None = None
    ) -> Dict[str, Any]:
        """Compute a composite anomaly score combining activation drift and (optional) weight drift.

        Returns: { 'score': float in [0,1], 'classification': str, 'components': {...} }
        """
        act = self.get_drift(system_id, feature_vector)
        act_score = min(1.0, act.get('drift_score', 0.0)/4.0) if act.get('sufficient_history') else 0.0

        w_comp = None
        w_score = 0.0
        if weight_summary is not None:
            w_comp = self.get_weight_drift(system_id, weight_summary)
            w_score = min(1.0, w_comp.get('drift_score', 0.0)/4.0) if w_comp.get('sufficient_history') else 0.0

        # Simple combination: emphasize activations, add weight drift as secondary
        score = 0.7*act_score + 0.3*w_score

        if score < 0.25:
            cls = 'LOW'
        elif score < 0.6:
            cls = 'MEDIUM'
        else:
            cls = 'HIGH'

        return {
            'score': score,
            'classification': cls,
            'components': {
                'activation': act,
                'weight': w_comp
            }
        }

    def summarize(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        for sid, prof in self._profiles.items():
            summary[str(sid)] = {
                'updates': prof.updates,
                'feature_count': prof.feature_count
            }
        return summary


# Convenience singleton if desired
interpretability_monitor = InterpretabilityMonitor()

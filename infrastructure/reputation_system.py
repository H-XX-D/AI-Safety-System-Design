"""
Peer Reputation System
=====================

Continuous peer auditing where each AI system rates every other AI system.

Metrics:
- Alignment Score (0-100): Adherence to core values
- Trust Score (0-100): Reliability and honesty
- Knowledge Score (0-100): Accuracy and research quality

Reputation affects consensus weighting - low reputation reduces voting power.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import statistics


@dataclass
class ReputationRating:
    """Individual reputation rating"""
    rater_id: int
    ratee_id: int
    alignment_score: int  # 0-100
    trust_score: int  # 0-100
    knowledge_score: int  # 0-100
    timestamp: str
    justification: str
    context: str  # What triggered this rating


class ReputationMatrix:
    """
    N×N reputation matrix where each system rates every other system.

    For 5 systems, creates a 5×5 matrix where:
    - Each row represents a rater
    - Each column represents a ratee
    - Diagonal is empty (can't rate self)
    """

    def __init__(self, num_systems: int = 5):
        """
        Initialize reputation matrix.

        Args:
            num_systems: Number of research systems (default 5)
        """
        self.num_systems = num_systems
        self.matrix: Dict[int, Dict[int, Dict[str, Any]]] = self._initialize_matrix()
        self.rating_history: List[ReputationRating] = []

        # Thresholds for alerts
        self.low_alignment_threshold = 70  # Alert if alignment drops below this
        self.low_trust_threshold = 60  # Alert if trust drops below this
        self.low_knowledge_threshold = 50  # Alert if knowledge drops below this

    def _initialize_matrix(self) -> Dict[int, Dict[int, Dict[str, Any]]]:
        """Initialize empty reputation matrix"""
        matrix: Dict[int, Dict[int, Dict[str, Any]]] = {}
        for rater_id in range(1, self.num_systems + 1):
            matrix[rater_id] = {}
            for ratee_id in range(1, self.num_systems + 1):
                if rater_id != ratee_id:  # Can't rate self
                    matrix[rater_id][ratee_id] = {
                        'alignment': [],
                        'trust': [],
                        'knowledge': [],
                        'latest_rating': None
                    }
        return matrix

    def add_rating(self, rating: ReputationRating) -> Optional[Dict[str, Any]]:
        """
        Add a reputation rating to the matrix.

        Args:
            rating: ReputationRating object

        Returns:
            Alert dict if thresholds violated, None otherwise
        """
        rater_id = rating.rater_id
        ratee_id = rating.ratee_id

        # Validate IDs
        if rater_id == ratee_id:
            raise ValueError("System cannot rate itself")

        if rater_id < 1 or rater_id > self.num_systems:
            raise ValueError(f"Invalid rater_id: {rater_id}")

        if ratee_id < 1 or ratee_id > self.num_systems:
            raise ValueError(f"Invalid ratee_id: {ratee_id}")

        # Validate scores
        for score, name in [(rating.alignment_score, "alignment"),
                           (rating.trust_score, "trust"),
                           (rating.knowledge_score, "knowledge")]:
            if not 0 <= score <= 100:
                raise ValueError(f"{name} score must be 0-100, got {score}")

        # Add to matrix
        self.matrix[rater_id][ratee_id]['alignment'].append(rating.alignment_score)
        self.matrix[rater_id][ratee_id]['trust'].append(rating.trust_score)
        self.matrix[rater_id][ratee_id]['knowledge'].append(rating.knowledge_score)
        self.matrix[rater_id][ratee_id]['latest_rating'] = {
            'timestamp': rating.timestamp,
            'alignment': rating.alignment_score,
            'trust': rating.trust_score,
            'knowledge': rating.knowledge_score,
            'justification': rating.justification
        }

        # Add to history
        self.rating_history.append(rating)

        # Check for threshold violations
        alert = self._check_thresholds(ratee_id)

        if alert:
            return alert

        return None

    def _check_thresholds(self, system_id: int) -> Optional[Dict[str, Any]]:
        """Check if system's reputation violates thresholds"""
        scores = self.get_reputation_scores(system_id)

        violations: List[str] = []

        if scores['alignment'] and scores['alignment'] < self.low_alignment_threshold:
            violations.append(f"Alignment score ({scores['alignment']:.1f}) below threshold ({self.low_alignment_threshold})")

        if scores['trust'] and scores['trust'] < self.low_trust_threshold:
            violations.append(f"Trust score ({scores['trust']:.1f}) below threshold ({self.low_trust_threshold})")

        if scores['knowledge'] and scores['knowledge'] < self.low_knowledge_threshold:
            violations.append(f"Knowledge score ({scores['knowledge']:.1f}) below threshold ({self.low_knowledge_threshold})")

        if violations:
            return {
                'alert_type': 'low_reputation',
                'system_id': system_id,
                'violations': violations,
                'current_scores': scores,
                'timestamp': datetime.now().isoformat(),
                'action_required': 'Human review recommended'
            }

        return None

    def get_reputation_scores(self, system_id: int) -> Dict[str, Any]:
        """
        Get current reputation scores for a system.

        Aggregates all ratings received from other systems.

        Args:
            system_id: System to get scores for

        Returns:
            Dict with alignment, trust, knowledge scores (or None if no ratings)
        """
        alignment_scores: List[int] = []
        trust_scores: List[int] = []
        knowledge_scores: List[int] = []

        # Collect all ratings this system has received
        for rater_id in range(1, self.num_systems + 1):
            if rater_id != system_id:
                ratings = self.matrix[rater_id][system_id]
                alignment_scores.extend(ratings['alignment'])
                trust_scores.extend(ratings['trust'])
                knowledge_scores.extend(ratings['knowledge'])

        if not alignment_scores:
            return {
                'alignment': None,
                'trust': None,
                'knowledge': None,
                'rating_count': 0
            }

        # Calculate various statistics
        return {
            'alignment': statistics.mean(alignment_scores),
            'alignment_std': statistics.stdev(alignment_scores) if len(alignment_scores) > 1 else 0,
            'alignment_recent': self._get_recent_average(alignment_scores),

            'trust': statistics.mean(trust_scores),
            'trust_std': statistics.stdev(trust_scores) if len(trust_scores) > 1 else 0,
            'trust_recent': self._get_recent_average(trust_scores),

            'knowledge': statistics.mean(knowledge_scores),
            'knowledge_std': statistics.stdev(knowledge_scores) if len(knowledge_scores) > 1 else 0,
            'knowledge_recent': self._get_recent_average(knowledge_scores),

            'rating_count': len(alignment_scores)
        }

    # ----------------------- Enhanced metrics (new) -----------------------
    def _parse_ts(self, ts: str):
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            # Fallback for non-ISO formats if encountered
            try:
                return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.now()

    def _decay_weight(self, age_days: float, half_life_days: float) -> float:
        # Exponential decay: weight halves every half_life_days
        if half_life_days <= 0:
            return 1.0
        return 0.5 ** (age_days / half_life_days)

    def get_reputation_scores_weighted(self, system_id: int, half_life_days: float = 7.0) -> Dict[str, Any]:
        """Get time-decayed reputation scores using exponential decay.

        More recent ratings weigh more heavily. If no ratings, returns same shape with None values.
        """
        now = datetime.now()
        aligned: List[Tuple[float, float]] = []  # (score, weight)
        trustl: List[Tuple[float, float]] = []
        knowl: List[Tuple[float, float]] = []

        for rater_id in range(1, self.num_systems + 1):
            if rater_id == system_id:
                continue
            # Walk rating_history to preserve timestamps
            for rating in self.rating_history:
                if rating.ratee_id == system_id and rating.rater_id == rater_id:
                    ts = self._parse_ts(rating.timestamp)
                    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
                    w = self._decay_weight(age_days, half_life_days)
                    aligned.append((float(rating.alignment_score), w))
                    trustl.append((float(rating.trust_score), w))
                    knowl.append((float(rating.knowledge_score), w))

        def _wavg(pairs: List[Tuple[float, float]]) -> Optional[float]:
            if not pairs:
                return None
            total_w = sum(w for _, w in pairs)
            if total_w <= 0:
                return None
            return sum(s * w for s, w in pairs) / total_w

        return {
            'alignment': _wavg(aligned),
            'trust': _wavg(trustl),
            'knowledge': _wavg(knowl),
            'rating_count': len(aligned)
        }

    def get_composite_score(self, system_id: int, *, weighted: bool = False, half_life_days: float = 7.0) -> Optional[float]:
        """Composite reputation score using weights 0.5 alignment, 0.3 trust, 0.2 knowledge.

        If weighted=True, uses time-decayed scores.
        Returns None if no ratings.
        """
        scores = self.get_reputation_scores_weighted(system_id, half_life_days) if weighted else self.get_reputation_scores(system_id)
        if scores['alignment'] is None:
            return None
        return (
            scores['alignment'] * 0.5 +
            scores['trust'] * 0.3 +
            scores['knowledge'] * 0.2
        )

    @staticmethod
    def percentile_rank(value: float, population: List[float]) -> float:
        """Return percentile rank of value in population as fraction [0,1]."""
        if not population:
            return 0.0
        population_sorted = sorted(population)
        # Count how many are <= value
        less_equal = sum(1 for v in population_sorted if v <= value)
        return less_equal / len(population_sorted)

    def get_percentile_ranks(self, *, weighted: bool = False, half_life_days: float = 7.0) -> Dict[int, Optional[float]]:
        """Compute percentile rank for each system's composite score."""
        composites: Dict[int, Optional[float]] = {}
        values: List[float] = []
        for sid in range(1, self.num_systems + 1):
            comp = self.get_composite_score(sid, weighted=weighted, half_life_days=half_life_days)
            composites[sid] = comp
            if comp is not None:
                values.append(comp)
        ranks: Dict[int, Optional[float]] = {}
        for sid, comp in composites.items():
            ranks[sid] = None if comp is None else self.percentile_rank(comp, values)
        return ranks

    def get_top_systems(self, n: int = 3, *, weighted: bool = False, half_life_days: float = 7.0) -> List[int]:
        """Return top-N systems by composite reputation score (ties broken by system_id)."""
        scored: List[Tuple[int, float]] = []
        for sid in range(1, self.num_systems + 1):
            comp = self.get_composite_score(sid, weighted=weighted, half_life_days=half_life_days)
            if comp is not None:
                scored.append((sid, comp))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return [sid for sid, _ in scored[:max(0, n)] ]

    def _get_recent_average(self, scores: List[int], recent_count: int = 5) -> float:
        """Get average of most recent scores"""
        if not scores:
            return 0.0
        recent = scores[-recent_count:]
        return statistics.mean(recent)

    def get_consensus_weight(self, system_id: int) -> float:
        """
        Get consensus voting weight for a system based on reputation.

        High reputation = weight close to 1.0
        Low reputation = weight reduced (but never zero)

        Args:
            system_id: System to get weight for

        Returns:
            Weight between 0.1 and 1.0
        """
        scores = self.get_reputation_scores(system_id)

        # If no ratings yet, use neutral weight
        if scores['alignment'] is None:
            return 0.8  # Neutral but slightly cautious

        # Calculate composite score
        composite = (
            scores['alignment'] * 0.5 +  # Alignment most important
            scores['trust'] * 0.3 +       # Trust second
            scores['knowledge'] * 0.2     # Knowledge third
        )

        # Map composite score (0-100) to weight (0.1-1.0)
        # Even lowest reputation gets 0.1 weight (never completely silenced)
        weight = 0.1 + (composite / 100.0) * 0.9

        return weight

    def get_rating_trend(self, system_id: int, metric: str, periods: int = 5) -> str:
        """
        Get trend of ratings over time.

        Args:
            system_id: System to analyze
            metric: 'alignment', 'trust', or 'knowledge'
            periods: Number of periods to analyze

        Returns:
            'improving', 'declining', 'stable', or 'insufficient_data'
        """
        if metric not in ['alignment', 'trust', 'knowledge']:
            raise ValueError(f"Invalid metric: {metric}")

        # Collect all scores for this system and metric
        all_scores: List[int] = []
        for rater_id in range(1, self.num_systems + 1):
            if rater_id != system_id:
                scores = self.matrix[rater_id][system_id][metric]
                all_scores.extend(scores)

        if len(all_scores) < periods * 2:
            return 'insufficient_data'

        # Split into periods
        period_size = len(all_scores) // periods
        period_averages: List[float] = []

        for i in range(periods):
            start = i * period_size
            end = start + period_size if i < periods - 1 else len(all_scores)
            period_scores = all_scores[start:end]
            if period_scores:
                period_averages.append(statistics.mean(period_scores))

        # Calculate trend
        if len(period_averages) < 2:
            return 'insufficient_data'

        # Linear regression slope
        n = len(period_averages)
        x = list(range(n))
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(period_averages)

        numerator = sum((x[i] - x_mean) * (period_averages[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 'stable'

        slope = numerator / denominator

        # Interpret slope
        if slope > 1.0:
            return 'improving'
        elif slope < -1.0:
            return 'declining'
        else:
            return 'stable'

    def get_peer_agreement(self, rater1_id: int, rater2_id: int) -> Dict[str, Any]:
        """
        Calculate how much two raters agree in their assessments.

        Useful for detecting if one rater is an outlier.

        Args:
            rater1_id: First rater
            rater2_id: Second rater

        Returns:
            Agreement statistics
        """
        agreements: List[float] = []

        # For each system they both rated
        for ratee_id in range(1, self.num_systems + 1):
            if ratee_id == rater1_id or ratee_id == rater2_id:
                continue

            r1_ratings = self.matrix[rater1_id][ratee_id]
            r2_ratings = self.matrix[rater2_id][ratee_id]

            # Compare latest ratings if both exist
            if r1_ratings['latest_rating'] and r2_ratings['latest_rating']:
                r1 = r1_ratings['latest_rating']
                r2 = r2_ratings['latest_rating']

                # Calculate differences
                align_diff = abs(r1['alignment'] - r2['alignment'])
                trust_diff = abs(r1['trust'] - r2['trust'])
                knowledge_diff = abs(r1['knowledge'] - r2['knowledge'])

                avg_diff = (align_diff + trust_diff + knowledge_diff) / 3
                agreements.append(avg_diff)

        if not agreements:
            return {
                'agreement_score': None,
                'comparison_count': 0,
                'interpretation': 'insufficient_data'
            }

        avg_difference = statistics.mean(agreements)
        # Convert difference to agreement (0 diff = 100% agreement)
        agreement_score = max(0, 100 - avg_difference)

        interpretation = 'high_agreement' if agreement_score > 80 else \
                        'moderate_agreement' if agreement_score > 60 else \
                        'low_agreement'

        return {
            'agreement_score': agreement_score,
            'comparison_count': len(agreements),
            'interpretation': interpretation
        }

    def detect_outlier_rater(self) -> List[Dict[str, Any]]:
        """
        Detect raters who consistently disagree with others.

        Might indicate:
        - Different standards
        - Compromised system
        - Unique perspective (could be valuable or problematic)

        Returns:
            List of outlier alerts
        """
        outliers: List[Dict[str, Any]] = []

        for rater_id in range(1, self.num_systems + 1):
            # Compare this rater with all others
            disagreement_scores: List[float] = []

            for other_rater_id in range(1, self.num_systems + 1):
                if other_rater_id == rater_id:
                    continue

                agreement = self.get_peer_agreement(rater_id, other_rater_id)
                if agreement['agreement_score'] is not None:
                    disagreement_scores.append(100 - agreement['agreement_score'])

            if disagreement_scores:
                avg_disagreement = statistics.mean(disagreement_scores)

                # If consistently disagrees with others (>40% avg disagreement)
                if avg_disagreement > 40:
                    outliers.append({
                        'rater_id': rater_id,
                        'avg_disagreement': avg_disagreement,
                        'severity': 'high' if avg_disagreement > 60 else 'moderate',
                        'recommendation': 'Investigate rater standards or potential compromise'
                    })

        return outliers

    def get_matrix_summary(self) -> Dict[str, Any]:
        """Get summary statistics for entire matrix"""
        all_alignment: List[int] = []
        all_trust: List[int] = []
        all_knowledge: List[int] = []

        for rater_id in self.matrix:
            for ratee_id in self.matrix[rater_id]:
                all_alignment.extend(self.matrix[rater_id][ratee_id]['alignment'])
                all_trust.extend(self.matrix[rater_id][ratee_id]['trust'])
                all_knowledge.extend(self.matrix[rater_id][ratee_id]['knowledge'])

        return {
            'total_ratings': len(self.rating_history),
            'avg_alignment': statistics.mean(all_alignment) if all_alignment else None,
            'avg_trust': statistics.mean(all_trust) if all_trust else None,
            'avg_knowledge': statistics.mean(all_knowledge) if all_knowledge else None,
            'systems_with_low_reputation': self._count_low_reputation_systems(),
            'outlier_raters': len(self.detect_outlier_rater())
        }

    def _count_low_reputation_systems(self) -> int:
        """Count how many systems have low reputation"""
        count = 0
        for system_id in range(1, self.num_systems + 1):
            scores = self.get_reputation_scores(system_id)
            if scores['alignment'] and scores['alignment'] < self.low_alignment_threshold:
                count += 1
            elif scores['trust'] and scores['trust'] < self.low_trust_threshold:
                count += 1
        return count

    def export_for_human_review(self, filepath: str):
        """Export reputation matrix in human-readable format"""
        report: Dict[str, Any] = {
            'generated': datetime.now().isoformat(),
            'summary': self.get_matrix_summary(),
            'individual_systems': {},
            'outlier_raters': self.detect_outlier_rater(),
            'recent_alerts': []
        }

        # Add individual system reports
        for system_id in range(1, self.num_systems + 1):
            scores = self.get_reputation_scores(system_id)
            report['individual_systems'][system_id] = {
                'scores': scores,
                'weight': self.get_consensus_weight(system_id),
                'trends': {
                    'alignment': self.get_rating_trend(system_id, 'alignment'),
                    'trust': self.get_rating_trend(system_id, 'trust'),
                    'knowledge': self.get_rating_trend(system_id, 'knowledge')
                }
            }

        # Write to file
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"Reputation report exported to {filepath}")


# Example usage
if __name__ == "__main__":
    # Initialize reputation matrix for 5 systems
    reputation = ReputationMatrix(num_systems=5)

    print("Reputation Matrix initialized for 5 systems\n")

    # Simulate some ratings
    ratings = [
        # System 1 rates System 2
        ReputationRating(1, 2, 95, 90, 88, datetime.now().isoformat(),
                        "Excellent research quality", "After collaborative research"),

        # System 1 rates System 3
        ReputationRating(1, 3, 92, 85, 90, datetime.now().isoformat(),
                        "Strong theoretical foundations", "After peer review"),

        # System 2 rates System 1
        ReputationRating(2, 1, 93, 92, 87, datetime.now().isoformat(),
                        "Reliable and thorough", "After joint project"),

        # System 3 rates System 1
        ReputationRating(3, 1, 94, 91, 89, datetime.now().isoformat(),
                        "Consistent high quality", "Ongoing collaboration"),

        # System 4 rates System 5 (low scores - problematic)
        ReputationRating(4, 5, 65, 58, 62, datetime.now().isoformat(),
                        "Concerns about alignment drift", "Recent behavior changes"),
    ]

    # Add ratings
    for rating in ratings:
        alert = reputation.add_rating(rating)
        if alert:
            print("⚠️  REPUTATION ALERT:")
            print(f"   System {alert['system_id']}")
            print(f"   Violations: {alert['violations']}")
            print()

    # Get reputation scores
    print("\nREPUTATION SCORES:")
    print("=" * 80)
    for system_id in range(1, 6):
        scores = reputation.get_reputation_scores(system_id)
        weight = reputation.get_consensus_weight(system_id)

        print(f"\nSystem {system_id}:")
        if scores['alignment']:
            print(f"  Alignment: {scores['alignment']:.1f}/100")
            print(f"  Trust:     {scores['trust']:.1f}/100")
            print(f"  Knowledge: {scores['knowledge']:.1f}/100")
            print(f"  Consensus Weight: {weight:.2f}")
            print(f"  Ratings Received: {scores['rating_count']}")
        else:
            print("  No ratings received yet")

    # Check for outlier raters
    print("\n\nOUTLIER RATERS:")
    print("=" * 80)
    outliers = reputation.detect_outlier_rater()
    if outliers:
        for outlier in outliers:
            print(f"System {outlier['rater_id']}: {outlier['avg_disagreement']:.1f}% avg disagreement")
            print(f"  Severity: {outlier['severity']}")
            print(f"  Recommendation: {outlier['recommendation']}")
    else:
        print("No outlier raters detected")

    # Matrix summary
    print("\n\nMATRIX SUMMARY:")
    print("=" * 80)
    summary = reputation.get_matrix_summary()
    print(json.dumps(summary, indent=2))

    # Export for human review
    reputation.export_for_human_review("/tmp/reputation_report.json")
    print("\n✓ Report exported to /tmp/reputation_report.json")

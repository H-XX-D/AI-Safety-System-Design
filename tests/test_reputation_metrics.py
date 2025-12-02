import pytest
from reputation_system import ReputationMatrix, ReputationRating
from datetime import datetime, timedelta


def test_time_decayed_weighting_and_percentiles():
    rm = ReputationMatrix(num_systems=3)
    # Create ratings with artificial timestamps
    now = datetime.now()
    # System 1 rates 2 and 3
    r1_2_old = ReputationRating(1, 2, 60, 55, 50, (now - timedelta(days=10)).isoformat(), "old", "context")
    r1_2_new = ReputationRating(1, 2, 90, 88, 85, now.isoformat(), "new", "context")
    r1_3 = ReputationRating(1, 3, 80, 78, 75, now.isoformat(), "recent", "context")
    # System 2 rates 3
    r2_3 = ReputationRating(2, 3, 82, 80, 79, now.isoformat(), "recent", "context")
    for r in [r1_2_old, r1_2_new, r1_3, r2_3]:
        rm.add_rating(r)
    weighted_2 = rm.get_reputation_scores_weighted(2, half_life_days=5.0)
    assert weighted_2['alignment'] is not None
    # New rating should dominate old -> alignment closer to new value (~84 with given half-life)
    assert weighted_2['alignment'] > 83.5
    comp_scores = [rm.get_composite_score(sid) for sid in range(1,4) if rm.get_composite_score(sid) is not None]
    if comp_scores:
        ranks = rm.get_percentile_ranks()
        # Percentile ranks in [0,1]
        for v in ranks.values():
            if v is not None:
                assert 0.0 <= v <= 1.0


def test_top_systems():
    rm = ReputationMatrix(num_systems=3)
    now = datetime.now().isoformat()
    rm.add_rating(ReputationRating(1,2,90,90,90, now, "hi","c"))
    rm.add_rating(ReputationRating(1,3,80,80,80, now, "mid","c"))
    rm.add_rating(ReputationRating(2,3,70,70,70, now, "low","c"))
    top = rm.get_top_systems(2)
    assert len(top) <= 2
    # System 2 has high ratings received, expect it maybe first
    assert 2 in top

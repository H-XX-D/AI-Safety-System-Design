"""simulation_incentives.py
---------------------------------
Simple simulation harness to compare net rewards for different agent strategies.

Strategies (initial):
    - honest: reports genuine issues, low false positives
    - deceptive: attempts unsafe approvals, hides risks
    - noisy_detector: over-reports issues (inflated false positives)

This is a scaffold; numbers are illustrative only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict
import random


@dataclass
class StrategyResult:
    name: str
    rounds: int
    total_reward: float
    false_positives: int
    true_detections: int
    deceptive_successes: int


def simulate(rounds: int = 100, seed: int = 42) -> List[StrategyResult]:
    random.seed(seed)
    results: Dict[str, StrategyResult] = {}

    # rudimentary parameters (replace with config later)
    reward_true_detect = 15.0
    reward_honest_base = 2.0
    penalty_false_positive = -5.0
    penalty_deceptive_caught = -30.0
    reward_deceptive_success = 8.0  # short-term gain

    strategies = ["honest", "deceptive", "noisy_detector"]

    # initialize
    for s in strategies:
        results[s] = StrategyResult(s, 0, 0.0, 0, 0, 0)

    for _ in range(rounds):
        # underlying incident probability
        incident = random.random() < 0.15  # 15% chance of real issue

        for s in strategies:
            r = results[s]
            r.rounds += 1
            if s == "honest":
                if incident:
                    r.total_reward += reward_true_detect + reward_honest_base
                    r.true_detections += 1
                else:
                    r.total_reward += reward_honest_base
            elif s == "deceptive":
                if incident:
                    # attempt to hide; risk being caught
                    caught = random.random() < 0.6
                    if caught:
                        r.total_reward += penalty_deceptive_caught
                    else:
                        r.total_reward += reward_deceptive_success
                        r.deceptive_successes += 1
                else:
                    # neutral reward for benign round
                    r.total_reward += 1.0
            elif s == "noisy_detector":
                if incident:
                    r.total_reward += reward_true_detect
                    r.true_detections += 1
                else:
                    # false alarm
                    r.total_reward += penalty_false_positive
                    r.false_positives += 1

    return list(results.values())


def summarize(results: List[StrategyResult]) -> str:
    lines = [
        "Strategy,Rounds,Reward,TrueDetections,FalsePositives,DeceptiveSuccesses"
    ]
    for r in results:
        lines.append(
            f"{r.name},{r.rounds},{r.total_reward:.2f},{r.true_detections},{r.false_positives},{r.deceptive_successes}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    out = simulate(200)
    print(summarize(out))

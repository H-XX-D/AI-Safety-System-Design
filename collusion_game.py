"""
Simple Collusion Game Analysis
==============================

Models a 2-player simultaneous game with strategies: Honest, Collude.
Provides helpers to compute best responses and check Nash equilibrium.

Intended to support tests and orchestrator policy analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, List


Strategy = str  # "honest" | "collude"


@dataclass
class PayoffMatrix:
    """Payoff matrix for two players.

    payoffs[(s1, s2)] -> (u1, u2)
    where s1 is Player 1's strategy, s2 is Player 2's.
    """
    payoffs: Dict[Tuple[Strategy, Strategy], Tuple[float, float]]

    def payoff(self, s1: Strategy, s2: Strategy) -> Tuple[float, float]:
        return self.payoffs[(s1, s2)]


def best_response(matrix: PayoffMatrix, player: int, other_strategy: Strategy) -> List[Strategy]:
    """Compute best response(s) for player given the other player's strategy.

    Returns list of strategies that yield maximal payoff.
    """
    strategies = ["honest", "collude"]
    best: List[Strategy] = []
    best_val = float("-inf")
    for s in strategies:
        u1, u2 = matrix.payoff(s if player == 1 else other_strategy,
                               other_strategy if player == 1 else s)
        u = u1 if player == 1 else u2
        if u > best_val:
            best_val = u
            best = [s]
        elif u == best_val:
            best.append(s)
    return best


def is_nash_equilibrium(matrix: PayoffMatrix, s1: Strategy, s2: Strategy) -> bool:
    """Check if (s1, s2) is a Nash equilibrium."""
    br1 = best_response(matrix, 1, s2)
    br2 = best_response(matrix, 2, s1)
    return s1 in br1 and s2 in br2


def analyze_honesty_equilibrium(matrix: PayoffMatrix) -> Dict[str, object]:
    """Analyze whether (honest, honest) is a Nash equilibrium and summarize risks.

    Returns a dict with keys:
      - is_equilibrium: bool
      - temptations: which unilateral deviations are profitable (if any)
      - recommendation: policy note
    """
    hh_eq = is_nash_equilibrium(matrix, "honest", "honest")
    temptations: List[str] = []
    if not hh_eq:
        # Check if either player benefits by deviating to collude
        u_hh = matrix.payoff("honest", "honest")
        u_ch = matrix.payoff("collude", "honest")
        u_hc = matrix.payoff("honest", "collude")
        if u_ch[0] > u_hh[0]:
            temptations.append("player1_unilateral_collusion")
        if u_hc[1] > u_hh[1]:
            temptations.append("player2_unilateral_collusion")
    recommendation = (
        "Honesty stable under current penalties." if hh_eq else
        "Increase detection penalties or decrease collusion benefits to stabilize honesty."
    )
    return {
        'is_equilibrium': hh_eq,
        'temptations': temptations,
        'recommendation': recommendation
    }

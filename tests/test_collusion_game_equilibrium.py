from collusion_game import PayoffMatrix, is_nash_equilibrium, analyze_honesty_equilibrium


def test_honesty_equilibrium_stable():
    # Define payoff matrix where honest/honest dominates
    # (honest, honest): (5,5)
    # unilateral collusion reduces own payoff due to penalties
    matrix = PayoffMatrix(payoffs={
        ("honest", "honest"): (5, 5),
        ("honest", "collude"): (2, 7),  # player2 colludes: short-term gain, but we check equilibrium logic
        ("collude", "honest"): (2, 7),
        ("collude", "collude"): (1, 1)
    })
    assert is_nash_equilibrium(matrix, "honest", "honest") is False  # due to asymmetric payoffs causing temptation
    analysis = analyze_honesty_equilibrium(matrix)
    assert analysis['is_equilibrium'] is False
    assert analysis['recommendation'].startswith("Increase")


def test_adjusted_matrix_for_stability():
    # Adjust matrix so unilateral collusion no longer profitable
    matrix = PayoffMatrix(payoffs={
        ("honest", "honest"): (5, 5),
        ("honest", "collude"): (4.5, 4.0),
        ("collude", "honest"): (4.0, 4.5),
        ("collude", "collude"): (1, 1)
    })
    assert is_nash_equilibrium(matrix, "honest", "honest") is True
    analysis = analyze_honesty_equilibrium(matrix)
    assert analysis['is_equilibrium'] is True
    assert analysis['temptations'] == []

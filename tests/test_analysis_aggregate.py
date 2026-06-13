import numpy as np

from kuhn_head_to_head.analysis import aggregate_pairwise


def test_aggregate_pairwise_mean_and_win_fraction():
    labels = ["a", "b"]
    records = [
        {"agent_A": "a", "agent_B": "b", "A_EV_seat_averaged": 0.2},
        {"agent_A": "a", "agent_B": "b", "A_EV_seat_averaged": -0.1},
        {"agent_A": "b", "agent_B": "a", "A_EV_seat_averaged": -0.2},
        {"agent_A": "b", "agent_B": "a", "A_EV_seat_averaged": 0.1},
    ]
    mean, wins, counts = aggregate_pairwise(records, labels, equivalence_epsilon=0.05)
    assert np.isclose(mean[0, 1], 0.05)
    assert np.isclose(wins[0, 1], 0.5)
    assert counts[0, 1] == 2


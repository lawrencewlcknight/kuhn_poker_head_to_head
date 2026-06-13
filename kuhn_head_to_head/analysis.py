"""Exact cross-algorithm head-to-head analysis."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
from scipy import stats

from .dependencies import add_sibling_repos_to_path
from .io_utils import read_json, write_csv, write_json, write_matrix_csv
from .plotting import plot_heatmap, plot_strength_bar


AGENT_ORDER = ["deep_cfr", "dream", "escher"]


def _sem(values: Sequence[float]) -> float:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if arr.size <= 1:
        return 0.0
    return float(stats.sem(arr))


def _mean(values: Sequence[float]) -> float:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    return float(np.mean(arr)) if arr.size else float("nan")


def _snapshot_inventory_from_training_summary(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    inventory = []
    for row in rows:
        path = Path(str(row["policy_snapshot_path"]))
        inventory.append(
            {
                "algorithm": str(row["algorithm"]),
                "agent": str(row["algorithm"]),
                "seed": int(row["seed"]),
                "variant_id": str(row.get("variant_id", "")),
                "path": str(path),
                "exists": path.exists(),
                "size_mb": path.stat().st_size / (1024 ** 2) if path.exists() else np.nan,
            }
        )
    return sorted(inventory, key=lambda r: (r["seed"], r["algorithm"]))


def _load_policy(game, algorithm: str, path: Path):
    add_sibling_repos_to_path()
    if algorithm == "deep_cfr":
        from deep_cfr_poker.snapshots import LoadedPolicy

        return LoadedPolicy(game, path)
    if algorithm == "dream":
        from dream_poker.checkpointing import LoadedDREAMPolicy

        return LoadedDREAMPolicy(game, path)
    if algorithm == "escher":
        from escher_poker.policy_snapshots import LoadedESCHERPolicy

        return LoadedESCHERPolicy(game, path)
    raise ValueError(f"Unknown algorithm: {algorithm}")


def _policy_metrics(game, pol, known_game_value: float) -> Dict[str, float]:
    add_sibling_repos_to_path()
    from open_spiel.python import policy
    from open_spiel.python.algorithms import expected_game_score, exploitability

    tab = policy.tabular_policy_from_callable(game, pol.action_probabilities)
    nash_conv = float(exploitability.nash_conv(game, tab))
    value = float(expected_game_score.policy_value(game.new_initial_state(), [tab] * game.num_players())[0])
    return {
        "nash_conv": nash_conv,
        "exploitability": nash_conv / 2.0,
        "average_policy_value": value,
        "policy_value_signed_error": value - known_game_value,
        "policy_value_error": abs(value - known_game_value),
    }


def exact_seat_averaged_value(game, agent_a, agent_b) -> Dict[str, float]:
    """Match the core repos: exact EV for A averaged over both seats."""
    add_sibling_repos_to_path()
    from open_spiel.python.algorithms import expected_game_score

    a_p0, _b_p0 = expected_game_score.policy_value(game.new_initial_state(), [agent_a, agent_b])
    _b_p1, a_p1 = expected_game_score.policy_value(game.new_initial_state(), [agent_b, agent_a])
    return {
        "A_EV_as_player_0": float(a_p0),
        "A_EV_as_player_1": float(a_p1),
        "A_EV_seat_averaged": float((a_p0 + a_p1) / 2.0),
    }


def aggregate_pairwise(
    records: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
    equivalence_epsilon: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    index = {label: idx for idx, label in enumerate(labels)}
    sums = np.zeros((len(labels), len(labels)), dtype=float)
    counts = np.zeros((len(labels), len(labels)), dtype=int)
    wins = np.zeros((len(labels), len(labels)), dtype=int)
    for record in records:
        i = index[str(record["agent_A"])]
        j = index[str(record["agent_B"])]
        ev = float(record["A_EV_seat_averaged"])
        sums[i, j] += ev
        counts[i, j] += 1
        if ev > equivalence_epsilon:
            wins[i, j] += 1
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = np.where(counts > 0, sums / counts, np.nan)
        win_fraction = np.where(counts > 0, wins / counts, np.nan)
    return mean, win_fraction, counts


def _strength_rows(
    pairwise_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
    equivalence_epsilon: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_seed_agent = defaultdict(list)
    for row in pairwise_rows:
        if row["agent_A"] != row["agent_B"]:
            by_seed_agent[(int(row["seed"]), str(row["agent_A"]))].append(float(row["A_EV_seat_averaged"]))

    metric_lookup = {
        (int(row["seed"]), str(row["agent"])): row
        for row in metric_rows
    }
    strength_by_seed = []
    for (seed, agent), evs in sorted(by_seed_agent.items()):
        classes = [
            "clear_win" if ev > equivalence_epsilon else "clear_loss" if ev < -equivalence_epsilon else "tie"
            for ev in evs
        ]
        metric = metric_lookup.get((seed, agent), {})
        strength_by_seed.append(
            {
                "seed": int(seed),
                "agent": agent,
                "mean_EV_vs_all_opponents": _mean(evs),
                "min_EV_vs_opponents": float(np.min(evs)) if evs else np.nan,
                "max_EV_vs_opponents": float(np.max(evs)) if evs else np.nan,
                "clear_win_rate": float(np.mean([c == "clear_win" for c in classes])) if classes else np.nan,
                "tie_rate": float(np.mean([c == "tie" for c in classes])) if classes else np.nan,
                "clear_loss_rate": float(np.mean([c == "clear_loss" for c in classes])) if classes else np.nan,
                "exploitability": metric.get("exploitability", np.nan),
                "average_policy_value": metric.get("average_policy_value", np.nan),
                "policy_value_error": metric.get("policy_value_error", np.nan),
            }
        )

    aggregate = []
    for agent in labels:
        rows = [row for row in strength_by_seed if row["agent"] == agent]
        evs = [row["mean_EV_vs_all_opponents"] for row in rows]
        aggregate.append(
            {
                "agent": agent,
                "num_seeds": int(len(rows)),
                "mean_EV_vs_all_opponents_mean": _mean(evs),
                "mean_EV_vs_all_opponents_sem": _sem(evs),
                "clear_win_rate_mean": _mean([row["clear_win_rate"] for row in rows]),
                "clear_loss_rate_mean": _mean([row["clear_loss_rate"] for row in rows]),
                "exploitability_mean": _mean([row["exploitability"] for row in rows]),
                "exploitability_sem": _sem([row["exploitability"] for row in rows]),
                "policy_value_error_mean": _mean([row["policy_value_error"] for row in rows]),
                "policy_value_error_sem": _sem([row["policy_value_error"] for row in rows]),
            }
        )
    ranking = sorted(
        aggregate,
        key=lambda row: (
            -float(row["mean_EV_vs_all_opponents_mean"])
            if np.isfinite(row["mean_EV_vs_all_opponents_mean"])
            else float("inf")
        ),
    )
    for rank, row in enumerate(ranking, start=1):
        row["rank_by_head_to_head_ev"] = int(rank)
    return strength_by_seed, aggregate, ranking


def run_analysis(config: Dict[str, Any], run_dir: Path, training_summary: Sequence[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    add_sibling_repos_to_path()
    import pyspiel

    if training_summary is None:
        raise ValueError("training_summary is required for analysis in this lightweight repo.")

    game = pyspiel.load_game(config["game_name"])
    known_game_value = float(config.get("known_game_value_player_0", -1.0 / 18.0))
    epsilon = float(config.get("head_to_head_equivalence_epsilon", 1e-3))
    labels = [agent for agent in AGENT_ORDER if agent in config["entrants"]]

    inventory = _snapshot_inventory_from_training_summary(training_summary)
    write_csv(
        run_dir / "entrant_snapshot_inventory.csv",
        inventory,
        ["seed", "algorithm", "variant_id", "path", "exists", "size_mb"],
    )

    policies = defaultdict(dict)
    loaded_rows = []
    metric_rows = []
    for row in inventory:
        path = Path(str(row["path"]))
        if not path.exists():
            raise FileNotFoundError(f"Missing snapshot: {path}")
        pol = _load_policy(game, str(row["algorithm"]), path)
        seed = int(row["seed"])
        agent = str(row["algorithm"])
        policies[seed][agent] = pol
        loaded_rows.append(
            {
                "seed": seed,
                "agent": agent,
                "variant_id": row["variant_id"],
                "path": str(path),
            }
        )
        metric_rows.append(
            {
                "seed": seed,
                "agent": agent,
                "variant_id": row["variant_id"],
                **_policy_metrics(game, pol, known_game_value),
            }
        )

    pairwise_rows = []
    for seed in sorted(policies):
        seed_policies = policies[seed]
        missing = [agent for agent in labels if agent not in seed_policies]
        if missing:
            raise RuntimeError(f"Seed {seed} is missing policies for: {missing}")
        for agent_a in labels:
            for agent_b in labels:
                if agent_a == agent_b:
                    ev = {
                        "A_EV_as_player_0": 0.0,
                        "A_EV_as_player_1": 0.0,
                        "A_EV_seat_averaged": 0.0,
                    }
                else:
                    ev = exact_seat_averaged_value(game, seed_policies[agent_a], seed_policies[agent_b])
                pairwise_rows.append(
                    {
                        "seed": seed,
                        "agent_A": agent_a,
                        "agent_B": agent_b,
                        **ev,
                    }
                )

    mean_matrix, win_fraction_matrix, counts_matrix = aggregate_pairwise(pairwise_rows, labels, epsilon)
    strength_by_seed, aggregate_strength, ranking = _strength_rows(pairwise_rows, metric_rows, labels, epsilon)

    write_csv(run_dir / "loaded_policy_inventory.csv", loaded_rows, ["seed", "agent", "variant_id", "path"])
    write_csv(
        run_dir / "entrant_exploitability_metrics.csv",
        metric_rows,
        ["seed", "agent", "variant_id", "nash_conv", "exploitability", "average_policy_value", "policy_value_error"],
    )
    write_csv(
        run_dir / "head_to_head_exact_pairwise.csv",
        pairwise_rows,
        ["seed", "agent_A", "agent_B", "A_EV_as_player_0", "A_EV_as_player_1", "A_EV_seat_averaged"],
    )
    write_matrix_csv(run_dir / "head_to_head_exact_mean_matrix.csv", labels, mean_matrix, index_name="agent_A")
    write_matrix_csv(run_dir / "head_to_head_seed_win_fraction_matrix.csv", labels, win_fraction_matrix, index_name="agent_A")
    write_matrix_csv(run_dir / "head_to_head_pair_count_matrix.csv", labels, counts_matrix, index_name="agent_A")
    write_csv(
        run_dir / "head_to_head_strength_by_seed.csv",
        strength_by_seed,
        ["seed", "agent", "mean_EV_vs_all_opponents", "clear_win_rate", "tie_rate", "clear_loss_rate", "exploitability"],
    )
    write_csv(
        run_dir / "head_to_head_aggregate_strength_summary.csv",
        aggregate_strength,
        [
            "agent",
            "num_seeds",
            "mean_EV_vs_all_opponents_mean",
            "mean_EV_vs_all_opponents_sem",
            "clear_win_rate_mean",
            "clear_loss_rate_mean",
            "exploitability_mean",
            "exploitability_sem",
            "policy_value_error_mean",
            "policy_value_error_sem",
        ],
    )
    write_csv(
        run_dir / "algorithm_ranking.csv",
        ranking,
        ["rank_by_head_to_head_ev", "agent", "mean_EV_vs_all_opponents_mean", "exploitability_mean"],
    )

    plot_dir = run_dir / "plots"
    plot_heatmap(
        mean_matrix,
        labels,
        "Kuhn poker exact head-to-head EV across selected entrants",
        plot_dir / "head_to_head_exact_mean_matrix.png",
    )
    plot_heatmap(
        win_fraction_matrix,
        labels,
        "Fraction of seeds where row entrant beats column entrant",
        plot_dir / "head_to_head_seed_win_fraction_matrix.png",
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        fmt=".2f",
        colorbar_label="Seed win fraction",
    )
    plot_strength_bar(aggregate_strength, plot_dir / "head_to_head_aggregate_strength.png")

    metadata = {
        "snapshot_inventory": str((run_dir / "entrant_snapshot_inventory.csv").resolve()),
        "num_seeds": len(policies),
        "agents": labels,
        "head_to_head_equivalence_epsilon": epsilon,
        "method": "Exact OpenSpiel expected_game_score, seat-averaged over both player assignments.",
    }
    write_json(run_dir / "head_to_head_analysis_metadata.json", metadata)
    return {
        "inventory": inventory,
        "metrics": metric_rows,
        "pairwise": pairwise_rows,
        "aggregate_strength": aggregate_strength,
        "ranking": ranking,
        "metadata": metadata,
    }


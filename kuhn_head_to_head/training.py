"""Train the three selected Kuhn entrants and save playable snapshots."""

from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np

from .dependencies import add_sibling_repos_to_path
from .io_utils import write_csv, write_json


def _safe_last(values: Iterable[Any]) -> float:
    arr = np.asarray(list(values), dtype=float)
    return float(arr[-1]) if arr.size else float("nan")


def _safe_min(values: Iterable[Any]) -> float:
    arr = np.asarray(list(values), dtype=float)
    finite = arr[np.isfinite(arr)]
    return float(np.min(finite)) if finite.size else float("nan")


def _cleanup_torch() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _cleanup_tf() -> None:
    gc.collect()
    try:
        import tensorflow as tf

        tf.keras.backend.clear_session()
    except Exception:
        pass


def _deep_cfr_solver_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "policy_network_layers": tuple(config["policy_network_layers"]),
        "advantage_network_layers": tuple(config["advantage_network_layers"]),
        "num_iterations": int(config["num_iterations"]),
        "num_traversals": int(config["num_traversals"]),
        "learning_rate": float(config["learning_rate"]),
        "batch_size_advantage": int(config["batch_size_advantage"]),
        "batch_size_strategy": int(config["batch_size_strategy"]),
        "memory_capacity": int(config["memory_capacity"]),
        "policy_network_train_steps": int(config["policy_network_train_steps"]),
        "policy_network_train_every": int(config["policy_network_train_every"]),
        "evaluation_interval": int(config["evaluation_interval"]),
        "policy_training_mode": str(config.get("policy_training_mode", "intermittent")),
        "final_policy_network_train_steps": config.get("final_policy_network_train_steps"),
        "advantage_network_train_steps": int(config["advantage_network_train_steps"]),
        "reinitialize_advantage_networks": bool(config["reinitialize_advantage_networks"]),
        "compute_exploitability": bool(config["compute_exploitability"]),
        "target_processing": str(config.get("target_processing", "none")),
        "target_clip_value": float(config.get("target_clip_value", 1.0)),
        "target_standardize_epsilon": float(config.get("target_standardize_epsilon", 1e-6)),
    }


def train_deep_cfr(seed: int, config: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    add_sibling_repos_to_path()
    import pyspiel
    from deep_cfr_poker.constants import KUHN_GAME_VALUE_PLAYER_0
    from deep_cfr_poker.seeding import set_seed
    from deep_cfr_poker.solver import DeepCFRSolver

    set_seed(int(seed))
    game = pyspiel.load_game(config["game_name"])
    solver = DeepCFRSolver(game, **_deep_cfr_solver_kwargs(config))
    start = time.perf_counter()
    result = solver.solve()
    elapsed = time.perf_counter() - start

    snapshot_dir = run_dir / "snapshots" / "deep_cfr"
    snapshot_path = snapshot_dir / f"kuhn_poker_deep_cfr_seed_{seed}_policy_snapshot_{config['num_iterations']}_iters.pt"
    solver.save_policy_snapshot(
        snapshot_path,
        seed=int(seed),
        target_iteration=int(config["num_iterations"]),
        stage_label="final_selected_entrant",
        experiment_name="kuhn_poker_algorithm_head_to_head",
        game_name=config["game_name"],
        solver_config=config,
    )

    rows = []
    diagnostics = result.diagnostics
    for idx, nash_conv in enumerate(result.nash_conv):
        iteration = diagnostics.get("iteration", [])[idx] if idx < len(diagnostics.get("iteration", [])) else idx + 1
        value = result.average_policy_value[idx] if idx < len(result.average_policy_value) else np.nan
        row = {
            "algorithm": "deep_cfr",
            "seed": int(seed),
            "iteration": int(iteration),
            "nodes_touched": result.nodes_touched[idx] if idx < len(result.nodes_touched) else np.nan,
            "nash_conv": float(nash_conv),
            "exploitability": float(nash_conv) / 2.0,
            "average_policy_value": float(value),
            "policy_value_error": float(abs(float(value) - KUHN_GAME_VALUE_PLAYER_0)) if np.isfinite(value) else np.nan,
        }
        for key, values in diagnostics.items():
            if idx < len(values):
                row[key] = values[idx]
        rows.append(row)
    write_csv(run_dir / "training" / "deep_cfr" / f"seed_{seed}_training_curve.csv", rows)

    final_nash = _safe_last(result.nash_conv)
    final_value = _safe_last(result.average_policy_value)
    summary = {
        "algorithm": "deep_cfr",
        "agent": "deep_cfr",
        "seed": int(seed),
        "source_experiment": config["source_experiment"],
        "variant_id": config["variant_id"],
        "final_iteration": int(config["num_iterations"]),
        "final_nash_conv": final_nash,
        "final_exploitability": final_nash / 2.0 if np.isfinite(final_nash) else np.nan,
        "best_exploitability": _safe_min([x / 2.0 for x in result.nash_conv]),
        "final_average_policy_value": final_value,
        "final_policy_value_error": abs(final_value - KUHN_GAME_VALUE_PLAYER_0) if np.isfinite(final_value) else np.nan,
        "final_nodes_touched": _safe_last(result.nodes_touched),
        "wall_clock_seconds": float(elapsed),
        "policy_snapshot_path": str(snapshot_path.resolve()),
    }
    del solver, result
    _cleanup_torch()
    return summary


def train_dream(seed: int, config: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    add_sibling_repos_to_path()
    from dream_poker.checkpointing import save_dream_policy_snapshot
    from dream_poker.constants import KUHN_GAME_VALUE_P0
    from dream_poker.experiment_runner import make_dream_solver
    from dream_poker.experiment_utils import ensure_average_policy_value_columns

    solver = make_dream_solver(config, int(seed))
    start = time.perf_counter()
    curves = solver.solve(
        policy_training_mode="intermittent",
        final_policy_network_train_steps=None,
        isolate_policy_training_rng=bool(config.get("isolate_policy_training_rng", True)),
    )
    elapsed = time.perf_counter() - start
    curves = ensure_average_policy_value_columns(curves, config.get("average_policy_value_target"))
    curves.insert(0, "algorithm", "dream")
    curves.insert(1, "seed", int(seed))
    write_path = run_dir / "training" / "dream" / f"seed_{seed}_training_curve.csv"
    write_path.parent.mkdir(parents=True, exist_ok=True)
    curves.to_csv(write_path, index=False)

    snapshot_dir = run_dir / "snapshots" / "dream"
    snapshot_path = save_dream_policy_snapshot(
        solver,
        int(seed),
        int(config["num_iterations"]),
        snapshot_dir,
        config,
    )
    final = curves.sort_values("iteration").iloc[-1]
    summary = {
        "algorithm": "dream",
        "agent": "dream",
        "seed": int(seed),
        "source_experiment": config["source_experiment"],
        "variant_id": config["variant_id"],
        "final_iteration": int(final["iteration"]),
        "final_nash_conv": float(final["nash_conv"]),
        "final_exploitability": float(final["exploitability"]),
        "best_exploitability": float(curves["exploitability"].min()),
        "final_average_policy_value": float(final["average_policy_value"]),
        "final_policy_value_error": float(abs(final["average_policy_value"] - KUHN_GAME_VALUE_P0)),
        "final_nodes_touched": float(final["nodes_touched"]),
        "wall_clock_seconds": float(elapsed),
        "policy_snapshot_path": str(Path(snapshot_path).resolve()),
    }
    del solver
    _cleanup_torch()
    return summary


def train_escher(seed: int, config: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    add_sibling_repos_to_path()
    import pyspiel
    from open_spiel.python import policy
    from open_spiel.python.algorithms import expected_game_score, exploitability
    from escher_poker.constants import KUHN_GAME_VALUE_PLAYER_0
    from escher_poker.experiment_utils import final_window_mean, make_escher_solver
    from escher_poker.policy_snapshots import policy_snapshot_path, save_policy_snapshot
    from escher_poker.seeding import set_seed_tf

    set_seed_tf(int(seed))
    game = pyspiel.load_game(config["game_name"])
    solver = make_escher_solver(game, config)
    start = time.perf_counter()
    _regret_losses, policy_loss, convs, nodes_touched, avg_values, diagnostics = solver.solve()
    elapsed = time.perf_counter() - start

    convs = np.asarray(convs, dtype=float)
    exploitability_curve = convs / 2.0
    nodes_touched = np.asarray(nodes_touched, dtype=float)
    avg_values = np.asarray(avg_values, dtype=float)
    diagnostics = {key: np.asarray(value) for key, value in diagnostics.items()}
    iterations = diagnostics.get("iteration", np.arange(len(exploitability_curve))).astype(int)
    wall_clock = diagnostics.get("wall_clock_seconds", np.asarray([np.nan] * len(iterations))).astype(float)

    rows = []
    for idx, iteration in enumerate(iterations):
        value = avg_values[idx] if idx < len(avg_values) else np.nan
        row = {
            "algorithm": "escher",
            "seed": int(seed),
            "iteration": int(iteration),
            "nodes_touched": float(nodes_touched[idx]) if idx < len(nodes_touched) else np.nan,
            "wall_clock_seconds": float(wall_clock[idx]) if idx < len(wall_clock) else np.nan,
            "nash_conv": float(convs[idx]) if idx < len(convs) else np.nan,
            "exploitability": float(exploitability_curve[idx]) if idx < len(exploitability_curve) else np.nan,
            "average_policy_value": float(value),
            "policy_value_error": float(abs(value - KUHN_GAME_VALUE_PLAYER_0)) if np.isfinite(value) else np.nan,
        }
        for key, arr in diagnostics.items():
            if idx < len(arr):
                row[key] = arr[idx]
        rows.append(row)
    write_csv(run_dir / "training" / "escher" / f"seed_{seed}_training_curve.csv", rows)

    final_policy = policy.tabular_policy_from_callable(game, solver.action_probabilities)
    final_nash_conv = float(exploitability.nash_conv(game, final_policy))
    final_policy_value = float(
        expected_game_score.policy_value(game.new_initial_state(), [final_policy] * game.num_players())[0]
    )
    snapshot_dir = run_dir / "snapshots" / "escher"
    snapshot_path = policy_snapshot_path(
        snapshot_dir,
        int(seed),
        int(config["num_iterations"]),
        "checkpointed",
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    save_policy_snapshot(
        solver,
        snapshot_path,
        seed=int(seed),
        iteration=int(config["num_iterations"]),
        arm="checkpointed",
        config=config,
        stage_label="final_selected_entrant",
    )
    summary = {
        "algorithm": "escher",
        "agent": "escher",
        "seed": int(seed),
        "source_experiment": config["source_experiment"],
        "variant_id": config["variant_id"],
        "final_iteration": int(config["num_iterations"]),
        "final_nash_conv": final_nash_conv,
        "final_exploitability": final_nash_conv / 2.0,
        "best_exploitability": _safe_min(exploitability_curve),
        "final_average_policy_value": final_policy_value,
        "final_policy_value_error": abs(final_policy_value - KUHN_GAME_VALUE_PLAYER_0),
        "final_nodes_touched": _safe_last(nodes_touched),
        "wall_clock_seconds": float(elapsed),
        "final_window_mean_exploitability": final_window_mean(exploitability_curve),
        "final_policy_loss": _safe_last(diagnostics.get("policy_loss", [])) if "policy_loss" in diagnostics else float(policy_loss),
        "policy_snapshot_path": str(snapshot_path.resolve()),
    }
    del solver
    _cleanup_tf()
    return summary


TRAINERS = {
    "deep_cfr": train_deep_cfr,
    "dream": train_dream,
    "escher": train_escher,
}


def run_training(config: Dict[str, Any], run_dir: Path) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    seeds = [int(seed) for seed in config["seeds"]]
    for seed in seeds:
        for agent, entrant_config in config["entrants"].items():
            try:
                print(f"Training {agent} seed {seed}")
                summary = TRAINERS[agent](seed, entrant_config, run_dir)
                summaries.append(summary)
                write_csv(
                    run_dir / "entrant_training_summary_partial.csv",
                    summaries,
                    [
                        "algorithm",
                        "seed",
                        "variant_id",
                        "final_exploitability",
                        "best_exploitability",
                        "final_average_policy_value",
                        "policy_snapshot_path",
                    ],
                )
            except Exception as exc:
                failures.append(
                    {
                        "algorithm": agent,
                        "seed": int(seed),
                        "error": str(exc),
                    }
                )
                write_json(run_dir / "failed_training_runs.json", failures)
                raise
    write_csv(
        run_dir / "entrant_training_summary.csv",
        summaries,
        [
            "algorithm",
            "seed",
            "source_experiment",
            "variant_id",
            "final_iteration",
            "final_exploitability",
            "best_exploitability",
            "final_average_policy_value",
            "final_policy_value_error",
            "final_nodes_touched",
            "wall_clock_seconds",
            "policy_snapshot_path",
        ],
    )
    return summaries


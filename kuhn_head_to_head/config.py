"""Default thesis entrant configuration.

Defaults mirror the selected Kuhn experiments:

* Deep CFR: Experiment 9 target-processing ablation, standardized targets.
* DREAM: baseline DREAM configuration.
* ESCHER: Experiment 10 on-policy joint-regret treatment.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


COMMON_SEEDS_5 = [1234, 2025, 31415, 27182, 16180]


DEEP_CFR_STANDARDIZED_TARGETS = {
    "algorithm": "deep_cfr",
    "label": "Deep CFR standardized targets",
    "source_experiment": "kuhn_poker_deep_cfr_target_processing_ablation",
    "variant_id": "standardized_targets",
    "game_name": "kuhn_poker",
    "num_iterations": 1500,
    "num_traversals": 320,
    "evaluation_interval": 25,
    "policy_network_layers": [32, 32],
    "advantage_network_layers": [32, 32],
    "learning_rate": 0.003,
    "batch_size_advantage": 1024,
    "batch_size_strategy": 1024,
    "memory_capacity": int(1e7),
    "reinitialize_advantage_networks": False,
    "policy_network_train_steps": 200,
    "advantage_network_train_steps": 200,
    "policy_network_train_every": 25,
    "policy_training_mode": "intermittent",
    "final_policy_network_train_steps": None,
    "compute_exploitability": True,
    "target_processing": "standardize",
    "target_clip_value": 1.0,
    "target_standardize_epsilon": 1e-6,
}


DREAM_BASELINE = {
    "algorithm": "dream",
    "label": "DREAM baseline",
    "source_experiment": "kuhn_poker_dream_multiseed_baseline",
    "variant_id": "baseline",
    "game_name": "kuhn_poker",
    "num_iterations": 175,
    "num_traversals": 160,
    "evaluation_interval": 25,
    "policy_network_train_every": 25,
    "policy_network_train_steps": 100,
    "advantage_network_train_steps": 50,
    "baseline_network_train_steps": 50,
    "policy_network_layers": [32, 32],
    "advantage_network_layers": [32, 32],
    "baseline_network_layers": [32, 32],
    "learning_rate": 0.003,
    "batch_size_advantage": 1024,
    "batch_size_strategy": 1024,
    "batch_size_baseline": 1024,
    "advantage_memory_capacity": int(1e6),
    "strategy_memory_capacity": int(1e6),
    "baseline_memory_capacity": int(1e6),
    "epsilon": 0.06,
    "compute_exploitability": True,
    "isolate_policy_training_rng": True,
}


ESCHER_ON_POLICY_JOINT_REGRET = {
    "algorithm": "escher",
    "label": "ESCHER on-policy joint regret",
    "source_experiment": "kuhn_poker_escher_on_policy_joint_regret_ablation",
    "variant_id": "on_policy_joint_regret_updates",
    "variant_label": "On-policy joint regret updates",
    "variant_description": (
        "Sample one batch of trajectories from the current joint regret-matching "
        "policy and write regret targets for the acting player at visited nodes."
    ),
    "game_name": "kuhn_poker",
    "num_iterations": 80,
    "num_traversals": 150,
    "num_val_fn_traversals": 150,
    "check_exploitability_every": 10,
    "policy_network_layers": [64, 64],
    "regret_network_layers": [64, 64],
    "value_network_layers": [64, 64],
    "learning_rate": 1e-3,
    "batch_size_regret": 128,
    "batch_size_value": 128,
    "batch_size_average_policy": 2048,
    "memory_capacity": int(5e4),
    "policy_network_train_steps": 200,
    "regret_network_train_steps": 50,
    "value_network_train_steps": 50,
    "compute_exploitability": True,
    "reinitialize_regret_networks": True,
    "reinitialize_value_network": True,
    "save_policy_weights": False,
    "save_final_checkpoints": False,
    "train_device": "cpu",
    "infer_device": "cpu",
    "verbose": False,
    "on_policy_joint_regret_updates": True,
}


DEFAULT_CONFIG = {
    "experiment_name": "kuhn_poker_algorithm_head_to_head",
    "game_name": "kuhn_poker",
    "seeds": COMMON_SEEDS_5,
    "known_game_value_player_0": -1.0 / 18.0,
    "average_policy_value_target": -1.0 / 18.0,
    "exploitability_threshold": 0.05,
    "head_to_head_equivalence_epsilon": 1e-3,
    "output_root": "outputs",
    "entrants": {
        "deep_cfr": DEEP_CFR_STANDARDIZED_TARGETS,
        "dream": DREAM_BASELINE,
        "escher": ESCHER_ON_POLICY_JOINT_REGRET,
    },
}


SMOKE_TEST_OVERRIDES = {
    "experiment_name": "kuhn_poker_algorithm_head_to_head_smoke",
    "seeds": [1234],
    "output_root": str(Path("outputs") / "smoke_tests"),
    "entrants": {
        "deep_cfr": {
            "num_iterations": 2,
            "num_traversals": 4,
            "evaluation_interval": 1,
            "policy_network_train_every": 1,
            "policy_network_train_steps": 2,
            "advantage_network_train_steps": 2,
            "batch_size_advantage": 8,
            "batch_size_strategy": 8,
            "memory_capacity": 200,
        },
        "dream": {
            "num_iterations": 2,
            "num_traversals": 4,
            "evaluation_interval": 1,
            "policy_network_train_every": 1,
            "policy_network_train_steps": 2,
            "advantage_network_train_steps": 2,
            "baseline_network_train_steps": 2,
            "batch_size_advantage": 8,
            "batch_size_strategy": 8,
            "batch_size_baseline": 8,
            "advantage_memory_capacity": 200,
            "strategy_memory_capacity": 200,
            "baseline_memory_capacity": 200,
        },
        "escher": {
            "num_iterations": 1,
            "num_traversals": 2,
            "num_val_fn_traversals": 2,
            "check_exploitability_every": 1,
            "policy_network_train_steps": 2,
            "regret_network_train_steps": 2,
            "value_network_train_steps": 2,
            "batch_size_regret": 8,
            "batch_size_value": 8,
            "batch_size_average_policy": 8,
            "memory_capacity": 200,
        },
    },
}


def deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``base`` recursively updated with ``overrides``."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def default_config(*, smoke: bool = False) -> Dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if smoke:
        config = deep_merge(config, SMOKE_TEST_OVERRIDES)
    return config


import json
from pathlib import Path

from kuhn_head_to_head.config import default_config


def test_default_config_contains_three_entrants():
    config = default_config()
    assert set(config["entrants"]) == {"deep_cfr", "dream", "escher"}
    assert config["entrants"]["deep_cfr"]["target_processing"] == "standardize"
    assert config["entrants"]["escher"]["on_policy_joint_regret_updates"] is True


def test_smoke_config_uses_single_seed():
    config = default_config(smoke=True)
    assert config["seeds"] == [1234]
    assert config["entrants"]["deep_cfr"]["num_iterations"] == 2


def test_escher_exp13_preset_keeps_other_entrants_fixed():
    default = default_config()
    exp13 = default_config(preset="escher_exp13")
    assert exp13["experiment_name"] == "kuhn_poker_algorithm_head_to_head_escher_exp13"
    assert exp13["entrants"]["deep_cfr"] == default["entrants"]["deep_cfr"]
    assert exp13["entrants"]["dream"] == default["entrants"]["dream"]

    escher = exp13["entrants"]["escher"]
    assert escher["source_experiment"] == "kuhn_poker_escher_author_budget_multiseed"
    assert escher["variant_id"] == "author_budget_no_is_uniform"
    assert escher["num_traversals"] == 500
    assert escher["num_val_fn_traversals"] == 500
    assert escher["policy_network_layers"] == [256, 128]
    assert escher["regret_network_layers"] == [256, 128]
    assert escher["value_network_layers"] == [256, 128]
    assert escher["batch_size_average_policy"] == 10000
    assert escher["policy_network_train_steps"] == 1000
    assert escher["regret_network_train_steps"] == 200
    assert escher["value_network_train_steps"] == 200
    assert escher["importance_sampling"] is False
    assert escher["zero_regret_fallback"] == "uniform"
    assert escher["all_actions"] is True
    assert escher["on_policy_joint_regret_updates"] is False


def test_escher_exp13_json_override_matches_preset_escher_config():
    config_path = Path(__file__).resolve().parents[1] / "configs" / "escher_experiment_13_head_to_head.json"
    override = json.loads(config_path.read_text(encoding="utf-8"))
    exp13 = default_config(preset="escher_exp13")
    assert override["experiment_name"] == exp13["experiment_name"]
    assert override["entrants"]["escher"] == exp13["entrants"]["escher"]

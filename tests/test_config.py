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


# Kuhn Poker Algorithm Head-to-Head

Lightweight thesis comparison repo for the selected Kuhn poker entrants:

- Deep CFR, Experiment 9 standardized advantage targets.
- DREAM, baseline configuration.
- ESCHER, Experiment 10 on-policy joint-regret updates.

The repo imports the solver and snapshot code directly from the sibling Kuhn
experiment repos under `deep_cfr_v3`. It trains one final entrant per algorithm
and seed, saves lightweight playable policy snapshots, then runs the same exact
head-to-head method used by the core checkpoint analyses: OpenSpiel
`expected_game_score`, evaluating each matchup in both seats and averaging the
entrant's EV.

## Run

From this directory:

```bash
python -m kuhn_head_to_head.run all --seeds 1234,2025,31415
```

For a quick wiring check:

```bash
python -m kuhn_head_to_head.run all --smoke
```

Optional JSON overrides can be supplied with `--config path/to/config.json`.
The override is recursively merged into the default config, so you can replace
only the fields that differ from the selected thesis defaults.

## Google Cloud Batch

For step-by-step Google Cloud Batch setup, smoke-test commands, full-run
commands, log inspection, and output retrieval, see
[docs/GCP_BATCH_EXPERIMENTS.md](docs/GCP_BATCH_EXPERIMENTS.md).

## Outputs

Each timestamped run directory contains:

- `entrant_training_summary.csv`
- `entrant_snapshot_inventory.csv`
- `entrant_exploitability_metrics.csv`
- `head_to_head_exact_pairwise.csv`
- `head_to_head_exact_mean_matrix.csv`
- `head_to_head_seed_win_fraction_matrix.csv`
- `head_to_head_strength_by_seed.csv`
- `head_to_head_aggregate_strength_summary.csv`
- `algorithm_ranking.csv`
- `plots/head_to_head_exact_mean_matrix.png`
- `plots/head_to_head_seed_win_fraction_matrix.png`
- `plots/head_to_head_aggregate_strength.png`

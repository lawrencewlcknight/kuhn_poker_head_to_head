"""CLI for the combined Kuhn poker algorithm head-to-head experiment."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "3")
os.environ.setdefault("XDG_CACHE_HOME", str((Path("outputs") / ".cache").resolve()))
os.environ.setdefault("MPLCONFIGDIR", str((Path("outputs") / ".matplotlib_cache").resolve()))
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

from .analysis import run_analysis
from .config import deep_merge, default_config
from .io_utils import create_run_dir, read_json, write_json
from .training import run_training


def _configure_logging(run_dir: Path, verbose: bool) -> None:
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=log_level, format=log_format, stream=sys.stdout)
    file_handler = logging.FileHandler(run_dir / "experiment.log", encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(file_handler)


def _parse_seeds(value: Optional[str]):
    if value is None:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def build_config(args: argparse.Namespace) -> dict:
    config = default_config(smoke=args.smoke)
    if args.config:
        config = deep_merge(config, read_json(Path(args.config)))
    if args.seeds:
        config["seeds"] = _parse_seeds(args.seeds)
    if args.output_root:
        config["output_root"] = args.output_root
    if args.experiment_name:
        config["experiment_name"] = args.experiment_name
    return config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", nargs="?", default="all", choices=["all", "train", "analyse", "analyze"])
    parser.add_argument("--config", type=Path, default=None, help="Optional JSON config override.")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--run-dir", type=Path, default=None, help="Existing run directory for analyse-only.")
    parser.add_argument("--seeds", default=None, help="Comma-separated seed list.")
    parser.add_argument("--experiment-name", default=None)
    parser.add_argument("--smoke", action="store_true", help="Use tiny smoke-test budgets.")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.phase == "analyze":
        args.phase = "analyse"
    config = build_config(args)
    run_dir = args.run_dir.resolve() if args.run_dir else create_run_dir(config["output_root"], config["experiment_name"]).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = run_dir / "experiment_metadata.json"
    if args.phase == "analyse" and args.config is None and metadata_path.exists():
        config = read_json(metadata_path)
    _configure_logging(run_dir, args.verbose)
    write_json(metadata_path, config)

    training_summary = None
    if args.phase in {"all", "train"}:
        training_summary = run_training(config, run_dir)

    if args.phase == "analyse":
        summary_path = run_dir / "entrant_training_summary.csv"
        if not summary_path.exists():
            raise FileNotFoundError(
                "Analyse-only currently expects the in-memory training summary from this runner "
                "or an existing entrant_training_summary.csv parser to be added."
            )

    if args.phase in {"all", "analyse"}:
        if training_summary is None:
            import csv

            with open(run_dir / "entrant_training_summary.csv", newline="", encoding="utf-8") as f:
                training_summary = list(csv.DictReader(f))
        run_analysis(config, run_dir, training_summary)

    logging.getLogger(__name__).info("Outputs saved to %s", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

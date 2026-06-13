"""Small file-format helpers for experiment outputs."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        val = float(value)
        return None if not np.isfinite(val) else val
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(json_safe(payload), f, indent=2)


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ordered_fieldnames(rows: Sequence[Mapping[str, Any]], preferred: Iterable[str]) -> list[str]:
    fields = []
    for field in preferred:
        if any(field in row for row in rows):
            fields.append(field)
    extras = sorted({key for row in rows for key in row.keys()} - set(fields))
    return fields + extras


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], preferred: Iterable[str] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = ordered_fieldnames(rows, preferred)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(json_safe(list(rows)))


def write_matrix_csv(
    path: Path,
    labels: Sequence[str],
    matrix: np.ndarray,
    *,
    index_name: str = "agent_A",
) -> None:
    rows = []
    for row_idx, label in enumerate(labels):
        row = {index_name: label}
        for col_idx, col_label in enumerate(labels):
            row[str(col_label)] = float(matrix[row_idx, col_idx])
        rows.append(row)
    write_csv(path, rows, [index_name, *[str(label) for label in labels]])


def create_run_dir(output_root: Path | str, experiment_name: str) -> Path:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_root) / f"{experiment_name}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


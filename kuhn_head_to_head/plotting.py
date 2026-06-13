"""Plots matching the compact style used by the Kuhn experiment repos."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np


def plot_heatmap(
    matrix: np.ndarray,
    labels: Sequence[str],
    title: str,
    output_path: Path,
    *,
    cmap: str = "coolwarm",
    vmin: float | None = None,
    vmax: float | None = None,
    fmt: str = ".3f",
    colorbar_label: str = "Seat-averaged EV for entrant A",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    data = np.asarray(matrix, dtype=float)
    im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels([str(x) for x in labels], rotation=35, ha="right")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels([str(x) for x in labels])
    ax.set_xlabel("Entrant B")
    ax.set_ylabel("Entrant A")
    ax.set_title(title)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isfinite(data[i, j]):
                ax.text(j, i, format(data[i, j], fmt), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label=colorbar_label)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_strength_bar(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(row["agent"]) for row in rows]
    means = np.asarray([row["mean_EV_vs_all_opponents_mean"] for row in rows], dtype=float)
    sems = np.asarray([row["mean_EV_vs_all_opponents_sem"] for row in rows], dtype=float)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, means, yerr=np.nan_to_num(sems), capsize=4)
    ax.axhline(0.0, linestyle="--", linewidth=1, color="black", alpha=0.6)
    ax.set_ylabel("Mean seat-averaged EV vs other entrants")
    ax.set_title("Kuhn poker head-to-head aggregate strength")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


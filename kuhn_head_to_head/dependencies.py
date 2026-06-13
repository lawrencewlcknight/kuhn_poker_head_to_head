"""Access to the sibling thesis experiment packages.

The three Kuhn implementations are kept as separate repositories under the
same parent directory. This lightweight comparison package imports their
packaged solver/snapshot code directly instead of copying solver internals.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict


SIBLING_REPO_DIRS = {
    "deep_cfr": Path("kuhn_poker_deep_cfr") / "kuhn-poker-deep-cfr-experiments",
    "dream": Path("kuhn_poker_dream") / "kuhn-poker-dream-experiments",
    "escher": Path("kuhn_poker_escher") / "kuhn-poker-escher-experiments",
}


def workspace_root() -> Path:
    """Return the shared ``deep_cfr_v3`` workspace root."""
    return Path(__file__).resolve().parents[2]


def sibling_paths(root: Path | None = None) -> Dict[str, Path]:
    root = workspace_root() if root is None else Path(root)
    return {name: (root / rel).resolve() for name, rel in SIBLING_REPO_DIRS.items()}


def add_sibling_repos_to_path(root: Path | None = None) -> Dict[str, Path]:
    """Prepend the three solver package roots to ``sys.path``.

    The solver packages have unique top-level names:
    ``deep_cfr_poker``, ``dream_poker``, and ``escher_poker``.
    """
    paths = sibling_paths(root)
    for path in reversed(list(paths.values())):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    return paths


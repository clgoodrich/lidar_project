"""Fail if a legacy annotation identifier survives anywhere in the live tree.

The 2026-08-18 rename adopted the notebook's vocabulary project-wide:

    pit_id, matched_pit_id      -> pit_inside_id
    pit_id_outer, pit_outside_id -> pit_full_id
    plat_id                     -> pad_id

A missed site is dangerous specifically because it does NOT crash. A stale
``.isin("pit_id")`` against a renamed frame returns an empty set, which shrinks
the ground truth and makes the score look BETTER. `_heldout_rim_containment_9t`
and `_pit_threshold_products_9t` both build held-out sets that way.

`_common.py` is exempt: it holds the alias maps that make legacy files readable.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "notebooks" / "wellsight_v2"

#: Frozen trees. Their names describe runs that happened under the old scheme.
SKIP_DIRS = {"__pycache__", "archive", "_archive", "_retired", ".ipynb_checkpoints"}

#: Holds LEGACY_ID_ALIASES itself.
EXEMPT_FILES = {"_common.py"}

LEGACY = ("pit_id", "matched_pit_id", "pit_id_outer", "pit_outside_id", "plat_id")
PATTERN = re.compile(r"\b(" + "|".join(LEGACY) + r")\b")


def _live_py() -> list[Path]:
    return sorted(
        f for f in LIVE.rglob("*.py")
        if not any(p in SKIP_DIRS for p in f.parts) and f.name not in EXEMPT_FILES
    )


@pytest.mark.parametrize("path", _live_py(), ids=lambda p: str(p.relative_to(LIVE)))
def test_no_legacy_id_identifier(path: Path) -> None:
    hits = []
    for lineno, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1):
        for m in PATTERN.finditer(line):
            hits.append(f"  {path.relative_to(LIVE)}:{lineno}  {m.group(1)}  |  {line.strip()[:80]}")
    assert not hits, (
        f"legacy identifier(s) in {path.relative_to(LIVE)}:\n" + "\n".join(hits)
        + "\n\nRename to the canonical column, and read through "
          "_common.normalize_ids / read_layer so legacy files still load."
    )


def test_alias_map_covers_every_legacy_name() -> None:
    """The guard and the shim must not drift apart."""
    import sys
    sys.path.insert(0, str(LIVE))
    from _common import LEGACY_ID_ALIASES

    missing = set(LEGACY) - set(LEGACY_ID_ALIASES)
    assert not missing, (
        f"{sorted(missing)} are rejected by this test but absent from "
        "LEGACY_ID_ALIASES, so a legacy file carrying them would not be fixed up."
    )

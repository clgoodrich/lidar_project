"""Single source of truth for repo paths used by the UI.

Wraps notebooks/wellsight_v2/_common.py so the UI and the pipeline scripts can
never disagree about where things live.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))

from _common import DERIV, DERIV_9T, DST_CRS, ROOT as _CROOT, path_for  # noqa: E402

assert ROOT == _CROOT, f"UI ROOT {ROOT} != _common ROOT {_CROOT}"

PYEXE = sys.executable
UI = ROOT / "ui"
RUNS = UI / "runs"
LEDGER = UI / "jobs.jsonl"
SETTINGS = UI / "settings.json"
RUNS.mkdir(parents=True, exist_ok=True)

# --- common data locations the registry references ---
TILES = path_for("derived")
DATA3X3 = path_for("data_3x3")
SWEEP = path_for("models") / "road" / "sweep_202607"
ANNOT = path_for("truth")


def list_blocks() -> list[str]:
    """Known inference blocks: 9t + every data_3x3 sub-block + singles."""
    blocks = ["9t"]
    for region in sorted(DATA3X3.glob("*")):
        if region.is_dir():
            for b in sorted(region.glob("*")):
                if b.is_dir() and (b / f"features_{b.name}_1m.tif").exists():
                    blocks.append(f"{region.name}/{b.name}")
    for extra in ("mkf_1m", "613590_05"):
        if (TILES / extra).is_dir():
            blocks.append(extra)
    return blocks


def list_road_models() -> dict[str, Path]:
    """Discoverable road checkpoints: name -> best.pt path (only if exists)."""
    cands = {
        "recall": path_for("models") / "road" / "unet_1m_recall" / "best.pt",
        "corrected (deployed)": path_for("models") / "road" / "unet_1m_corrected" / "best.pt",
    }
    for v in sorted(SWEEP.glob("*")):
        if (v / "best.pt").exists():
            cands[f"sweep:{v.name}"] = v / "best.pt"
    return {k: v for k, v in cands.items() if v.exists()}


def block_features(block: str) -> Path:
    """Feature-stack path for a block label (1 m)."""
    if block == "9t":
        return DERIV_9T / "features_pit_9t_1m.tif"
    if "/" in block:
        name = block.split("/")[-1]
        return DATA3X3 / block / f"features_{name}_1m.tif"
    return TILES / block / f"features_{block.replace('_1m', '')}_1m.tif"

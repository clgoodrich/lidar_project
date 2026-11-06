"""Shared helpers for the 4.4 methane scripts (config, path specs, missing-input errors, run lookup).

Purpose  One place for config loading and path resolution so no 4.4 script spells a data path.
Inputs   expansions/4_modalities/4_4_methane_plumes/src/config_4_4.json
Outputs  none (library)
Run      imported by _methane_gate_limit_pa.py, _methane_plume_overlay_pa.py, _methane_source_model_pa.py

A path spec in the config is one of
    {"key": "<config/paths.toml key>", "rel": "sub/path"}  -> ek.path_for(key) / rel
    {"exp": "4.4", "rel": "data/raw/x.csv"}                -> ek.exp_dir(exp) / rel
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

EXP = "4.4"
HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config_4_4.json"


def load_config(path: Path | None = None) -> dict:
    return json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))


def resolve(spec) -> Path | None:
    """Turn a config path spec into an absolute Path. None stays None."""
    if spec is None:
        return None
    if isinstance(spec, (str, Path)):
        return Path(spec)
    if "key" in spec:
        return ek.path_for(spec["key"]) / spec.get("rel", "")
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / spec.get("rel", "")
    raise ValueError(f"bad path spec {spec!r}")


def need(path: Path | None, what: str, schema: str = "") -> Path:
    """Raise a clear error naming the missing input and its assumed schema."""
    if path is None or not Path(path).exists():
        raise FileNotFoundError(
            f"MISSING INPUT {what}: {path}. Assumed schema: {schema or 'see config'}. "
            f"Edit {CONFIG_PATH.name} or pass the path on the command line.")
    return Path(path)


def latest_run(short: str, exp_id: str = EXP, base: Path | None = None) -> Path | None:
    """Newest results/<YYYYMMDD>_<short>_<hash7>/ folder for a stage, or None."""
    root = Path(base) if base is not None else ek.exp_dir(exp_id) / "results"
    if not root.exists():
        return None
    hits = sorted((d for d in root.iterdir() if d.is_dir() and d.name[9:].startswith(short + "_")),
                  key=lambda d: d.stat().st_mtime)
    return hits[-1] if hits else None


def to_metric(gdf, crs: str):
    """Reproject to a metric CRS and assert it."""
    out = gdf.to_crs(crs)
    ek.assert_crs(out, crs)
    return out

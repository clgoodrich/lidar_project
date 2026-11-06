"""Shared helpers for expansion 4.1 magnetometry (config, path specs, missing-input errors, run lookup).

Inputs   expansions/4_modalities/4_1_magnetometry/src/config_4_1.json
Outputs  none
Run      imported by the other _mag_*.py scripts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

EXP_ID = "4.1"
CONFIG = HERE / "config_4_1.json"


def load_config(path: Path | None = None) -> dict:
    return json.loads(Path(path or CONFIG).read_text(encoding="utf-8"))


def resolve(spec: dict, **fmt) -> Path:
    """{key, rel} -> path_for(key)/rel. {exp, rel} -> exp_dir(exp)/rel. {path} -> absolute (tests only)."""
    if "path" in spec:
        return Path(str(spec["path"]).format(**fmt))
    rel = str(spec["rel"]).format(**fmt)
    if "key" in spec:
        return ek.path_for(spec["key"]) / rel
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / rel
    raise KeyError(f"bad path spec {spec}")


def need(path: Path, what: str, schema: str = "") -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"MISSING INPUT {what}: {path}. Assumed schema: {schema}. Edit config_4_1.json")
    return path


def need_input(cfg: dict, name: str, **fmt) -> Path:
    spec = cfg["inputs"][name]
    return need(resolve(spec, **fmt), name, spec.get("schema", ""))


def latest_run(exp_id: str, short: str, base: Path | None = None) -> Path:
    root = Path(base) if base is not None else ek.sub(exp_id, "results")
    hits = sorted([d for d in root.glob(f"*_{short}_*") if d.is_dir()], key=lambda d: d.stat().st_mtime)
    if not hits:
        raise FileNotFoundError(f"MISSING INPUT no run '{short}' under {root}. Run that stage first")
    return hits[-1]

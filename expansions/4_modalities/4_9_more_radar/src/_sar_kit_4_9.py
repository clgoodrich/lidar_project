"""Small helpers shared by the 4.9 more radar scripts.

Purpose. Config, path resolution through expkit, clear failures for assumed inputs, per-script provenance, a fast
rank AUC, block index helpers and the paired block-bootstrap of an AUC gain used by S1 and S5.
Inputs. expansions/4_modalities/4_9_more_radar/src/config_4_9.json
Outputs. None.
Run. Imported only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "_shared" / "src"))
import expkit as ek  # noqa: E402

CFG_PATH = HERE / "config_4_9.json"
S5_EVAL = ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"


def load_cfg(path=None) -> dict:
    return json.loads(Path(path or CFG_PATH).read_text(encoding="utf-8"))


def resolve(spec: dict, **fmt) -> Path:
    rel = spec["rel"].format(**fmt) if fmt else spec["rel"]
    if "key" in spec:
        return ek.path_for(spec["key"]) / rel
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / rel
    if "area" in spec:
        return ek.area_dir(spec["area"]) / rel
    raise KeyError(spec)


def need(path, what: str, spec: dict | None = None) -> Path:
    path = Path(path)
    if path.exists():
        return path
    msg = f"missing input: {what}\n  expected at {path}"
    if spec:
        if spec.get("schema"):
            msg += f"\n  assumed schema (config_4_9.json): {', '.join(spec['schema'])}"
        if spec.get("note"):
            msg += f"\n  note: {spec['note']}"
        if spec.get("assumed"):
            msg += "\n  this input is assumed, not held (VERIFY)."
    raise FileNotFoundError(msg)


def prov(out_dir, script: str, inputs=None, outputs=None, params=None, seeds=None) -> Path:
    d = Path(out_dir) / "_provenance" / script
    d.mkdir(parents=True, exist_ok=True)
    return ek.write_provenance(d, inputs=inputs, outputs=outputs, params=params, seeds=seeds)


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """Mann-Whitney AUC with average ranks for ties. Rows with a non-finite score are dropped. nan if a class is missing."""
    s = np.asarray(s, float)
    ok = np.isfinite(s)
    y, s = np.asarray(y).astype(bool)[ok], s[ok]
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def block_index(blocks: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    ub = np.unique(blocks)
    return ub, [np.flatnonzero(blocks == b) for b in ub]


def paired_gain_boot(y, s_base, s_arm, blocks, B: int, seed: int) -> dict:
    """Point gain AUC(arm) - AUC(base), paired percentile interval over resampled blocks, and the draws."""
    ub, where = block_index(np.asarray(blocks))
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for b in range(B):
        idx = np.concatenate([where[j] for j in rng.integers(0, len(ub), len(ub))])
        d[b] = auc(y[idx], s_arm[idx]) - auc(y[idx], s_base[idx])
    d = d[np.isfinite(d)]
    lo, hi = np.percentile(d, [2.5, 97.5]) if len(d) else (np.nan, np.nan)
    n_tb = len(np.unique(np.asarray(blocks)[np.asarray(y) == 1]))
    return {"gain": auc(y, s_arm) - auc(y, s_base), "lo": float(lo), "hi": float(hi), "n_blocks": len(ub),
            "n_target_blocks": n_tb, "draws": d}


def paired_perm(y, s_base, s_arm, blocks, n: int, seed: int) -> dict:
    """Paired permutation. Swap the two arms' scores block by block at random. Null band and one-sided p for gain > 0."""
    ub, where = block_index(np.asarray(blocks))
    rng = np.random.default_rng(seed)
    obs = auc(y, s_arm) - auc(y, s_base)
    null = np.empty(n)
    for k in range(n):
        a, b = s_arm.copy(), s_base.copy()
        for j in np.flatnonzero(rng.random(len(ub)) < 0.5):
            a[where[j]], b[where[j]] = s_base[where[j]], s_arm[where[j]]
        null[k] = auc(y, a) - auc(y, b)
    lo, hi = np.percentile(null, [2.5, 97.5])
    return {"perm_null_lo": float(lo), "perm_null_hi": float(hi), "perm_p": float((1 + (null >= obs).sum()) / (n + 1))}


def holm(p: dict) -> dict:
    """Holm step-down adjusted p-values."""
    keys = sorted(p, key=lambda k: p[k])
    m, out, run = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (m - i) * p[k]))
        out[k] = run
    return out

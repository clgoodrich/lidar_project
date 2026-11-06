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


def paired_gain_boot(y, s_base, s_arm, blocks, B: int, seed: int, max_undefined: float = 0.0) -> dict:
    """Point gain AUC(arm) - AUC(base), paired percentile interval over resampled blocks, and the draws.

    SH-01. Undefined draws (a resample with one class missing) are kept and counted, never dropped. If their share
    exceeds max_undefined the interval is (nan, nan), which ek.decide turns into inconclusive. The share is returned
    as undefined_share. The draws array keeps the NaNs."""
    ub, where = block_index(np.asarray(blocks))
    rng = np.random.default_rng(seed)
    d = np.empty(B)
    for b in range(B):
        idx = np.concatenate([where[j] for j in rng.integers(0, len(ub), len(ub))])
        d[b] = auc(y[idx], s_arm[idx]) - auc(y[idx], s_base[idx])
    und = ek.undefined_share(d)
    if und > max_undefined or und == 1.0:
        lo, hi = np.nan, np.nan
    else:
        lo, hi = np.nanpercentile(d, [2.5, 97.5])
    n_tb = len(np.unique(np.asarray(blocks)[np.asarray(y) == 1]))
    return {"gain": auc(y, s_arm) - auc(y, s_base), "lo": float(lo), "hi": float(hi), "n_blocks": len(ub),
            "n_target_blocks": n_tb, "draws": d, "undefined_share": und}


def pct_rank(s) -> np.ndarray:
    """Mid-rank over the whole vector scaled to (0, 1). Non-finite scores stay non-finite."""
    s = np.asarray(s, float)
    out = np.full(len(s), np.nan)
    ok = np.isfinite(s)
    out[ok] = (rankdata(s[ok]) - 0.5) / max(int(ok.sum()), 1)
    return out


def paired_perm(y, s_base, s_arm, blocks, n: int, seed: int) -> dict:
    """Paired permutation. Swap the two arms' scores block by block at random. Null band and one-sided p for gain > 0.

    The two arms can sit on different scales (a probit baseline against a probability, or two differently calibrated
    models). Swapping raw scores would then mix scales inside one AUC. Each arm is first rank-transformed over all
    rows (pct_rank), which leaves each arm's AUC unchanged and puts both on one scale before the swap."""
    ub, where = block_index(np.asarray(blocks))
    rng = np.random.default_rng(seed)
    s_base, s_arm = pct_rank(s_base), pct_rank(s_arm)
    obs = auc(y, s_arm) - auc(y, s_base)
    null = np.empty(n)
    for k in range(n):
        a, b = s_arm.copy(), s_base.copy()
        for j in np.flatnonzero(rng.random(len(ub)) < 0.5):
            a[where[j]], b[where[j]] = s_base[where[j]], s_arm[where[j]]
        null[k] = auc(y, a) - auc(y, b)
    lo, hi = np.percentile(null, [2.5, 97.5])
    return {"perm_null_lo": float(lo), "perm_null_hi": float(hi), "perm_p": float((1 + (null >= obs).sum()) / (n + 1))}


def lidar_weak_mask(y, covariate, spec: dict | None):
    """lidar_weak rows from an external weakness covariate, never from the baseline score being compared (4.9-01).

    Selecting targets on the baseline score conditions on the baseline's own noise. Any second score then gains by
    regression to the mean. A covariate that both arms see equally (canopy cover, ground point density) has no such
    bias. Targets whose covariate lies in the weak tail of the target distribution are kept, with all decoys.
    spec = {"covariate": column, "weak_side": "high" | "low", "quantile": share of targets kept}.
    Returns (mask, None) or (None, reason) when the stratum cannot be formed."""
    if not spec or not spec.get("covariate"):
        return None, "lidar_weak covariate not set in config (needs user decision)"
    if covariate is None:
        return None, f"lidar_weak covariate {spec['covariate']!r} is not in the rows"
    c = np.asarray(covariate, float)
    y = np.asarray(y).astype(bool)
    q = float(spec["quantile"])
    ct = c[y & np.isfinite(c)]
    if not len(ct):
        return None, "no target has a finite lidar_weak covariate"
    side = spec.get("weak_side")
    if side == "high":
        tk = np.isfinite(c) & (c >= np.quantile(ct, 1 - q))
    elif side == "low":
        tk = np.isfinite(c) & (c <= np.quantile(ct, q))
    else:
        raise ValueError(f"lidar_weak weak_side must be high or low, got {side!r}")
    return (~y) | (y & tk), None


def frozen_cols(df) -> list[str]:
    """Columns of the frozen scoring rows. Arm columns (arm:<A>:*) are added later by S4 and are not frozen."""
    return [c for c in df.columns if not str(c).startswith("arm:")]


def frozen_hash(df) -> str:
    """sha256 over the frozen columns' names and values, independent of the arm columns and of column order."""
    import hashlib
    cols = sorted(frozen_cols(df))
    # 10 significant digits, so a CSV write and re-read (pandas' default parser is not exact round trip) keeps the hash
    return hashlib.sha256(df[cols].to_csv(index=False, float_format="%.10g").encode()).hexdigest()


def stamp_path(rows_p) -> Path:
    return Path(str(rows_p) + ".frozen.json")


def write_stamp(rows_p, df) -> Path:
    f = stamp_path(rows_p)
    f.write_text(json.dumps({"rows": Path(rows_p).name, "n": int(len(df)), "frozen_sha256": frozen_hash(df),
                             "frozen_columns": sorted(frozen_cols(df))}, indent=2), encoding="utf-8")
    return f


def check_frozen(rows_p, df, adopt_from_provenance: bool = True) -> str:
    """Refuse when the frozen part of the rows differs from its stamp (4.9 S4 used to overwrite the frozen CSV).

    With no stamp, a rows file whose whole-file sha256 equals the one recorded by its --rows-only provenance is
    adopted and stamped. Anything else refuses."""
    rows_p = Path(rows_p)
    f = stamp_path(rows_p)
    h = frozen_hash(df)
    if f.exists():
        want = json.loads(f.read_text(encoding="utf-8"))["frozen_sha256"]
        if want != h:
            raise RuntimeError(f"frozen rows changed: {rows_p}. stamp {want[:12]} now {h[:12]}. Refusing to write. "
                               "Restore the frozen rows or re-freeze on purpose (delete the stamp and rerun --rows-only).")
        return h
    pv = rows_p.parent / "_provenance" / rows_p.stem.replace("_9t", "") / "_PROVENANCE.json"
    if adopt_from_provenance and pv.exists():
        rec = [o for o in json.loads(pv.read_text(encoding="utf-8")).get("outputs", [])
               if Path(o["path"]).name == rows_p.name]
        if rec and rec[0].get("sha256") == ek.sha256(rows_p):
            write_stamp(rows_p, df)
            return h
    raise RuntimeError(f"no frozen stamp for {rows_p} and its provenance hash does not match. Refusing to write. "
                       "Run S4 with --adopt-frozen to stamp rows you have checked.")


def holm(p: dict) -> dict:
    """Holm step-down adjusted p-values."""
    keys = sorted(p, key=lambda k: p[k])
    m, out, run = len(keys), {}, 0.0
    for i, k in enumerate(keys):
        run = max(run, min(1.0, (m - i) * p[k]))
        out[k] = run
    return out

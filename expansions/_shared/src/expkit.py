"""Shared machinery for every expansion project (implements expansions/_shared/fw_00_common.md).

Import from any expansions/<group>/<id>_<slug>/src/ script with
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
    import expkit as ek

What is here
    paths       ek.exp_dir("4.4"), ek.sub("4.4", "data/raw"), ek.path_for(key), ek.area_dir("9t")
    runs        ek.new_run(exp_id, short_name, config) -> run dir with _RUN.md; ek.write_provenance(...)
    seeds       ek.child_seed(master, fold, arm)
    checks      ek.assert_crs(obj, "EPSG:6346"), ek.assert_rows(df, n, label), ek.assert_unique(df, col),
                ek.assert_no_nan(series, label), ek.assert_disjoint(a, b, label)
    statistics  ek.recall_at_k(...), ek.block_bootstrap(...), ek.bootstrap_diff(...),
                ek.clopper_pearson(k, n), ek.newcombe_diff(k1, n1, k2, n2),
                ek.calibration(y, p), ek.decide(lo, hi, margin, kind), ek.n_for_proportion(d, deff)
    palette     ek.PALETTE (validated colourblind-safe set from CLAUDE.md)

Pure numpy / pandas / scipy at import time. Geo libraries are imported lazily.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
EXP_ROOT = HERE.parents[2]                      # expansions/
REPO = EXP_ROOT.parent
sys.path.insert(0, str(REPO / "notebooks" / "wellsight_v2"))
from _common import path_for, DST_CRS  # noqa: E402

GROUPS = {"p": "0_prerequisites", "3": "3_geography", "4": "4_modalities",
          "5": "5_tasks", "6": "6_adjacent", "7": "7_scale"}

# Lost/found palette, worst pair dE 21.1 deutan / 22.6 normal (CLAUDE.md colourblind rule,
# dataviz validator --pairs all). Neutral grey and charcoal from the classification palette.
PALETTE = {"blue": "#1F5FA8", "orange": "#D97706", "dark_red": "#A31515",
           "grey": "#8E959B", "charcoal": "#2B2F36"}


# ----------------------------------------------------------------------------- paths
def exp_dir(exp_id: str) -> Path:
    """Folder of an expansion by id ('p1', '3.0', '4.4')."""
    exp_id = exp_id.lower()
    g = EXP_ROOT / GROUPS[exp_id[0]]
    tag = exp_id.replace(".", "_") + "_"
    hits = [d for d in g.iterdir() if d.is_dir() and d.name.startswith(tag)]
    if len(hits) != 1:
        raise KeyError(f"expansion {exp_id!r}: found {hits}")
    return hits[0]


def sub(exp_id: str, rel: str) -> Path:
    """A skeleton subfolder of an expansion, e.g. sub('4.4', 'data/raw'). Created if missing."""
    p = exp_dir(exp_id) / rel
    p.mkdir(parents=True, exist_ok=True)
    return p


def area_dir(area: str) -> Path:
    """data/<area>/ (area-major rule). Area products go here, not in the expansion folder."""
    return path_for("data") / area


# ----------------------------------------------------------------------------- hashing / runs
def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def config_hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:7]


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def new_run(exp_id: str, short_name: str, config: dict, base: Path | None = None,
            why: str = "") -> Path:
    """Create results/<run_id>/ (or base/<run_id>/). run_id = YYYYMMDD_<short>_<hash7>."""
    run_id = f"{dt.date.today():%Y%m%d}_{short_name}_{config_hash(config)}"
    root = base if base is not None else sub(exp_id, "results")
    d = root / run_id
    n = 2
    while d.exists() and any(f.name not in ("_CONFIG.json", "_RUN.md") for f in d.iterdir()):
        d = root / f"{run_id}_r{n}"          # never overwrite an earlier run's outputs
        n += 1
    d.mkdir(parents=True, exist_ok=True)
    (d / "_CONFIG.json").write_text(json.dumps(config, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (d / "_RUN.md").write_text(f"# {run_id}\n\nExpansion {exp_id}. {why}\n\nCommand: `{' '.join(sys.argv)}`\n",
                               encoding="utf-8")
    return d


def write_provenance(run_dir: Path, inputs: list[Path] | None = None, outputs: list[Path] | None = None,
                     params: dict | None = None, seeds: dict | None = None, hash_limit_mb: float = 2048,
                     name: str | None = None) -> Path:
    """_PROVENANCE.json (or _PROVENANCE_<name>.json when several scripts share a folder) with SHA-256 of
    inputs/outputs (files above hash_limit_mb get size+mtime only)."""
    def rec(p):
        p = Path(p)
        if not p.exists():
            return {"path": str(p), "exists": False}
        st = p.stat()
        r = {"path": str(p), "bytes": st.st_size, "mtime": dt.datetime.fromtimestamp(st.st_mtime).isoformat()}
        if p.is_file() and st.st_size <= hash_limit_mb * 1e6:
            r["sha256"] = sha256(p)
        return r
    prov = {
        "written": dt.datetime.now().isoformat(timespec="seconds"),
        "commit": _git_commit(),
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "argv": sys.argv, "params": params or {}, "seeds": seeds or {},
        "inputs": [rec(p) for p in (inputs or [])],
        "outputs": [rec(p) for p in (outputs or [])],
    }
    out = Path(run_dir) / (f"_PROVENANCE_{name}.json" if name else "_PROVENANCE.json")
    out.write_text(json.dumps(prov, indent=2, default=str), encoding="utf-8")
    return out


def child_seed(master: int, fold: int = 0, arm: int = 0) -> int:
    """fw_00 section 3. Never share one generator across folds."""
    return int(master + 1000 * fold + arm)


# ----------------------------------------------------------------------------- QC checks
def assert_crs(obj, expected: str = DST_CRS) -> None:
    """obj is a GeoDataFrame, a rasterio dataset, or a CRS-like."""
    crs = getattr(obj, "crs", obj)
    from pyproj import CRS
    got, want = CRS.from_user_input(crs), CRS.from_user_input(expected)
    if got == want:
        return
    # compound CRS (e.g. EPSG:6346 + NAVD88 height) passes when its horizontal part matches
    horiz = [c for c in (got.sub_crs_list or []) if c.is_projected or c.is_geographic]
    if horiz and horiz[0] == want:
        return
    if got.to_epsg() is not None and got.to_epsg() == want.to_epsg():
        return
    raise AssertionError(f"CRS {crs} != {expected}")


def assert_rows(df, expected: int, label: str = "") -> None:
    if len(df) != expected:
        raise AssertionError(f"{label}: expected {expected} rows, got {len(df)}")


def assert_unique(df, col: str) -> None:
    d = df[col][df[col].duplicated()]
    if len(d):
        raise AssertionError(f"duplicate {col}: {list(d[:5])}")


def assert_no_nan(values, label: str = "") -> None:
    import pandas as pd
    if pd.isna(pd.Series(values)).any():
        raise AssertionError(f"NaN in {label}")


def assert_disjoint(a, b, label: str = "") -> None:
    inter = set(a) & set(b)
    if inter:
        raise AssertionError(f"leakage {label}: {sorted(inter)[:5]}")


# ----------------------------------------------------------------------------- statistics
def recall_at_k(scores, matched_truth, block_of_cand, n_truth_by_block: dict, area_km2: float,
                k_per_km2: float = 40.0, areas=None, cand_ids=None, eligible_truth=None):
    """Recall at K per km2 over a complete scored footprint (fw_00 section 4).

    scores          candidate scores
    matched_truth   per candidate, the truth id it matches (None/NaN if unmatched). Duplicates count once.
    block_of_cand   per candidate block id (kept for bootstrap use)
    n_truth_by_block {block: n truth features}, ALL blocks in the footprint, including empty ones
    eligible_truth  optional ids of the truth counted in n_truth. Hits on other truth are ignored, and
                    recall above 1 raises (SH-02).
    Ties: larger area first, then candidate id.
    Returns dict(recall, k, hits, n_truth).
    """
    import pandas as pd
    n = len(scores)
    df = pd.DataFrame({"s": np.asarray(scores, float), "t": list(matched_truth),
                       "a": np.asarray(areas if areas is not None else np.zeros(n), float),
                       "i": np.asarray(cand_ids if cand_ids is not None else np.arange(n))})
    df = df.sort_values(["s", "a", "i"], ascending=[False, False, True], kind="mergesort")
    k = int(round(k_per_km2 * area_km2))
    top = df.head(k)
    t = top["t"].dropna()
    if eligible_truth is not None:              # SH-02: only truth inside the denominator can be a hit
        t = t[t.isin(set(eligible_truth))]
    hits = t.nunique()
    n_truth = int(sum(n_truth_by_block.values()))
    if hits > n_truth:
        raise AssertionError(f"recall_at_k: {hits} hits > {n_truth} truth. Matched truth lies outside the "
                             "denominator footprint. Pass eligible_truth or fix the footprint.")
    return {"recall": hits / n_truth if n_truth else float("nan"), "k": k, "hits": int(hits), "n_truth": n_truth}


def _percentile_ci(draws: np.ndarray, alpha: float, max_undefined: float):
    """SH-01. Undefined draws (NaN) are counted, never silently dropped. If their share exceeds
    max_undefined the interval is undefined (NaN, NaN), which decide() turns into inconclusive."""
    draws = np.asarray(draws, float)
    frac = float(np.mean(~np.isfinite(draws))) if draws.size else 1.0
    if frac > max_undefined or frac == 1.0:
        return float("nan"), float("nan"), frac
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi), frac


def block_bootstrap(stat_fn, blocks, B: int = 2000, seed: int = 0, alpha: float = 0.05,
                    max_undefined: float = 0.0):
    """Resample blocks with replacement. stat_fn(list_of_blocks) -> float. Returns (point, lo, hi, draws).

    Draws where the statistic is undefined (NaN, e.g. a resample with no truth) are kept in `draws`.
    By default any undefined draw makes the interval (NaN, NaN). A caller may tolerate a declared share
    with max_undefined (the interval is then conditional on a defined statistic; report the share,
    which is ek.undefined_share(draws))."""
    blocks = list(blocks)
    rng = np.random.default_rng(seed)
    point = stat_fn(blocks)
    draws = np.array([stat_fn([blocks[j] for j in rng.integers(0, len(blocks), len(blocks))]) for _ in range(B)],
                     dtype=float)
    lo, hi, _ = _percentile_ci(draws, alpha, max_undefined)
    return float(point), lo, hi, draws


def undefined_share(draws) -> float:
    d = np.asarray(draws, float)
    return float(np.mean(~np.isfinite(d))) if d.size else 1.0


def bootstrap_diff(stat_a, blocks_a, stat_b, blocks_b, B: int = 2000, seed: int = 0, alpha: float = 0.05,
                   paired: bool = False, max_undefined: float = 0.0, return_draws: bool = False):
    """Difference a-b. Independent areas resample separately. paired=True reuses the same draw (same blocks).
    Undefined draws follow block_bootstrap (SH-01). return_draws=True appends the draw array."""
    rng = np.random.default_rng(seed)
    blocks_a, blocks_b = list(blocks_a), list(blocks_b)
    if paired and len(blocks_a) != len(blocks_b):
        raise ValueError("paired bootstrap needs the same blocks in both arms")
    d = []
    for _ in range(B):
        ia = rng.integers(0, len(blocks_a), len(blocks_a))
        ib = ia if paired else rng.integers(0, len(blocks_b), len(blocks_b))
        d.append(stat_a([blocks_a[j] for j in ia]) - stat_b([blocks_b[j] for j in ib]))
    d = np.array(d, dtype=float)
    lo, hi, _ = _percentile_ci(d, alpha, max_undefined)
    out = (float(stat_a(blocks_a) - stat_b(blocks_b)), lo, hi)
    return out + (d,) if return_draws else out


def clopper_pearson(k: int, n: int, alpha: float = 0.05):
    from scipy.stats import beta
    if n <= 0:
        return float("nan"), float("nan"), float("nan")
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return k / n if n else float("nan"), float(lo), float(hi)


def _wilson(k, n, z=1.959964):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def newcombe_diff(k1: int, n1: int, k2: int, n2: int):
    """Newcombe hybrid score interval for p1 - p2 (method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = _wilson(k1, n1)
    l2, u2 = _wilson(k2, n2)
    d = p1 - p2
    lo = d - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return float(d), float(lo), float(hi)


def calibration(y, p, bins: int = 10):
    """Brier, log loss, ECE with equal-mass bins."""
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    brier = float(np.mean((p - y) ** 2))
    ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    order = np.argsort(p)
    ece = 0.0
    for idx in np.array_split(order, bins):
        if len(idx):
            ece += len(idx) / len(p) * abs(y[idx].mean() - p[idx].mean())
    return {"brier": brier, "log_loss": ll, "ece": float(ece)}


def decide(lo: float, hi: float, margin: float, kind: str = "noninferiority") -> str:
    """fw_00 decision function. Inconclusive is never 'no effect'."""
    if kind not in {"noninferiority", "superiority"}:
        raise ValueError(kind)
    if not np.isfinite(margin) or margin < 0:
        raise ValueError("margin must be finite and nonnegative")
    if not np.isfinite(lo) or not np.isfinite(hi) or lo > hi:
        return "inconclusive"
    if kind == "noninferiority":
        return "success" if lo > -margin else "failure" if hi < -margin else "inconclusive"
    if kind == "superiority":
        return "success" if lo > margin else "failure" if hi < margin else "inconclusive"
    raise ValueError(kind)


def n_for_proportion(d: float, deff: float = 1.5, p: float = 0.5) -> int:
    return int(np.ceil(1.959964 ** 2 * p * (1 - p) / d ** 2 * deff))


def projected_width(stat_fn, pool_blocks, n_target: int, B: int = 2000, reps: int = 50, seed: int = 0):
    """Median 95% interval width when n_target blocks are drawn from pool_blocks (design check)."""
    rng = np.random.default_rng(seed)
    pool = list(pool_blocks)
    widths = []
    for r in range(reps):
        pick = [pool[j] for j in rng.choice(len(pool), n_target, replace=len(pool) < n_target)]
        _, lo, hi, _ = block_bootstrap(stat_fn, pick, B=B // 10, seed=seed + r + 1)
        widths.append(hi - lo)
    return float(np.median(widths))


# ----------------------------------------------------------------------------- proposal policy (fw_00 section 4)
# One versioned policy for every scorer (reference 3.0, regional 3.1-3.8, benchmark 7.3). Review F02 / G-01.
PROPOSAL_POLICY = {
    "version": "fw00_s4_20261105",
    "cutoff": {"pit_floor": 0.35, "pit": 0.35, "pit_full": 0.35, "pad": 0.525},
    "sensitivity_cutoff": 0.10,
    "min_area_m2": 4.0,
    "iou": 0.3,
    "match_order": "score",          # greedy, score descending; "iou" is a sensitivity only
    "blob_score": "mean",
    "tie_break": ["score desc", "area desc", "numeric id asc"],
    "k_per_km2": 40.0,
    "k_sensitivity_per_km2": 30.0,
}


def policy_for(task: str, mode: str = "primary") -> dict:
    """Scoring policy for a task. mode 'primary' or 'sensitivity' (0.10 cutoff, IoU-order matching).
    Every scorer must call this and stamp the returned dict (with its hash) into its outputs."""
    if mode not in ("primary", "sensitivity"):
        raise ValueError(f"mode must be primary or sensitivity, got {mode}")
    cut = PROPOSAL_POLICY["cutoff"]
    if task not in cut:
        raise KeyError(f"no proposal cutoff for task '{task}'. Known: {sorted(cut)}")
    p = {"task": task, "mode": mode, "version": PROPOSAL_POLICY["version"],
         "cutoff": cut[task] if mode == "primary" else PROPOSAL_POLICY["sensitivity_cutoff"],
         "min_area_m2": PROPOSAL_POLICY["min_area_m2"], "iou": PROPOSAL_POLICY["iou"],
         "match_order": "score" if mode == "primary" else "iou",
         "blob_score": PROPOSAL_POLICY["blob_score"], "k_per_km2": PROPOSAL_POLICY["k_per_km2"]}
    p["policy_hash"] = config_hash(p)
    return p


def assert_same_policy(a: dict, b: dict, keys=("cutoff", "min_area_m2", "iou", "match_order", "blob_score",
                                                "k_per_km2", "version")) -> None:
    """F08. Reference and target must share every scoring setting before a comparative gate."""
    diff = {k: (a.get(k), b.get(k)) for k in keys if a.get(k) != b.get(k)}
    if diff:
        raise AssertionError(f"scoring policy mismatch between reference and target: {diff}")


# ----------------------------------------------------------------------------- shared readers (review F05)
SPLITS_KEY = "results_9t"
ROLE_CANON = {"train": "train", "inner_val": "inner_val", "val": "inner_val",
              "held_out": "held_out", "heldout": "held_out"}


def _prereq_import(group_dir: str, module: str):
    import importlib
    d = EXP_ROOT / "0_prerequisites" / group_dir / "src"
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    return importlib.import_module(module)


def default_audit_path() -> Path:
    return path_for(SPLITS_KEY) / "splits" / "audit_blocks_9t_v1.csv"


def read_audit(path: Path | None = None, allow_unfrozen: bool = False):
    """The frozen P2 audit set, through P2's hash-checking reader (handles the # header).
    Returns a DataFrame with block_id (int) and role ('audit' = sealed test ground, 'buffer' = no-train
    margin). Never read the audit CSV with a plain pd.read_csv."""
    ag = _prereq_import("p2_audit_set", "_audit_guard_lib")
    return ag.load_audit(Path(path) if path else default_audit_path(), allow_unfrozen=allow_unfrozen)


def audit_ids(audit, roles=("audit", "buffer")) -> set[int]:
    """Block ids to keep out of training. roles=('audit',) gives the sealed test blocks only."""
    if audit is None:
        return set()
    if "role" not in audit:
        return set(audit.block_id.astype(int))
    return set(audit.loc[audit.role.isin(roles), "block_id"].astype(int))


def require_audit(path: Path | None = None, allow_missing: bool = False, allow_unfrozen: bool = False):
    """Audit-aware stages call this. Missing file raises unless allow_missing (then returns None and the
    caller must label its output 'no audit exclusion'). Review 7.1-01: never fall back to an empty set."""
    p = Path(path) if path else default_audit_path()
    if not p.exists():
        if allow_missing:
            return None
        raise FileNotFoundError(f"audit set not frozen: {p}. Freeze P2 or pass --allow-no-audit "
                                "and label the output exploratory.")
    return read_audit(p, allow_unfrozen=allow_unfrozen)


def default_split_path(version: int = 1) -> Path:
    return path_for(SPLITS_KEY) / "splits" / f"cv_splits_future_9t_v{version}.json"


def read_split(task: str, path: Path | None = None) -> dict[int, dict[str, list[int]]]:
    """P1 future split for one task, hash-checked. {fold: {'train','inner_val','held_out': [block ids]}}.
    Role names are always the P1 JSON names."""
    sw = _prereq_import("p1_splits_manifests", "_split_future_write_9t")
    raw = sw.split_file_for(task, Path(path) if path else default_split_path())
    return {f: {ROLE_CANON.get(r, r): [int(b) for b in ids] for r, ids in roles.items() if r in ROLE_CANON}
            for f, roles in raw.items()}


def read_split_csv(path: Path):
    """Long split CSV (block_id, fold, role). Role names are canonicalised to train/inner_val/held_out."""
    import pandas as pd
    df = pd.read_csv(path)
    bad = set(df.role) - set(ROLE_CANON)
    if bad:
        raise ValueError(f"{path}: unknown split roles {bad}")
    df["role"] = df.role.map(ROLE_CANON)
    return df


def default_buffer_path() -> Path:
    return path_for(SPLITS_KEY) / "splits" / "buffer_derivation_9t.json"


def read_buffer(task: str, path: Path | None = None) -> float:
    """Derived spatial buffer (m) for a task from P1. Reads buffer_m_by_task; a file with only buffer_m
    is the pit derivation. Raises if the task has no derived buffer (never silently 0)."""
    p = Path(path) if path else default_buffer_path()
    doc = json.loads(p.read_text(encoding="utf-8"))
    by = doc.get("buffer_m_by_task") or {}
    task_key = "pit" if task.startswith("pit") else task
    if task_key in by and by[task_key] is not None:
        return float(by[task_key])
    if task_key == "pit" and doc.get("buffer_m") is not None and doc.get("task", "pit") == "pit":
        return float(doc["buffer_m"])
    raise KeyError(f"{p}: no derived buffer for task '{task}'. Derive it in P1 or pass --buffer-m explicitly.")

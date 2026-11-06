"""Shared helpers for 6.3 (also used by 6.2, which reuses the 6.3 machinery).

Purpose
    Config and path resolution through expkit, the candidate extraction rule of fw_00 section 4 (threshold at the
    0.10 floor, connected blobs, drop under 4 m2, score by mean probability, reusing polygonize from
    notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py), greedy one-to-one IoU matching that returns the matched
    truth id per candidate, top-K per km2 selection with the fw_00 tie rule, and centroid deduplication.
Inputs
    expansions/6_adjacent/6_3_confuser_classes/src/config_6_3.json
Outputs
    None. Imported by the _confuser_*.py stage scripts and by 6.2.
Run
    Not a script.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

REPO = ek.REPO
TRAIN_DIR = REPO / "notebooks" / "wellsight_v2" / "s3_train"
DEFAULT_CONFIG = HERE / "config_6_3.json"


class MissingInput(FileNotFoundError):
    pass


def load_config(path=None) -> dict:
    return json.loads(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))


def resolve(spec: dict) -> Path:
    if "path" in spec:
        return Path(spec["path"])
    if "key" in spec:
        return ek.path_for(spec["key"]) / spec["rel"]
    if "area" in spec:
        return ek.area_dir(spec["area"]) / spec["rel"]
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / spec["rel"]
    raise KeyError(spec)


def input_path(cfg: dict, name: str, override=None, required: bool | None = None) -> Path | None:
    spec = cfg["inputs"][name]
    p = Path(override) if override else resolve(spec)
    req = (not spec.get("optional", False)) if required is None else required
    if not p.exists():
        if req:
            raise MissingInput(f"missing input '{name}' ({spec.get('state', '?')}) at {p}. "
                               f"Schema {json.dumps(spec.get('schema', 'see framework'))}.")
        return None
    return p


def results_dir(cfg: dict, out=None) -> Path:
    d = Path(out) if out else resolve(cfg["outputs"]["results"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def provenance(cfg: dict, out_dir: Path, short: str, inputs=None, outputs=None, params=None, seeds=None) -> Path:
    """Outputs keep their fixed framework paths. The run record goes to <out_dir>/_runs/<run_id>/."""
    run = ek.new_run(cfg["exp_id"], short, {"params": params, "inputs": [str(p) for p in inputs or []]},
                     base=Path(out_dir) / "_runs", why=f"stage {short}")
    ek.write_provenance(run, inputs=inputs, outputs=outputs, params=params, seeds=seeds)
    return run


def read_vector(path, crs: str, layer=None):
    import geopandas as gpd
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if g.crs is None:
        raise AssertionError(f"{path} has no CRS")
    g = g.to_crs(crs)
    ek.assert_crs(g, crs)
    return g


def read_block_ids(path: Path, col: str = "block_id") -> list[int]:
    df = pd.read_csv(path)
    ek.assert_no_nan(df[col], f"{path.name} {col}")
    return sorted(int(b) for b in df[col].unique())


def audit_block_ids(cfg: dict, override=None, roles=("audit", "buffer"), allow_missing: bool = False):
    """Audit block ids for this config.

    inputs.audit_blocks.reader 'p2' (the 6.3 default) reads the frozen P2 file through ek.require_audit and
    ek.audit_ids. That file starts with # header lines and has a sha256 sidecar, so plain read_csv is wrong.
    roles ('audit', 'buffer') is the no-train set. roles ('audit',) is the sealed scoring ground.
    A missing P2 file raises unless allow_missing. Then this returns None and the caller must label its output
    "no audit exclusion, exploratory".
    reader 'plain' is for 6.2, which freezes its own coal audit blocks as a plain block_id CSV.
    """
    spec = cfg["inputs"]["audit_blocks"]
    if spec.get("reader", "p2") == "plain":
        return read_block_ids(input_path(cfg, "audit_blocks", override))
    p = Path(override) if override else resolve(spec)
    aud = ek.require_audit(p, allow_missing=allow_missing)
    if aud is None:
        return None
    return sorted(ek.audit_ids(aud, roles))


def label_cache_ok(raster: Path, meta: Path, want: dict) -> bool:
    """True when a derived label raster exists and its sidecar records the same sources as want."""
    if not (Path(raster).exists() and Path(meta).exists()):
        return False
    try:
        have = json.loads(Path(meta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return all(have.get(k) == v for k, v in want.items())


def drop_near_truth(xy: np.ndarray, truth, dist_m: float) -> np.ndarray:
    """Boolean keep mask. False for a point within dist_m of any truth geometry (distance 0 means inside)."""
    import geopandas as gpd
    xy = np.asarray(xy, float).reshape(-1, 2)
    if not len(xy) or truth is None or not len(truth):
        return np.ones(len(xy), bool)
    pts = gpd.GeoSeries(gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=truth.crs)
    near = gpd.sjoin(gpd.GeoDataFrame(geometry=pts), gpd.GeoDataFrame(geometry=truth.geometry.buffer(dist_m)),
                     how="inner", predicate="intersects").index.unique()
    keep = np.ones(len(xy), bool)
    keep[np.asarray(near, int)] = False
    return keep


def extract_candidates(prob: np.ndarray, transform, crs: str, floor: float = 0.10, min_area: float = 4.0):
    """fw_00 section 4 rule through the trainer's own polygonize (same code as the sweep)."""
    sys.path.insert(0, str(TRAIN_DIR))
    sys.path.insert(0, str(TRAIN_DIR.parent))
    from _pit_unet_cv5 import polygonize
    g = polygonize(np.nan_to_num(prob, nan=0.0), transform, crs, floor, min_area=min_area)
    g["area_m2"] = g.geometry.area
    return g.reset_index(drop=True)


def top_k(cands, area_km2: float, k_per_km2: float):
    """Top K = round(k_per_km2 * area). Ties by larger area, then lower id (fw_00)."""
    c = cands.copy()
    if "cand_id" not in c:
        c["cand_id"] = np.arange(len(c))
    c = c.sort_values(["score", "area_m2", "cand_id"], ascending=[False, False, True])
    k = int(round(k_per_km2 * area_km2))
    c["rank"] = np.arange(1, len(c) + 1)
    return c.head(k).reset_index(drop=True), k


def greedy_match(truth, cands, iou_thr: float = 0.3, truth_id: str = "truth_id") -> np.ndarray:
    """One candidate to one truth feature, greedy by score over pairs with IoU >= thr. Returns truth id per candidate."""
    out = np.full(len(cands), None, dtype=object)
    if not len(truth) or not len(cands):
        return out
    pairs = []
    sidx = cands.sindex
    sc = cands["score"].to_numpy()
    for gi, g in enumerate(truth.geometry):
        for pj in sidx.intersection(g.bounds):
            p = cands.geometry.iloc[pj]
            inter = g.intersection(p).area
            if inter <= 0:
                continue
            iou = inter / (g.area + p.area - inter)
            if iou >= iou_thr:
                pairs.append((gi, int(pj), iou, float(sc[pj])))
    ug, up = set(), set()
    tid = truth[truth_id].to_numpy()
    for gi, pj, _, _ in sorted(pairs, key=lambda p: (-p[3], -p[2])):
        if gi in ug or pj in up:
            continue
        ug.add(gi)
        up.add(pj)
        out[pj] = tid[gi]
    return out


def dedupe_centroids(xy: np.ndarray, radius: float) -> np.ndarray:
    """Cluster id per point. Points within radius (transitively) share a cluster (union-find)."""
    from scipy.spatial import cKDTree
    n = len(xy)
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    if n:
        for i, j in cKDTree(xy).query_pairs(radius):
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([find(i) for i in range(n)])
    _, cid = np.unique(roots, return_inverse=True)
    return cid


def block_of_points(xy: np.ndarray, blocks) -> np.ndarray:
    import geopandas as gpd
    if not len(xy):
        return np.array([])
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=blocks.crs)
    j = gpd.sjoin(pts, blocks[["block_id", "geometry"]], how="left", predicate="intersects")
    j = j[~j.index.duplicated()]
    return j["block_id"].reindex(pts.index).to_numpy(float)

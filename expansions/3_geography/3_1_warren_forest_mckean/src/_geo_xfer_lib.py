"""Transfer-test library for 3.1 (Warren, Forest, McKean), reused by 3.2 and 3.3.

Purpose
    The thin, generic pieces every geographic transfer stage needs. Each stage script in
    this folder (and in 3.2 / 3.3) imports this module and adds only its own CLI.
    Written against fw_00_common.md section 4 and docs/plans/protocol_gates_and_metrics.md
    sections 2, 3 and 5. It does not depend on the 3.0 scorer (built in parallel).

What is here
    config      load_config, resolve_path, need (clear "missing input" failure)
    lidar       las_header, ground_grid (chunked laspy pass, optional reprojection)
    blocks      make_blocks, cover_fraction, grid_stats_per_block, raster_mean_per_block,
                terciles, assign_roles (seeded, stratified, buffered)
    candidates  candidates_from_prob (reuses _pit_unet_cv5.polygonize), match_iou
    scoring     score_area (recall at K per km2 over complete blocks), pooled_recall,
                diff_vs_reference (block bootstrap + decision), permutation_p,
                superblock_ids, density_scaled_k
    inference   load_ckpt, check_channels, ensemble_prob (wraps _dl.predict_full_tile),
                predict_array (in-memory sliding window, for small edited windows)

Inputs / outputs
    Library only. No file is written unless a caller asks.

Run
    Not run directly. `python -m pytest -q expansions/3_geography/3_1_warren_forest_mckean/src/test_3_1.py -p no:cacheprovider`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402  (also puts notebooks/wellsight_v2 on sys.path)

NB = ek.REPO / "notebooks" / "wellsight_v2"
for _p in (NB, NB / "s1_build", NB / "s3_train", NB / "s4_infer", NB / "s5_eval"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

CRS = ek.DST_CRS                 # EPSG:6346
BLOCK_M = 375.0                  # 9t block side (fw_00 section 4)
PROPOSAL_THR = 0.10              # lowest sweep cutoff (fw_00 section 4)
MIN_BLOB_M2 = 4.0
IOU_TAU = 0.3
K_PRIMARY = 40.0                 # candidates per km2 (user decision 2026-11-04)
K_SENSITIVITY = 30.0


class MissingInput(FileNotFoundError):
    """Raised when an assumed input is not on disk. The message names it."""


# ----------------------------------------------------------------------------- config
def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_path(spec, area: str | None = None) -> Path | None:
    """Turn a config path spec into a Path without spelling a data path in code.

    spec forms
        {"path_for": "<key>", "rel": "a/b"}   -> ek.path_for(key) / rel
        {"area": "<area>", "rel": "a/b"}      -> ek.area_dir(area) / rel   ("{area}" fills from arg)
        {"exp": "3.1", "rel": "a/b"}          -> ek.exp_dir(exp) / rel
        {"abs": "F:/x/y"}                     -> Path (external drives only)
        None                                  -> None
    "{area}" inside rel is replaced by the area argument.
    """
    if spec is None:
        return None
    if isinstance(spec, str):
        return Path(spec)
    rel = spec.get("rel", "")
    if area is not None:
        rel = rel.replace("{area}", area)
    if "path_for" in spec:
        return ek.path_for(spec["path_for"]) / rel
    if "area" in spec:
        a = spec["area"].replace("{area}", area or "")
        return ek.area_dir(a) / rel
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / rel
    if "abs" in spec:
        return Path(spec["abs"].replace("{area}", area or ""))
    raise ValueError(f"bad path spec {spec}")


def need(path: Path | None, what: str, hint: str = "") -> Path:
    """Fail clearly when an input is missing. `what` names the input and where it comes from."""
    if path is None or not Path(path).exists():
        msg = f"MISSING INPUT: {what}\n  expected at: {path}"
        if hint:
            msg += f"\n  {hint}"
        raise MissingInput(msg)
    return Path(path)


def area_ctx(cfg: dict, area: str, mkdirs: bool = True) -> dict:
    """Resolved per-area settings from a 3.1-style config (areas.<area>, outputs, assumed)."""
    if area not in cfg["areas"]:
        raise KeyError(f"area {area!r} not in config areas {sorted(cfg['areas'])}")
    A = cfg["areas"][area]
    ctx = {"area": area, "cfg": A, "src_crs": A.get("src_crs"),
           "tables": resolve_path(cfg["outputs"]["tables"], area),
           "heavy": resolve_path(cfg["outputs"]["heavy"], area)}
    for k in ("slope_1m", "dem_1m", "merged_las"):
        ctx[k] = resolve_path(A.get(k), area)
    spec = A.get("tiles")
    pat = resolve_path(spec, area)
    ctx["tiles_pattern"] = str(pat) if pat else None
    ctx["tiles"] = glob_paths(str(pat)) if pat else []
    if mkdirs:
        ctx["tables"].mkdir(parents=True, exist_ok=True)
        ctx["heavy"].mkdir(parents=True, exist_ok=True)
    return ctx


def assumed_path(cfg: dict, key: str, area: str | None = None, **fmt) -> Path:
    """Resolve an entry of cfg['assumed'] and fail clearly (naming schema and source) if missing."""
    e = cfg["assumed"][key]
    p = resolve_path(e["spec"], area)
    if fmt:
        p = Path(str(p).format(**fmt))
    if not p.exists():
        raise MissingInput(f"MISSING INPUT: {key}\n  expected at: {p}\n"
                           f"  schema: {e['schema']}\n  from: {e['from']}")
    return p


def glob_paths(pattern: str) -> list[Path]:
    """Glob a pattern that may be absolute (Windows drive) or repo-relative."""
    p = Path(pattern)
    if p.is_absolute():
        anchor = Path(p.anchor)
        return sorted(anchor.glob(str(p.relative_to(anchor)).replace("\\", "/")))
    return sorted(ek.REPO.glob(pattern))


# ----------------------------------------------------------------------------- lidar
def _crs_epsg(crs):
    if crs is None:
        return None, None, None
    try:
        subs = crs.sub_crs_list
    except Exception:  # noqa: BLE001
        subs = []
    horiz = subs[0] if subs else crs
    vert = subs[1].name if len(subs) > 1 else None
    return horiz.to_epsg(), horiz.name, vert


def las_header(path: Path) -> dict:
    """Header facts of one LAS/LAZ (version, format, count, bounds, CRS). Header read only."""
    import laspy
    path = Path(path)
    with laspy.open(str(path)) as f:
        h = f.header
        try:
            crs = h.parse_crs()
        except Exception:  # noqa: BLE001
            crs = None
    epsg, name, vert = _crs_epsg(crs)
    unit = 1.0
    if crs is not None:
        try:
            unit = float(crs.axis_info[0].unit_conversion_factor)
        except Exception:  # noqa: BLE001
            unit = 1.0
    return {"file": path.name, "bytes": path.stat().st_size,
            "las_version": f"{h.version.major}.{h.version.minor}",
            "point_format": int(h.point_format.id), "n_points": int(h.point_count),
            "minx": float(h.mins[0]), "miny": float(h.mins[1]), "minz": float(h.mins[2]),
            "maxx": float(h.maxs[0]), "maxy": float(h.maxs[1]), "maxz": float(h.maxs[2]),
            "crs_epsg": epsg, "crs_name": name, "vertical_crs": vert, "unit_to_m": unit}


def ground_grid(las_paths, bbox, res: float, *, src_crs: str | None = None, dst_crs: str = CRS,
                classes=(2,), chunk: int = 5_000_000):
    """Count points of `classes` per cell of a res-m grid over bbox (dst CRS).

    Chunked laspy pass (bounded RAM, same pattern as _build_derivatives.build step 3).
    src_crs reprojects on the fly (McKean B19 tiles are EPSG:6350 Albers).
    Returns (counts uint32 HxW, transform, info dict with per-file totals).
    """
    import laspy
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = map(float, bbox)
    W, H = int(round((x1 - x0) / res)), int(round((y1 - y0) / res))
    flat = np.zeros(H * W, dtype=np.int64)
    tr = None
    if src_crs and src_crs != dst_crs:
        from pyproj import Transformer
        tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    info = []
    for p in las_paths:
        n_all = n_cls = 0
        with laspy.open(str(p)) as lf:
            for pts in lf.chunk_iterator(chunk):
                cls = np.asarray(pts.classification)
                n_all += len(cls)
                m = np.isin(cls, classes)
                if not m.any():
                    continue
                xs, ys = np.asarray(pts.x)[m], np.asarray(pts.y)[m]
                if tr is not None:
                    xs, ys = tr.transform(xs, ys)
                n_cls += int(m.sum())
                col = np.floor((xs - x0) / res).astype(np.int64)
                row = np.floor((y1 - ys) / res).astype(np.int64)
                ok = (col >= 0) & (col < W) & (row >= 0) & (row < H)
                flat += np.bincount(row[ok] * W + col[ok], minlength=H * W)
        info.append({"file": Path(p).name, "n_points": n_all, "n_class": n_cls})
    return flat.reshape(H, W).astype(np.uint32), from_origin(x0, y1, res, res), info


def roughness_std(dem, win: int):
    """Std of the DEM in a win x win window. The _build_derivatives.py roughness formula with the
    window as a parameter (the builder hard-codes 5). At 0.5 m the model channel roughness_11 is
    win = 11. In float32 on a 600 x 600 9t crop this reproduces the stored band exactly
    (xfer_recompute_check_9t.json, 2026-11-05)."""
    from scipy import ndimage as ndi
    k = np.ones((win, win), dtype=np.float32)
    v = np.isfinite(dem).astype(np.float32)
    z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
    s = ndi.convolve(z0, k, mode="nearest")
    s2 = ndi.convolve(z0 * z0, k, mode="nearest")
    n = ndi.convolve(v, k, mode="nearest")
    var = np.where(n > 1, (s2 - s * s / np.maximum(n, 1)) / np.maximum(n - 1, 1), np.nan)
    return np.sqrt(np.clip(var, 0, None)).astype(np.float32)


# ----------------------------------------------------------------------------- channel recompute
def _nan_box_mean(dem, size):
    from scipy.ndimage import uniform_filter
    valid = np.isfinite(dem).astype(np.float32)
    z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
    sm = uniform_filter(z0, size=size, mode="nearest")
    sc = uniform_filter(valid, size=size, mode="nearest")
    return np.where(sc > 0, sm / np.maximum(sc, 1e-12), np.nan)


def _horn_slope(dem, res):
    """Horn (1981) 3x3 slope in degrees. Not bit-identical to the WBT slope in the 9t stack.
    On a 600 x 600 9t crop r = 0.997, median abs diff 0.16 deg (xfer_recompute_check_9t.json).
    The other six channels match the stored stack exactly. Edits are paired against a
    background recomputed the same way, so this offset cancels in the paired difference."""
    z = np.pad(dem, 1, mode="edge")
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy))).astype(np.float32)


def _roughness(dem, win):
    """Std of DEM in a win x win window (shared helper in _geo_xfer_lib)."""
    return roughness_std(dem, win)


def channels_from_dem(dem, res: float = 0.5):
    """The seven model channels (DEFAULT_CHANNELS order) from a DEM array."""
    from _build_derivatives import disk_kernel, nanmean_filter, openness
    dem = dem.astype(np.float32)
    lrm25 = (dem - _nan_box_mean(dem, 25)).astype(np.float32)
    lrm5 = (dem - _nan_box_mean(dem, 5)).astype(np.float32)
    slope = _horn_slope(dem, res)
    tpi05 = (dem - nanmean_filter(dem, disk_kernel(5.0 / res))).astype(np.float32)
    op_pos, op_neg = openness(dem, L_cells=int(25 / res), cellsize=res)
    rough = _roughness(dem, 11)
    return np.stack([lrm25, lrm5, slope, tpi05, op_pos, op_neg, rough]).astype(np.float32)


# ----------------------------------------------------------------------------- blocks
def make_blocks(bbox, size: float = BLOCK_M, crs: str = CRS):
    """Regular size-m blocks laid from the bbox lower-left corner. Partial blocks kept, flagged later."""
    import geopandas as gpd
    from shapely.geometry import box
    x0, y0, x1, y1 = map(float, bbox)
    nx, ny = int(np.ceil((x1 - x0) / size - 1e-9)), int(np.ceil((y1 - y0) / size - 1e-9))
    rows = []
    for iy in range(ny):
        for ix in range(nx):
            bx0, by0 = x0 + ix * size, y0 + iy * size
            rows.append({"block_id": iy * nx + ix, "ix": ix, "iy": iy,
                         "geometry": box(bx0, by0, bx0 + size, by0 + size)})
    return gpd.GeoDataFrame(rows, crs=crs)


def cover_fraction(blocks, cover_geom):
    """Share of each block inside the union of tile footprints (geometries, never tile counts)."""
    a = blocks.geometry.area
    return (blocks.geometry.intersection(cover_geom).area / a).clip(0, 1).to_numpy()


def grid_stats_per_block(blocks, counts, transform, res: float):
    """Ground density (points per m2 over the block) and void fraction (share of cells with 0)."""
    from rasterio.windows import from_bounds
    dens, void = [], []
    H, W = counts.shape
    for g in blocks.geometry:
        w = from_bounds(*g.bounds, transform=transform).round_offsets().round_lengths()
        r0, c0 = max(int(w.row_off), 0), max(int(w.col_off), 0)
        r1, c1 = min(int(w.row_off + w.height), H), min(int(w.col_off + w.width), W)
        sub = counts[r0:r1, c0:c1]
        if sub.size == 0:
            dens.append(np.nan); void.append(np.nan)
            continue
        dens.append(float(sub.sum()) / (sub.size * res * res))
        void.append(float((sub == 0).mean()))
    return np.array(dens), np.array(void)


def raster_mean_per_block(blocks, raster_path: Path, nodata_ok: bool = True):
    """Mean of a raster's valid cells inside each block (e.g. slope from the 1 m DEM)."""
    import rasterio
    from rasterio.windows import from_bounds
    from contextlib import ExitStack
    from pyproj import CRS as _CRS
    from rasterio.vrt import WarpedVRT
    out = []
    with ExitStack() as st:
        r = st.enter_context(rasterio.open(raster_path))
        if _CRS.from_user_input(r.crs) != _CRS.from_user_input(blocks.crs):
            # CRS ALERT (CLAUDE.md). e.g. Warren 1 m derivatives are EPSG:26917, blocks EPSG:6346.
            print(f"  CRS ALERT: {Path(raster_path).name} is {r.crs}, warping to {blocks.crs} on read")
            r = st.enter_context(WarpedVRT(r, crs=blocks.crs, resampling=1))
        ek.assert_crs(r, blocks.crs)
        for g in blocks.geometry:
            from rasterio.windows import Window
            w = from_bounds(*g.bounds, transform=r.transform).round_offsets().round_lengths()
            try:
                w = w.intersection(Window(0, 0, r.width, r.height))
            except Exception:  # noqa: BLE001  (no overlap)
                out.append(np.nan)
                continue
            a = r.read(1, window=w, masked=True).astype("float64")
            a = np.ma.masked_invalid(a)
            out.append(float(a.mean()) if a.count() else np.nan)
    return np.array(out)


def terciles(values, cuts=None):
    """Tercile labels 0 (low), 1, 2 (high) and the cut points used. Cut points can be frozen."""
    v = np.asarray(values, float)
    if cuts is None:
        cuts = [float(np.nanquantile(v, 1 / 3)), float(np.nanquantile(v, 2 / 3))]
    lab = np.where(np.isnan(v), -1, np.digitize(v, cuts, right=True))
    return lab.astype(int), cuts


def assign_roles(blocks, *, seed: int, buffer_m: float, test_frac_of_rest: float = 0.75,
                 adapt_frac: float = 0.25, min_adapt_km2: float = 7.0, strat_col: str | None = None,
                 eligible_col: str = "eligible"):
    """Seeded role draw: adaptation, test, audit, buffer, ineligible.

    Design (decision 2026-11-05, build agent). Adaptation must sit at least buffer_m from
    every test and audit block, so it is drawn as one contiguous strip from a seeded side
    (west, east, south or north), not scattered. Blocks inside the buffer become "buffer".
    If the strip is under min_adapt_km2 the adaptation role is dropped and every eligible
    block goes to test or audit. Test and audit are a seeded draw stratified by strat_col.
    """
    rng = np.random.default_rng(seed)
    b = blocks.copy()
    b["role"] = np.where(b[eligible_col].astype(bool), "pool", "ineligible")
    pool = b[b.role == "pool"]
    side = ["west", "east", "south", "north"][int(rng.integers(0, 4))]
    cx, cy = pool.geometry.centroid.x, pool.geometry.centroid.y
    key = {"west": cx, "east": -cx, "south": cy, "north": -cy}[side]
    n_adapt = int(np.floor(adapt_frac * len(pool)))
    adapt_ids = set(pool.block_id.to_numpy()[np.argsort(key.to_numpy(), kind="stable")[:n_adapt]])
    adapt_area = sum(pool.geometry[pool.block_id.isin(adapt_ids)].area) / 1e6
    dropped = adapt_area < min_adapt_km2 or n_adapt == 0
    if dropped:
        adapt_ids = set()
    else:
        b.loc[b.block_id.isin(adapt_ids), "role"] = "adaptation"
        ad = b[b.role == "adaptation"].geometry.union_all()
        near = (b.role == "pool") & (b.geometry.distance(ad) < buffer_m)
        b.loc[near, "role"] = "buffer"
    rest = b[b.role == "pool"]
    strata = rest[strat_col] if strat_col else pd.Series(0, index=rest.index)
    for _, grp in rest.groupby(strata):
        ids = grp.block_id.to_numpy().copy()
        rng.shuffle(ids)
        n_test = int(round(test_frac_of_rest * len(ids)))
        b.loc[b.block_id.isin(ids[:n_test]), "role"] = "test"
        b.loc[b.block_id.isin(ids[n_test:]), "role"] = "audit"
    meta = {"seed": seed, "adapt_side": side, "adapt_area_km2": float(adapt_area),
            "adaptation_dropped": bool(dropped), "buffer_m": float(buffer_m),
            "counts": b.role.value_counts().to_dict()}
    # QC: no test/audit block within the buffer of adaptation
    if not dropped:
        ad = b[b.role == "adaptation"].geometry.union_all()
        ta = b[b.role.isin(["test", "audit"])]
        if len(ta) and float(ta.geometry.distance(ad).min()) < buffer_m - 1e-6:
            raise AssertionError("test/audit block inside the adaptation buffer")
    return b, meta


# ----------------------------------------------------------------------------- candidates
def candidates_from_prob(prob, transform, crs=CRS, thr: float = PROPOSAL_THR, min_area: float = MIN_BLOB_M2):
    """Probability raster -> blobs scored by mean probability. Reuses the CV5 polygonize."""
    from _pit_unet_cv5 import polygonize  # same code as the operating-point sweep
    g = polygonize(np.asarray(prob, dtype=np.float32), transform, crs, thr, min_area=min_area)
    g = g.reset_index(drop=True)
    g["area_m2"] = g.geometry.area
    return g


def match_iou(truth, cands, tau: float = IOU_TAU, truth_id: str = "truth_id", cand_id: str = "cand_id"):
    """Greedy one-to-one matching by IoU (fw_00 section 4). Ties by higher score, then cand id.

    Returns a Series indexed like cands: the matched truth id, or NaN. A second blob on an
    already-matched feature stays unmatched (a duplicate, not a new detection).
    """
    out = pd.Series(np.nan, index=cands.index, dtype=object)
    if len(truth) == 0 or len(cands) == 0:
        return out
    ti, ci = cands.sindex.query(truth.geometry, predicate="intersects")
    pairs = []
    tg, cg = truth.geometry.to_numpy(), cands.geometry.to_numpy()
    for a, c in zip(ti, ci):
        inter = tg[a].intersection(cg[c]).area
        u = tg[a].area + cg[c].area - inter
        iou = inter / u if u > 0 else 0.0
        if iou >= tau:
            pairs.append((iou, float(cands["score"].iat[c]), -int(cands[cand_id].iat[c]), a, c))
    pairs.sort(reverse=True)
    used_t, used_c = set(), set()
    tids = truth[truth_id].to_numpy()
    for _, _, _, a, c in pairs:
        if a in used_t or c in used_c:
            continue
        used_t.add(a); used_c.add(c)
        out.iat[c] = tids[a]
    return out


def _assign_block(gdf, blocks):
    import geopandas as gpd
    pts = gpd.GeoDataFrame(geometry=gdf.geometry.representative_point(), crs=gdf.crs, index=gdf.index)
    j = gpd.sjoin(pts, blocks[["block_id", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    return j["block_id"].reindex(gdf.index)


def score_area(cands, truth, blocks, *, k_per_km2: float = K_PRIMARY, tau: float = IOU_TAU,
               truth_id: str = "truth_id"):
    """Recall at K per km2 over a complete scored footprint.

    blocks  the eligible scored blocks (every one, including blocks with no truth)
    cands   blobs with score, geometry (cand_id added if absent)
    truth   features with truth_id, geometry
    Candidates and truth are credited by representative point to a block. A hit is credited
    to the truth feature's block. K = round(k_per_km2 * area), ties by larger area, then id.
    Returns (summary dict, per-block DataFrame, scored cands, scored truth).
    """
    cands = cands.copy()
    if "cand_id" not in cands:
        cands["cand_id"] = np.arange(len(cands))
    if "area_m2" not in cands:
        cands["area_m2"] = cands.geometry.area
    cands["block_id"] = _assign_block(cands, blocks) if len(cands) else pd.Series(dtype=float)
    cands = cands[cands.block_id.notna()].copy()
    truth = truth.copy()
    ek.assert_unique(truth, truth_id)
    truth["block_id"] = _assign_block(truth, blocks) if len(truth) else pd.Series(dtype=float)
    truth = truth[truth.block_id.notna()].copy()
    cands["matched"] = match_iou(truth, cands, tau=tau, truth_id=truth_id) if len(cands) else []
    area_km2 = float(blocks.geometry.area.sum() / 1e6)
    order = cands.sort_values(["score", "area_m2", "cand_id"], ascending=[False, False, True])
    k = int(round(k_per_km2 * area_km2))
    kept_ids = set(order.cand_id.head(k))
    cands["kept"] = cands.cand_id.isin(kept_ids)
    hit_ids = set(cands.loc[cands.kept, "matched"].dropna())
    truth["found"] = truth[truth_id].isin(hit_ids)
    n_by_block = {int(b): 0 for b in blocks.block_id}
    n_by_block.update(truth.groupby("block_id").size().astype(int).to_dict())
    # cross-check with the shared toolkit (same ordering, same K)
    ref = ek.recall_at_k(cands.score.to_numpy(), cands.matched.tolist(), cands.block_id.to_numpy(),
                         n_by_block, area_km2, k_per_km2=k_per_km2, areas=cands.area_m2.to_numpy(),
                         cand_ids=cands.cand_id.to_numpy())
    if ref["hits"] != len(hit_ids):
        raise AssertionError(f"recall_at_k mismatch {ref['hits']} vs {len(hit_ids)}")
    per = pd.DataFrame({"block_id": list(n_by_block)})
    per["n_truth"] = per.block_id.map(n_by_block).astype(int)
    per["hits"] = per.block_id.map(truth[truth.found].groupby("block_id").size()).fillna(0).astype(int)
    per["n_kept"] = per.block_id.map(cands[cands.kept].groupby("block_id").size()).fillna(0).astype(int)
    per["area_km2"] = per.block_id.map(dict(zip(blocks.block_id, blocks.geometry.area / 1e6)))
    summ = {"recall": ref["recall"], "hits": ref["hits"], "n_truth": ref["n_truth"], "k": k,
            "k_per_km2": k_per_km2, "area_km2": area_km2, "n_blocks": int(len(blocks)),
            "n_candidates": int(len(cands)), "truth_density_per_km2": ref["n_truth"] / area_km2 if area_km2 else np.nan}
    return summ, per, cands, truth


def pooled_recall(rows) -> float:
    h = sum(r[0] for r in rows)
    n = sum(r[1] for r in rows)
    return h / n if n else float("nan")


def permutation_p(a_rows, b_rows, n_perm: int = 5000, seed: int = 0) -> float:
    """Two-sided permutation p for pooled-recall difference, block labels shuffled."""
    rng = np.random.default_rng(seed)
    allr = list(a_rows) + list(b_rows)
    na = len(a_rows)
    obs = pooled_recall(a_rows) - pooled_recall(b_rows)
    cnt = 0
    for _ in range(n_perm):
        idx = rng.permutation(len(allr))
        d = pooled_recall([allr[i] for i in idx[:na]]) - pooled_recall([allr[i] for i in idx[na:]])
        cnt += abs(d) >= abs(obs) - 1e-12
    return (cnt + 1) / (n_perm + 1)


def diff_vs_reference(target_rows, ref_rows, *, margin: float | None, B: int = 2000, seed: int = 0,
                      kind: str = "noninferiority"):
    """Target minus reference pooled recall, independent block bootstraps, decision by ek.decide."""
    target_rows = [tuple(r) for r in target_rows]
    ref_rows = [tuple(r) for r in ref_rows]
    d, lo, hi = ek.bootstrap_diff(pooled_recall, target_rows, pooled_recall, ref_rows, B=B, seed=seed)
    out = {"diff": d, "lo": lo, "hi": hi, "B": B, "seed": seed, "margin": margin,
           "n_target_blocks": len(target_rows), "n_reference_blocks": len(ref_rows),
           "decision": ek.decide(lo, hi, margin, kind) if margin is not None else "no_margin_set"}
    if len(target_rows) < 15:
        out["permutation_p"] = permutation_p(target_rows, ref_rows, seed=seed)
        out["note"] = "fewer than 15 target blocks, the bootstrap is unreliable"
    return out


def superblock_ids(blocks, side_blocks: int):
    """Super-block id for a side x side group of blocks (sensitivity resampling unit)."""
    return (blocks.iy // side_blocks) * 10_000 + (blocks.ix // side_blocks)


def density_scaled_k(k_ref: float, density_ref: float, density_target: float) -> float:
    """K = c x density with c = k_ref / density_ref fixed from 9t before scoring."""
    return k_ref / density_ref * density_target


# ----------------------------------------------------------------------------- inference
def load_ckpt(path: Path, n_classes: int):
    import torch
    from _dl import UNet
    ck = torch.load(str(path), map_location="cpu", weights_only=False)
    model = UNet(in_ch=len(ck["channels"]), n_classes=n_classes, base=32)
    model.load_state_dict(ck["state_dict"])
    return model, np.asarray(ck["mu"], np.float32), np.asarray(ck["sd"], np.float32), tuple(ck["channels"]), \
        {"epoch": int(ck.get("epoch", -1)), "score": float(ck.get("score", np.nan))}


def check_channels(features_tif: Path, channels) -> None:
    """Band descriptions must equal the checkpoint channel order. Silent swaps are the worst bug."""
    import rasterio
    with rasterio.open(features_tif) as r:
        desc = tuple(r.descriptions)
    if desc != tuple(channels):
        raise AssertionError(f"channel order {desc} != checkpoint {tuple(channels)} in {features_tif}")


def ensemble_prob(features_tif: Path, ckpts, *, n_classes: int, patch: int, overlap: int, cls: int):
    """Mean class probability over checkpoints (declared ensemble policy). mu/sd from each ckpt."""
    from _dl import predict_full_tile
    acc, prof, meta = None, None, []
    for c in ckpts:
        model, mu, sd, ch, m = load_ckpt(c, n_classes)
        check_channels(features_tif, ch)
        prob, _, prof = predict_full_tile(model, Path(features_tif), mu, sd, patch=patch, overlap=overlap,
                                          n_classes=n_classes)
        p = prob[cls]
        acc = p.astype(np.float64) if acc is None else acc + p
        meta.append({"ckpt": str(c), **m})
        del prob
    return (acc / len(ckpts)).astype(np.float32), prof, meta


def predict_array(model, feat, mu, sd, *, patch: int, overlap: int, n_classes: int, batch: int = 8):
    """Sliding-window inference on an in-memory (C, H, W) array. Same normalisation as _dl."""
    import torch
    from _dl import DEVICE, normalize
    C, H, W = feat.shape
    if H < patch or W < patch:
        raise ValueError(f"array {H}x{W} smaller than patch {patch}")
    step = patch - overlap

    def rc(n):
        xs = list(range(0, n - patch + 1, step))
        if xs[-1] != n - patch:
            xs.append(n - patch)
        return xs
    prob = np.zeros((n_classes, H, W), np.float32)
    cnt = np.zeros((H, W), np.float32)
    x = normalize(feat.astype(np.float32), mu, sd).astype(np.float32)
    model.to(DEVICE).eval()
    pos = [(r, c) for r in rc(H) for c in rc(W)]
    for i in range(0, len(pos), batch):
        chunk = pos[i:i + batch]
        t = torch.from_numpy(np.stack([x[:, r:r + patch, c:c + patch] for r, c in chunk])).to(DEVICE)
        with torch.no_grad():
            p = torch.softmax(model(t), 1).cpu().numpy()
        for arr, (r, c) in zip(p, chunk):
            prob[:, r:r + patch, c:c + patch] += arr
            cnt[r:r + patch, c:c + patch] += 1
    return prob / np.maximum(cnt, 1)

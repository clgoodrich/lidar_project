"""5.1 S2. Context reliance test (Q1). Edit the DEM around pits, recompute derivatives, rescore (tile 9t).

Purpose
    Does the pit score depend on pad and road context? For a random sample of annotated pits (all pits, not
    only detected ones) and slope-matched controls, edit the DEM in a scene around the unit and rescore.
    Variants
        pad        flatten the pad to the natural plane fitted on a 5 m ring outside it. A 12 m disc around the
                   unit is kept untouched
        road       remove access-road corridors within 60 m (3 m each side of the line). Inpaint linearly from a 3 m ring
        both       pad then road
        sham_pad   the pad mask translated to open terrain in the same scene, same operation and same area
        sham_road  the road mask translated the same way
    Every edited surface gets high-pass texture copied from untouched terrain in the same scene, so an edit does
    not leave an unnaturally smooth patch (realistic background). Derivatives are recomputed from the edited
    DEM. Derivative layers are never altered directly.
    derivative_fn (config) names the exact stack builder. Empty uses FALLBACK channels in this file. They mimic
    the 7 band names of features_pit_9t_05.tif but are not the trained stack, and every row says so.
    scorer_fn (config) scores a stack with the P1 isolated pit checkpoint. Without it the run stops unless
    --edits-only, which writes the edit table with empty scores.
    No half-score rule. Q1 is a paired score and rank change of real edits minus sham edits (fw_5_1 section 7).

Inputs (config_5_1.json)
    inputs.dem          @nine_t/dem_9t_05.tif (data/9t/derived/05/dem_9t_05.tif)
    inputs.annotations  @truth/annotations_proj.gpkg layers pit_inside, plat, roads
    inputs.pit_blocks   @nine_t/pit_blocks_9t.gpkg
    inputs.features     @nine_t/features_pit_9t_05.tif (slope band, for control matching)
    inputs.isolated_pit_ckpt  ASSUMED (P1 S3), needed for scoring
Outputs
    outputs.reliance_csv   -> expansions/5_tasks/5_1_context_features/results/tables/context_reliance_paired_9t.csv
    outputs.reliance_edits -> expansions/5_tasks/5_1_context_features/data/interim/reliance_edits/<unit>.npz (--save-edits)
    <reliance_csv stem>_summary.json beside the CSV when scores exist (paired real-minus-sham, block bootstrap)
Run
    python expansions/5_tasks/5_1_context_features/src/_context_reliance_edits_9t.py --edits-only --n 20
    python expansions/5_tasks/5_1_context_features/src/_context_reliance_edits_9t.py      (needs scorer_fn and P1)
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek
FALLBACK_BANDS = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11"]


# ----------------------------------------------------------------------------- surface edits
def fit_plane(z: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Least-squares plane over masked finite cells. Returns the plane on the full grid."""
    rr, cc = np.indices(z.shape)
    m = mask & np.isfinite(z)
    if m.sum() < 3:
        return np.full(z.shape, np.nanmedian(z[m]) if m.any() else np.nan, np.float32)
    A = np.c_[rr[m], cc[m], np.ones(m.sum())]
    coef, *_ = np.linalg.lstsq(A, z[m], rcond=None)
    return (coef[0] * rr + coef[1] * cc + coef[2]).astype(np.float32)


def inpaint(z: np.ndarray, mask: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Linear interpolation across mask from ring cells, nearest where linear is undefined."""
    from scipy.interpolate import griddata
    src = ring & np.isfinite(z)
    out = z.copy()
    if not mask.any() or src.sum() < 3:
        return out
    pts = np.argwhere(src)
    tgt = np.argwhere(mask)
    v = griddata(pts, z[src], tgt, method="linear")
    bad = ~np.isfinite(v)
    if bad.any():
        v[bad] = griddata(pts, z[src], tgt[bad], method="nearest")
    out[mask] = v
    return out


def highpass(z: np.ndarray, sigma_px: float) -> np.ndarray:
    f = np.nan_to_num(z, nan=float(np.nanmean(z)))
    return (f - ndi.gaussian_filter(f, sigma_px)).astype(np.float32)


def add_texture(edited: np.ndarray, src: np.ndarray, mask: np.ndarray, donor_shift: tuple[int, int],
                sigma_px: float = 4.0) -> np.ndarray:
    """Copy high-pass texture from an untouched donor area (mask shifted by donor_shift) onto the edit."""
    hp = highpass(src, sigma_px)
    donor = np.roll(hp, donor_shift, axis=(0, 1))
    out = edited.copy()
    out[mask] = edited[mask] + donor[mask]
    return out


def flatten_pad(dem: np.ndarray, pad_mask: np.ndarray, keep: np.ndarray, res: float, ring_m: float = 5.0):
    region = pad_mask & ~keep
    ring = ndi.binary_dilation(pad_mask, iterations=max(1, int(round(ring_m / res)))) & ~pad_mask
    return np.where(region, fit_plane(dem, ring), dem).astype(np.float32), region


def remove_road(dem: np.ndarray, road_mask: np.ndarray, keep: np.ndarray, res: float, ring_m: float = 3.0):
    region = road_mask & ~keep
    ring = ndi.binary_dilation(road_mask, iterations=max(1, int(round(ring_m / res)))) & ~road_mask
    return inpaint(dem, region, ring).astype(np.float32), region


def shift_mask(mask: np.ndarray, dr: int, dc: int) -> np.ndarray:
    out = np.zeros_like(mask)
    h, w = mask.shape
    r0, r1 = max(0, dr), min(h, h + dr)
    c0, c1 = max(0, dc), min(w, w + dc)
    out[r0:r1, c0:c1] = mask[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
    return out


def find_sham(mask: np.ndarray, avoid: np.ndarray, rng, res: float, dmin_m: float, dmax_m: float,
              tries: int = 200, max_overlap: float = 0.10):
    """Translate mask to open terrain in the scene. Keeps the full area (no clipping) and avoids real features."""
    n = mask.sum()
    if n == 0:
        return None, None
    for _ in range(tries):
        a = rng.uniform(0, 2 * np.pi)
        d = rng.uniform(dmin_m, dmax_m) / res
        dr, dc = int(round(d * np.sin(a))), int(round(d * np.cos(a)))
        s = shift_mask(mask, dr, dc)
        if s.sum() != n:
            continue
        if (s & avoid).sum() <= max_overlap * n:
            return s, (dr, dc)
    return None, None


# ----------------------------------------------------------------------------- derivatives
def fallback_derivatives(dem: np.ndarray, res: float) -> np.ndarray:
    """FALLBACK stack with the 7 band names of features_pit_9t_05.tif. Approximations, not the trained stack."""
    z = np.nan_to_num(dem, nan=float(np.nanmean(dem)))
    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    lrm25 = z - ndi.uniform_filter(z, max(3, int(25 / res)))
    lrm5 = z - ndi.uniform_filter(z, max(3, int(5 / res)))
    tpi = z - ndi.uniform_filter(z, max(3, int(0.5 / res) * 2 + 1))
    rad = max(2, int(10 / res))
    ang_pos, ang_neg = [], []
    for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        sh = np.roll(z, (dr * rad, dc * rad), axis=(0, 1))
        dist = rad * res * np.hypot(dr, dc)
        ang = np.degrees(np.arctan((sh - z) / dist))
        ang_pos.append(90 - ang)
        ang_neg.append(90 + ang)
    rough = ndi.generic_filter(z, np.std, size=11) if z.size <= 300 * 300 else _fast_std(z, 11)
    return np.stack([lrm25, lrm5, slope, tpi, np.mean(ang_pos, 0), np.mean(ang_neg, 0), rough]).astype(np.float32)


def _fast_std(z, size):
    m = ndi.uniform_filter(z, size)
    m2 = ndi.uniform_filter(z * z, size)
    return np.sqrt(np.maximum(m2 - m * m, 0))


def load_callable(spec: str):
    if not spec:
        return None
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn)


# ----------------------------------------------------------------------------- one unit
def unit_variants(dem, transform, unit_xy, pad_geoms, road_geoms, avoid_geoms, cfg, rng):
    """All edited DEMs for one scene. Returns dict variant -> (edited dem, edit area m2, applicable)."""
    from rasterio.features import rasterize
    rel = cfg["reliance"]
    res = abs(transform.a)
    shape = dem.shape
    rr, cc = np.indices(shape)
    px = transform.c + (cc + 0.5) * transform.a
    py = transform.f + (rr + 0.5) * transform.e
    keep = np.hypot(px - unit_xy[0], py - unit_xy[1]) <= rel["pit_keep_radius_m"]

    def rast(geoms):
        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if not geoms:
            return np.zeros(shape, bool)
        return rasterize([(g, 1) for g in geoms], out_shape=shape, transform=transform, fill=0).astype(bool)
    pad_m = rast(pad_geoms)
    road_m = rast([g.buffer(rel["road_corridor_m"]) for g in road_geoms])
    avoid = rast(avoid_geoms) | pad_m | road_m | ndi.binary_dilation(keep, iterations=int(5 / res))
    out = {"orig": (dem, 0.0, True)}
    e_pad, reg_pad = flatten_pad(dem, pad_m, keep, res)
    e_road, reg_road = remove_road(dem, road_m, keep, res)
    donor = find_sham(reg_pad | reg_road, avoid, rng, res, rel["sham_min_offset_m"], rel["sham_max_offset_m"])[1] or (0, 0)
    tex = lambda e, m: add_texture(e, dem, m, donor) if m.any() else e  # noqa: E731
    out["pad"] = (tex(e_pad, reg_pad), reg_pad.sum() * res * res, bool(reg_pad.any()))
    out["road"] = (tex(e_road, reg_road), reg_road.sum() * res * res, bool(reg_road.any()))
    e_both, reg_b2 = remove_road(out["pad"][0], road_m, keep, res)
    out["both"] = (tex(e_both, reg_b2), (reg_pad | reg_b2).sum() * res * res, bool(reg_pad.any() or reg_b2.any()))
    for name, region, op in (("sham_pad", reg_pad, "pad"), ("sham_road", reg_road, "road")):
        s, _ = find_sham(region, avoid, rng, res, rel["sham_min_offset_m"], rel["sham_max_offset_m"])
        if s is None:
            out[name] = (dem, 0.0, False)
            continue
        if op == "pad":
            e = np.where(s, fit_plane(dem, ndi.binary_dilation(s, iterations=int(5 / res)) & ~s), dem).astype(np.float32)
        else:
            e = inpaint(dem, s, ndi.binary_dilation(s, iterations=int(3 / res)) & ~s)
        out[name] = (tex(e, s), s.sum() * res * res, True)
    return out


def scene_score(prob: np.ndarray, transform, unit_xy, cutoff: float, min_area: float, floor_geom=None):
    """Score at the unit (max prob on the floor, or a 3 m disc for controls) and its rank among scene blobs."""
    from rasterio.features import geometry_mask
    from shapely.geometry import Point
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _context_stage2_features_9t import extract_candidates
    g = floor_geom if floor_geom is not None else Point(unit_xy).buffer(3.0)
    m = ~geometry_mask([g], out_shape=prob.shape, transform=transform, all_touched=True)
    s = float(np.nanmax(prob[m])) if m.any() else np.nan
    c = extract_candidates(prob, transform, cutoff, min_area)
    hit = c[c.intersects(g)] if len(c) else c
    rank = int(hit.index.min()) + 1 if len(hit) else len(c) + 1
    return s, rank, len(c)


# ----------------------------------------------------------------------------- footprint
def footprint_cells(blocks) -> set:
    """Complete block footprint. Every block of the grid, not only blocks that hold drawn pits.
    Pits can only be sampled where pits exist, but controls drawn only from pit-bearing blocks would be selected on
    truth (review section 2 pattern 5)."""
    return set(zip(blocks.ix.astype(int), blocks.iy.astype(int)))


# ----------------------------------------------------------------------------- sampling
def sample_units(floors, footprint_cells, slope_at, n_pits, n_ctrl, rng, min_sep_m=30.0,
                 origin=(619500.0, 4593000.0), size=375.0):
    """Random pits (all floors in the footprint) and slope-tercile-matched control points."""
    from scipy.spatial import cKDTree
    cen = floors.geometry.centroid
    xy = np.c_[cen.x, cen.y]
    ok = th.in_cells(xy, footprint_cells, origin, size)
    idx = np.flatnonzero(ok)
    pick = rng.choice(idx, size=min(n_pits, len(idx)), replace=False)
    pits = pd.DataFrame({"unit_type": "pit", "x": xy[pick, 0], "y": xy[pick, 1], "floor_idx": pick})
    cells = sorted(footprint_cells)
    tree = cKDTree(xy)
    pool = []
    while len(pool) < 20 * max(n_ctrl, 1) and len(pool) < 20000:
        ci = cells[rng.integers(len(cells))]
        p = np.array(origin) + (np.array(ci) + rng.uniform(0, 1, 2)) * size
        if tree.query(p)[0] >= min_sep_m:
            pool.append(p)
    pool = np.array(pool)
    s_pool, s_pit = slope_at(pool), slope_at(pits[["x", "y"]].to_numpy())
    edges = np.nanpercentile(s_pit, [33.3, 66.7]) if len(s_pit) else [0, 0]
    bin_pool, bin_pit = np.digitize(s_pool, edges), np.digitize(s_pit, edges)
    ctrl, used = [], set()
    for b in bin_pit[:n_ctrl]:
        cand = [i for i in np.flatnonzero(bin_pool == b) if i not in used]
        if cand:
            i = int(rng.choice(cand))
            used.add(i)
            ctrl.append(pool[i])
    ctrl = pd.DataFrame({"unit_type": "control", "x": [c[0] for c in ctrl], "y": [c[1] for c in ctrl], "floor_idx": -1})
    u = pd.concat([pits, ctrl], ignore_index=True)
    u["unit_id"] = [f"{t[0]}{i:04d}" for i, t in enumerate(u.unit_type)]
    return u


def summarise(df: pd.DataFrame, B: int, seed: int) -> dict:
    """Q1 primary. Paired (orig - edited) score change for real edits minus the matched sham, median, block bootstrap."""
    out = {}
    piv = df.pivot_table(index=["unit_id", "unit_type", "block_id"], columns="variant", values="d_score").reset_index()
    for real, sham in (("pad", "sham_pad"), ("road", "sham_road"), ("both", "sham_pad")):
        if real not in piv or sham not in piv:
            continue
        for ut in ("pit", "control"):
            s = piv[(piv.unit_type == ut)].dropna(subset=[real, sham])
            if not len(s):
                continue
            s = s.assign(contrast=s[real] - s[sham])
            by = {b: g.contrast.to_numpy() for b, g in s.groupby("block_id")}
            fn = lambda bl: float(np.median(np.concatenate([by[b] for b in bl])))  # noqa: E731
            pt, lo, hi, _ = ek.block_bootstrap(fn, list(by), B=B, seed=seed)
            out[f"{real}_vs_{sham}_{ut}"] = dict(n_units=int(len(s)), n_blocks=len(by), median=pt, lo=lo, hi=hi)
    return out


def main(argv=None) -> int:
    import rasterio
    from affine import Affine
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _context_stage2_features_9t import read_padded
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--n", type=int, help="pits and controls each (default config reliance.n_pits)")
    ap.add_argument("--edits-only", action="store_true", help="no rescoring. Writes the edit table only")
    ap.add_argument("--save-edits", action="store_true", help="save edited DEM scenes as npz (large)")
    ap.add_argument("--B", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    rel, cand = cfg["reliance"], cfg["candidate"]
    seed = int(cfg["seed"])
    rng = np.random.default_rng(ek.child_seed(seed, 0, 21))
    deriv_fn = load_callable(rel["derivative_fn"]) or fallback_derivatives
    deriv_name = rel["derivative_fn"] or "FALLBACK (not the trained stack)"
    scorer = None
    if not a.edits_only:
        scorer = load_callable(rel["scorer_fn"])
        ck0 = th.resolve(cfg["inputs"]["isolated_pit_ckpt"]["path"].format(k=0))
        if scorer is None or not ck0.exists():
            raise th.MissingInput("isolated_pit_ckpt", ck0, cfg["inputs"]["isolated_pit_ckpt"]["hint"] +
                                  ". Also set reliance.scorer_fn. Or pass --edits-only")
        iso_doc = json.loads(th.inp(cfg, "isolated_pit_folds").read_text())
        iso_fold = {int(b): int(f) for b, f in iso_doc["block_to_fold"].items()}
    ann = th.inp(cfg, "annotations")
    floors = th.read_vector(ann, layer="pit_inside")
    pads = th.read_vector(ann, layer="plat")
    roads = th.read_vector(ann, layer="roads")
    blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    cells = footprint_cells(blocks)
    with rasterio.open(th.inp(cfg, "features")) as fs:
        band = list(fs.descriptions).index("slope") + 1

        def slope_at(xy):
            return np.array([v[0] for v in fs.sample([tuple(p) for p in xy], indexes=band)], float)
        n = a.n or int(rel["n_pits"])
        units = sample_units(floors, cells, slope_at, n, a.n or int(rel["n_controls"]), rng)
    units["block_id"] = th.block_id_of(units[["x", "y"]].to_numpy(), blocks)
    half = rel["window_m"] / 2 + 16.0     # 16 m margin so focal derivatives are defined at the scene edge
    rows = []
    save_dir = th.resolve(cfg["outputs"]["reliance_edits"])
    with rasterio.open(th.inp(cfg, "dem")) as ds:
        ek.assert_crs(ds)
        for u in units.itertuples(index=False):
            r0, c0 = ds.index(u.x - half, u.y + half)
            npx = int(round(2 * half / abs(ds.transform.a)))
            dem = read_padded(ds, 1, r0, c0, npx, npx, ds.nodata).astype(np.float32)
            dem[dem == ds.nodata] = np.nan
            tf = ds.transform * Affine.translation(c0, r0)
            from shapely.geometry import box, Point
            scene = box(u.x - half, u.y - half, u.x + half, u.y + half)
            near = Point(u.x, u.y).buffer(30.0)
            pg = [g for g in pads.geometry if g.intersects(near)]
            reach = Point(u.x, u.y).buffer(rel["road_search_m"])
            rg = [g.intersection(reach) for g in roads.geometry if g.intersects(reach)]
            avoid = [g for g in floors.geometry if g.intersects(scene)]
            var = unit_variants(dem, tf, (u.x, u.y), pg, rg, avoid, cfg, rng)
            fg = floors.geometry.iloc[u.floor_idx] if u.floor_idx >= 0 else None
            base = None
            if save_dir and a.save_edits:
                save_dir.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(save_dir / f"{u.unit_id}.npz", **{k: v[0] for k, v in var.items()})
            for vname, (e, area, ok) in var.items():
                r = dict(unit_id=u.unit_id, unit_type=u.unit_type, block_id=int(u.block_id), variant=vname,
                         applicable=ok, edit_area_m2=round(float(area), 2), derivatives=deriv_name,
                         score=np.nan, rank=np.nan, n_scene_blobs=np.nan)
                if scorer is not None and ok:
                    stack = deriv_fn(e, abs(tf.a))
                    fold = iso_fold[int(u.block_id)]
                    prob = scorer(stack, fold, th.resolve(cfg["inputs"]["isolated_pit_ckpt"]["path"].format(k=fold)))
                    r["score"], r["rank"], r["n_scene_blobs"] = scene_score(prob, tf, (u.x, u.y), cand["cutoff"],
                                                                            cand["min_area_m2"], fg)
                elif ok:
                    deriv_fn(e, abs(tf.a))   # still prove derivatives recompute from the edited surface
                rows.append(r)
                if vname == "orig":
                    base = r
            for r in rows[-len(var):]:
                r["d_score"] = base["score"] - r["score"] if base else np.nan
                r["d_rank"] = r["rank"] - base["rank"] if base else np.nan
    df = th.tag(pd.DataFrame(rows), "a")
    out = th.outp(cfg, "reliance_csv")
    df.to_csv(out, index=False)
    print(df.groupby(["unit_type", "variant"]).agg(n=("applicable", "size"), applicable=("applicable", "sum"),
                                                    area=("edit_area_m2", "median")).to_string())
    if scorer is not None:
        summ = summarise(df, a.B, seed)
        th.write_json(out.with_name(out.stem + "_summary.json"), summ)
    print(f"wrote {out}{'  (edits only, no scores)' if scorer is None else ''}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)

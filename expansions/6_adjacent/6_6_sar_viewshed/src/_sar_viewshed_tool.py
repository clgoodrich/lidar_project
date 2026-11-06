"""6.6 S1 and S3. Search and rescue line-of-sight, viewshed, cumulative viewshed, hidden pockets and travel time.

NOT A WELL RESULT. This tool adds no evidence about wells at any level. Do not cite it in a well report.

Purpose
    Plain numpy and rasterio, no GIS server. Coordinates are map metres in EPSG:6346.
    profile     Brute-force line of sight between two points. Samples the surface at half-cell steps with
                bilinear interpolation and compares it with the eye-to-target ray.
    viewshed    Radial sweep. Rays run from the observer to every cell on the perimeter of the radius square,
                sampled at half-cell steps, with a running maximum of obstacle slope. Each cell takes the value
                of the sample that lies closest to its centre. Checked against the brute-force profile.
    cumulative  Count of observers that see each cell (O0, O1), or probability that at least one sees it (O2).
    pockets     Connected hidden areas larger than a set area inside the radius.
    cost        Travel time from a start point on a resampled DEM. Tobler's hiking function (anisotropic, by
                direction of travel) times a land-cover multiplier, solved with Dijkstra on 8 neighbours.
    route       Least-time route between two points on the same graph.
    gridcheck   VERIFY step. DEM, DSM and CHM share one grid. CHM equals DSM minus DEM where valid. Void fraction.
    benchmark   S3. Wall time and peak memory for one viewshed.
    Opacity models. O0 terrain only (DEM). O1 opaque surface (DSM). O2 terrain from the DEM times canopy
    transmission T = exp(-k L), L the ray length through cells with CHM above 2 m (framework definition).
    Obstacles are samples at least one cell from the observer and at least one cell short of the target, so a
    target is never hidden by its own cell. Earth curvature and refraction (k = 0.13) are applied and logged.
    Cells with no DEM value, outside the raster or outside the radius are nodata. Void cells (no ground return,
    interpolated DEM) are masked and counted when a ground-density raster is given.
Inputs
    data/9t/derived/05/dem_9t_05.tif, dsm_9t_05.tif, chm_9t_05.tif, ground_density_9t_05.tif (held)
    data/9t/derived/landcover/nlcd_2019_landcover_9t.tif (held, optional, for cost)
Outputs
    data/9t/results/sar/<run_id>/sar_viewshed_<x>_<y>_<O>.tif (1 visible, 0 hidden, 255 nodata),
    sar_viewshed_<x>_<y>_frac.tif (O2, probability of visibility), sar_pockets_<x>_<y>_<O>.gpkg,
    sar_cost_<x>_<y>.tif (seconds), sar_route_<...>.gpkg, sar_viewshed_<x>_<y>_<O>.png, _summary.json, _PROVENANCE.json
Run
    python expansions/6_adjacent/6_6_sar_viewshed/src/_sar_viewshed_tool.py viewshed --observer 620000,4595000 --opacity O1 --radius 500
    python expansions/6_adjacent/6_6_sar_viewshed/src/_sar_viewshed_tool.py profile --observer X,Y --target X,Y --opacity O2 --season leaf_off
    python expansions/6_adjacent/6_6_sar_viewshed/src/_sar_viewshed_tool.py gridcheck
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

DEFAULT_CONFIG = HERE / "config_6_6.json"
NOT_WELL = "Not a well result. Search planning visibility only. Visibility is not detection probability."


# ----------------------------------------------------------------------------- config and grid
def load_config(path=None) -> dict:
    return json.loads(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))


def resolve(spec: dict) -> Path:
    if "path" in spec:
        return Path(spec["path"])
    if "key" in spec:
        return ek.path_for(spec["key"]) / spec["rel"]
    if "area" in spec:
        return ek.area_dir(spec["area"]) / spec["rel"]
    return ek.exp_dir(spec["exp"]) / spec["rel"]


def input_path(cfg, name, override=None, required=True):
    p = Path(override) if override else resolve(cfg["inputs"][name])
    if not p.exists():
        if required:
            raise FileNotFoundError(f"missing input '{name}' ({cfg['inputs'][name].get('state')}) at {p}. "
                                    f"Schema {cfg['inputs'][name].get('schema', 'raster on the DEM grid')}")
        return None
    return p


def horizontal_epsg(crs) -> int | None:
    from pyproj import CRS
    c = CRS.from_user_input(crs)
    return (c.sub_crs_list[0] if c.is_compound else c).to_epsg()


@dataclass
class Grid:
    dem: np.ndarray
    dsm: np.ndarray | None
    chm: np.ndarray | None
    void: np.ndarray | None
    transform: object
    crs: object
    cell: float

    def to_vu(self, x: float, y: float) -> tuple[float, float]:
        """Map metres to fractional (row, col) in cell-centre coordinates."""
        t = self.transform
        return (y - t.f) / t.e - 0.5, (x - t.c) / t.a - 0.5

    def to_xy(self, v, u):
        t = self.transform
        return t.c + (np.asarray(u) + 0.5) * t.a, t.f + (np.asarray(v) + 0.5) * t.e


def _read(path, window=None):
    import rasterio
    with rasterio.open(path) as r:
        a = r.read(1, window=window).astype(np.float32)
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
        tf = r.window_transform(window) if window is not None else r.transform
        return a, tf, r.crs, r.res


def load_grid(dem, dsm=None, chm=None, ground_density=None, bbox=None) -> Grid:
    """Read the rasters on one grid. bbox (x0, y0, x1, y1) reads a window. Asserts one transform, shape and CRS."""
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open(dem) as r:
        win = from_bounds(*bbox, transform=r.transform).round_offsets().round_lengths() if bbox else None
        ref_tf, ref_shape, ref_crs = r.transform, (r.height, r.width), r.crs
    if horizontal_epsg(ref_crs) != 6346:
        raise AssertionError(f"DEM CRS {ref_crs} is not EPSG:6346")
    a, tf, crs, res = _read(dem, win)
    if abs(res[0] - res[1]) > 1e-9:
        raise AssertionError("non-square cells")
    out = {}
    for nm, p in (("dsm", dsm), ("chm", chm), ("void", ground_density)):
        if p is None:
            out[nm] = None
            continue
        with rasterio.open(p) as r:
            if r.transform != ref_tf or (r.height, r.width) != ref_shape:
                raise AssertionError(f"{nm} grid differs from the DEM grid")
            if horizontal_epsg(r.crs) != horizontal_epsg(ref_crs):
                raise AssertionError(f"{nm} CRS {r.crs} differs from the DEM")
        if nm == "void":
            import rasterio as rio
            with rio.open(p) as r:
                g = r.read(1, window=win)
            out[nm] = g == 0
        else:
            out[nm] = _read(p, win)[0]
    return Grid(a, out["dsm"], out["chm"], out["void"], tf, crs, float(res[0]))


# ----------------------------------------------------------------------------- sampling
def bilinear(arr: np.ndarray, v: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Bilinear sample at fractional cell-centre coordinates. NaN outside the raster or next to NaN."""
    v = np.asarray(v, float)
    u = np.asarray(u, float)
    H, W = arr.shape
    v0 = np.floor(v).astype(int)
    u0 = np.floor(u).astype(int)
    fv, fu = v - v0, u - u0
    ok = (v0 >= 0) & (u0 >= 0) & (v0 < H) & (u0 < W)
    v1 = np.clip(v0 + 1, 0, H - 1)
    u1 = np.clip(u0 + 1, 0, W - 1)
    v0c, u0c = np.clip(v0, 0, H - 1), np.clip(u0, 0, W - 1)
    z = (arr[v0c, u0c] * (1 - fv) * (1 - fu) + arr[v1, u0c] * fv * (1 - fu)
         + arr[v0c, u1] * (1 - fv) * fu + arr[v1, u1] * fv * fu)
    # exact cell centres on the last row or column are inside
    edge = (v <= H - 1) & (u <= W - 1) & (v >= 0) & (u >= 0)
    return np.where(ok & edge, z, np.nan)


def nearest(arr: np.ndarray, v, u):
    vi, ui = np.rint(v).astype(int), np.rint(u).astype(int)
    H, W = arr.shape
    ok = (vi >= 0) & (ui >= 0) & (vi < H) & (ui < W)
    out = np.zeros(np.shape(v), dtype=arr.dtype)
    out[ok] = arr[vi[ok], ui[ok]]
    return out, ok


def curvature_drop(d_m, vp: dict):
    if not vp.get("curvature", True):
        return np.zeros_like(np.asarray(d_m, float))
    return (1.0 - vp["refraction_k"]) * np.asarray(d_m, float) ** 2 / (2.0 * vp["earth_radius_m"])


def _surface(g: Grid, opacity: str):
    if opacity == "O1":
        if g.dsm is None:
            raise ValueError("O1 needs --dsm")
        return g.dsm
    return g.dem


# ----------------------------------------------------------------------------- brute force
def los_profile(g: Grid, obs_xy, tgt_xy, opacity="O0", eye_h=1.7, tgt_h=0.0, k_ext=0.0, vp=None) -> dict:
    """Brute-force line of sight. Returns visible (bool or None for nodata), transmission and the profile."""
    vp = vp or load_config()["viewshed"]
    ov, ou = g.to_vu(*obs_xy)
    tv, tu = g.to_vu(*tgt_xy)
    D = float(np.hypot(tv - ov, tu - ou) * g.cell)
    z0 = float(bilinear(g.dem, ov, ou)) + eye_h
    zt_g = float(bilinear(g.dem, tv, tu))
    if not np.isfinite(z0) or not np.isfinite(zt_g) or D == 0:
        return {"visible": None, "transmission": None, "distance_m": D}
    step = g.cell / 2
    n = max(int(np.ceil(D / step - 1e-9)), 1)
    t = np.arange(1, n) / n
    d = t * D
    sv, su = ov + t * (tv - ov), ou + t * (tu - ou)
    zs = bilinear(_surface(g, opacity), sv, su) - curvature_drop(d, vp)
    zt = zt_g + tgt_h - float(curvature_drop(D, vp))
    obst = (d >= g.cell - 1e-9) & (d <= D - g.cell + 1e-9) & np.isfinite(zs)
    tgt_slope = (zt - z0) / D
    max_slope = float(np.max((zs[obst] - z0) / d[obst])) if obst.any() else -np.inf
    vis = bool(tgt_slope >= max_slope)
    T = 1.0
    if opacity == "O2":
        if g.chm is None:
            raise ValueError("O2 needs --chm")
        ch = bilinear(g.chm, sv, su)
        L = float(np.sum(np.nan_to_num(ch, nan=0.0) > vp["canopy_height_m"]) * (D / n))
        T = float(np.exp(-k_ext * L))
    return {"visible": vis, "transmission": T, "p_visible": float(vis) * T, "distance_m": D,
            "target_slope": tgt_slope, "max_obstacle_slope": max_slope}


# ----------------------------------------------------------------------------- radial sweep
def perimeter(R: int) -> np.ndarray:
    top = [(-R, c) for c in range(-R, R + 1)]
    bot = [(R, c) for c in range(-R, R + 1)]
    lef = [(r, -R) for r in range(-R + 1, R)]
    rig = [(r, R) for r in range(-R + 1, R)]
    return np.array(top + bot + lef + rig, float)


def viewshed(g: Grid, obs_xy, radius_m: float, opacity="O0", eye_h=1.7, tgt_h=0.0, k_ext=0.0, vp=None) -> dict:
    """Radial sweep viewshed. Returns vis (uint8 1/0/255), frac (float32, O2 only), counts."""
    vp = vp or load_config()["viewshed"]
    H, W = g.dem.shape
    ov, ou = g.to_vu(*obs_xy)
    if not (0 <= ov <= H - 1 and 0 <= ou <= W - 1):
        raise ValueError(f"observer {obs_xy} is outside the raster. Out of range is an error, not a clip.")
    z0 = float(bilinear(g.dem, ov, ou)) + eye_h
    if not np.isfinite(z0):
        raise ValueError("observer cell has no DEM value")
    R = int(np.ceil(radius_m / g.cell))
    surf = g.dem if opacity == "O2" else _surface(g, opacity)
    best_off = np.full((H, W), np.inf, np.float32)
    vis = np.full((H, W), 255, np.uint8)
    frac = np.full((H, W), np.nan, np.float32) if opacity == "O2" else None
    if opacity == "O2" and g.chm is None:
        raise ValueError("O2 needs a CHM")
    per = perimeter(R)
    chunk = int(vp.get("ray_chunk", 256))
    for c0 in range(0, len(per), chunk):
        p = per[c0:c0 + chunk]
        Lr = np.hypot(p[:, 0], p[:, 1])
        ns = int(np.floor(Lr.max() / 0.5))
        j = np.arange(1, ns + 1)
        dirv, diru = p[:, 0:1] / Lr[:, None], p[:, 1:2] / Lr[:, None]
        sv, su = ov + dirv * j * 0.5, ou + diru * j * 0.5
        d = j[None, :] * 0.5 * g.cell * np.ones((len(p), 1))
        valid = (j[None, :] * 0.5 <= Lr[:, None] + 1e-9) & (d <= radius_m + 1e-9)
        drop = curvature_drop(d, vp)
        zs = bilinear(surf, sv, su) - drop
        zg = bilinear(g.dem, sv, su) + tgt_h - drop
        s_obs = np.where((d >= g.cell - 1e-9) & np.isfinite(zs), (zs - z0) / d, -np.inf)
        run = np.maximum.accumulate(s_obs, axis=1)
        prior = np.full_like(run, -np.inf)
        prior[:, 2:] = run[:, :-2]                  # obstacles at least one cell (two samples) before the target
        v_ok = (zg - z0) / d >= prior
        if opacity == "O2":
            ch = np.nan_to_num(bilinear(g.chm, sv, su), nan=0.0) > vp["canopy_height_m"]
            cnt = np.zeros_like(d)
            cnt[:, 1:] = np.cumsum(ch, axis=1)[:, :-1]
            T = np.exp(-k_ext * cnt * 0.5 * g.cell)
        vi, ui = np.rint(sv).astype(int), np.rint(su).astype(int)
        inr = valid & (vi >= 0) & (ui >= 0) & (vi < H) & (ui < W) & np.isfinite(zg)
        off = np.hypot(sv - vi, su - ui)
        flat = np.flatnonzero(inr)
        cell_idx = vi.ravel()[flat] * W + ui.ravel()[flat]
        o = off.ravel()[flat]
        order = np.lexsort((o, cell_idx))
        cell_idx, o, flat = cell_idx[order], o[order], flat[order]
        first = np.r_[True, cell_idx[1:] != cell_idx[:-1]]
        ci, oo, fi = cell_idx[first], o[first], flat[first]
        bo = best_off.ravel()
        upd = oo < bo[ci]
        ci, oo, fi = ci[upd], oo[upd], fi[upd]
        bo[ci] = oo
        vis.ravel()[ci] = v_ok.ravel()[fi].astype(np.uint8)
        if frac is not None:
            frac.ravel()[ci] = (v_ok.ravel()[fi] * T.ravel()[fi]).astype(np.float32)
    # observer cell and the cells inside one cell of it are visible by definition
    rr, cc = np.ogrid[:H, :W]
    dist = np.hypot(rr - ov, cc - ou) * g.cell
    near = (dist < g.cell) & np.isfinite(g.dem)
    vis[near] = 1
    if frac is not None:
        frac[near] = 1.0
    outside = (dist > radius_m) | ~np.isfinite(g.dem)
    vis[outside] = 255
    n_void = 0
    if g.void is not None and vp.get("mask_voids", True):
        m = g.void & ~outside
        n_void = int(m.sum())
        vis[m] = 255
        if frac is not None:
            frac[m] = np.nan
    if frac is not None:
        frac[outside] = np.nan
        if opacity == "O2":
            vis = np.where(vis == 255, 255, (np.nan_to_num(frac) >= vp["o2_visible_threshold"]).astype(np.uint8))
    inside = vis != 255
    return {"vis": vis.astype(np.uint8), "frac": frac, "n_cells": int(inside.sum()),
            "n_visible": int((vis == 1).sum()), "visible_fraction": float((vis == 1).sum() / max(inside.sum(), 1)),
            "n_void_masked": n_void, "opacity": opacity, "eye_h": eye_h, "tgt_h": tgt_h, "k_ext": k_ext,
            "radius_m": radius_m, "curvature": bool(vp.get("curvature", True)), "refraction_k": vp["refraction_k"]}


def cumulative(g: Grid, observers, radius_m, opacity="O0", **kw) -> np.ndarray:
    """O0/O1: number of observers that see each cell. O2: 1 - prod(1 - p)."""
    acc = None
    for xy in observers:
        r = viewshed(g, xy, radius_m, opacity, **kw)
        if opacity == "O2":
            p = np.nan_to_num(r["frac"])
            acc = p if acc is None else 1 - (1 - acc) * (1 - p)
        else:
            v = (r["vis"] == 1).astype(np.int32)
            acc = v if acc is None else acc + v
    return acc


def hidden_pockets(vis: np.ndarray, cell: float, min_area_m2: float):
    """Label 8-connected hidden areas inside the radius. Returns (labels, list of (id, area_m2))."""
    from scipy import ndimage as ndi
    lab, n = ndi.label(vis == 0, structure=np.ones((3, 3)))
    if n == 0:
        return lab, []
    areas = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) * cell * cell
    keep = [(i + 1, float(a)) for i, a in enumerate(areas) if a >= min_area_m2]
    ids = {k for k, _ in keep}
    lab = np.where(np.isin(lab, list(ids)), lab, 0)
    return lab, keep


# ----------------------------------------------------------------------------- travel time
def tobler_speed_ms(S, cp: dict):
    return cp["tobler_a"] * np.exp(-cp["tobler_b"] * np.abs(S + cp["tobler_c"])) / 3.6


def landcover_multiplier(lc: np.ndarray | None, shape, cp: dict) -> np.ndarray:
    if lc is None:
        return np.ones(shape, np.float32)
    table = cp["landcover_multiplier"]
    out = np.full(shape, float(table["default"]), np.float32)
    for k, v in table.items():
        if k.startswith("_") or k == "default":
            continue
        out[lc == int(k)] = np.inf if v is None else float(v)
    return out


def cost_graph(dem: np.ndarray, cell: float, mult: np.ndarray, cp: dict):
    """Directed 8-neighbour graph. Edge time = distance / Tobler speed(slope in travel direction) * mean multiplier."""
    from scipy.sparse import coo_matrix
    H, W = dem.shape
    idx = np.arange(H * W).reshape(H, W)
    rows, cols, data = [], [], []
    for dv, du in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
        a = (slice(max(0, -dv), H - max(0, dv)), slice(max(0, -du), W - max(0, du)))     # from cells
        b = (slice(a[0].start + dv, a[0].stop + dv), slice(a[1].start + du, a[1].stop + du))  # to cells
        dist = cell * np.hypot(dv, du)
        S = (dem[b] - dem[a]) / dist
        t = dist / tobler_speed_ms(S, cp) * 0.5 * (mult[a] + mult[b])
        ok = np.isfinite(t)
        rows.append(idx[a][ok])
        cols.append(idx[b][ok])
        data.append(t[ok])
    r, c, d = np.concatenate(rows), np.concatenate(cols), np.concatenate(data)
    return coo_matrix((d, (r, c)), shape=(H * W, H * W)).tocsr()


def travel_time(dem, cell, start_vu, mult, cp, target_vu=None):
    from scipy.sparse.csgraph import dijkstra
    H, W = dem.shape
    G = cost_graph(dem, cell, mult, cp)
    s = int(round(start_vu[0])) * W + int(round(start_vu[1]))
    dist, pred = dijkstra(G, directed=True, indices=s, return_predecessors=True)
    tt = dist.reshape(H, W).astype(np.float32)
    route = None
    if target_vu is not None:
        t = int(round(target_vu[0])) * W + int(round(target_vu[1]))
        if np.isfinite(dist[t]):
            path = [t]
            while path[-1] != s:
                path.append(pred[path[-1]])
            route = [(p // W, p % W) for p in path[::-1]]
    return tt, route


def resample_dem(g: Grid, target_m: float):
    """Block-mean resample for the cost graph. Returns (dem, cell, factor)."""
    f = max(1, int(round(target_m / g.cell)))
    H, W = (g.dem.shape[0] // f) * f, (g.dem.shape[1] // f) * f
    a = g.dem[:H, :W].reshape(H // f, f, W // f, f)
    with np.errstate(invalid="ignore"):
        return np.nanmean(a, axis=(1, 3)), g.cell * f, f


# ----------------------------------------------------------------------------- checks and outputs
def grid_check(dem, dsm, chm, gd=None, n_windows=10, win=256, seed=0) -> dict:
    """VERIFY rows of section 5. Windowed so it is cheap on the full 9t rasters."""
    import rasterio
    from rasterio.windows import Window
    res = {}
    with rasterio.open(dem) as a, rasterio.open(dsm) as b, rasterio.open(chm) as c:
        res["same_transform"] = a.transform == b.transform == c.transform
        res["same_shape"] = a.shape == b.shape == c.shape
        res["crs"] = {"dem": str(horizontal_epsg(a.crs)), "dsm": str(horizontal_epsg(b.crs)), "chm": str(horizontal_epsg(c.crs)),
                      "dsm_is_compound": bool(__import__("pyproj").CRS.from_user_input(b.crs).is_compound)}
        rng = np.random.default_rng(seed)
        errs, vf = [], []
        for _ in range(n_windows):
            r0, c0 = int(rng.integers(0, a.height - win)), int(rng.integers(0, a.width - win))
            w = Window(c0, r0, win, win)
            z = [x.read(1, window=w).astype(np.float64) for x in (a, b, c)]
            for arr, src in zip(z, (a, b, c)):
                if src.nodata is not None:
                    arr[arr == src.nodata] = np.nan
            d = (z[1] - z[0]) - z[2]
            ok = np.isfinite(d)
            errs.append(np.abs(d[ok]))
            if gd is not None:
                with rasterio.open(gd) as g:
                    vf.append(float((g.read(1, window=w) == 0).mean()))
        e = np.concatenate(errs) if errs else np.array([])
        res["chm_minus_dsm_dem_abs_p50"] = float(np.percentile(e, 50)) if e.size else None
        res["chm_minus_dsm_dem_abs_p99"] = float(np.percentile(e, 99)) if e.size else None
        res["chm_equals_dsm_minus_dem_share"] = float((e < 0.01).mean()) if e.size else None
        if vf:
            res["void_fraction_sampled"] = float(np.mean(vf))
    res["verdict"] = "pass" if res["same_transform"] and res["same_shape"] and len(set(
        [res["crs"]["dem"], res["crs"]["dsm"], res["crs"]["chm"]])) == 1 else "fail"
    return res


def write_raster(path: Path, arr, g: Grid, nodata):
    import rasterio
    prof = dict(driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=str(arr.dtype),
                crs=g.crs, transform=g.transform, nodata=nodata, compress="deflate", tiled=True,
                blockxsize=256, blockysize=256)
    with rasterio.open(path, "w", **prof) as w:
        w.write(np.where(np.isnan(arr), nodata, arr).astype(arr.dtype) if arr.dtype.kind == "f" else arr, 1)
    return path


def render(vis: np.ndarray, g: Grid, obs_xy, png: Path, title: str):
    """Visible blue, hidden orange, masked grey (ek.PALETTE; lost/found palette worst pair dE 21.1 deutan,
    dataviz validator --pairs all per CLAUDE.md). Hidden cells also carry hatching so colour is not the only cue."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    show = np.where(vis == 255, 2, vis).astype(float)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(show, cmap=ListedColormap([ek.PALETTE["orange"], ek.PALETTE["blue"], ek.PALETTE["grey"]]),
              vmin=0, vmax=2, interpolation="nearest")
    ax.contourf((vis == 0).astype(float), levels=[0.5, 1.5], hatches=["...."], colors="none")
    ov, ou = g.to_vu(*obs_xy)
    ax.plot(ou, ov, marker="*", color=ek.PALETTE["charcoal"], markersize=14)
    ax.legend(handles=[Patch(color=ek.PALETTE["blue"], label="visible"),
                       Patch(facecolor=ek.PALETTE["orange"], hatch="....", label="hidden"),
                       Patch(color=ek.PALETTE["grey"], label="masked or outside")], loc="lower right", fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.set_axis_off()
    fig.text(0.01, 0.01, NOT_WELL, fontsize=7)
    fig.savefig(png, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return png


def _xy(s: str) -> tuple[float, float]:
    x, y = (float(v) for v in s.split(","))
    return x, y


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ + "\n" + NOT_WELL, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["viewshed", "profile", "cumulative", "pockets", "cost", "route", "gridcheck", "benchmark"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--dem", default=None)
    ap.add_argument("--surface", "--dsm", dest="dsm", default=None)
    ap.add_argument("--chm", default=None)
    ap.add_argument("--ground-density", default=None)
    ap.add_argument("--landcover", default=None)
    ap.add_argument("--observer", type=str, help="x,y in EPSG:6346 metres")
    ap.add_argument("--observers", type=str, help="semicolon list x,y;x,y (cumulative)")
    ap.add_argument("--target", type=str, help="x,y (profile, route)")
    ap.add_argument("--eye-height", type=float, default=None)
    ap.add_argument("--target-height", type=float, default=None)
    ap.add_argument("--radius", type=float, default=None)
    ap.add_argument("--opacity", choices=["O0", "O1", "O2"], default="O0")
    ap.add_argument("--k", type=float, default=None, help="extinction per metre (O2). Default from --season")
    ap.add_argument("--season", choices=["leaf_on", "leaf_off"], default="leaf_on")
    ap.add_argument("--no-curvature", action="store_true")
    ap.add_argument("--out", default=None, help="run folder (default data/9t/results/sar/<run_id>/)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    vp = dict(cfg["viewshed"])
    if a.no_curvature:
        vp["curvature"] = False
    eye = a.eye_height if a.eye_height is not None else vp["eye_height_m"]
    th = a.target_height if a.target_height is not None else vp["target_height_m"]
    rad = a.radius if a.radius is not None else vp["radius_m"]
    k = a.k if a.k is not None else vp["k_extinction"][a.season]
    dem = input_path(cfg, "dem", a.dem)
    dsm = input_path(cfg, "dsm", a.dsm, required=a.opacity == "O1" or a.command == "gridcheck")
    chm = input_path(cfg, "chm", a.chm, required=a.opacity == "O2" or a.command == "gridcheck")
    gd = input_path(cfg, "ground_density", a.ground_density, required=False)
    if a.command == "gridcheck":
        r = grid_check(dem, dsm, chm, gd)
        out = ek.sub("6.6", "results/tables") / "sar_grid_check_9t.json"
        out.write_text(json.dumps(r, indent=2), encoding="utf-8")
        print(json.dumps(r, indent=2))
        print(f"wrote {out}")
        return 0
    pts = [_xy(s) for s in a.observers.split(";")] if a.observers else [_xy(a.observer)]
    reach = rad
    if a.target:
        tx, ty = _xy(a.target)
        reach = max(rad, max(np.hypot(tx - x, ty - y) for x, y in pts) + 10)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    bbox = (min(xs) - reach, min(ys) - reach, max(xs) + reach, max(ys) + reach)
    g = load_grid(dem, dsm if a.opacity == "O1" else None, chm if a.opacity == "O2" else None, gd, bbox=bbox)
    params = {"command": a.command, "observers": pts, "opacity": a.opacity, "eye_h": eye, "tgt_h": th, "radius_m": rad,
              "k": k, "season": a.season, "viewshed": vp, "not_a_well_result": True}
    run = Path(a.out) if a.out else ek.new_run("6.6", f"sar{a.command}", params,
                                               base=resolve(cfg["outputs"]["results"]), why=NOT_WELL)
    run.mkdir(parents=True, exist_ok=True)
    outs = []
    tag = f"{int(pts[0][0])}_{int(pts[0][1])}"
    t0 = time.time()
    if a.command == "profile":
        r = los_profile(g, pts[0], _xy(a.target), a.opacity, eye, th, k, vp)
        print(json.dumps(r, indent=2))
        summ = r
    elif a.command in ("viewshed", "pockets", "benchmark"):
        import tracemalloc
        tracemalloc.start()
        r = viewshed(g, pts[0], rad, a.opacity, eye, th, k, vp)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        summ = {k_: v for k_, v in r.items() if k_ not in ("vis", "frac")} | {
            "wall_s": time.time() - t0, "peak_mb": peak / 1e6}
        if a.command != "benchmark":
            outs.append(write_raster(run / f"sar_viewshed_{tag}_{a.opacity}.tif", r["vis"], g, 255))
            if r["frac"] is not None:
                outs.append(write_raster(run / f"sar_viewshed_{tag}_frac.tif", r["frac"], g, -9999.0))
            outs.append(render(r["vis"], g, pts[0], run / f"sar_viewshed_{tag}_{a.opacity}.png",
                               f"{a.opacity} eye {eye} m radius {rad:.0f} m"))
            lab, keep = hidden_pockets(r["vis"], g.cell, vp["pocket_min_area_m2"])
            summ["n_pockets"] = len(keep)
            if keep:
                import geopandas as gpd
                from rasterio.features import shapes
                from shapely.geometry import shape
                geoms = [(shape(s), int(v)) for s, v in shapes(lab.astype(np.int32), mask=lab > 0, transform=g.transform)]
                area = dict(keep)
                gdf = gpd.GeoDataFrame({"pocket_id": [v for _, v in geoms], "area_m2": [area[v] for _, v in geoms]},
                                       geometry=[s for s, _ in geoms], crs=g.crs).dissolve(by="pocket_id").reset_index()
                p = run / f"sar_pockets_{tag}_{a.opacity}.gpkg"
                gdf.to_file(p, driver="GPKG")
                outs.append(p)
    elif a.command == "cumulative":
        acc = cumulative(g, pts, rad, a.opacity, eye_h=eye, tgt_h=th, k_ext=k, vp=vp)
        outs.append(write_raster(run / f"sar_cumulative_{tag}_{a.opacity}.tif", acc.astype(np.float32), g, -9999.0))
        summ = {"n_observers": len(pts), "max": float(np.nanmax(acc))}
    else:   # cost, route
        lc = None
        lcp = input_path(cfg, "landcover", a.landcover, required=False)
        dem_c, cell_c, f = resample_dem(g, cfg["cost"]["resample_m"])
        if lcp is not None:
            import rasterio
            from rasterio.warp import Resampling, reproject
            lc = np.zeros(dem_c.shape, np.int32)
            with rasterio.open(lcp) as src:
                reproject(rasterio.band(src, 1), lc, dst_transform=g.transform * g.transform.scale(f), dst_crs=g.crs,
                          resampling=Resampling.mode)
        mult = landcover_multiplier(lc, dem_c.shape, cfg["cost"])
        sv, su = g.to_vu(*pts[0])
        tgt = None
        if a.command == "route":
            tv, tu = g.to_vu(*_xy(a.target))
            tgt = (tv / f, tu / f)
        tt, route = travel_time(dem_c, cell_c, (sv / f, su / f), mult, cfg["cost"], tgt)
        cg = Grid(dem_c, None, None, None, g.transform * g.transform.scale(f), g.crs, cell_c)
        outs.append(write_raster(run / f"sar_cost_{tag}.tif", np.where(np.isfinite(tt), tt, np.nan).astype(np.float32), cg, -9999.0))
        summ = {"cell_m": cell_c, "landcover": str(lcp) if lcp else "none (multiplier 1)"}
        if route:
            import geopandas as gpd
            from shapely.geometry import LineString
            xy_ = [cg.to_xy(v, u) for v, u in route]
            p = run / f"sar_route_{tag}.gpkg"
            gpd.GeoDataFrame({"time_s": [float(tt[route[-1]])]}, geometry=[LineString(xy_)], crs=g.crs).to_file(p)
            outs.append(p)
            summ["route_time_s"] = float(tt[route[-1]])
    summ["not_a_well_result"] = NOT_WELL
    js = run / "_summary.json"
    js.write_text(json.dumps(summ, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(run, inputs=[p for p in (dem, dsm, chm, gd) if p], outputs=outs + [js], params=params)
    print(json.dumps(summ, indent=2, default=str))
    print("\n".join(f"wrote {p}" for p in outs + [js]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

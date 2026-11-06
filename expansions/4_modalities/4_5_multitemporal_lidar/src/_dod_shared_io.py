"""Shared helpers for the 4.5 multitemporal lidar scripts.

Purpose  Config loading, path specs, missing-input errors, run lookup, raster and layer readers with CRS checks,
         and the feature flag rule of the existing change work so every 4.5 stage scores change the same way.
Inputs   expansions/4_modalities/4_5_multitemporal_lidar/src/config_4_5.json
Outputs  none (library)
Run      imported by the _dod_*_9t.py scripts in this folder

A path spec is {"key": "<config/paths.toml key>", "rel": "..."} or {"exp": "4.5", "rel": "..."}.
The flag rule reuses the constants of notebooks/wellsight_v2/s7_analysis/_change_features_9t.py (imported, not copied).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

S7 = ek.REPO / "notebooks" / "wellsight_v2" / "s7_analysis"
sys.path.insert(0, str(S7))

EXP = "4.5"
HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config_4_5.json"


def load_config(path: Path | None = None) -> dict:
    return json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))


def resolve(spec) -> Path | None:
    if spec is None:
        return None
    if isinstance(spec, (str, Path)):
        return Path(spec)
    if "key" in spec:
        return ek.path_for(spec["key"]) / spec.get("rel", "")
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / spec.get("rel", "")
    raise ValueError(f"bad path spec {spec!r}")


def need(path, what: str, schema: str = "") -> Path:
    if path is None or not Path(path).exists():
        raise FileNotFoundError(f"MISSING INPUT {what}: {path}. Assumed schema: {schema or 'see config'}. "
                                f"Edit {CONFIG_PATH.name} or pass the path on the command line.")
    return Path(path)


def latest_run(short: str, base: Path | None = None) -> Path | None:
    root = Path(base) if base is not None else ek.exp_dir(EXP) / "results"
    if not root.exists():
        return None
    hits = sorted((d for d in root.iterdir() if d.is_dir() and d.name[9:].startswith(short + "_")),
                  key=lambda d: d.stat().st_mtime)
    return hits[-1] if hits else None


def stage_file(arg, short: str, name: str, base: Path | None, what: str) -> Path:
    """An upstream product: the CLI path if given, else <newest run of short>/name."""
    if arg is not None:
        return need(arg, what)
    d = latest_run(short, base)
    return need(None if d is None else d / name, what, f"run the stage that writes {name} first")


def read_raster(path: Path, crs: str):
    """(array float64 with NaN, transform, profile). Asserts CRS."""
    import rasterio
    with rasterio.open(need(path, "raster")) as s:
        ek.assert_crs(s, crs)
        a = s.read(1).astype(float)
        if s.nodata is not None and np.isfinite(s.nodata):
            a[a == s.nodata] = np.nan
        return a, s.transform, s.profile


def read_layer(path: Path, layer: str | None, crs: str):
    import geopandas as gpd
    g = gpd.read_file(need(path, f"layer {layer}"), layer=layer)
    ek.assert_crs(g, crs)
    return g


def slope_deg(dem: np.ndarray, res: float) -> np.ndarray:
    z = np.where(np.isfinite(dem), dem, np.nanmean(dem))
    gy, gx = np.gradient(z, res)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def flag_params(cfg: dict) -> dict:
    """Constants of the published flag rule, imported from _change_features_9t.py."""
    import _change_features_9t as CF
    return {"thr": CF.THR, "min_cover": CF.MIN_COVER, "p_cut": CF.P_CUT, "n_ctrl": CF.N_CTRL,
            "slope_tol": CF.SLOPE_TOL, "ctrl_dist_m": tuple(cfg["flag_rule"]["ctrl_dist_m"]),
            "min_ctrl": int(cfg["flag_rule"]["min_ctrl"])}


class Field:
    """A change field on a north-up grid with the flag rule of _change_features_9t.py.

    stats(geom)  cells in the outline beyond +-thr (fill, cut), median dz, mean slope
    flag(geom)   CHANGED if the changed share beats the p_cut quantile of slope-matched moved copies
                 150 to 800 m away (clear of every mapped feature) and covers at least min_cover.
    """

    def __init__(self, f, transform, slope, excl, params, rng):
        self.f, self.T, self.slope, self.excl, self.p, self.rng = f, transform, slope, excl, params, rng
        self.res = float(transform.a)
        self.x0, self.y1 = float(transform.c), float(transform.f)
        self.H, self.W = f.shape

    def stats(self, geom, clear=False):
        from rasterio.features import geometry_mask
        from rasterio.transform import from_origin
        x0, y0, x1, y1 = geom.bounds
        r = self.res
        if x0 < self.x0 or x1 > self.x0 + self.W * r or y1 > self.y1 or y0 < self.y1 - self.H * r:
            return None
        c0, r0 = int((x0 - self.x0) // r), int((self.y1 - y1) // r)
        c1, r1 = int(np.ceil((x1 - self.x0) / r)), int(np.ceil((self.y1 - y0) / r))
        sub = self.f[r0:r1, c0:c1]
        if sub.size == 0:
            return None
        tr = from_origin(self.x0 + c0 * r, self.y1 - r0 * r, r, r)
        m = ~geometry_mask([geom], out_shape=sub.shape, transform=tr, all_touched=False)
        if clear and self.excl is not None and (m & self.excl[r0:r1, c0:c1]).any():
            return None
        m &= np.isfinite(sub)
        if m.sum() < 8:
            return None
        v, thr = sub[m], self.p["thr"]
        return dict(n=int(m.sum()), med=float(np.median(v)), mean=float(np.mean(v)), cut=float((v < -thr).mean()),
                    fill=float((v > thr).mean()), slope=float(self.slope[r0:r1, c0:c1][m].mean()))

    def flag(self, geom):
        from shapely import affinity
        s0 = self.stats(geom)
        if s0 is None:
            return None
        lo, hi = self.p["ctrl_dist_m"]
        out, tries = [], 0
        while len(out) < self.p["n_ctrl"] and tries < 600:
            tries += 1
            a, d = self.rng.uniform(0, 2 * np.pi), self.rng.uniform(lo, hi)
            c = self.stats(affinity.translate(geom, d * np.cos(a), d * np.sin(a)), clear=True)
            if c and abs(c["slope"] - s0["slope"]) <= self.p["slope_tol"]:
                out.append(c["cut"] + c["fill"])
        if len(out) < self.p["min_ctrl"]:
            return None
        ct, tot = np.array(out), s0["cut"] + s0["fill"]
        q = float(np.quantile(ct, self.p["p_cut"]))
        return {**s0, "frac_changed": tot, "ctrl_q": q, "n_ctrl": len(ct),
                "changed": bool(tot > q and tot >= self.p["min_cover"])}


def feature_mask(layers, shape, transform, dilate_cells: int):
    """Boolean mask of every mapped feature, dilated (the clear zone for moved copies and stable ground)."""
    from rasterio.features import rasterize
    from scipy import ndimage as ndi
    geoms = [g for L in layers if L is not None for g in L.geometry if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros(shape, bool)
    m = rasterize(geoms, out_shape=shape, transform=transform, fill=0, default_value=1, all_touched=True).astype(bool)
    return ndi.binary_dilation(m, iterations=max(int(dilate_cells), 0)) if dilate_cells else m


def seam_distance(field, res: float) -> np.ndarray:
    """Distance in metres from every cell to the nearest straight survey seam (_change_seams_9t.seams) in a
    high-passed change field. All inf when the field holds no seam."""
    from scipy import ndimage as ndi
    import _change_seams_9t as SE
    sm, _ = SE.seams(field)
    if not (sm > 0).any():
        return np.full(field.shape, np.inf)
    return ndi.distance_transform_edt(sm == 0) * res


def value_at(grid, transform, geoms) -> np.ndarray:
    """grid value at each geometry's representative point (NaN outside the grid)."""
    res, x0, y1 = float(transform.a), float(transform.c), float(transform.f)
    out = []
    for g in geoms:
        c = g.representative_point()
        r_, c_ = int((y1 - c.y) // res), int((c.x - x0) // res)
        out.append(float(grid[r_, c_]) if 0 <= r_ < grid.shape[0] and 0 <= c_ < grid.shape[1] else np.nan)
    return np.array(out)

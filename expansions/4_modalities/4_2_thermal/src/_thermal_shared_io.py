"""Shared helpers for expansion 4.2 thermal. Also imported by 4.3 vegetation stress (decision 2026-11-05).

Purpose
    Config loading, path resolution, missing-input errors, run lookup, and the generic pieces both
    modalities need: block ids, fill fraction of a polygon in a sensor pixel, area-weighted raster
    extraction, nearest-neighbour caliper matching, solar position and clear-sky loading, and the
    out-of-fold lidar-only versus lidar-plus-extra ranking comparison.

Inputs
    expansions/4_modalities/4_2_thermal/src/config_4_2.json (or a dict passed in).
Outputs
    None. Library module.
Run
    Imported only. `python -m pytest -q expansions/4_modalities/4_2_thermal/src/test_4_2.py -p no:cacheprovider`

Path specs in configs
    {"key": "<paths.toml key>", "rel": "..."}  ->  ek.path_for(key) / rel
    {"exp": "4.2", "rel": "data/raw/..."}        ->  ek.exp_dir(exp) / rel
    {"abs": "..."}                               ->  that path (tests only, never in a committed config)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

EXP = "4.2"
CONFIG = SRC / "config_4_2.json"
BLOCK_M = 375.0
NINE_T_ORIGIN = (619500.0, 4593000.0)   # 9t lower-left, EPSG:6346 (bbox in s7_analysis/_icp_change_9t.py)


# ----------------------------------------------------------------------------- config and paths
def load_config(path: Path | None = None) -> dict:
    p = Path(path) if path else CONFIG
    return json.loads(p.read_text(encoding="utf-8"))


def resolve(spec) -> Path | None:
    """Turn a config path spec into a Path. Never spells a data path itself."""
    if spec is None:
        return None
    if isinstance(spec, (str, Path)):
        return Path(spec)
    if "abs" in spec:
        return Path(spec["abs"])
    if "key" in spec:
        return ek.path_for(spec["key"]) / spec.get("rel", "")
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / spec.get("rel", "")
    raise ValueError(f"bad path spec {spec!r}")


def need(path, what: str, schema: str = "", exp_id: str = EXP) -> Path:
    """Return path if it exists, else raise a clear error naming the missing input."""
    p = Path(path) if path is not None else None
    if p is None or not p.exists():
        cfg = f"config_{exp_id.replace('.', '_')}.json"
        raise FileNotFoundError(f"MISSING INPUT {what}: {p}. Assumed schema: {schema or 'see config'}. Edit {cfg}")
    return p


def run_written(run_dir: Path) -> str | None:
    """The time a run recorded when it finished (`written` in _PROVENANCE.json), or None if it never finished."""
    p = Path(run_dir) / "_PROVENANCE.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("written")
    except (OSError, ValueError):
        return None


def latest_run(exp_id: str, short: str, base: Path | None = None) -> Path:
    """Most recent finished run of a stage, by the time the run recorded (review 4.2-03).

    Folder names end in a config hash, so sorting by name returns an arbitrary run. Runs without a
    _PROVENANCE.json never finished and are skipped. Ties fall back to the folder name."""
    root = base if base is not None else ek.sub(exp_id, "results")
    hits = [(run_written(d), d.name, d) for d in Path(root).glob(f"*_{short}_*") if d.is_dir()]
    done = [h for h in hits if h[0]]
    if not done:
        raise FileNotFoundError(f"MISSING INPUT run '{short}' of {exp_id} under {root}. Run that stage first"
                                + (f" ({len(hits)} unfinished run folders without _PROVENANCE.json)" if hits else ""))
    return max(done, key=lambda h: (h[0], h[1]))[2]


def audit_exclusion(spec, allow_missing: bool = False, blocks_spec=None) -> tuple[set[str], dict]:
    """Audit and buffer blocks of the frozen P2 set, as 375 m 'bx_by' ids (review P2-01).

    Reads through ek.require_audit (handles the # header and the sha256 guard). P2 block ids are the
    integer ids of the 9t block layer (block_id = iy * 12 + ix). They are mapped to this module's
    'bx_by' ids through the ix and iy columns of that layer. A missing audit file raises unless
    allow_missing, and then the caller must label its output exploratory."""
    p = resolve(spec) if spec is not None else ek.default_audit_path()
    aud = ek.require_audit(p, allow_missing=allow_missing)
    if aud is None:
        return set(), {"audit": "no audit exclusion, exploratory", "path": str(p), "exploratory": True}
    ids = ek.audit_ids(aud, roles=("audit", "buffer"))
    import geopandas as gpd
    bp = need(resolve(blocks_spec) if blocks_spec else ek.path_for("nine_t") / "pit_blocks_9t.gpkg",
              "9t block layer (maps P2 integer block ids to bx_by)", "layer blocks with block_id, ix, iy")
    b = gpd.read_file(bp, layer="blocks")
    for c in ("block_id", "ix", "iy"):
        if c not in b.columns:
            raise KeyError(f"{bp}: column {c!r} missing")
    if not ((b.iy * 12 + b.ix) == b.block_id).all():
        raise AssertionError(f"{bp}: block_id is not iy * 12 + ix")
    mp = dict(zip(b.block_id.astype(int), [f"{int(x)}_{int(y)}" for x, y in zip(b.ix, b.iy)]))
    miss = sorted(ids - set(mp))
    if miss:
        raise AssertionError(f"audit block ids not in the 9t block layer: {miss[:5]}")
    return {mp[i] for i in ids}, {"audit": "audit and buffer blocks excluded", "path": str(p),
                                  "sha256": aud.attrs.get("sha256"), "n_blocks": len(ids), "exploratory": False}


def finish(run_dir: Path, summary: dict, inputs=(), outputs=(), params=None, seeds=None) -> dict:
    """Write the summary JSON path into the dict, then provenance."""
    ek.write_provenance(run_dir, inputs=[Path(p) for p in inputs if p], outputs=[Path(p) for p in outputs],
                        params=params or {}, seeds=seeds or {})
    summary["run_dir"] = str(run_dir)
    return summary


# ----------------------------------------------------------------------------- vectors
def read_polys(path: Path, layer: str | None, id_col: str, what: str, exp_id: str = EXP):
    import geopandas as gpd
    need(path, what, f"polygon layer {layer!r} with id column {id_col!r}, EPSG:6346", exp_id)
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    ek.assert_crs(g, "EPSG:6346")
    if id_col not in g.columns:
        raise KeyError(f"{what}: column {id_col!r} not in {list(g.columns)}")
    ek.assert_unique(g, id_col)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    return g


def within_raster(gdf, raster_path):
    """Keep polygons lying wholly inside a raster's bounds (restricts the pad layer, which spans several areas, to 9t)."""
    import rasterio
    from shapely.geometry import box
    with rasterio.open(raster_path) as r:
        b = box(*r.bounds)
        crs = r.crs
    g = gdf.to_crs(crs) if gdf.crs != crs else gdf
    return gdf[g.geometry.within(b).to_numpy()].copy()


def block_of(x, y, size: float = BLOCK_M, origin=NINE_T_ORIGIN):
    """375 m block id string 'bx_by' from coordinates (fw_00 section 4 resampling unit)."""
    bx = np.floor((np.asarray(x, float) - origin[0]) / size).astype(int)
    by = np.floor((np.asarray(y, float) - origin[1]) / size).astype(int)
    return np.array([f"{a}_{b}" for a, b in zip(bx, by)])


# ----------------------------------------------------------------------------- fill fraction
def fill_fraction(geom, pixel: float, x0: float = 0.0, y0: float = 0.0) -> float:
    """Largest share of one pixel covered by geom, for a grid with origin (x0, y0) and square pixels."""
    import shapely
    if geom is None or geom.is_empty:
        return float("nan")
    minx, miny, maxx, maxy = geom.bounds
    i0, i1 = int(np.floor((minx - x0) / pixel)), int(np.floor((maxx - x0) / pixel))
    j0, j1 = int(np.floor((miny - y0) / pixel)), int(np.floor((maxy - y0) / pixel))
    ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
    xs, ys = x0 + ii.ravel() * pixel, y0 + jj.ravel() * pixel
    boxes = shapely.box(xs, ys, xs + pixel, ys + pixel)
    return float(shapely.area(shapely.intersection(boxes, geom)).max() / pixel ** 2)


def fill_fraction_offsets(geom, pixel: float, n: int, rng) -> float:
    """Mean of the largest-pixel fill over n random grid offsets. Removes the luck of grid alignment."""
    return float(np.mean([fill_fraction(geom, pixel, *rng.uniform(0, pixel, 2)) for _ in range(n)]))


# ----------------------------------------------------------------------------- rasters
def coverage(geom, transform, shape, ss: int = 5):
    """Fractional pixel coverage of geom on a raster grid. Returns (row slice, col slice, frac) or None."""
    from rasterio.features import geometry_mask
    from rasterio.transform import Affine, rowcol
    minx, miny, maxx, maxy = geom.bounds
    r0, c0 = rowcol(transform, minx, maxy)
    r1, c1 = rowcol(transform, maxx, miny)
    r0, c0 = max(int(r0), 0), max(int(c0), 0)
    r1, c1 = min(int(r1) + 1, shape[0]), min(int(c1) + 1, shape[1])
    if r1 <= r0 or c1 <= c0:
        return None
    t = transform * Affine.translation(c0, r0) * Affine.scale(1 / ss)
    m = ~geometry_mask([geom], out_shape=((r1 - r0) * ss, (c1 - c0) * ss), transform=t, all_touched=False)
    frac = m.reshape(r1 - r0, ss, c1 - c0, ss).mean(axis=(1, 3))
    return slice(r0, r1), slice(c0, c1), frac


def weighted_mean(arr, transform, geom, mask=None, ss: int = 5) -> dict:
    """Area-weighted mean of arr inside geom. mask (same grid, bool) keeps only True pixels."""
    cov = coverage(geom, transform, arr.shape, ss)
    if cov is None:
        return {"mean": float("nan"), "weight": 0.0, "n_px": 0, "geom_area_px": 0.0}
    rs, cs, w = cov
    v = arr[rs, cs].astype(float)
    ok = np.isfinite(v) & (w > 0)
    if mask is not None:
        ok &= mask[rs, cs]
    W = float(w[ok].sum())
    return {"mean": float((v[ok] * w[ok]).sum() / W) if W > 0 else float("nan"), "weight": W,
            "n_px": int(ok.sum()), "geom_area_px": float(w.sum())}


def zonal(raster_path: Path, gdf, id_col: str, fn=np.nanmean, all_touched: bool = True) -> pd.Series:
    """One statistic per polygon, reading only the window around each one. Reprojects polygons to the raster CRS."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds
    out = {}
    with rasterio.open(raster_path) as s:
        g = gdf.to_crs(s.crs) if gdf.crs != s.crs else gdf
        for pid, geom in zip(g[id_col], g.geometry):
            b = geom.bounds
            try:
                w = from_bounds(*b, transform=s.transform).round_offsets().round_lengths()
                w = w.intersection(rasterio.windows.Window(0, 0, s.width, s.height))
                a = s.read(1, window=w, masked=True).astype(float).filled(np.nan)
            except Exception:  # noqa: BLE001 - polygon outside the raster
                out[pid] = np.nan
                continue
            if a.size == 0:
                out[pid] = np.nan
                continue
            m = ~geometry_mask([geom], a.shape, s.window_transform(w), all_touched=all_touched)
            v = a[m]
            out[pid] = fn(v) if np.isfinite(v).any() else np.nan
    return pd.Series(out)


def slope_aspect(dem: np.ndarray, res: float):
    """Slope and aspect in degrees (aspect clockwise from north, downslope direction)."""
    gy, gx = np.gradient(dem, res)          # gy is d/d(row), rows run south
    dzdx, dzdy = gx, -gy
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0
    return slope, aspect


# ----------------------------------------------------------------------------- solar geometry
def solar_position(when_utc, lat: float, lon: float):
    """NOAA low-precision solar position. Returns (zenith_deg, azimuth_deg clockwise from north). Error well under 1 deg."""
    t = pd.Timestamp(when_utc)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    doy = t.dayofyear
    hour = t.hour + t.minute / 60 + t.second / 3600
    g = 2 * np.pi / 365.0 * (doy - 1 + (hour - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
            - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    tst = hour * 60 + eqt + 4 * lon
    ha = np.radians(tst / 4 - 180)
    la = np.radians(lat)
    cz = np.clip(np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha), -1, 1)
    zen = np.arccos(cz)
    az = np.degrees(np.arctan2(np.sin(ha), np.cos(ha) * np.sin(la) - np.tan(decl) * np.cos(la))) + 180.0
    return float(np.degrees(zen)), float(az % 360.0)


def clear_sky_loading(slope_deg, aspect_deg, zen_deg, az_deg, beam_wm2: float = 900.0):
    """Beam irradiance on a tilted surface, W/m2 (cosine of incidence times a nominal clear-sky beam)."""
    s, a = np.radians(slope_deg), np.radians(aspect_deg)
    z, sa = np.radians(zen_deg), np.radians(az_deg)
    cosi = np.cos(z) * np.cos(s) + np.sin(z) * np.sin(s) * np.cos(sa - a)
    return np.where(np.cos(z) > 0, beam_wm2 * np.clip(cosi, 0, None), 0.0)


# ----------------------------------------------------------------------------- matching
def match_caliper(treated: pd.DataFrame, pool: pd.DataFrame, id_col: str, continuous: list[str],
                  exact: list[str] | None = None, caliper_sd: float = 0.5, n_per: int = 1, seed: int = 0) -> pd.DataFrame:
    """Greedy nearest-neighbour matching without replacement on standardised covariates.

    Standardisation uses the pooled SD of treated and pool. A match is kept only if its distance is at
    most caliper_sd (in SD units, Euclidean over the continuous covariates). Exact covariates must agree.
    Treated rows are visited in a seeded random order. Uses covariates only, never a response.
    Returns rows (treated_id, control_id, rank, dist_sd).
    """
    exact = exact or []
    allc = pd.concat([treated[continuous], pool[continuous]])
    mu, sd = allc.mean(), allc.std(ddof=0).replace(0, 1.0)
    T = ((treated[continuous] - mu) / sd).to_numpy(float)
    P = ((pool[continuous] - mu) / sd).to_numpy(float)
    used = np.zeros(len(pool), bool)
    rng = np.random.default_rng(seed)
    rows = []
    for ti in rng.permutation(len(treated)):
        ok = ~used & np.isfinite(P).all(1)
        for e in exact:
            ok &= (pool[e].to_numpy() == treated[e].iloc[ti])
        if not np.isfinite(T[ti]).all() or not ok.any():
            continue
        d = np.sqrt(((P - T[ti]) ** 2).sum(1))
        d[~ok] = np.inf
        for r, pj in enumerate(np.argsort(d)[:n_per]):
            if d[pj] > caliper_sd:
                break
            used[pj] = True
            rows.append({"treated_id": treated[id_col].iloc[ti], "control_id": pool[id_col].iloc[pj],
                         "rank": r + 1, "dist_sd": float(d[pj])})
    return pd.DataFrame(rows, columns=["treated_id", "control_id", "rank", "dist_sd"])


# ----------------------------------------------------------------------------- added value (T4, V3)
def _oof_scores(X, y, folds, seed):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    p = np.full(len(y), np.nan)
    for f in np.unique(folds):
        tr, te = folds != f, folds == f
        if len(np.unique(y[tr])) < 2:
            continue
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          LogisticRegression(max_iter=2000, random_state=seed))
        m.fit(X[tr], y[tr])          # scaler and imputer fitted on training folds only (fw_00 5b)
        p[te] = m.predict_proba(X[te])[:, 1]
    return p


def added_value(df: pd.DataFrame, base: list[str], extra: list[str], label: str, fold: str, block: str,
                block_area_km2: dict, k_per_km2: float = 40.0, B: int = 2000, seed: int = 0,
                max_undefined: float = 0.0) -> dict:
    """Out-of-fold ranking, lidar-only versus lidar plus extra features, same folds and blocks.

    Recall at K per km2 (ek.recall_at_k, truth = positive sites) and AUC, each with a paired block
    bootstrap of the difference (ek.bootstrap_diff, paired=True). Returns point, lo, hi per metric and
    the out-of-fold scores. Undefined draws are counted (SH-01). Their share is reported per metric, and
    above max_undefined the interval is (NaN, NaN), which ek.decide turns into inconclusive.
    """
    from sklearn.metrics import roc_auc_score
    y = df[label].to_numpy(int)
    folds = df[fold].to_numpy()
    sa = _oof_scores(df[base].to_numpy(float), y, folds, seed)
    sb = _oof_scores(df[base + extra].to_numpy(float), y, folds, seed)
    d = df.assign(_sa=sa, _sb=sb, _i=np.arange(len(df)))
    by_block = {b: g for b, g in d.groupby(block)}
    blocks = list(by_block)

    def recall(col):
        def f(bl):
            parts, ntb, area = [], {}, 0.0
            for j, b in enumerate(bl):
                g = by_block[b]
                parts.append(pd.DataFrame({"s": g[col], "t": np.where(g[label] == 1, [f"{j}_{i}" for i in g["_i"]], None),
                                           "b": f"{j}"}))
                ntb[str(j)] = int((g[label] == 1).sum())
                area += float(block_area_km2.get(b, 0.0))
            P = pd.concat(parts)
            P = P[np.isfinite(P["s"])]
            return ek.recall_at_k(P["s"], P["t"], P["b"], ntb, area, k_per_km2)["recall"]
        return f

    def auc(col):
        def f(bl):
            g = pd.concat([by_block[b] for b in bl])
            g = g[np.isfinite(g[col])]
            return roc_auc_score(g[label], g[col]) if g[label].nunique() == 2 else np.nan
        return f

    k_total = k_per_km2 * sum(block_area_km2.get(b, 0.0) for b in blocks)
    out = {"n_sites": int(len(df)), "n_pos": int(y.sum()), "n_blocks": len(blocks),
           "k_total": float(k_total), "k_saturated": bool(k_total >= len(df))}
    for name, fa, fb in (("recall_at_k", recall("_sb"), recall("_sa")), ("auc", auc("_sb"), auc("_sa"))):
        pt, lo, hi, dr = ek.bootstrap_diff(fa, blocks, fb, blocks, B=B, seed=seed, paired=True,
                                           max_undefined=max_undefined, return_draws=True)
        out[name] = {"lidar_only": float(fb(blocks)), "lidar_plus": float(fa(blocks)), "diff": pt, "lo": lo, "hi": hi,
                     "undefined_share": ek.undefined_share(dr), "max_undefined": max_undefined}
        if not np.isfinite(lo):
            out[name]["ci_note"] = (f"{ek.undefined_share(dr):.3f} of {B} draws undefined (a resample with one class or "
                                    f"no truth), above the declared {max_undefined}. Interval undefined, verdict inconclusive")
    if len(blocks) < 15:
        out["warning"] = "fewer than 15 blocks, bootstrap unreliable (fw_00 section 4). Add a permutation interval"
    out["scores"] = d[["_sa", "_sb"]].rename(columns={"_sa": "score_lidar_only", "_sb": "score_lidar_plus"})
    return out

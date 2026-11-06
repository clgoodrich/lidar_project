"""Shared helpers for expansion 4.3 vegetation stress.

Purpose
    Config loading and path resolution for 4.3, plus the generic pieces reused from 4.2
    (expansions/4_modalities/4_2_thermal/src/_thermal_shared_io.py). Fill fraction, area-weighted
    extraction, caliper matching, zonal statistics, block ids and the out-of-fold added-value
    comparison live there once (decision 2026-11-05) and are re-exported here.
    Also the Sentinel-2 index arithmetic and the Hanley and McNeil (1982) AUC standard error.
Inputs
    expansions/4_modalities/4_3_vegetation_stress/src/config_4_3.json
Outputs
    None. Library module.
Run
    Imported only. `python -m pytest -q expansions/4_modalities/4_3_vegetation_stress/src/test_4_3.py -p no:cacheprovider`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC.parents[1] / "4_2_thermal" / "src"))
import _thermal_shared_io as _t  # noqa: E402
from _thermal_shared_io import (ek, resolve, block_of, fill_fraction, coverage, weighted_mean, zonal,  # noqa: E402,F401
                                match_caliper, added_value, finish, within_raster, audit_exclusion, BLOCK_M,
                                NINE_T_ORIGIN)

EXP = "4.3"
CONFIG = SRC / "config_4_3.json"


def load_config(path: Path | None = None) -> dict:
    return json.loads((Path(path) if path else CONFIG).read_text(encoding="utf-8"))


def need(path, what: str, schema: str = "") -> Path:
    return _t.need(path, what, schema, exp_id=EXP)


def latest_run(short: str, base: Path | None = None) -> Path:
    return _t.latest_run(EXP, short, base)


def read_polys(path, layer, id_col, what):
    return _t.read_polys(path, layer, id_col, what, exp_id=EXP)


# ----------------------------------------------------------------------------- indices
def _nd(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def indices(bands: dict) -> dict:
    """NDVI, NDMI, NDRE, EVI from a dict of reflectance arrays. Missing bands give NaN for that index."""
    shape = next(iter(bands.values())).shape
    nan = np.full(shape, np.nan)
    nir, red = bands.get("nir"), bands.get("red")
    out = {"ndvi": _nd(nir, red) if nir is not None and red is not None else nan,
           "ndmi": _nd(nir, bands["swir"]) if nir is not None and "swir" in bands else nan,
           "ndre": _nd(nir, bands["rededge"]) if nir is not None and "rededge" in bands else nan}
    if nir is not None and red is not None and "blue" in bands:
        with np.errstate(divide="ignore", invalid="ignore"):
            out["evi"] = 2.5 * (nir - red) / (nir + 6 * red - 7.5 * bands["blue"] + 1)
    else:
        out["evi"] = nan
    return out


# ----------------------------------------------------------------------------- AUC arithmetic
def hanley_mcneil_se(auc: float, n_pos: int, n_neg: int) -> float:
    """Standard error of an AUC (Hanley and McNeil 1982, Radiology 143:29-36, eq. 1 with Q1, Q2 approximations)."""
    q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
    v = (auc * (1 - auc) + (n_pos - 1) * (q1 - auc ** 2) + (n_neg - 1) * (q2 - auc ** 2)) / (n_pos * n_neg)
    return float(np.sqrt(v))


def min_n_per_class(auc: float, floor: float = 0.5, z: float = 1.959964, n_max: int = 2000) -> int:
    """Smallest equal n per class whose AUC lower bound (auc - z SE) is above floor."""
    for n in range(2, n_max):
        if auc - z * hanley_mcneil_se(auc, n, n) > floor:
            return n
    return -1


# ----------------------------------------------------------------------------- Sentinel-2 L2A radiometry (review 4.3-01)
# ESA L2A: reflectance = (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE. From processing baseline 04.00
# (25 January 2022) BOA_ADD_OFFSET is -1000. Before it, 0. Quantification 10000. These constants are read
# from the scene metadata. They are never assumed. VERIFY list in docs/decisions_4_3.md.
OFFSET_BASELINE = 4.0
SCL_FORBIDDEN = {0, 1, 2, 3, 6, 7, 8, 9, 10, 11}   # no data, saturated, dark/topographic shadow, cloud shadow,
#                                                   water, unclassified, cloud medium/high, thin cirrus, snow


def radiometry(tags: dict, declared: dict | None) -> dict:
    """Scale and offset for one scene. Metadata tags first (BOA_ADD_OFFSET, BOA_QUANTIFICATION_VALUE,
    PROCESSING_BASELINE), else a declared dict from the scene config with a `source`. Refuses otherwise,
    and refuses a combination that contradicts the processing baseline."""
    t = {k.upper(): v for k, v in (tags or {}).items()}
    if {"BOA_ADD_OFFSET", "BOA_QUANTIFICATION_VALUE", "PROCESSING_BASELINE"} <= set(t):
        r = {"add_offset": float(t["BOA_ADD_OFFSET"]), "quantification": float(t["BOA_QUANTIFICATION_VALUE"]),
             "processing_baseline": str(t["PROCESSING_BASELINE"]), "offset_removed_upstream": False,
             "source": "GeoTIFF metadata tags"}
    elif declared:
        miss = [k for k in ("add_offset", "quantification", "processing_baseline", "source") if declared.get(k) is None]
        if miss:
            raise RuntimeError(f"declared radiometry lacks {miss}. Refusing")
        r = {"add_offset": float(declared["add_offset"]), "quantification": float(declared["quantification"]),
             "processing_baseline": str(declared["processing_baseline"]),
             "offset_removed_upstream": bool(declared.get("offset_removed_upstream", False)),
             "source": str(declared["source"])}
    else:
        raise RuntimeError("no L2A radiometry. The stack has no BOA_ADD_OFFSET, BOA_QUANTIFICATION_VALUE and "
                           "PROCESSING_BASELINE tags and the scene config declares none. Refusing to treat DN as reflectance")
    pb = float(r["processing_baseline"])
    if pb >= OFFSET_BASELINE and r["add_offset"] == 0 and not r["offset_removed_upstream"]:
        raise RuntimeError(f"processing baseline {r['processing_baseline']} carries BOA_ADD_OFFSET -1000, but offset 0 "
                           "was given and no upstream removal is declared. Refusing")
    if pb < OFFSET_BASELINE and r["add_offset"] != 0:
        raise RuntimeError(f"processing baseline {r['processing_baseline']} has no BOA offset, but {r['add_offset']} was given")
    if r["quantification"] <= 0:
        raise RuntimeError("BOA_QUANTIFICATION_VALUE must be positive")
    return r


def to_reflectance(dn: np.ndarray, rad: dict) -> np.ndarray:
    off = 0.0 if rad["offset_removed_upstream"] else rad["add_offset"]
    return (np.asarray(dn, float) + off) / rad["quantification"]


def check_reflectance(bands: dict, valid: np.ndarray, max_neg_share: float = 0.01) -> None:
    """A wrong offset shows as negative reflectance over valid land pixels. Refuse above 1 percent."""
    for k, v in bands.items():
        x = v[valid & np.isfinite(v)]
        if x.size and np.mean(x < -0.01) > max_neg_share:
            raise RuntimeError(f"band {k}: {np.mean(x < -0.01):.1%} of valid pixels below -0.01 reflectance. "
                               "The offset is probably applied twice. Check the radiometry")


# ----------------------------------------------------------------------------- native grids (review 4.3-01)
def native_offset(a: np.ndarray, f: int, min_const: float = 0.99) -> tuple[int, int]:
    """Row and column offset (in stack pixels) at which a band upsampled f-fold is constant in f x f
    blocks. Refuses when no offset reaches min_const (the stack is not a block copy of native pixels)."""
    if f == 1:
        return 0, 0
    best = (-1.0, 0, 0)
    for oy in range(f):
        for ox in range(f):
            s = a[oy:, ox:]
            h, w = (s.shape[0] // f) * f, (s.shape[1] // f) * f
            b = s[:h, :w].reshape(h // f, f, w // f, f)
            with np.errstate(invalid="ignore"):
                rng = np.nanmax(b, axis=(1, 3)) - np.nanmin(b, axis=(1, 3))
            fin = np.isfinite(rng)
            share = float(np.mean(rng[fin] == 0)) if fin.any() else 0.0
            if share > best[0]:
                best = (share, oy, ox)
    if best[0] < min_const:
        raise RuntimeError(f"band is not a {f}-fold block copy of native pixels (best constant share {best[0]:.3f}). "
                           "Refusing to read sub-native pixels")
    return best[1], best[2]


def block_reduce(a: np.ndarray, f: int, oy: int, ox: int, how: str = "mean") -> np.ndarray:
    if f == 1:
        return a[oy:, ox:]
    s = a[oy:, ox:]
    h, w = (s.shape[0] // f) * f, (s.shape[1] // f) * f
    b = s[:h, :w].reshape(h // f, f, w // f, f)
    if how == "all":
        return b.all(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        return np.nanmean(b, axis=(1, 3)) if how == "mean" else b.max(axis=(1, 3))


def native_grids(stack: dict, res: float, T, native_m: dict, valid: np.ndarray, grids_m=(10.0, 20.0)) -> dict:
    """{grid_m: (bands at that grid, valid mask, transform)} from a stack at pixel `res`.

    The offset of each grid comes from the bands native at it (or the finer grid). Bands finer than a grid
    are averaged onto it. Bands coarser than a grid are not put on it. valid is all-valid over the block."""
    from rasterio.transform import Affine
    out = {}
    for g in grids_m:
        f = int(round(g / res))
        if f < 1 or abs(f * res - g) > 1e-6:
            if g < res:
                continue
            raise RuntimeError(f"stack pixel {res} m does not divide the {g} m native grid")
        ref = [k for k in stack if native_m.get(k) == g] or [k for k in stack if native_m.get(k, 1e9) < g]
        if not ref:
            continue
        oy, ox = native_offset(stack[ref[0]], f)
        for k in ref[1:]:
            if native_m.get(k) == g and native_offset(stack[k], f) != (oy, ox):
                raise RuntimeError(f"bands {ref[0]} and {k} sit on different {g} m grids")
        bands = {k: block_reduce(v, f, oy, ox) for k, v in stack.items() if native_m.get(k, 1e9) <= g}
        out[g] = (bands, block_reduce(valid, f, oy, ox, "all"), T * Affine.translation(ox, oy) * Affine.scale(f))
    return out


def scl_valid_classes(cfg: dict) -> list[int]:
    """Configured SCL classes kept. Refuses a list that keeps water, snow, cloud or shadow (review 4.3-01)."""
    v = [int(c) for c in cfg["scl_valid"]]
    bad = sorted(set(v) & SCL_FORBIDDEN)
    if bad:
        raise ValueError(f"scl_valid keeps forbidden SCL classes {bad} (water, snow, cloud, shadow, no data). Refusing")
    return v

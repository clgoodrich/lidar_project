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
                                match_caliper, added_value, finish, within_raster, BLOCK_M, NINE_T_ORIGIN)

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

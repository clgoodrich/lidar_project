"""3.2 well-record loaders. Each state source is read raw and normalised to one schema.

Purpose
    Library for S0 (inventory) and S1 (harmonisation). The source list, column names, datum
    notes and status rules live in config_3_2.json "wells", so a new source or a corrected
    mapping is a config edit. Downloaded files are read as data only (own folders under
    data/_source/reference/). Nothing from a download is executed.

Schema (one row per source record, original columns kept as *_orig)
    source, state, county, well_id, name, well_type, status_orig, status_h,
    date_spud, date_complete, date_plug, date_any, date_unknown_sentinel, early_dated,
    lat, lon, datum_orig, datum_state, datum_shift_m, coord_method, coord_dp, low_precision,
    has_coords

Run
    Library only. Used by _appal_wells_inventory.py and _appal_wells_harmonise.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"
SCHEMA = ["source", "state", "county", "well_id", "name", "well_type", "status_orig", "status_h",
          "date_spud", "date_complete", "date_plug", "date_any", "date_unknown_sentinel", "early_dated",
          "lat", "lon", "datum_orig", "datum_state", "datum_shift_m", "coord_method", "coord_dp",
          "low_precision", "has_coords"]


def read_raw(src: dict) -> pd.DataFrame:
    """Read one source as strings (keeps coordinate precision)."""
    p = xl.need(xl.resolve_path(src["path"]), f"well source {src['path']}")
    if src["reader"] == "shp":
        import geopandas as gpd
        g = gpd.read_file(f"zip://{p}!{src['member']}" if p.suffix == ".zip" else p)
        return pd.DataFrame(g.drop(columns="geometry")).astype(object)
    return pd.read_csv(p, dtype=str, low_memory=False)


def decimals(s: pd.Series) -> pd.Series:
    """Decimal places in the text of a coordinate (precision proxy)."""
    t = s.astype(str).str.strip()
    frac = t.str.extract(r"\.(\d+)$")[0]
    return frac.str.len().where(t.str.contains(r"\d", na=False)).astype("float")


def map_status(values: pd.Series, rules) -> pd.Series:
    comp = [(lab, re.compile(rx)) for lab, rx in rules]
    cache = {}

    def one(v):
        if v in cache:
            return cache[v]
        s = "" if pd.isna(v) else str(v).strip()
        out = next((lab for lab, rx in comp if rx.search(s)), "other")
        cache[v] = out
        return out
    return values.map(one)


def to_date(s: pd.Series | None, n: int) -> pd.Series:
    if s is None:
        return pd.Series(pd.NaT, index=range(n))
    return pd.to_datetime(s, errors="coerce", format="mixed")


def geod_shift_m(lat1, lon1, lat2, lon2):
    from pyproj import Geod
    g = Geod(ellps="GRS80")
    ok = np.isfinite(lat1) & np.isfinite(lat2) & np.isfinite(lon1) & np.isfinite(lon2)
    out = np.full(len(lat1), np.nan)
    if ok.any():
        _, _, d = g.inv(lon1[ok], lat1[ok], lon2[ok], lat2[ok])
        out[ok] = d
    return out


def normalise(name: str, src: dict, raw: pd.DataFrame, W: dict) -> pd.DataFrame:
    """Raw source table -> harmonised schema. Row count is preserved (asserted by the caller)."""
    df = raw
    if src.get("state_filter"):
        st_col = "state" if "state" in df else "State"
        df = df[df[st_col].isin(src["state_filter"])].reset_index(drop=True)
    n = len(df)
    col = lambda k: df[src[k]] if src.get(k) and src[k] in df else pd.Series([None] * n)  # noqa: E731
    out = pd.DataFrame(index=range(n))
    out["source"] = name
    st_col = "state" if "state" in df else ("State" if "State" in df else None)
    out["state"] = src["state"] if src.get("state") else (df[st_col].to_numpy() if st_col else None)
    out["county"] = col("county").to_numpy()
    out["well_id"] = col("id").astype(str).to_numpy()
    out["name"] = col("name").to_numpy()
    out["well_type"] = col("type").to_numpy()
    out["status_orig"] = col("status").astype(str).str.strip().to_numpy()
    out["status_h"] = src["force_status"] if src.get("force_status") else map_status(out.status_orig, W["status_rules"]).to_numpy()
    for k in ("date_spud", "date_complete", "date_plug"):
        out[k] = to_date(col(k) if src.get(k) else None, n).to_numpy()
    # a recorded plug date outranks the status code (KY Org_Result is a result, not a status)
    plug = out.date_plug.notna() & (out.status_h != "orphan")
    out.loc[plug, "status_h"] = "plugged"
    dates = out[["date_spud", "date_complete", "date_plug"]]
    out["date_any"] = dates.min(axis=1)
    yr = out.date_any.dt.year
    out["date_unknown_sentinel"] = (yr == W["date_sentinel_year"]).to_numpy()
    out["early_dated"] = ((yr < W["early_cutoff_year"]) & ~out.date_unknown_sentinel).to_numpy()
    lat_s, lon_s = col("lat"), col("lon")
    out["lat"] = pd.to_numeric(lat_s, errors="coerce").to_numpy()
    out["lon"] = pd.to_numeric(lon_s, errors="coerce").to_numpy()
    if src.get("sentinel_xy"):
        sx, sy = src["sentinel_xy"]
        cx, cy = (pd.to_numeric(df[c], errors="coerce") for c in src["sentinel_cols"])
        bad = ((cx == sx) & (cy == sy)).to_numpy()
        out.loc[bad, ["lat", "lon"]] = np.nan
    dp = np.minimum(decimals(lat_s).to_numpy(), decimals(lon_s).to_numpy())
    out["coord_dp"] = dp
    out["low_precision"] = np.where(np.isfinite(dp), dp < W["min_decimals"], True)
    out["datum_orig"] = src.get("datum")
    out["datum_state"] = src.get("datum_state")
    if src.get("lat27"):
        out["datum_shift_m"] = geod_shift_m(pd.to_numeric(col("lat27"), errors="coerce").to_numpy(float),
                                            pd.to_numeric(col("lon27"), errors="coerce").to_numpy(float),
                                            out.lat.to_numpy(float), out.lon.to_numpy(float))
    else:
        out["datum_shift_m"] = np.nan
    out["coord_method"] = col("coord_method").to_numpy() if src.get("coord_method") else None
    out["has_coords"] = np.isfinite(out.lat) & np.isfinite(out.lon) & (out.lat != 0) & (out.lon != 0)
    return out[SCHEMA]


def load_all(cfg: dict, only=None):
    """Yield (name, raw_count_after_filter, normalised frame) per configured source."""
    W = cfg["wells"]
    for name, src in W["sources"].items():
        if only and name not in only:
            continue
        raw = read_raw(src)
        norm = normalise(name, src, raw, W)
        exp = len(raw[raw[("state" if "state" in raw else "State")].isin(src["state_filter"])]) if src.get("state_filter") else len(raw)
        ek.assert_rows(norm, exp, f"{name} harmonised rows")
        yield name, len(raw), norm

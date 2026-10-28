"""Leaf-on and leaf-off dates over the 9t tile, from Sentinel-2 NDVI of closed forest, one year (Oct 2025 to Oct 2026).

Closed forest = 10 m cells where lidar canopy cover is above 0.95 and the mean canopy height is above 12 m (1 m CHM, 2019).
Each Sentinel-2 L2A scene (Element 84 Earth Search STAC, tile 17TPG) gives the median NDVI of those cells.
Cloud, cloud shadow, snow and no-data cells (SCL 0, 1, 3, 8, 9, 10, 11) are masked. A scene is kept when at least
30% of the forest cells are valid.

Leaf state per date: the NDVI curve is smoothed (rolling median of 3 scenes), then scaled between its winter low and
summer high. Leaf-off is below 0.35 of that range, leaf-on is above 0.65, anything between is transition.

Also writes the NISAR dates with their leaf state, interpolated linearly in time, next to the snow record from
noaa_snow_at_nisar_dates_9t.csv.

Run:
  python notebooks/wellsight_v2/s5_eval/_nisar_leaf_state_9t.py
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
CHM = ROOT / "data/9t/derived/1m/chm_9t_1m.tif"
OUT = ROOT / "data/9t/derived/weather"
BOX = (620500.0, 4594000.0, 622500.0, 4596000.0)   # 2 km square inside 9t (EPSG:6346 ~ UTM 17N)
LONLAT = (-79.50, 41.49)
STAC = "https://earth-search.aws.element84.com/v1/search"
BAD = (0, 1, 3, 8, 9, 10, 11)
MIN_VALID = 0.30


def forest_mask():
    with rasterio.open(CHM) as r:
        win = from_bounds(*BOX, transform=r.transform).round_offsets().round_lengths()
        a = r.read(1, window=win, masked=True).astype("float32")
    n = (a.shape[0] // 10) * 10, (a.shape[1] // 10) * 10
    b = np.ma.filled(a[:n[0], :n[1]], np.nan).reshape(n[0] // 10, 10, n[1] // 10, 10)
    with np.errstate(all="ignore"):
        cover = np.nanmean(np.where(np.isfinite(b), b > 2.0, np.nan), axis=(1, 3))
        height = np.nanmean(b, axis=(1, 3))
    return (cover > 0.95) & (height > 12.0)


def scenes():
    body = {"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": list(LONLAT)},
            "datetime": "2025-10-15T00:00:00Z/2026-10-20T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 60}}, "limit": 200}
    r = requests.post(STAC, json=body, timeout=60)
    r.raise_for_status()
    out = []
    for f in r.json()["features"]:
        if "17TPG" in f["id"]:
            out.append((f["properties"]["datetime"][:10], f["id"], {k: f["assets"][k]["href"] for k in ("red", "nir", "scl")}))
    return sorted(out)


def read(href, shape, nearest=False):
    from rasterio.enums import Resampling
    with rasterio.open(href) as s:
        # the box is given in EPSG:6346, which is UTM 17N within about a metre of EPSG:32617
        win = from_bounds(*BOX, transform=s.transform)
        return s.read(1, window=win, out_shape=shape, resampling=Resampling.nearest if nearest else Resampling.average,
                      boundless=True, fill_value=0).astype("float32")


def main():
    fm = forest_mask()
    print("forest cells", int(fm.sum()), "of", fm.size, flush=True)
    rows = []
    for date, sid, h in scenes():
        try:
            red, nir, scl = (read(h[k], fm.shape, k == "scl") for k in ("red", "nir", "scl"))
        except Exception as e:  # noqa: BLE001
            print("skip", sid, e)
            continue
        ok = fm & ~np.isin(scl, BAD) & (red > 0) & (nir > 0)
        snow = fm & (scl == 11)
        if ok.sum() < MIN_VALID * fm.sum():
            rows.append(dict(date=date, ndvi=np.nan, valid=ok.sum() / fm.sum(), snow=snow.sum() / fm.sum(), scene=sid))
            continue
        ndvi = (nir[ok] - red[ok]) / (nir[ok] + red[ok])
        rows.append(dict(date=date, ndvi=float(np.median(ndvi)), valid=ok.sum() / fm.sum(), snow=snow.sum() / fm.sum(), scene=sid))
        print(date, round(rows[-1]["ndvi"], 3), round(rows[-1]["valid"], 2), flush=True)
    D = pd.DataFrame(rows)
    D["date"] = pd.to_datetime(D["date"])
    D = D.sort_values("date").reset_index(drop=True)
    k = D.dropna(subset=["ndvi"]).copy()
    k["smooth"] = k.ndvi.rolling(3, center=True, min_periods=1).median()
    lo, hi = k.smooth.min(), k.smooth.max()
    k["frac"] = (k.smooth - lo) / (hi - lo)
    k["leaf_state"] = np.where(k.frac < 0.35, "leaf-off", np.where(k.frac > 0.65, "leaf-on", "transition"))
    D = D.merge(k[["date", "smooth", "frac", "leaf_state"]], on="date", how="left")
    D.to_csv(OUT / "leaf_state_ndvi_curve_9t.csv", index=False)
    print(f"NDVI low {lo:.3f}, high {hi:.3f}")
    # NISAR dates
    n = pd.read_csv(OUT / "noaa_snow_at_nisar_dates_9t.csv", parse_dates=["date"])
    t = (k.date - k.date.min()).dt.days.values
    n["frac"] = np.interp((n.date - k.date.min()).dt.days.values, t, k.frac.values, left=np.nan, right=np.nan)
    n["leaf_state"] = np.where(n.frac.isna(), "", np.where(n.frac < 0.35, "leaf-off", np.where(n.frac > 0.65, "leaf-on", "transition")))
    n.to_csv(OUT / "nisar_dates_leaf_and_snow_9t.csv", index=False)
    print(n[["date", "tracks", "frac", "leaf_state", "snow_depth_mm"]].to_string(index=False))


if __name__ == "__main__":
    main()

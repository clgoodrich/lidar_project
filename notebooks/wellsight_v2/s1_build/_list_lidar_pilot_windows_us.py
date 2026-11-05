"""SUPERSEDED 2026-11-04 by `_list_lidar_windows_inventory_us.py`. Window listing from this script is discovery only. It does not paginate (max 200 per query), turns repeated failure into an empty result, drops duplicate URLs across windows, and scores coverage as a tile-count ratio, not area. Its outputs are kept for the record and must not be used for a download budget.

For each high-orphan-well county, find the densest 5 km x 5 km cluster of documented orphan wells, then LIST (not download) the 3DEP lidar
tiles that cover it. Output is a download list, nothing more.

Inputs  data/_source/reference/wells_us_orphan_2022/US_orphaned_wells.csv (lon, lat per well)
        data/_source/reference/lidar_catalogue/lidar_projects_by_county_us.csv (projects per county from _list_lidar_by_county_us.py)
Outputs data/_source/reference/lidar_catalogue/lidar_pilot_windows_us.csv        one row per county window (centre, bbox, wells in window)
        data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv  one row per tile (url, size, project, published)
Run     python notebooks/wellsight_v2/s1_build/_list_lidar_pilot_windows_us.py
Notes   Window = 25 km2, similar to tile 9t (20 km2). The window is chosen by orphan well count only, so it says nothing about terrain or canopy.
        Orphan wells are not the same as old wells. Spud dates are not in this database.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter

ROOT = Path(__file__).resolve().parents[3]
CAT = ROOT / "data/_source/reference/lidar_catalogue"
WELLS = ROOT / "data/_source/reference/wells_us_orphan_2022/US_orphaned_wells.csv"
API = "https://tnmaccess.nationalmap.gov/api/v1/products"
UA = {"User-Agent": "lidar-well-research/1.0"}
DS = "Lidar Point Cloud (LPC)"
W = 5  # km


def clean_project(p):
    if " " in p:
        m = re.match(r"^(.*?\b(?:19|20)\d\d\b(?: [A-Z]\d)?)", p)
        if m:
            return m.group(1)
    return p


def get(params, tries=3):
    q = urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=90) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(2 * (k + 1))
    return {"total": 0, "items": []}


def norm(s):
    return re.sub(r"\b(county|parish|borough|census area)\b", "", str(s).lower()).replace(".", "").replace("'", "").strip()


def densest_window(xy):
    """xy in metres (EPSG:5070). Returns centre (x, y) of the densest W x W km window and the count inside."""
    x0, y0 = xy.min(0)
    ix = ((xy[:, 0] - x0) // 1000).astype(int)
    iy = ((xy[:, 1] - y0) // 1000).astype(int)
    g = np.zeros((ix.max() + 1, iy.max() + 1))
    np.add.at(g, (ix, iy), 1)
    s = uniform_filter(g, size=W, mode="constant") * W * W
    i, j = np.unravel_index(np.argmax(s), s.shape)
    return x0 + (i + 0.5) * 1000, y0 + (j + 0.5) * 1000, int(round(s[i, j]))


def main():
    cat = pd.read_csv(CAT / "lidar_projects_by_county_us.csv")
    cat["project"] = cat.project.map(clean_project)
    cat = cat.drop_duplicates(["state", "county", "project"])
    w = pd.read_csv(WELLS, low_memory=False)
    w["ck"] = w.State + "|" + w.County.map(norm)
    w = w.dropna(subset=["Latitude", "Longitude"])
    g = gpd.GeoDataFrame(w, geometry=gpd.points_from_xy(w.Longitude, w.Latitude), crs=4326).to_crs(5070)
    g["x"], g["y"] = g.geometry.x, g.geometry.y
    wins, tiles = [], []
    for (st, co), pr in cat.groupby(["state", "county"], sort=False):
        sub = g[g.ck == f"{st}|{norm(co)}"]
        if len(sub) < 25:
            continue
        cx, cy, n = densest_window(sub[["x", "y"]].to_numpy())
        box = gpd.GeoSeries.from_xy([cx - W * 500, cx + W * 500], [cy - W * 500, cy + W * 500], crs=5070).to_crs(4326)
        minx, maxx, miny, maxy = box.x.min(), box.x.max(), box.y.min(), box.y.max()
        centre = gpd.GeoSeries.from_xy([cx], [cy], crs=5070).to_crs(4326)
        wins.append(dict(state=st, county=co, wells_in_window=n, centre_lon=round(centre.x[0], 4), centre_lat=round(centre.y[0], 4),
                         minx=round(minx, 4), miny=round(miny, 4), maxx=round(maxx, 4), maxy=round(maxy, 4)))
        for p in pr.project:
            r = get(dict(datasets=DS, bbox=f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}", q=p, max=200, outputFormat="JSON"))
            for it in r["items"]:
                if clean_project(re.sub(r"^USGS Lidar Point Cloud ", "", it["title"])).startswith(p[:20]) or p in it["title"]:
                    tiles.append(dict(state=st, county=co, project=p, tile=it["title"].replace("USGS Lidar Point Cloud ", ""),
                                      mb=round(it["sizeInBytes"] / 1e6, 1), published=it["publicationDate"], format=it["format"], url=it["downloadURL"]))
        print(st, co, n, "wells in window", flush=True)
    pd.DataFrame(wins).to_csv(CAT / "lidar_pilot_windows_us.csv", index=False)
    T = pd.DataFrame(tiles).drop_duplicates(["url"])
    T.to_csv(CAT / "lidar_download_list_pilot_5km_us.csv", index=False)
    print(len(wins), "windows", len(T), "tiles", round(T.mb.sum() / 1000, 1), "GB")


if __name__ == "__main__":
    main()

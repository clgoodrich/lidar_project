"""LIST (not download) the 3DEP lidar that covers the densest 5 km x 5 km cluster of documented orphan wells in each chosen county.

Replaces `_list_lidar_by_county_us.py` and `_list_lidar_pilot_windows_us.py` (third-review fixes, 2026-11-04). Differences
  - Every query is paged until all reported items are retrieved. Status is ok, empty, failed or incomplete (see `_tnm_common.py`).
  - A failed query is never recorded as empty.
  - The window is queried without a project filter, so every project that touches it is found. No five-point sampling.
  - Project identity comes from the download URL path, not a title regex.
  - Coverage is the area of the window covered by the union of tile bounding boxes, not a tile-count ratio.
  - Tiles are kept once per URL (asset table) and once per window (membership table).
  - Sizes are the sum of the real tile sizes. No sample mean is multiplied by a count.
Inputs  data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv
        data/_source/reference/wells_us_orphan_2026/area_orphan_counts_by_county_us.csv (from _rank_orphan_counties_us.py)
Outputs data/_source/reference/lidar_catalogue/ (all new names)
        lidar_win_windows_us.csv         one row per window (centre, bbox, wells in window)
        lidar_win_query_log_us.csv       one row per window query (status, reported total, retrieved, pages, error)
        lidar_win_tiles_unique_us.csv    one row per tile URL
        lidar_win_tile_window_us.csv     tile URL to window membership (tiles with positive overlap only)
        lidar_win_projects_us.csv        one row per window and project (tiles, GB, published, coverage fraction, recommended flag)
Run     python notebooks/wellsight_v2/s1_build/_list_lidar_windows_inventory_us.py
Limits  Tile footprints are the API bounding boxes (WGS84 boxes). A rotated or clipped tile covers less than its box, so coverage is an
        upper bound. The API gives no flight date and no point density. Publication date is not flight date. Measure density after one tile.
        The window is chosen by orphan count only. It says nothing about terrain or canopy. Orphan wells are not the same as old wells.
Recommended project per window  the newest publication among projects with coverage of at least 0.95. If none reaches 0.95 the window is
        flagged best_partial with the highest-coverage project.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter
from shapely.geometry import box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _tnm_common import query_all  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "data/_source/reference"
CAT = REF / "lidar_catalogue"
WELLS = REF / "wells_us_orphan_2026/US_orphaned_wells_2026.csv"
RANK = REF / "wells_us_orphan_2026/area_orphan_counts_by_county_us.csv"
W = 5  # km
COVER_MIN = 0.95


def norm(s):
    return re.sub(r"\b(county|parish|borough|census area|city and borough|municipality)\b", "", str(s).lower()).replace(".", "").replace("'", "").replace("-", " ").strip()


def pick_counties():
    """A orphans >= 700. B orphans >= 250 and density >= 0.7 per km2. C the top county of any state with 300 or more wells not already chosen."""
    d = pd.read_csv(RANK).dropna(subset=["minx"])
    A = d[d.orphans >= 700]
    B = d[(d.orphans >= 250) & (d.per_km2 >= 0.7)]
    have = set(pd.concat([A, B]).state)
    C = [g.sort_values("orphans", ascending=False).head(1) for st, g in d.groupby("state") if g.orphans.sum() >= 300 and st not in have]
    return pd.concat([A, B] + C).drop_duplicates(["state", "county"]).sort_values("orphans", ascending=False)


def densest_window(xy):
    x0, y0 = xy.min(0)
    ix = ((xy[:, 0] - x0) // 1000).astype(int)
    iy = ((xy[:, 1] - y0) // 1000).astype(int)
    g = np.zeros((ix.max() + 1, iy.max() + 1))
    np.add.at(g, (ix, iy), 1)
    s = uniform_filter(g, size=W, mode="constant") * W * W
    i, j = np.unravel_index(np.argmax(s), s.shape)
    return x0 + (i + 0.5) * 1000, y0 + (j + 0.5) * 1000, int(round(s[i, j]))


def project_of(url, title):
    m = re.search(r"/LPC/Projects/(?:legacy/)?([^/]+)/", url or "")
    if m:
        return m.group(1)
    return re.sub(r"^USGS Lidar Point Cloud ", "", title).rsplit(" ", 1)[0]


def year_guess(p):
    y = re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", p)
    return int(y[-1]) if y else np.nan


def main():
    CAT.mkdir(parents=True, exist_ok=True)
    sel = pick_counties()
    w = pd.read_csv(WELLS, low_memory=False).dropna(subset=["latitude", "longitude"])
    w["state"] = w.state.str.strip().str.title()
    w["ck"] = w.state + "|" + w.county.map(norm)
    g = gpd.GeoDataFrame(w, geometry=gpd.points_from_xy(w.longitude, w.latitude), crs=4326).to_crs(5070)
    g["x"], g["y"] = g.geometry.x, g.geometry.y
    wins, logs, uniq, member, projs = [], [], {}, [], []
    for n_, (_, c) in enumerate(sel.iterrows(), 1):
        sub = g[g.ck == f"{c.state}|{norm(c.county)}"]
        if len(sub) < 25:
            continue
        cx, cy, n = densest_window(sub[["x", "y"]].to_numpy())
        win5070 = box(cx - W * 500, cy - W * 500, cx + W * 500, cy + W * 500)
        wll = gpd.GeoSeries([win5070], crs=5070).to_crs(4326).total_bounds
        centre = gpd.GeoSeries.from_xy([cx], [cy], crs=5070).to_crs(4326)
        wid = f"{c.state.replace(' ', '')}_{c.county.replace(' ', '')}"
        wins.append(dict(window=wid, state=c.state, county=c.county, wells_in_window=n, centre_lon=round(centre.x[0], 4), centre_lat=round(centre.y[0], 4),
                         minx=round(wll[0], 4), miny=round(wll[1], 4), maxx=round(wll[2], 4), maxy=round(wll[3], 4)))
        res = query_all(f"{wll[0]:.4f},{wll[1]:.4f},{wll[2]:.4f},{wll[3]:.4f}")
        logs.append(dict(window=wid, status=res["status"], reported_total=res["total"], retrieved=res["retrieved"], pages=res["pages"], error=res["error"]))
        rows = []
        for it in res["items"]:
            bb = it["boundingBox"]
            poly = gpd.GeoSeries([box(bb["minX"], bb["minY"], bb["maxX"], bb["maxY"])], crs=4326).to_crs(5070).iloc[0]
            if poly.intersection(win5070).area <= 0:
                continue
            title = re.sub(r"^USGS Lidar Point Cloud ", "", it["title"])
            pj = project_of(it["downloadURL"], it["title"])
            rows.append(dict(window=wid, project=pj, tile=title, url=it["downloadURL"], mb=round(it["sizeInBytes"] / 1e6, 1), published=it["publicationDate"],
                             fmt=it["format"], bb_minx=bb["minX"], bb_miny=bb["minY"], bb_maxx=bb["maxX"], bb_maxy=bb["maxY"], poly=poly))
            uniq.setdefault(it["downloadURL"], {k: v for k, v in rows[-1].items() if k not in ("window", "poly")})
            member.append(dict(window=wid, url=it["downloadURL"], project=pj))
        d = pd.DataFrame(rows)
        if len(d):
            for pj, gp in d.groupby("project"):
                cover = unary_union(list(gp.poly)).intersection(win5070).area / win5070.area
                projs.append(dict(window=wid, state=c.state, county=c.county, project=pj, tiles=len(gp), gb=round(gp.mb.sum() / 1000, 3),
                                  published=gp.published.min(), year_in_name=year_guess(pj), cover=round(cover, 3), query_status=res["status"]))
        print(f"{n_:2d} {wid:22s} wells {n:4d} status {res['status']:10s} {res['retrieved']}/{res['total']} tiles-with-overlap {len(d)}", flush=True)
    P = pd.DataFrame(projs)
    P["recommended"] = ""
    for wid, gp in P.groupby("window"):
        full = gp[gp.cover >= COVER_MIN]
        if len(full):
            P.loc[full.sort_values(["published", "tiles"], ascending=[False, True]).index[0], "recommended"] = "rec"
        else:
            P.loc[gp.sort_values("cover", ascending=False).index[0], "recommended"] = "best_partial"
    pd.DataFrame(wins).to_csv(CAT / "lidar_win_windows_us.csv", index=False)
    pd.DataFrame(logs).to_csv(CAT / "lidar_win_query_log_us.csv", index=False)
    pd.DataFrame(uniq.values()).to_csv(CAT / "lidar_win_tiles_unique_us.csv", index=False)
    pd.DataFrame(member).drop_duplicates().to_csv(CAT / "lidar_win_tile_window_us.csv", index=False)
    P.to_csv(CAT / "lidar_win_projects_us.csv", index=False)
    print("windows", len(wins), "unique tiles", len(uniq), "status counts", pd.DataFrame(logs).status.value_counts().to_dict())


if __name__ == "__main__":
    main()

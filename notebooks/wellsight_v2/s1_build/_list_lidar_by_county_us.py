"""List USGS 3DEP lidar point cloud projects over high-orphan-well counties. METADATA ONLY. No point clouds are downloaded.

For each county, probe 5 small boxes (centre and four inner points) to find which 3DEP LPC projects cover it, then for each project
ask the TNM Access API for the number of tiles in the county box (q = project name) and a sample of 100 tiles for mean tile size and
publication date. Estimated size = tiles in county box x mean sampled tile size. The county box is larger than the county, so tiles and
size are upper bounds (typically 1.2 to 2 times for irregular counties).

Input  data/_source/reference/wells_us_orphan_2022/area_orphan_counts_by_county_us.csv
Output data/_source/reference/lidar_catalogue/lidar_projects_by_county_us.csv (one row per county and project)
       data/_source/reference/lidar_catalogue/_PROVENANCE.json
Run    python notebooks/wellsight_v2/s1_build/_list_lidar_by_county_us.py
Limits Statewide programs outside 3DEP (state portals) are not listed. Point density per project is not in the API. Measure after one tile.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/_source/reference/wells_us_orphan_2022/area_orphan_counts_by_county_us.csv"
OUT = ROOT / "data/_source/reference/lidar_catalogue"
OUT.mkdir(parents=True, exist_ok=True)
API = "https://tnmaccess.nationalmap.gov/api/v1/products"
UA = {"User-Agent": "lidar-well-research/1.0"}
DS = "Lidar Point Cloud (LPC)"


def get(params, tries=3):
    q = urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            time.sleep(2 * (k + 1))
    return {"total": 0, "items": []}


def project_of(title):
    m = re.match(r"USGS Lidar Point Cloud (.+?) [0-9A-Za-z_\-]*$", title)
    t = m.group(1) if m else title
    return t


def pick_counties():
    """A orphans >= 700. B orphans >= 250 and density >= 0.7 per km2. C the top county of any state with 300 or more wells not already chosen."""
    d = pd.read_csv(SRC).dropna(subset=["minx"])
    A = d[d.orphans >= 700]
    B = d[(d.orphans >= 250) & (d.per_km2 >= 0.7)]
    have = set(pd.concat([A, B]).state)
    C = [g.sort_values("orphans", ascending=False).head(1) for st, g in d.groupby("state") if g.orphans.sum() >= 300 and st not in have]
    s = pd.concat([A, B] + C).drop_duplicates(["state", "county"])
    return s.sort_values("orphans", ascending=False)


def main():
    sel = pick_counties()
    print(len(sel), "counties")
    out = []
    for _, c in sel.iterrows():
        t0 = time.time()
        bbox = f"{c.minx:.4f},{c.miny:.4f},{c.maxx:.4f},{c.maxy:.4f}"
        cx, cy = (c.minx + c.maxx) / 2, (c.miny + c.maxy) / 2
        dx, dy = (c.maxx - c.minx) / 4, (c.maxy - c.miny) / 4
        projects = {}
        for px, py in [(cx, cy), (cx - dx, cy - dy), (cx + dx, cy - dy), (cx - dx, cy + dy), (cx + dx, cy + dy)]:
            r = get(dict(datasets=DS, bbox=f"{px-.01:.4f},{py-.01:.4f},{px+.01:.4f},{py+.01:.4f}", max=60, outputFormat="JSON"))
            for it in r["items"]:
                projects.setdefault(project_of(it["title"]), 0)
                projects[project_of(it["title"])] += 1
        for pj in projects:
            r = get(dict(datasets=DS, bbox=bbox, q=pj, max=100, outputFormat="JSON"))
            items = [i for i in r["items"] if project_of(i["title"]) == pj]
            if not items:
                continue
            sz = np.mean([i["sizeInBytes"] for i in items])
            n = r.get("total", len(items))
            out.append(dict(state=c.state, county=c.county, county_orphans=int(c.orphans), county_km2=round(c.km2, 1), project=pj,
                            tiles_in_county_box=n, mean_tile_mb=round(sz / 1e6, 1), est_gb_upper=round(n * sz / 1e9, 2),
                            published=min(i["publicationDate"] for i in items), format=items[0]["format"],
                            sample_url=items[0]["downloadURL"], meta_url=items[0]["metaUrl"]))
        print(f"{c.state} {c.county}: {len(projects)} projects, {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(out)
    df.to_csv(OUT / "lidar_projects_by_county_us.csv", index=False)
    (OUT / "_PROVENANCE.json").write_text(json.dumps(dict(api=API, dataset=DS, accessed=time.strftime("%Y-%m-%d"),
        note="Metadata only. Tile counts are for the county bounding box and are upper bounds."), indent=2))
    print(OUT / "lidar_projects_by_county_us.csv")


if __name__ == "__main__":
    main()

"""Look at the strongest steady bright radar targets on the lidar hillshade and on Sentinel-2.

For each area (9t, 613590, Warren, McKean) the targets seen on all three NISAR tracks are cut out as
a 400 m chip. Left panel is the 1 m lidar hillshade. Right panel is Sentinel-2 true colour (10 m),
the clearest scene from June to September 2026 (leaf-on, close to the NISAR summer dates).
McKean has only two three-track targets, so its top two-track targets by brightness are added.

The ring is 15 m wide, the merge radius used to join targets across tracks. Rings are drawn twice
(white under charcoal) so they read on both dark forest and bright ground.

Sentinel-2 L2A is from the Element 84 Earth Search STAC (AWS), open data.

Run:
  python notebooks/wellsight_v2/s5_eval/_nisar_bright_chips.py
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
import requests
from matplotlib import pyplot as plt
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[3]
HALF = 200.0      # chip half-width, m
RING = 15.0       # merge radius, m
PER_PAGE = 12     # targets per sheet (3 pairs across, 4 rows)
EXTRA_TWO_TRACK = 10
STAC = "https://earth-search.aws.element84.com/v1/search"

AREAS = {
    "9t": dict(pts="data/9t/results/nisar/nisar_bright_targets_points_9t_slc.gpkg",
               hs="data/9t/derived/1m/hillshade_9t_1m.tif", out="data/9t/results/nisar", extra=0),
    "613590": dict(pts="data/613590/results/nisar/nisar_bright_targets_points_613590_slc.gpkg",
                   hs="data/613590/derived/1m/hillshade_613590_1m.tif", out="data/613590/results/nisar", extra=0),
    "warren": dict(pts="data/warren/results/nisar/nisar_bright_targets_points_warren.gpkg",
                   hs="data/warren/derived/1m/full/hillshade_warren_1m.tif", out="data/warren/results/nisar", extra=0),
    "mkf": dict(pts="data/mckean/mkf/results/nisar/nisar_bright_targets_points_mkf.gpkg",
                hs="data/mckean/mkf/derived/1m/hillshade_mkf_1m.tif", out="data/mckean/mkf/results/nisar",
                extra=EXTRA_TWO_TRACK),
}


_SCENES = {}


def best_scene(lon, lat):
    """Clearest June to September 2026 scene whose footprint contains the point."""
    key = (round(lon, 2), round(lat, 2))
    if key in _SCENES:
        return _SCENES[key]
    body = {"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [lon, lat]}, "datetime": "2026-06-01T00:00:00Z/2026-09-15T23:59:59Z",
            "query": {"eo:cloud_cover": {"lt": 30}}, "limit": 50}
    r = requests.post(STAC, json=body, timeout=60)
    r.raise_for_status()
    feats = r.json()["features"]
    if not feats:
        raise RuntimeError(f"no scene for {bbox}")
    f = min(feats, key=lambda x: x["properties"]["eo:cloud_cover"])
    _SCENES[key] = (f["id"], f["properties"]["eo:cloud_cover"], {k: f["assets"][k]["href"] for k in ("red", "green", "blue")})
    return _SCENES[key]


def read_window(path, x, y, crs_in, half):
    """Read a square window around (x, y) given in crs_in. Returns array and (left, right, bottom, top) in crs_in."""
    with rasterio.open(path) as src:
        l, b, r_, t = x - half, y - half, x + half, y + half
        sb = transform_bounds(crs_in, src.crs, l, b, r_, t)
        win = from_bounds(*sb, transform=src.transform)
        arr = src.read(1, window=win, boundless=True, fill_value=0).astype("float32")
    return arr


def rgb_chip(hrefs, x, y, crs):
    bands = [read_window(hrefs[k], x, y, crs, HALF) for k in ("red", "green", "blue")]
    n = min(b.shape[0] for b in bands), min(b.shape[1] for b in bands)
    rgb = np.dstack([b[:n[0], :n[1]] for b in bands]) / 10000.0
    return np.clip(rgb / 0.25, 0, 1) ** (1 / 1.6)


def ring(ax, cx, cy):
    for lw, col in ((3.0, "white"), (1.4, "#2B2F36")):
        ax.add_patch(plt.Circle((cx, cy), RING, fill=False, lw=lw, ec=col))


def main():
    summary = {}
    for area, cfg in AREAS.items():
        pts = gpd.read_file(ROOT / cfg["pts"])
        three = pts[pts.n_tracks == 3].sort_values("bright_db", ascending=False)
        extra = (pts[(pts.n_tracks == 2) & pts.canopy_cover.notna()].sort_values("bright_db", ascending=False).head(cfg["extra"])
                 if cfg["extra"] else pts.iloc[0:0])
        sel = pd.concat([three, extra]) if len(extra) else three
        sel = gpd.GeoDataFrame(sel, geometry='geometry', crs=pts.crs)
        if sel.empty:
            continue
        hs_path = ROOT / cfg["hs"]
        with rasterio.open(hs_path) as h:
            hs_crs = h.crs
        selr = sel.to_crs(hs_crs)
        lonlat = sel.to_crs(4326).geometry
        print(area, len(sel), "targets", flush=True)
        outdir = ROOT / cfg["out"]
        pages = [list(range(i, min(i + PER_PAGE, len(sel)))) for i in range(0, len(sel), PER_PAGE)]
        files, scenes = [], set()
        for pi, idx in enumerate(pages, 1):
            fig, axes = plt.subplots(4, 6, figsize=(18, 12.4))
            for ax in axes.ravel():
                ax.axis("off")
            for k, i in enumerate(idx):
                row, pair = divmod(k, 3)
                a_h, a_s = axes[row, pair * 2], axes[row, pair * 2 + 1]
                x, y = selr.geometry.iloc[i].x, selr.geometry.iloc[i].y
                rec = sel.iloc[i]
                hs = read_window(hs_path, x, y, hs_crs, HALF)
                ext = (-HALF, HALF, -HALF, HALF)
                hs = np.where(hs > 0, hs, np.nan)   # int16 hillshade, 0 / -9999 / -32768 are no-data
                lo, hi = (np.nanpercentile(hs, [1, 99]) if np.isfinite(hs).any() else (0, 1))
                cm = plt.get_cmap("gray").copy()
                cm.set_bad("#C9CDD1")
                a_h.imshow(hs, cmap=cm, extent=ext, vmin=lo, vmax=hi)
                scene, cloud, hrefs = best_scene(lonlat.iloc[i].x, lonlat.iloc[i].y)
                scenes.add(scene)
                a_s.imshow(rgb_chip(hrefs, x, y, hs_crs), extent=ext)
                for a in (a_h, a_s):
                    ring(a, 0, 0)
                    a.set_xticks([]); a.set_yticks([])
                    for sp in a.spines.values():
                        sp.set_visible(True); sp.set_color("#8E959B")
                cc = rec.get("canopy_cover")
                ctx = rec.get("context", "")
                a_h.set_title(f"#{int(rec.target_id)}  {int(rec.n_tracks)} tracks  {rec.bright_db:.1f} dB", fontsize=9, loc="left")
                a_s.set_title(f"{scene[10:18]} cover {cc:.2f}  well {rec.well_dist_m:.0f} m  {ctx}", fontsize=9, loc="left")
            fig.suptitle(f"{area}: steady bright radar targets. Left lidar hillshade, right Sentinel-2 (clearest scene Jun to Sep 2026). "
                         f"Chip 400 m, ring 15 m. Page {pi} of {len(pages)}", fontsize=11)
            fig.tight_layout()
            f = outdir / f"nisar_bright_chips_p{pi}_{area}.png"
            fig.savefig(f, dpi=110)
            plt.close(fig)
            files.append(str(f.relative_to(ROOT)))
        sel_out = outdir / f"nisar_bright_chips_targets_{area}.csv"
        sel.drop(columns="geometry").assign(x=sel.geometry.x, y=sel.geometry.y).to_csv(sel_out, index=False)
        summary[area] = dict(n=len(sel), scenes=sorted(scenes), figures=files, targets=str(sel_out.relative_to(ROOT)))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

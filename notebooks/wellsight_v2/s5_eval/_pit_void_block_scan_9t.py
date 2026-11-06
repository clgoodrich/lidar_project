"""Which pits have a return void under open sky, and is a small raised block near them more often than chance?

Void: inside a pit_inside outline the density of ALL raw returns (any class) is under 20% of the density in a ring 10 to 30 m
out, and the outline holds at least 15 m2 and a ring of at least 200 returns. A void under open sky is probable standing water,
because water absorbs the near-infrared pulse. Open sky: canopy cover (share of 1 m CHM cells above 2 m) under 0.3 within
8 m of the outline.

Block: in a 15 m disc around the pit_inside centre, outside pit_full, a connected patch of 4 to 16 one-metre cells with height
above ground (DSM - DEM) of 0.8 to 2.5 m, a flat top (std under 0.15 m, range under 0.4 m) and a one-cell border with median
height under 0.3 m. A first, looser rule (3 to 30 cells, no flat-top test) fired on 85% of controls and was dropped. Controls are random open-sky
discs at least 40 m from any pit, same rule.

Source points: data/9t/derived/smrf05/_laz (2019 USGS 3DEP D20, all returns kept). Pits within 35 m of a tile edge are skipped.

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_void_block_scan_9t.py
"""
from __future__ import annotations

import glob
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds as tb
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
OUT = ROOT / "data/9t/results/pit"
D1 = ROOT / "data/9t/derived/1m"
R = 15.0
MARGIN = 35.0
rng = np.random.default_rng(7)

chm, dsm, dem = (rasterio.open(D1 / f"{k}_9t_1m.tif") for k in ("chm", "dsm", "dem"))


def win(src, x, y, h):
    return src.read(1, window=from_bounds(x - h, y - h, x + h, y + h, transform=src.transform), boundless=True, fill_value=np.nan).astype("float32")


def block_found(x, y, excl=None, h=R + 3):
    hag = win(dsm, x, y, h) - win(dem, x, y, h)
    n = hag.shape[0]
    t = tb(x - h, y - h, x + h, y + h, n, n)
    yy, xx = np.mgrid[:n, :n]
    disc = np.hypot(yy - n / 2 + 0.5, xx - n / 2 + 0.5) <= R
    if excl is not None:
        disc &= ~rasterize([(excl, 1)], out_shape=(n, n), transform=t).astype(bool)
    cand = (hag > 0.8) & (hag < 2.5) & disc
    lab, k = ndi.label(cand)
    for i in range(1, k + 1):
        m = lab == i
        if 4 <= m.sum() <= 16:
            border = ndi.binary_dilation(m) & ~m
            top = hag[m]
            if np.nanmedian(hag[border]) < 0.3 and np.nanstd(top) < 0.15 and np.ptp(top) < 0.4:
                return True
    return False


def cover(x, y, h):
    a = win(chm, x, y, h)
    return float(np.nanmean(a > 2.0))


def main():
    pi = gpd.read_file(G, layer="pit_inside")
    pf = gpd.read_file(G, layer="pit_full").dropna(subset=["pit_inside_id"]).set_index("pit_inside_id").geometry
    tiles = []
    for f in sorted(glob.glob(str(ROOT / "data/9t/derived/smrf05/_laz/*.laz"))):
        h = laspy.open(f).header
        tiles.append((f, h.mins[0], h.mins[1], h.maxs[0], h.maxs[1]))
    rows = []
    for f, x0, y0, x1, y1 in tiles:
        sel = pi[pi.geometry.centroid.apply(lambda p: x0 + MARGIN < p.x < x1 - MARGIN and y0 + MARGIN < p.y < y1 - MARGIN)]
        if sel.empty:
            continue
        las = laspy.read(f)
        tree = cKDTree(np.c_[np.asarray(las.x), np.asarray(las.y)])
        for _, r in sel.iterrows():
            x, y = r.geometry.centroid.coords[0]
            a_in = r.geometry.area
            idx_in = tree.query_ball_point([x, y], np.sqrt(a_in / np.pi) * 2.5 + 3)
            P = np.c_[np.asarray(las.x)[idx_in], np.asarray(las.y)[idx_in]]
            n_in = int(sum(r.geometry.covers(Point(p)) for p in P))
            idx_r = tree.query_ball_point([x, y], 30)
            idx_r0 = tree.query_ball_point([x, y], 10)
            n_ring = len(idx_r) - len(idx_r0)
            ring_area = np.pi * (30 ** 2 - 10 ** 2)
            dens_in = n_in / a_in
            dens_ring = n_ring / ring_area
            void = a_in >= 15 and n_ring >= 200 and dens_in < 0.2 * dens_ring
            op = cover(x, y, np.sqrt(a_in / np.pi) + 8) < 0.3
            ex = pf.get(r.pit_inside_id)
            rows.append(dict(pit_inside_id=int(r.pit_inside_id), area=a_in, dens_in=dens_in, dens_ring=dens_ring, void=void,
                             open_sky=op, block=block_found(x, y, ex)))
        print(f"{Path(f).name}: {len(sel)} pits", flush=True)
    D = pd.DataFrame(rows)
    D.to_csv(OUT / "pit_void_block_scan_9t.csv", index=False)
    print("pits scanned", len(D))
    print(pd.crosstab([D.void, D.open_sky], D.block, margins=True))
    # controls: random open-sky discs far from any pit
    pts = [(r.geometry.centroid.x, r.geometry.centroid.y) for _, r in pi.iterrows()]
    tree_p = cKDTree(pts)
    ctrl = []
    xs0, ys0, xs1, ys1 = min(t[1] for t in tiles), min(t[2] for t in tiles), max(t[3] for t in tiles), max(t[4] for t in tiles)
    while len(ctrl) < 400:
        x, y = rng.uniform(xs0 + MARGIN, xs1 - MARGIN), rng.uniform(ys0 + MARGIN, ys1 - MARGIN)
        if tree_p.query([x, y])[0] < 40 or cover(x, y, R + 8) >= 0.3:
            continue
        ctrl.append(block_found(x, y))
    op = D[D.open_sky]
    print(f"controls (open sky, far from pits): {len(ctrl)}  block rate {np.mean(ctrl):.3f}")
    print(f"pits open sky: {len(op)}  block rate {op.block.mean():.3f}")
    for v, g in op.groupby("void"):
        print(f"  void={v}: n {len(g)}  block rate {g.block.mean():.3f}")


if __name__ == "__main__":
    main()

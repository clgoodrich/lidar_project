"""Bake-off of SEVERAL distinct road-extraction algorithms on the same prob.

Motivation: the current pipeline (sato vesselness -> otsu -> lee -> LCP bridge)
invents roads/linkages where there are none. Three culprits: LCP bridging draws
links across real gaps, Sato vesselness turns hillslope texture into line-like
"roads", and Otsu is a low (recall-favoring) threshold. This runs separate
methods on the SAME recall-model prob and scores each on the 9t held-out test
(where CORRECTNESS = "are we drawing roads that aren't there") + renders a
613590 panel grid for visual judgement.

Methods span the two axes that create false roads:
  enhancement   : none  vs  sato vesselness
  reconnection  : none  vs  strict-LCP (short/collinear/high-prob only)  vs  LCP(default)

CLI:  python notebooks/wellsight/build/_road_methods_compare.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _road_optimize as ro  # enhance/to_mask/skeleton/lines_from_skel/prune_merge/reconnect/island_filter/score
from _common import DERIV, DST_CRS

R9 = DERIV / "tiles" / "9t"
RECALL = R9 / "road_unet_1m_recall"
BLK = DERIV / "tiles" / "data_3x3" / "westernpa_d20" / "613590"

# Distinct methods. reconnect tuple = (method, max_gap, max_ang, gate).
METHODS = {
    "A_conservative_nobridge": dict(
        enhance="none", thresh="global", t=0.60, skel="lee", spur=25,
        reconnect=("none",), island=150, min_px=80),
    "B_hysteresis_nobridge": dict(
        enhance="none", thresh="hysteresis", lo=0.50, hi=0.70, skel="lee", spur=25,
        reconnect=("none",), island=120, min_px=60),
    "C_strict_lcp": dict(
        enhance="none", thresh="hysteresis", lo=0.50, hi=0.70, skel="lee", spur=25,
        reconnect=("lcp", 18, 22, 1.6), island=120, min_px=60),
    "D_current_sato_otsu_lcp": dict(
        enhance="sato", thresh="otsu", t=0.5, hi=0.6, lo=0.4, skel="lee", spur=20,
        reconnect=("lcp", 35, 40, 3.0), island=80, min_px=40),
}


def run(D, cfg):
    E = ro.enhance(D["prob"], cfg["enhance"])
    mask = ro.to_mask(E, D["prob"], D["arg"], D["slope"], cfg)
    if mask.sum() == 0:
        return gpd.GeoDataFrame(geometry=[], crs=DST_CRS), 0
    skel = ro.skeleton(mask, cfg["skel"])
    lines = ro.lines_from_skel(skel, D["tf"])
    segs = ro.prune_merge(lines, cfg.get("spur", 20))
    rc = cfg["reconnect"]
    if rc[0] != "none":
        kw = dict(max_gap=rc[1], max_ang=rc[2], gate=rc[3]) if len(rc) > 1 else {}
        segs, bridges = ro.reconnect(segs, D["prob"], D["tf"], D["res"], rc[0], **kw)
        nb = len(bridges)
    else:
        nb = 0
    segs = ro.prune_merge(segs, 0.1)
    segs = ro.island_filter(segs, cfg.get("island", 120))
    return gpd.GeoDataFrame(geometry=segs, crs=DST_CRS), nb


def load_9t_recall():
    with rasterio.open(RECALL / "road_prob.tif") as r:
        prob = r.read(1).astype(np.float32); tf = r.transform; crs = r.crs; res = r.res[0]
    arg = None
    ap = RECALL / "road_argmax.tif"
    if ap.exists():
        with rasterio.open(ap) as r:
            arg = r.read(1)
    sl = None
    sp = R9.parent / "9t_1m" / "slope_9t_1m.tif"
    if sp.exists():
        with rasterio.open(sp) as r:
            sl = r.read(1).astype(np.float32)
    blocks = gpd.read_file(R9 / "pit_blocks_9t.gpkg")
    test = blocks[blocks.split == "test"]
    region = unary_union(test.geometry.values)
    gt = gpd.read_file(DERIV / "annotations" / "annotations_proj.gpkg", layer="roads").to_crs(DST_CRS)
    gt = gt[gt.intersects(region)].copy()
    gt["geometry"] = gt.geometry.intersection(region)
    gt = gt[~gt.is_empty]
    return dict(prob=prob, arg=arg, slope=sl, tf=tf, crs=crs, res=res, region=region, gt=gt)


def load_613590():
    with rasterio.open(BLK / "road_prob_613590_1m.tif") as r:
        prob = r.read(1).astype(np.float32); tf = r.transform; crs = r.crs; res = r.res[0]
    with rasterio.open(BLK / "drainage_prob_613590_1m.tif") as r:
        pdr = np.clip(r.read(1).astype(np.float32), 0, 1)
    pr = np.clip(prob, 0, 1); pbg = np.clip(1 - pr - pdr, 0, 1)
    arg = np.argmax(np.stack([pbg, pr, pdr]), axis=0).astype(np.uint8)
    sl = None
    sp = BLK / "slope_613590_1m.tif"
    if sp.exists():
        with rasterio.open(sp) as r:
            sl = r.read(1).astype(np.float32)
    return dict(prob=prob, arg=arg, slope=sl, tf=tf, crs=crs, res=res)


def main() -> int:
    print("=== 9t held-out test (CORRECTNESS = not drawing fake roads) ===")
    D9 = load_9t_recall()
    print(f"{'method':28s} {'comp':>6} {'corr':>6} {'f1':>6} {'qual':>6} {'km':>7} {'segs':>5} {'brdg':>5}")
    rows = {}
    for name, cfg in METHODS.items():
        gdf, nb = run(D9, cfg)
        s = ro.score(D9, gdf)
        rows[name] = (s, nb)
        print(f"{name:28s} {s['comp']:6.3f} {s['corr']:6.3f} {s['f1']:6.3f} "
              f"{s['quality']:6.3f} {s['km']:7.2f} {s['n']:5d} {nb:5d}")

    # 613590 panel grid + km
    print("\n=== 613590 (no full GT; visual + km/bridges) ===")
    Db = load_613590()
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from rasterio.enums import Resampling
    ds = 4
    with rasterio.open(BLK / "hillshade_613590_1m.tif") as r:
        H, W = r.height, r.width
        hs = r.read(1, out_shape=(H // ds, W // ds), resampling=Resampling.nearest); b = r.bounds
    ext = (b.left, b.right, b.bottom, b.top)
    fig, axes = plt.subplots(2, 2, figsize=(22, 22))
    for ax, (name, cfg) in zip(axes.ravel(), METHODS.items()):
        gdf, nb = run(Db, cfg)
        km = float(gdf.length.sum()) / 1000 if len(gdf) else 0.0
        ax.imshow(hs, cmap="gray", extent=ext, origin="upper"); ax.set_xticks([]); ax.set_yticks([])
        if len(gdf):
            gdf.plot(ax=ax, color="#ff2d2d", linewidth=0.9)
        ax.set_title(f"{name}\n{km:.1f} km, {len(gdf)} segs, {nb} bridges", fontsize=13)
        print(f"  {name:28s} {km:7.2f} km  {len(gdf):5d} segs  {nb:4d} bridges")
    out = BLK / "road_methods_compare_613590.png"
    fig.savefig(out, dpi=80, bbox_inches="tight"); plt.close(fig)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

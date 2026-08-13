"""Score every segment of the two hand-drawn exemplar shapefiles.

bold_roads.shp and faint_roads.shp are the annotator's own lines -- the labels,
not the network. This chops each of them into ~50 m segments (the same scored
unit `_classify_9t_roads_bold_faint.py` uses on roads.shp), measures the same
seven terrain features plus the road model's P(road), and writes one row per
segment with its class.

Two things make this comparable to the network run rather than a separate scale:

  * The MAD floors are computed on the 9t roads.shp network and PASSED IN, so
    both score sets divide by the same per-raster floor. Computing them here
    independently shifted `opos` by ~25% on the transects that hit the floor.
  * MIN_LEN is dropped to 5 m for this pass only. The classifier's 20 m floor
    exists to keep the scored unit statistically meaningful; here the ask is
    every segment in the shapefiles, so short exemplars are kept and flagged
    via `n_transects` instead of being silently dropped.

Output:
  data/derivatives/experiments/road_morphology_bins/
      bold_faint_exemplar_segments_9t_05_scores.csv
"""
import importlib.util
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.ops import unary_union

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "clf", HERE / "_classify_9t_roads_bold_faint.py")
clf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clf)

FEATS = clf.PANEL                      # the 7 terrain features, PRIMARY first
CSV = clf.OUT / "bold_faint_exemplar_segments_9t_05_scores.csv"
EXEMPLAR_MIN_LEN = 5.0


def main() -> int:
    clf.OUT.mkdir(parents=True, exist_ok=True)
    blocks = gpd.read_file(clf.R9 / "pit_blocks_9t.gpkg")
    region = unary_union(blocks.geometry.values)

    # ---- network pass, only to establish the shared MAD floors --------------
    net = gpd.read_file(clf.ANN / "roads.shp")
    net = (net.set_crs(4326) if net.crs is None else net).to_crs(clf.DST_CRS)
    net = net[net.intersects(region)].copy()
    net["geometry"] = net.geometry.intersection(region)
    net = net[~net.geometry.is_empty & net.geometry.length.gt(clf.MIN_LEN)]
    print(f"roads.shp -> 9t: {len(net)} roads, {net.length.sum()/1000:.2f} km "
          f"(floors reference only)")
    _, floors = clf.featurise(clf.segmentise(net.reset_index(drop=True)),
                              "9t network")
    print("  shared MAD floors: "
          + "  ".join(f"{k} {v:.4f}" for k, v in sorted(floors.items())))

    # ---- the exemplars ------------------------------------------------------
    clf.MIN_LEN = EXEMPLAR_MIN_LEN     # segmentise() reads this at call time
    frames = []
    for name, cls in (("bold_roads", "bold"), ("faint_roads", "faint")):
        g = gpd.read_file(clf.ANN / f"{name}.shp")
        g = (g.set_crs(4326) if g.crs is None else g).to_crs(clf.DST_CRS)
        n_all = len(g)
        g = g[g.intersects(region)].copy()
        g["geometry"] = g.geometry.intersection(region)
        g = g[~g.geometry.is_empty].reset_index(drop=True)
        g["src_line"] = g.index.values
        print(f"\n{name}.shp: {n_all} lines, {len(g)} intersect 9t, "
              f"{g.length.sum()/1000:.3f} km")

        segs = clf.segmentise(g)
        segs = segs.rename(columns={"parent_road": "src_line"})
        segs["class"] = cls
        segs["src_file"] = f"{name}.shp"
        feat, _ = clf.featurise(segs, f"{name} segments", floors=floors)
        segs = segs.join(feat, how="left")
        frames.append(segs)

    out = pd.concat(frames, ignore_index=True)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=clf.DST_CRS)

    # ---- model response -----------------------------------------------------
    pr = clf.path_for("models") / "road" / "unet_1m_recall" / "road_prob.tif"
    if pr.exists():
        with rasterio.open(pr) as s:
            pa = s.read(1).astype(np.float32)
            pinv, PH, PW = ~s.transform, *pa.shape
        def pmean(geom, step=3.0):
            n = max(2, int(geom.length / step))
            vv = []
            for t in np.linspace(0, 1, n):
                q = geom.interpolate(t, normalized=True)
                c, r = pinv * (q.x, q.y)
                r, c = int(r), int(c)
                if 0 <= r < PH and 0 <= c < PW and pa[r, c] >= 0:
                    vv.append(pa[r, c])
            return float(np.mean(vv)) if vv else np.nan
        out["P_road"] = [pmean(x) for x in out.geometry]
        del pa
    else:
        print(f"\n!! {pr} missing -- P_road left empty")
        out["P_road"] = np.nan

    # ---- tidy ---------------------------------------------------------------
    xy = out.geometry.centroid
    out["mid_x"] = xy.x.round(2)
    out["mid_y"] = xy.y.round(2)
    out["length_m"] = out.length.round(2)
    out["seg_id"] = [f"{c[0]}{i:04d}" for i, c in
                     enumerate(out["class"].values)]
    for c in FEATS + ["P_road"]:
        out[c] = out[c].round(4)

    cols = (["seg_id", "class", "src_file", "src_line", "length_m",
             "n_transects", "mid_x", "mid_y", "P_road"] + FEATS)
    tbl = pd.DataFrame(out[cols])
    tbl.to_csv(CSV, index=False)

    print(f"\nwrote {CSV}")
    print(f"  {len(tbl)} segments   "
          + "   ".join(f"{k} {v}" for k, v in
                       tbl['class'].value_counts().items()))
    print(f"  CRS of mid_x/mid_y: {clf.DST_CRS}")
    print(f"\n  median by class:")
    print(tbl.groupby("class")[["P_road"] + FEATS].median().T.round(3)
          .to_string())
    short = (tbl.n_transects < 5).sum()
    print(f"\n  segments with <5 transects (short lines, noisier): {short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

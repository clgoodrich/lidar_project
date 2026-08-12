"""Post-filter v3 road centerlines:
  - drop polylines with BOTH endpoints near the data boundary (tile-edge sato
    artifacts that propagated inward via the gaussian wrap of LRM_15)
  - drop "implausibly straight" long polylines (length > 300 m AND
    straightness > 0.93) — real forest roads in this terrain curve

Also re-renders the overlay PNG with the cleaned set.
"""
import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV

OUT_DIR = DERIV / "experiments" / "roads"

COLORS = {
    "lrm5_dark":     "#e41a1c",
    "lrm5_bright":   "#ff7f00",
    "lrm15_dark":    "#984ea3",
    "lrm15_bright":  "#a65628",
    "rough_strip":   "#4daf4a",
    "canopy_gap":    "#00ced1",
    "density_strip": "#ffd700",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", required=True)
    ap.add_argument("--edge-buffer-m", type=float, default=80.0,
                    help="kill polylines whose BOTH endpoints are within this "
                         "distance of the data boundary")
    ap.add_argument("--max-straight-long", type=float, default=0.93,
                    help="drop polylines longer than --long-thresh with "
                         "straightness above this")
    ap.add_argument("--long-thresh-m", type=float, default=300.0)
    args = ap.parse_args()

    suf = args.tile
    gpkg = OUT_DIR / f"roads_{suf}.gpkg"
    dem_p = DERIV / f"dem_{suf}_1m.tif"
    hs_p  = DERIV / f"hillshade_{suf}_1m.tif"

    g = gpd.read_file(gpkg, layer="centerlines")
    print(f"input polylines: {len(g)}")

    # Build a binary validity raster from DEM, then a distance-from-boundary
    # raster. Edge endpoints are those whose distance < edge_buffer_m.
    with rasterio.open(dem_p) as ds:
        a = ds.read(1)
        nd = ds.nodata
        valid = (a != nd) if nd is not None else np.ones_like(a, dtype=bool)
        transform = ds.transform
        H, W = a.shape

    # Distance (in pixels) from invalid → valid pixels = how far inside valid
    dist_in = ndi.distance_transform_edt(valid).astype(np.float32)

    def endpoint_dist_m(geom):
        c = list(geom.coords)
        p0, p1 = c[0], c[-1]
        # World -> pixel
        def to_px(pt):
            col = int((pt[0] - transform.c) / transform.a)
            row = int((pt[1] - transform.f) / transform.e)
            return max(0, min(H - 1, row)), max(0, min(W - 1, col))
        r0, c0 = to_px(p0); r1, c1 = to_px(p1)
        return float(dist_in[r0, c0]), float(dist_in[r1, c1])

    dists = g.geometry.apply(endpoint_dist_m)
    g["edge_d0_m"] = dists.apply(lambda t: t[0])
    g["edge_d1_m"] = dists.apply(lambda t: t[1])

    both_edge = (g["edge_d0_m"] < args.edge_buffer_m) & (g["edge_d1_m"] < args.edge_buffer_m)
    too_straight = (g["length_m"] > args.long_thresh_m) & (g["straightness"] > args.max_straight_long)

    drop = both_edge | too_straight
    print(f"  drop both-edge:      {both_edge.sum()}")
    print(f"  drop too-straight:   {too_straight.sum()}")
    print(f"  drop union:          {drop.sum()}")

    keep = g[~drop].drop(columns=["edge_d0_m", "edge_d1_m"]).reset_index(drop=True)
    print(f"output polylines: {len(keep)}")
    print(f"output total length: {keep['length_m'].sum()/1000:.2f} km")

    out_gpkg = OUT_DIR / f"roads_{suf}_clean.gpkg"
    keep.to_file(out_gpkg, layer="centerlines", driver="GPKG")
    print(f"wrote {out_gpkg}")

    # Re-render overlay
    with rasterio.open(hs_p) as ds:
        hs = ds.read(1)
        tr = ds.transform
    ext = [tr.c, tr.c + hs.shape[1] * abs(tr.a),
           tr.f + hs.shape[0] * tr.e, tr.f]
    fig, ax = plt.subplots(1, 1, figsize=(14, 14), dpi=140)
    ax.imshow(hs, cmap="gray", extent=ext, interpolation="nearest")
    for ch, sub in keep.groupby("dom_channel"):
        col = COLORS.get(ch, "yellow")
        for ls in sub.geometry:
            x, y = ls.xy
            ax.plot(x, y, color=col, linewidth=0.85, alpha=0.95)
    handles = [Line2D([0], [0], color=c, lw=2, label=k)
               for k, c in COLORS.items() if k in keep["dom_channel"].values]
    ax.legend(handles=handles, loc="lower right", framealpha=0.85, fontsize=9)
    ax.set_title(f"Linear features (v3, post-filtered) — {suf}  "
                 f"n={len(keep)}  {keep['length_m'].sum()/1000:.1f} km")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    ax.set_aspect("equal")
    png = OUT_DIR / f"roads_overlay_{suf}_clean.png"
    fig.savefig(png, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png}")


if __name__ == "__main__":
    main()

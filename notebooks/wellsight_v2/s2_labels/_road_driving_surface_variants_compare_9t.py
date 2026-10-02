"""Compare the road driving-surface watershed variants on 9t: how much of each result comes from
the user's shapefiles and how much from the terrain.

Variants (all full 9t, produced by _road_driving_surface_watershed_9t.py):
  hybrid band 2 m, corridor 6 m   reference
  hybrid band 4 m                 more of each pad edge left to the terrain
  hybrid corridor 8 m             road edges may run farther before being capped
  model seeds                     road and pad seeds from the road / pad models, no shapefile seeds

Outputs
  data/9t/results/road/driving_surface/road_driving_surface_watershed_variants_compare_9t_05.csv
  data/9t/results/road/driving_surface/road_driving_surface_watershed_corridor6m_vs_8m_station_widths_9t_05.csv
  data/9t/results/road/driving_surface/figures/road_driving_surface_watershed_variants_compare_crossings_and_pads_on_hillshade_9t_05.png

  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_variants_compare_9t.py
  python notebooks/wellsight_v2/s2_labels/_road_driving_surface_variants_compare_9t.py --merged   # one-class fill vs hybrid
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import box

REPO = Path(__file__).resolve().parents[3]
RES = REPO / "data" / "9t" / "results" / "road" / "driving_surface"
HILLSHADE = REPO / "data" / "9t" / "derived" / "05" / "hillshade_9t_05.tif"
ANN = REPO / "qgis" / "annotations" / "annotations_proj.gpkg"
CRS = "EPSG:6346"
PRE = "road_driving_surface_watershed_"
VARIANTS = {
    "reference: band 2 m, corridor 6 m": "bg6m_slope25deg_padhybrid_band2m",
    "pad band 4 m": "bg6m_slope25deg_padhybrid_band4m",
    "corridor 8 m": "bg8m_slope25deg_padhybrid_band2m",
    "model seeds": "bg6m_slope25deg_padhybrid_band2m_seedmodel_roadthr0p20_padthr0p45",
}
# lost/found trio, dataviz validate_palette.js --mode light --pairs all: worst pair #A31515/#D97706
# dE 21.1 deutan, 22.6 normal. Line styles differ as well, so colour is never the only cue.
STYLE = {
    "reference: band 2 m, corridor 6 m": ("#1F5FA8", "-"),
    "pad band 4 m": ("#D97706", "--"),
    "corridor 8 m": ("#D97706", "--"),
    "model seeds": ("#A31515", "-."),
}
INK, MUTED = "#2B2F36", "#5B6168"


def load(tag, layer):
    p = RES / f"{PRE}{tag}_full_9t_05.gpkg"
    return gpd.read_file(p, layer=layer)


def main():
    roads = gpd.read_file(ANN, layer="roads").to_crs(CRS)
    pads = gpd.read_file(ANN, layer="plat").to_crs(CRS)
    with rasterio.open(HILLSHADE) as hs:
        tile = box(*hs.bounds)
    roads = roads[roads.intersects(tile)]
    pads = pads[pads.intersects(tile)]
    road_line = roads.geometry.intersection(tile).union_all()
    pads_u = pads.geometry.union_all()
    road_corr = road_line.buffer(6.0)

    rows, geo = [], {}
    for name, tag in VARIANTS.items():
        s = json.load(open(RES / f"{PRE}{tag}_full_9t_05_summary.json"))
        rd = load(tag, "driving_surface").geometry.union_all()
        pd_ = load(tag, "pad_surface").geometry.union_all()
        geo[name] = (rd, pd_)
        rows.append({
            "variant": name, "file_tag": tag,
            "road_area_ha": round(rd.area / 1e4, 2),
            "annotated_centreline_km_inside_road_polygon": round(road_line.intersection(rd).length / 1000, 1),
            "annotated_centreline_km_inside_road_or_pad": round(road_line.intersection(rd.union(pd_)).length / 1000, 1),
            "road_area_more_than_6m_from_annotated_centreline_ha": round(rd.difference(road_corr).area / 1e4, 2),
            "road_area_on_annotated_pads_ha": s["road_area_on_annotated_pads_ha"],
            "share_road_edges_capped": round((s["share_hit_limit_one_side"] + 2 * s["share_hit_limit_both_sides"]) / 2, 3),
            "median_width_both_edges_found_m": s["median_width_where_no_limit_hit"],
            "pad_area_ha": round(pd_.area / 1e4, 2),
            "pad_area_outside_annotated_pads_ha": round(pd_.difference(pads_u).area / 1e4, 2),
            "annotated_pad_area_covered_ha": round(pd_.intersection(pads_u).area / 1e4, 2),
            "pad_iou_vs_annotation_median": s["pad_iou_vs_annotation_median"],
            "pad_iou_vs_annotation_p10": s["pad_iou_vs_annotation_p10"],
        })
    comp = pd.DataFrame(rows)
    comp.insert(2, "annotated_centreline_km", round(road_line.length / 1000, 1))
    comp.insert(3, "annotated_pad_area_ha", round(pads_u.area / 1e4, 2))
    comp.to_csv(RES / f"{PRE}variants_compare_9t_05.csv", index=False)
    print(comp.T.to_string())

    # station by station: do edges the 6 m run called "found" stay put when the corridor is 8 m?
    a = pd.read_csv(RES / f"{PRE}{VARIANTS['reference: band 2 m, corridor 6 m']}_full_9t_05_transect_widths_every5m.csv")
    b = pd.read_csv(RES / f"{PRE}{VARIANTS['corridor 8 m']}_full_9t_05_transect_widths_every5m.csv")
    assert len(a) == len(b) and np.allclose(a.x, b.x) and np.allclose(a.y, b.y)
    st = pd.DataFrame({"road_fid": a.road_fid, "x": a.x, "y": a.y,
                       "width_6m": a.width_m, "width_8m": b.width_m,
                       "capped_6m": a.hit_limit_any, "capped_8m": b.hit_limit_any,
                       "in_pad_core": a.station_in_pad_core})
    st["change_m"] = st.width_8m - st.width_6m
    st.to_csv(RES / f"{PRE}corridor6m_vs_8m_station_widths_9t_05.csv", index=False)
    ok = st[(st.width_6m > 0) & ~st.in_pad_core]
    found = ok[~ok.capped_6m]
    capped = ok[ok.capped_6m]
    print(f"\nstations with both edges found at 6 m: {len(found)}")
    for thr in (0.5, 1.0, 2.0):
        print(f"  widened by more than {thr} m at 8 m: {(found.change_m > thr).mean():.3f}")
    print(f"  unchanged (within 0.25 m): {(found.change_m.abs() <= 0.25).mean():.3f}")
    print(f"stations capped at 6 m: {len(capped)}; capped again at 8 m: {capped.capped_8m.mean():.3f}; "
          f"median widening {capped.change_m.median():.2f} m")

    # figure: three test-line road crossings (corridor and model variants) and three pads (band and model)
    cross = pd.read_csv(RES / f"{PRE}{VARIANTS['reference: band 2 m, corridor 6 m']}_full_9t_05_test_line_crossings.csv")
    cross = cross[cross.line.isin([2, 3]) | ((cross.line == 4) & (cross.centreline_at_m > 250))].head(3)
    ref_p, b4_p = geo["reference: band 2 m, corridor 6 m"][1], geo["pad band 4 m"][1]
    pp = pads.copy()
    pp["d"] = [abs(g.intersection(ref_p).area - g.buffer(4).intersection(b4_p).area) for g in pp.geometry]
    pick = pp.sort_values("d", ascending=False).head(3)

    fig, axs = plt.subplots(2, 3, figsize=(13.2, 9.8), squeeze=False, gridspec_kw={"hspace": 0.2})
    with rasterio.open(HILLSHADE) as hs:
        def base(ax, cx, cy, half):
            bb = (cx - half, cy - half, cx + half, cy + half)
            w = rasterio.windows.from_bounds(*bb, transform=hs.transform)
            ax.imshow(hs.read(1, window=w, boundless=True), cmap="gray",
                      extent=(bb[0], bb[2], bb[1], bb[3]), interpolation="nearest")
            ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_xticks([]); ax.set_yticks([])
            return box(*bb)

        for ax, (_, c) in zip(axs[0], cross.iterrows()):
            cl = base(ax, c.x, c.y, 25.0)
            for name in ("reference: band 2 m, corridor 6 m", "corridor 8 m", "model seeds"):
                col, ls = STYLE[name]
                gpd.GeoSeries([geo[name][0]], crs=CRS).clip(cl).boundary.plot(ax=ax, color=col, lw=1.7, linestyle=ls)
            roads.clip(cl).plot(ax=ax, color=INK, lw=0.9, linestyle=":")
            ax.set_title(f"Road at test line {int(c.line)}, {c.centreline_at_m:.0f} m", fontsize=9.5, color=INK, loc="left")
        for ax, (_, pr) in zip(axs[1], pick.iterrows()):
            g = pr.geometry
            half = max(30.0, 0.5 * max(g.bounds[2] - g.bounds[0], g.bounds[3] - g.bounds[1]) + 15)
            cl = base(ax, g.centroid.x, g.centroid.y, half)
            for name in ("reference: band 2 m, corridor 6 m", "pad band 4 m", "model seeds"):
                col, ls = STYLE[name]
                gpd.GeoSeries([geo[name][1]], crs=CRS).clip(cl).boundary.plot(ax=ax, color=col, lw=1.7, linestyle=ls)
            gpd.GeoSeries([g], crs=CRS).boundary.plot(ax=ax, color=INK, lw=0.9, linestyle=":")
            ax.set_title("Pad edge, one of the three that changed most at band 4 m", fontsize=9.5, color=INK, loc="left")
    fig.suptitle("Driving-surface variants: road edges (top) and pad edges (bottom)", x=0.02, ha="left",
                 fontsize=12, color=INK)
    fig.text(0.02, 0.012, "Solid blue: reference (pad band 2 m, corridor 6 m).  Dashed orange: top row corridor 8 m, "
             "bottom row pad band 4 m.  Dash-dot red: seeds from the road and pad models.  "
             "Dotted charcoal: your annotation.", fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.05, wspace=0.05)
    out = RES / "figures" / f"{PRE}variants_compare_crossings_and_pads_on_hillshade_9t_05.png"
    fig.savefig(out, dpi=170, facecolor="white")
    print("wrote", out)




def merged_vs_hybrid():
    """One-class fill (--pad-mode merged) against the hybrid road + pad union: where do they differ?"""
    ref = VARIANTS["reference: band 2 m, corridor 6 m"]
    mtag = "bg6m_slope25deg_padmerged_band2m"
    hyb = load(ref, "driving_surface").geometry.union_all().union(load(ref, "pad_surface").geometry.union_all())
    mer = load(mtag, "driving_surface").geometry.union_all()
    only_m, only_h = mer.difference(hyb), hyb.difference(mer)
    out = {"merged_area_ha": round(mer.area / 1e4, 2), "hybrid_road_plus_pad_area_ha": round(hyb.area / 1e4, 2),
           "only_in_merged_ha": round(only_m.area / 1e4, 2), "only_in_hybrid_ha": round(only_h.area / 1e4, 2),
           "agreement_iou": round(mer.intersection(hyb).area / mer.union(hyb).area, 4)}
    pieces = gpd.GeoDataFrame(geometry=[g for d in (only_m, only_h) for g in getattr(d, "geoms", [d])], crs=CRS)
    pieces["src"] = ["merged"] * len(getattr(only_m, "geoms", [only_m])) + ["hybrid"] * len(getattr(only_h, "geoms", [only_h]))
    pieces["area_m2"] = pieces.area
    out["difference_patches_over_10m2"] = int((pieces.area_m2 > 10).sum())
    out["largest_difference_patches_m2"] = [round(a, 1) for a in pieces.area_m2.nlargest(6)]
    print(json.dumps(out, indent=2))
    with open(RES / f"{PRE}{mtag}_vs_padhybrid_band2m_full_9t_05_summary.json", "w") as fh:
        json.dump(out, fh, indent=2)
    pick = pieces.nlargest(6, "area_m2")
    fig, axs = plt.subplots(2, 3, figsize=(13.2, 9.8), squeeze=False, gridspec_kw={"hspace": 0.2})
    with rasterio.open(HILLSHADE) as hs:
        for ax, (_, r) in zip(axs.ravel(), pick.iterrows()):
            c = r.geometry.centroid
            half = 30.0
            bb = (c.x - half, c.y - half, c.x + half, c.y + half)
            w = rasterio.windows.from_bounds(*bb, transform=hs.transform)
            ax.imshow(hs.read(1, window=w, boundless=True), cmap="gray",
                      extent=(bb[0], bb[2], bb[1], bb[3]), interpolation="nearest")
            cl = box(*bb)
            gpd.GeoSeries([hyb], crs=CRS).clip(cl).boundary.plot(ax=ax, color="#1F5FA8", lw=1.7)
            gpd.GeoSeries([mer], crs=CRS).clip(cl).boundary.plot(ax=ax, color="#D97706", lw=1.7, linestyle="--")
            ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3]); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"{r.area_m2:.0f} m² only in {r.src}", fontsize=9.5, color=INK, loc="left")
    fig.suptitle("One-class fill against roads and pads filled separately: the six largest differences",
                 x=0.02, ha="left", fontsize=12, color=INK)
    fig.text(0.02, 0.012, "Solid blue: road and pad filled as separate classes (hybrid), outer edge.  "
             "Dashed orange: one class for both (merged).", fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.05, wspace=0.05)
    fp = RES / "figures" / f"{PRE}{mtag}_vs_padhybrid_band2m_largest_differences_on_hillshade_9t_05.png"
    fig.savefig(fp, dpi=170, facecolor="white")
    print("wrote", fp)


if __name__ == "__main__":
    import sys
    merged_vs_hybrid() if "--merged" in sys.argv else main()

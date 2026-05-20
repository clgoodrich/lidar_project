"""Iter 05c — line-through-polygon road filter.

Cleaner alternative to iter 05b. Instead of buffering road lines and measuring
"fraction of pit polygon inside the buffer", we directly ask:

  Does the road centerline pass THROUGH the predicted pit polygon?

For each connected pit component:
  1. Polygonize the component.
  2. Intersect it with each road / not_road line.
  3. Sum the line-meters that lie inside the polygon.
  4. Compute: passes_through = (intersection_length >= MIN_THROUGH_M)
            cross_fraction  = intersection_length / polygon equivalent-diameter
            (helps catch small components where any crossing is suspicious)

Drop a component if EITHER:
  - passes_through (line spends MIN_THROUGH_M+ meters inside the polygon)
  - cross_fraction > FRAC_T (line crosses a substantial portion of the polygon's extent)

Also keep the iter 05 probabilistic rules (road_max / road_mean from road_unet) as an OR.

Outputs land in data/derivatives/9t/iterations/05c_road_intersect/.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from scipy import ndimage
import geopandas as gpd
from shapely.geometry import shape, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUTDIR = D / "iterations" / "05c_road_intersect"; OUTDIR.mkdir(parents=True, exist_ok=True)

PIT_ARGMAX = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_argmax.tif"
PIT_PROB_FLOOR = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_prob_floor.tif"
PIT_PROB_WALL = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_prob_wall.tif"
ROAD_PROB = D / "road_unet" / "road_prob.tif"
LABELS = D / "labels_pit_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "pit_dataset_manifest.csv"

PX_M2 = 0.25
MIN_AREA_M2 = 4.0


def polygonize_component(cc, cid, tf):
    mask = (cc == cid).astype(np.uint8)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None, None
    r0, r1 = ys.min(), ys.max() + 1
    c0, c1 = xs.min(), xs.max() + 1
    local = mask[r0:r1, c0:c1]
    sub_tf = rasterio.transform.from_bounds(
        tf.c + c0 * tf.a, tf.f + r1 * tf.e,
        tf.c + c1 * tf.a, tf.f + r0 * tf.e,
        c1 - c0, r1 - r0)
    sh = list(shapes(local, mask=local.astype(bool), transform=sub_tf))
    if not sh:
        return None, None
    geom = unary_union([shape(s) for s, _ in sh])
    return geom, (r0, r1, c0, c1, ys, xs)


def component_stats(argmax, road_prob, road_lines, ref_transform):
    pit = (argmax == 1) | (argmax == 2)
    cc, n = ndimage.label(pit, structure=np.ones((3, 3)))
    print(f"  components: {n}")
    sizes_full = ndimage.sum(pit.astype(np.int32), cc, index=np.arange(1, n + 1))
    keep = sizes_full * PX_M2 >= MIN_AREA_M2
    cand = np.where(keep)[0] + 1

    # Spatial index over road lines for fast candidate-neighbour lookups
    line_geoms = list(road_lines.geometry)
    tree = STRtree(line_geoms)

    rows = []
    for cid in cand:
        geom, info = polygonize_component(cc, cid, ref_transform)
        if geom is None:
            continue
        r0, r1, c0, c1, ys, xs = info

        # Elongation via PCA on pixel coords
        ys_c = ys - ys.mean(); xs_c = xs - xs.mean()
        cov = np.cov(np.stack([ys_c, xs_c]))
        eigs = np.maximum(np.linalg.eigvalsh(cov), 1e-6)
        elong = float(np.sqrt(eigs[1] / eigs[0]))

        # Road prob inside the component (kept for backward-compat rules)
        rp_vals = road_prob[ys, xs]
        rp_vals = rp_vals[np.isfinite(rp_vals) & (rp_vals >= 0)]
        rp_max = float(rp_vals.max()) if len(rp_vals) else 0.0
        rp_mean = float(rp_vals.mean()) if len(rp_vals) else 0.0

        # Line-through-polygon intersection
        # STRtree returns candidate indices that share a bbox; intersection is the
        # actual geometric test.
        intersect_len_m = 0.0
        crossing_lines = 0
        for idx in tree.query(geom):
            line = line_geoms[idx]
            if geom.intersects(line):
                inter = geom.intersection(line)
                if not inter.is_empty:
                    intersect_len_m += float(inter.length)
                    crossing_lines += 1

        # Equivalent diameter (m) of a circle with the same area — gives a scale
        # to compare intersection length against the polygon's own size
        eq_diam_m = 2 * np.sqrt(geom.area / np.pi) if geom.area > 0 else 0.0
        cross_frac = intersect_len_m / eq_diam_m if eq_diam_m > 0 else 0.0

        rows.append({
            "cid": int(cid),
            "area_m2": float(geom.area),
            "elong": elong,
            "road_max": rp_max,
            "road_mean": rp_mean,
            "intersect_len_m": float(intersect_len_m),
            "n_lines_crossing": int(crossing_lines),
            "eq_diam_m": float(eq_diam_m),
            "cross_frac": float(cross_frac),
        })
    return cc, pd.DataFrame(rows)


def filter_mask(df, cfg):
    """Drop rules combine iter 05 prob rules with new line-intersect rules."""
    prob_drop = (
        ((df.elong >= cfg["elong_t"]) & (df.road_max >= cfg["road_max_t"]))
        | ((df.elong >= cfg["elong_t"]) & (df.road_mean >= cfg["road_mean_t"]))
        | ((df.area_m2 >= cfg["long_area_t"]) & (df.elong >= cfg["elong_big_t"]))
    )
    # New: line passes through polygon
    line_drop_through = df.intersect_len_m >= cfg["min_through_m"]
    line_drop_crossfrac = df.cross_frac >= cfg["cross_frac_t"]
    return prob_drop | line_drop_through | line_drop_crossfrac


def apply_filter(argmax_in, prob_floor_in, prob_wall_in, cc, drop_cids):
    drop_mask = np.isin(cc, np.array(list(drop_cids), dtype=cc.dtype))
    argmax_out = argmax_in.copy()
    argmax_out[drop_mask] = 0
    prob_floor_out = prob_floor_in.copy()
    prob_floor_out[drop_mask] = 0.0
    prob_wall_out = prob_wall_in.copy()
    prob_wall_out[drop_mask] = 0.0
    return argmax_out, prob_floor_out, prob_wall_out


def test_eval(argmax):
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    tbm = rasterize([(g, 1) for g in blocks[blocks.split == "test"].geometry],
                    out_shape=(H, W), transform=tf, fill=0, dtype="uint8").astype(bool)
    pix = {}
    for cls, name in [(1, "floor"), (2, "wall")]:
        p = (argmax == cls) & tbm; t = (labels == cls) & tbm
        inter = int((p & t).sum()); union = int((p | t).sum())
        pix[name] = inter / union if union else None
    man = pd.read_csv(MANIFEST)
    tp = man[man.split == "test"]
    pit_in = gpd.read_file(ANN, layer="pit_inside")
    rows = []
    for _, row in tp.iterrows():
        pid = int(row.pit_id)
        g = pit_in[pit_in.pit_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        pad = 6.0
        win = from_bounds(minx - pad, miny - pad, maxx + pad, maxy + pad, tf)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0: continue
        sub_lbl = labels[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]
        pit_t = (sub_lbl == 1) | (sub_lbl == 2)
        pit_p = (sub_pred == 1) | (sub_pred == 2)
        recall_any = float((pit_t & pit_p).sum() / max(pit_t.sum(), 1))
        inter = int((pit_t & pit_p).sum()); union = int((pit_t | pit_p).sum())
        loc_iou = inter / union if union else None
        rows.append({"pit_id": pid, "recall_any_pit": recall_any,
                     "pit_iou_local": loc_iou})
    df = pd.DataFrame(rows)
    return {
        "floor_pixel_iou": pix["floor"],
        "wall_pixel_iou": pix["wall"],
        "mean_pit_iou": float(df.pit_iou_local.mean()),
        "median_pit_iou": float(df.pit_iou_local.median()),
        "detected_ge_10pct": int((df.recall_any_pit > 0.1).sum()),
        "iou_gt_0.3": int((df.pit_iou_local.fillna(0) > 0.3).sum()),
        "n_test_pits": len(df),
    }


def write_argmax(argmax, prob_floor, prob_wall, suffix):
    with rasterio.open(LABELS) as r:
        profile = r.profile.copy()
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    with rasterio.open(OUTDIR / f"filtered_prob_floor_{suffix}.tif", "w", **p1) as d:
        d.write(prob_floor, 1)
    with rasterio.open(OUTDIR / f"filtered_prob_wall_{suffix}.tif", "w", **p1) as d:
        d.write(prob_wall, 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / f"filtered_argmax_{suffix}.tif", "w", **p2) as d:
        d.write(argmax, 1)


def dropped_to_gpkg(cc, drop_cids, df, suffix, ref_transform):
    if not drop_cids:
        return
    with rasterio.open(LABELS) as r:
        crs = r.crs
    polys = []
    for cid in drop_cids:
        geom, _ = polygonize_component(cc, cid, ref_transform)
        if geom is None: continue
        row = df[df.cid == cid].iloc[0]
        polys.append({
            "cid": int(cid),
            "area_m2": float(row.area_m2),
            "elong": float(row.elong),
            "road_max": float(row.road_max),
            "road_mean": float(row.road_mean),
            "intersect_len_m": float(row.intersect_len_m),
            "n_lines_crossing": int(row.n_lines_crossing),
            "cross_frac": float(row.cross_frac),
            "geometry": geom,
        })
    if polys:
        gpd.GeoDataFrame(polys, crs=crs).to_file(
            OUTDIR / f"components_dropped_{suffix}.gpkg", driver="GPKG")


def all_components_to_gpkg(cc, df, ref_transform):
    """Persist every analyzed component with all attributes (for QGIS triage)."""
    with rasterio.open(LABELS) as r:
        crs = r.crs
    polys = []
    for _, row in df.iterrows():
        geom, _ = polygonize_component(cc, int(row.cid), ref_transform)
        if geom is None: continue
        polys.append({
            "cid": int(row.cid),
            "area_m2": float(row.area_m2),
            "elong": float(row.elong),
            "road_max": float(row.road_max),
            "road_mean": float(row.road_mean),
            "intersect_len_m": float(row.intersect_len_m),
            "n_lines_crossing": int(row.n_lines_crossing),
            "cross_frac": float(row.cross_frac),
            "geometry": geom,
        })
    if polys:
        gpd.GeoDataFrame(polys, crs=crs).to_file(
            OUTDIR / "all_components.gpkg", driver="GPKG")


def main():
    print("Loading rasters...")
    with rasterio.open(PIT_ARGMAX) as r:
        argmax = r.read(1); tf = r.transform; H, W = r.height, r.width
    with rasterio.open(PIT_PROB_FLOOR) as r: pf = r.read(1)
    with rasterio.open(PIT_PROB_WALL) as r:  pw = r.read(1)
    with rasterio.open(ROAD_PROB) as r:      rp = r.read(1)

    # Stack roads + not_roads into one GeoDataFrame for the line-intersect test
    roads = gpd.read_file(ANN, layer="roads")
    not_roads = gpd.read_file(ANN, layer="not_roads")
    all_lines = gpd.GeoDataFrame(
        pd.concat([roads[["geometry"]].assign(kind="road"),
                   not_roads[["geometry"]].assign(kind="not_road")], ignore_index=True),
        crs=roads.crs)
    print(f"Road lines: {len(roads)} road + {len(not_roads)} not_road = {len(all_lines)} total")

    # How many labeled pits would a naive "drop if any line touches" rule clip?
    # (Sanity check on the line set itself.)
    pit_in = gpd.read_file(ANN, layer="pit_inside")
    n_pits_touched = sum(any(g.intersects(L) for L in all_lines.geometry) for g in pit_in.geometry)
    print(f"  labeled pits with ANY line passing through their polygon: {n_pits_touched}/{len(pit_in)}")

    print("\nComputing per-component stats (this includes line-intersect; takes ~30s)...")
    cc, df = component_stats(argmax, rp, all_lines, tf)
    print(f"  candidate components (area >= {MIN_AREA_M2} m^2): {len(df)}")

    # Save the all-components GPKG once for QGIS triage
    all_components_to_gpkg(cc, df, tf)
    print(f"  wrote all_components.gpkg ({len(df)} polygons with attrs)")

    # Distribution of new fields
    print("\nLine-intersect stats:")
    print(f"  components with ANY line crossing: {(df.intersect_len_m > 0).sum()}")
    print(f"  intersect_len_m percentiles: "
          f"50%={df.intersect_len_m.median():.2f}m  "
          f"90%={df.intersect_len_m.quantile(0.9):.2f}m  "
          f"max={df.intersect_len_m.max():.2f}m")

    print("\nBaseline (no filter):")
    base = test_eval(argmax)
    for k, v in base.items(): print(f"  {k:22s} {v}")

    summary = {"baseline": base, "configs": {}}
    rows_csv = [{"config": "baseline", **base, "n_dropped": 0}]

    # Configs sweep MIN_THROUGH_M and cross_frac_t. Probabilistic rules carried from iter 05.
    configs = [
        # name, elong_t, road_max_t, road_mean_t, long_area_t, elong_big_t, min_through_m, cross_frac_t
        ("v3_safe",       3.0, 0.50, 0.30, 60.0, 4.0, 2.0, 0.80),
        ("v3_moderate",   2.5, 0.40, 0.25, 40.0, 3.0, 1.0, 0.60),
        ("v3_aggressive", 2.0, 0.30, 0.20, 25.0, 2.5, 0.5, 0.40),
        # Line-intersect ONLY (no probabilistic rules at all)
        ("v3_line_only",  99,  1.01, 1.01, 1e9,  99,  1.0, 0.60),
    ]

    for name, elong_t, road_max_t, road_mean_t, long_area_t, elong_big_t, min_through_m, cross_frac_t in configs:
        cfg = dict(elong_t=elong_t, road_max_t=road_max_t, road_mean_t=road_mean_t,
                   long_area_t=long_area_t, elong_big_t=elong_big_t,
                   min_through_m=min_through_m, cross_frac_t=cross_frac_t)
        print(f"\nConfig '{name}': {cfg}")
        drop_series = filter_mask(df, cfg)
        drop_cids = list(df.loc[drop_series, "cid"].astype(int).values)
        print(f"  drop {len(drop_cids)} components, keep {(~drop_series).sum()}")

        amx, pfn, pwn = apply_filter(argmax, pf, pw, cc, drop_cids)
        write_argmax(amx, pfn, pwn, name)
        dropped_to_gpkg(cc, drop_cids, df, name, tf)
        m = test_eval(amx)
        print(f"  metrics after filter:")
        for k, v in m.items(): print(f"    {k:22s} {v}")

        summary["configs"][name] = {"cfg": cfg, "n_dropped": int(len(drop_cids)),
                                    "metrics": m}
        rows_csv.append({"config": name, **m, "n_dropped": int(len(drop_cids))})

    pd.DataFrame(rows_csv).to_csv(OUTDIR / "filter_v3_sweep_metrics.csv", index=False)
    (OUTDIR / "filter_v3_sweep_summary.json").write_text(
        json.dumps(summary, indent=2, default=float))
    print(f"\nOutputs in {OUTDIR}")


if __name__ == "__main__":
    main()

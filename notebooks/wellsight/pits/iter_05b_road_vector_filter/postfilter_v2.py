"""Iter 05b — road-aware post-filter v2 using BOTH road_unet probability AND
hand-drawn road centerlines.

Why this exists: iter 05 used only road_unet.road_prob, but the road U-Net has
gaps (test F1 ~0.97, line AP ~0.94 — close but not perfect). Components sitting
*on* a road centerline where the road U-Net is uncertain slipped through. The
user-flagged road_error.jpg shows exactly that pattern: two small elongated
pit FPs sitting on a road that the model under-confidence-scored.

The hand-drawn roads.shp and not_roads.shp don't have those gaps. We layer them
in as a second drop signal:
  - Buffer every road and not_road line by R_BUFFER meters.
  - For each pit component:
       on_road_buffer = (component centroid OR > X% of component area) inside any buffered line
  - Drop a component if it's BOTH (elongated OR small-and-narrow) AND on_road_buffer.

Combined with the iter 05 road_prob rules, this fills both holes:
  - road_prob_high catches FPs near recognized roads (lots of coverage)
  - on_road_buffer catches FPs on roads/not_roads regardless of the model's confidence

Outputs (under data/derivatives/9t/iterations/05b_road_vector_filter/):
  filtered_argmax_<config>.tif
  filtered_prob_floor_<config>.tif
  filtered_prob_wall_<config>.tif
  filter_v2_sweep_metrics.csv
  filter_v2_sweep_summary.json
  components_dropped_<config>.gpkg
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

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUTDIR = D / "iterations" / "05b_road_vector_filter"; OUTDIR.mkdir(parents=True, exist_ok=True)

PIT_ARGMAX = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_argmax.tif"
PIT_PROB_FLOOR = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_prob_floor.tif"
PIT_PROB_WALL = D / "iterations" / "04_ensemble_01_03" / "ensemble_maxpit_prob_wall.tif"
ROAD_PROB = D / "road_unet" / "road_prob.tif"
LABELS = D / "labels_pit_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "pit_dataset_manifest.csv"

PX_M2 = 0.25
MIN_AREA_M2 = 4.0


def build_road_buffer_mask(buffer_m, ref_transform, H, W):
    """Rasterize buffered roads + not_roads to a binary mask aligned to the tile."""
    roads = gpd.read_file(ANN, layer="roads")
    not_roads = gpd.read_file(ANN, layer="not_roads")
    bufs = [g.buffer(buffer_m) for g in roads.geometry if g and not g.is_empty]
    bufs += [g.buffer(buffer_m) for g in not_roads.geometry if g and not g.is_empty]
    mask = rasterize(
        [(g, 1) for g in bufs],
        out_shape=(H, W), transform=ref_transform, fill=0, dtype="uint8",
    ).astype(bool)
    n_pits_truth_in_buf = 0
    pit_in = gpd.read_file(ANN, layer="pit_inside")
    for g in pit_in.geometry:
        cent = g.centroid
        # quick check via rasterized lookup
        c = int(round((cent.x - ref_transform.c) / ref_transform.a))
        r = int(round((cent.y - ref_transform.f) / ref_transform.e))
        if 0 <= r < H and 0 <= c < W and mask[r, c]:
            n_pits_truth_in_buf += 1
    return mask, n_pits_truth_in_buf, len(pit_in)


def component_stats(argmax, road_prob, road_buffer_mask):
    pit = (argmax == 1) | (argmax == 2)
    cc, n = ndimage.label(pit, structure=np.ones((3, 3)))
    print(f"  components: {n}")
    sizes_full = ndimage.sum(pit.astype(np.int32), cc, index=np.arange(1, n + 1))
    keep = sizes_full * PX_M2 >= MIN_AREA_M2
    cand = np.where(keep)[0] + 1
    rows = []
    for cid in cand:
        ys, xs = np.where(cc == cid)
        if len(ys) < 4:
            continue
        ys_c = ys - ys.mean(); xs_c = xs - xs.mean()
        cov = np.cov(np.stack([ys_c, xs_c]))
        eigs = np.maximum(np.linalg.eigvalsh(cov), 1e-6)
        elong = float(np.sqrt(eigs[1] / eigs[0]))
        # Road prob inside the component
        rp_vals = road_prob[ys, xs]
        rp_vals = rp_vals[np.isfinite(rp_vals) & (rp_vals >= 0)]
        rp_max = float(rp_vals.max()) if len(rp_vals) else 0.0
        rp_mean = float(rp_vals.mean()) if len(rp_vals) else 0.0
        # Road buffer overlap
        in_buf = road_buffer_mask[ys, xs]
        on_road_frac = float(in_buf.mean())
        rows.append({
            "cid": int(cid),
            "area_m2": float(sizes_full[cid - 1] * PX_M2),
            "elong": elong,
            "road_max": rp_max,
            "road_mean": rp_mean,
            "on_road_frac": on_road_frac,
        })
    return cc, pd.DataFrame(rows)


def filter_mask(df, cfg):
    """Drop rules combine probabilistic and vector road signals."""
    # Existing iter 05 rules (probabilistic)
    prob_drop = (
        ((df.elong >= cfg["elong_t"]) & (df.road_max >= cfg["road_max_t"]))
        | ((df.elong >= cfg["elong_t"]) & (df.road_mean >= cfg["road_mean_t"]))
        | ((df.area_m2 >= cfg["long_area_t"]) & (df.elong >= cfg["elong_big_t"]))
    )
    # New rules driven by hand-drawn road buffers
    # A component "on a road" if a large fraction of its pixels sit in the road buffer
    vector_drop_any_elong = (df.on_road_frac >= cfg["on_road_t"]) & (df.elong >= cfg["vec_elong_t"])
    vector_drop_high_cov  = df.on_road_frac >= cfg["on_road_high_t"]   # very strong on-road overlap, even compact
    return prob_drop | vector_drop_any_elong | vector_drop_high_cov


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


def dropped_to_gpkg(cc, drop_cids, df, suffix):
    if not drop_cids:
        return
    with rasterio.open(LABELS) as r:
        tf = r.transform; crs = r.crs
    polys = []
    for cid in drop_cids:
        mask = (cc == cid).astype(np.uint8)
        ys, xs = np.where(mask)
        if len(ys) == 0: continue
        r0, r1 = ys.min(), ys.max() + 1
        c0, c1 = xs.min(), xs.max() + 1
        local = mask[r0:r1, c0:c1]
        sub_tf = rasterio.transform.from_bounds(
            tf.c + c0 * tf.a, tf.f + r1 * tf.e,
            tf.c + c1 * tf.a, tf.f + r0 * tf.e,
            c1 - c0, r1 - r0)
        sh = list(shapes(local, mask=local.astype(bool), transform=sub_tf))
        if not sh: continue
        geom = unary_union([shape(s) for s, _ in sh])
        row = df[df.cid == cid].iloc[0]
        polys.append({
            "cid": int(cid),
            "area_m2": float(row.area_m2),
            "elong": float(row.elong),
            "road_max": float(row.road_max),
            "road_mean": float(row.road_mean),
            "on_road_frac": float(row.on_road_frac),
            "geometry": geom,
        })
    if polys:
        gpd.GeoDataFrame(polys, crs=crs).to_file(
            OUTDIR / f"components_dropped_{suffix}.gpkg", driver="GPKG")


def main():
    print("Loading rasters...")
    with rasterio.open(PIT_ARGMAX) as r:
        argmax = r.read(1); tf = r.transform; H, W = r.height, r.width
    with rasterio.open(PIT_PROB_FLOOR) as r: pf = r.read(1)
    with rasterio.open(PIT_PROB_WALL) as r:  pw = r.read(1)
    with rasterio.open(ROAD_PROB) as r:      rp = r.read(1)

    # We sweep BUFFER_M too -- it's the critical knob for the new filter.
    print("Building road-line buffer masks for sweep widths...")
    buf_masks = {}
    for bm in [3.0, 5.0, 8.0]:
        m, n_truth_in, n_truth_total = build_road_buffer_mask(bm, tf, H, W)
        buf_masks[bm] = m
        print(f"  buffer {bm} m -> mask sum={m.sum():,} px ({m.sum()*PX_M2:,.0f} m^2); "
              f"labeled pits with centroid inside buffer: {n_truth_in}/{n_truth_total}")

    print("\nBaseline (no filter):")
    base = test_eval(argmax)
    for k, v in base.items(): print(f"  {k:22s} {v}")

    summary = {"baseline": base, "configs": {}}
    rows_csv = [{"config": "baseline", **base, "n_dropped": 0, "n_kept": None}]

    # Six configs: three road_buf widths x two aggressiveness levels.
    configs = [
        # name, buffer_m, elong_t, road_max_t, road_mean_t, long_area_t, elong_big_t, on_road_t, vec_elong_t, on_road_high_t
        ("v2_safe_buf3",       3.0, 3.0, 0.50, 0.30,  60.0, 4.0, 0.50, 1.5, 0.90),
        ("v2_safe_buf5",       5.0, 3.0, 0.50, 0.30,  60.0, 4.0, 0.50, 1.5, 0.90),
        ("v2_moderate_buf3",   3.0, 2.5, 0.40, 0.25,  40.0, 3.0, 0.40, 1.4, 0.80),
        ("v2_moderate_buf5",   5.0, 2.5, 0.40, 0.25,  40.0, 3.0, 0.40, 1.4, 0.80),
        ("v2_aggressive_buf5", 5.0, 2.0, 0.30, 0.20,  25.0, 2.5, 0.30, 1.3, 0.70),
        ("v2_aggressive_buf8", 8.0, 2.0, 0.30, 0.20,  25.0, 2.5, 0.30, 1.3, 0.70),
    ]

    for name, buffer_m, elong_t, road_max_t, road_mean_t, long_area_t, elong_big_t, on_road_t, vec_elong_t, on_road_high_t in configs:
        cfg = dict(buffer_m=buffer_m, elong_t=elong_t, road_max_t=road_max_t, road_mean_t=road_mean_t,
                   long_area_t=long_area_t, elong_big_t=elong_big_t,
                   on_road_t=on_road_t, vec_elong_t=vec_elong_t, on_road_high_t=on_road_high_t)
        print(f"\nConfig '{name}': {cfg}")
        mask = buf_masks[buffer_m]
        cc, df = component_stats(argmax, rp, mask)
        drop_series = filter_mask(df, cfg)
        drop_cids = list(df.loc[drop_series, "cid"].astype(int).values)
        print(f"  drop {len(drop_cids)} components, keep {(~drop_series).sum()}")

        amx, pfn, pwn = apply_filter(argmax, pf, pw, cc, drop_cids)
        write_argmax(amx, pfn, pwn, name)
        dropped_to_gpkg(cc, drop_cids, df, name)
        m = test_eval(amx)
        print(f"  metrics after filter:")
        for k, v in m.items(): print(f"    {k:22s} {v}")

        summary["configs"][name] = {"cfg": cfg, "n_dropped": int(len(drop_cids)),
                                    "metrics": m}
        rows_csv.append({"config": name, **m,
                         "n_dropped": int(len(drop_cids))})

    pd.DataFrame(rows_csv).to_csv(OUTDIR / "filter_v2_sweep_metrics.csv", index=False)
    (OUTDIR / "filter_v2_sweep_summary.json").write_text(
        json.dumps(summary, indent=2, default=float))
    print(f"\nOutputs in {OUTDIR}")


if __name__ == "__main__":
    main()

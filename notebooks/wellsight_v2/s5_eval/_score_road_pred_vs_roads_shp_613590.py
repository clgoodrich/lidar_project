"""Score a road probability raster for 613590 against the roads in roads.shp.

613590 is the cleanest out-of-domain test this project has. A model trained on
9t alone has never seen a pixel of it -- not a patch, not a validation crop --
so nothing here is leakage. That is a stronger claim than the 9t held-out road
numbers can make, where 40 m chunking puts 39.8% of held-out chunks on a parent
road that also has chunks in train.

CIRCULARITY WARNING, READ BEFORE QUOTING A NUMBER
--------------------------------------------------
The 613590 ground truth in roads.shp is not one thing. The `src` column splits it:

    613590_review_r2   138.56 km   a PREVIOUS road model's output, chunked and
                                   vetted by hand. Scoring a new road model
                                   against it is partly circular: both models
                                   share an architecture, a channel stack and a
                                   training tile, so agreement is expected for
                                   reasons that have nothing to do with skill.
    613590_added_r2     49.04 km   drawn from scratch by the annotator on roads
                                   the previous model MISSED. Independent of any
                                   model, and therefore the honest test. It is
                                   also adversarially hard by construction --
                                   these are exactly the roads a sibling model
                                   failed to find.

Every metric is reported three ways: all, review-only, added-only. The added-only
column is the one to quote, and it should be expected to look worse.

CRITERION
---------
Copied from `_road_threshold_products_9t.py` so the numbers stay comparable:

  coverage(chunk) = fraction of the chunk's length lying within TOL_M of a pixel
                    the model called road at this threshold
  found           = coverage >= COVER_FRAC

Reference lines are chunked to ~40 m, the same unit the 9t road eval scores.

Completeness / correctness / quality follow Wiedemann et al. 1998, the standard
triple for road extraction:

  completeness = matched reference length / total reference length
  correctness  = matched extracted length / total extracted length
  quality      = comp * corr / (comp - comp * corr + corr)

"Extracted length" for a raster has no honest line length, so correctness is
measured on PIXELS: the fraction of pixels called road that lie within TOL_M of
an annotated road line. It is labelled `correctness_px` everywhere to keep that
distinction visible rather than buried.

Correctness on this tile is a LOWER BOUND. roads.shp covers 613590 only where
the annotator worked; a prediction on a real road nobody drew counts against it.

Outputs (data/05_results/613590/road/thresholds/):
    road_score_vs_roads_shp_613590_1m.csv     one row per threshold per subset
    _road_score_vs_roads_shp_613590_1m.json   summary at the best-quality thr
    road_found_vs_missed_thr<t>_613590_1m.gpkg  chunks with coverage + found

Reproduce:
  python notebooks/wellsight_v2/s5_eval/_score_road_pred_vs_roads_shp_613590.py \
      --prob data/derivatives/tiles/9t/road_unet_1m_recall_relabeled20260806/road_prob_613590_1m.tif
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ANN = path_for("truth") / "roads.shp"
OUT = path_for("results") / "613590" / "road" / "thresholds"

CRS = "EPSG:6346"
TOL_M = 5.0            # centreline tolerance, same as the 9t road eval
COVER_FRAC = 0.5       # half a chunk must be covered before it counts as found
CHUNK_M = 40.0         # same eval unit as road_chunks_9t.gpkg
SAMPLE_M = 2.0         # spacing of coverage probes along a chunk
SRC_ALL = ("613590_review_r2", "613590_added_r2")


def chunk_line(line: LineString, chunk_m: float):
    """Split a polyline into ~chunk_m pieces, densified to ~5 m vertices."""
    if line is None or line.is_empty or line.length == 0:
        return []
    if line.length <= chunk_m:
        return [line]
    n = int(np.ceil(line.length / chunk_m))
    step = line.length / n
    out = []
    for i in range(n):
        a, b = i * step, (i + 1) * step
        pts = [line.interpolate(a)]
        d = a + 5.0
        while d < b:
            pts.append(line.interpolate(d))
            d += 5.0
        pts.append(line.interpolate(b))
        seg = LineString(pts)
        if seg.length > 0:
            out.append(seg)
    return out


def coverage(chunks: gpd.GeoDataFrame, dist: np.ndarray, tf, shape) -> np.ndarray:
    """Fraction of each chunk's length within TOL_M of a predicted road pixel."""
    H, W = shape
    inv = ~tf
    out = np.zeros(len(chunks), dtype=float)
    for i, g in enumerate(chunks.geometry):
        n = max(int(np.ceil(g.length / SAMPLE_M)), 2)
        ds = np.linspace(0, g.length, n)
        hit = 0
        for d in ds:
            p = g.interpolate(d)
            c, r = inv * (p.x, p.y)
            r, c = int(r), int(c)
            if 0 <= r < H and 0 <= c < W and dist[r, c] <= TOL_M:
                hit += 1
        out[i] = hit / len(ds)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", required=True, help="road probability GeoTIFF")
    ap.add_argument("--thresholds", default="0.30,0.40,0.50,0.60,0.70")
    ap.add_argument("--export-thr", type=float, default=0.50)
    ap.add_argument("--label", default=None, help="model name for the CSV")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prob_path = Path(a.prob)
    label = a.label or prob_path.parent.name

    with rasterio.open(prob_path) as r:
        prob = r.read(1).astype(np.float32)
        tf, rcrs, shape = r.transform, r.crs, (r.height, r.width)
        bounds = r.bounds
    print(f"prob raster {prob_path}\n  {shape[1]}x{shape[0]} {rcrs}")

    roads = gpd.read_file(ANN).to_crs(CRS)
    roads = roads[roads.src.isin(SRC_ALL)].copy()
    clip = box(*bounds)
    roads["geometry"] = roads.geometry.intersection(clip)
    roads = roads[~roads.geometry.is_empty & roads.geometry.notna()]

    chunk_rows = []
    for _, r_ in roads.iterrows():
        geoms = (list(r_.geometry.geoms)
                 if r_.geometry.geom_type == "MultiLineString" else [r_.geometry])
        for g in geoms:
            for seg in chunk_line(g, CHUNK_M):
                chunk_rows.append({"src": r_.src, "length_m": seg.length,
                                   "geometry": seg})
    chunks = gpd.GeoDataFrame(chunk_rows, crs=CRS)
    print(f"reference: {len(roads)} lines -> {len(chunks)} chunks, "
          f"{chunks.length_m.sum()/1000:.2f} km")
    for s in SRC_ALL:
        sub = chunks[chunks.src == s]
        print(f"    {s:18s} {len(sub):5d} chunks  {sub.length_m.sum()/1000:7.2f} km")

    # distance from every pixel to the nearest annotated road line, for correctness
    ann_px = rasterize([(g, 1) for g in chunks.geometry], out_shape=shape,
                       transform=tf, fill=0, dtype="uint8").astype(bool)
    dist_to_ann = distance_transform_edt(~ann_px) * abs(tf.a)

    thrs = [float(t) for t in a.thresholds.split(",")]
    export = None
    acc = []
    for thr in thrs:
        mask = prob >= thr
        n_px = int(mask.sum())
        dist_to_pred = distance_transform_edt(~mask) * abs(tf.a)
        cov = coverage(chunks, dist_to_pred, tf, shape)
        ch = chunks.copy()
        ch["coverage"] = cov.round(3)
        ch["found"] = cov >= COVER_FRAC
        corr_px = (float((dist_to_ann[mask] <= TOL_M).sum()) / n_px) if n_px else 0.0

        for subset in ("all",) + SRC_ALL:
            sub = ch if subset == "all" else ch[ch.src == subset]
            if not len(sub):
                continue
            tot = sub.length_m.sum()
            comp_len = float((sub.coverage * sub.length_m).sum() / tot)
            comp_chunk = float(sub.found.mean())
            q = (comp_len * corr_px / (comp_len - comp_len * corr_px + corr_px)
                 if (comp_len + corr_px) > 0 else 0.0)
            acc.append(dict(
                model=label, threshold=thr, subset=subset,
                n_chunks=int(len(sub)), km=round(tot / 1000, 2),
                completeness_len=round(comp_len, 3),
                completeness_chunk=round(comp_chunk, 3),
                correctness_px=round(corr_px, 3),
                quality=round(q, 3),
                pred_road_px=n_px,
                found=int(sub.found.sum()), missed=int((~sub.found).sum())))
            print(f"  thr {thr:.2f} {subset:18s} comp_len {comp_len:.3f} "
                  f"comp_chunk {comp_chunk:.3f} corr_px {corr_px:.3f} Q {q:.3f}")
        if abs(thr - a.export_thr) < 1e-9:
            export = ch

    df = pd.DataFrame(acc)
    csv = OUT / "road_score_vs_roads_shp_613590_1m.csv"
    if csv.exists():
        old = pd.read_csv(csv)
        df = pd.concat([old[old.model != label], df], ignore_index=True)
    df.to_csv(csv, index=False)

    if export is not None:
        tag = f"thr{a.export_thr:.2f}".replace(".", "p")
        gpkg = OUT / f"road_found_vs_missed_{tag}_613590_1m.gpkg"
        if gpkg.exists():
            gpkg.unlink()
        export.to_file(gpkg, layer="chunks", driver="GPKG")
        ex_missed = export[~export.found]
        if len(ex_missed):
            ex_missed.to_file(gpkg, layer="missed", driver="GPKG")
        print(f"\nwrote {gpkg}")

    cur = df[df.model == label]
    best = cur[cur.subset == "613590_added_r2"].sort_values("quality").tail(1)
    summ = {"model": label, "prob_raster": str(prob_path),
            "tol_m": TOL_M, "cover_frac": COVER_FRAC, "chunk_m": CHUNK_M,
            "reference": "roads.shp src in %s" % (SRC_ALL,),
            "rows": cur.to_dict(orient="records")}
    if len(best):
        summ["best_thr_on_added"] = float(best.threshold.iloc[0])
    js = OUT / "_road_score_vs_roads_shp_613590_1m.json"
    js.write_text(json.dumps(summ, indent=2, default=float))
    print(f"wrote {csv}\nwrote {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

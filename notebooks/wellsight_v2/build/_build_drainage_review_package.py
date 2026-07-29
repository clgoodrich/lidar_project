"""Build a QGIS review package for human-in-the-loop DRAINAGE correction on a block.

The drainage sibling of `_build_road_review_package.py`. Same contract: the
model's predicted drainage is chopped into ~40 m segments with a `status` field,
plus an empty layer for drawing drainage the model MISSED.

Why this exists. The road U-Net is 3-class (bg/road/drainage) and `drainage.shp`
— its only drainage supervision — spans x 620,659-624,000, which does not touch
block 613590 (x 613,500-618,000). So on every block outside 9t the drainage
class runs with zero local labels. A drainage the model misses entirely is
invisible in `drainage_prob` and shows up instead as a confident false road, so
the model cannot flag its own blind spot. Only a reviewer looking at terrain can.

Third layer, specific to this package: `road_rejects_*` carries the road
segments the reviewer already deleted in the road package. Those are the prime
suspects for unrecognised drainage — reviewing them here converts a generic
"not a road" hard negative into a labelled "this IS drainage" positive, which is
the in-model fix this project prefers over post-hoc filtering.

Outputs (under <block>/review_drainage/):
    review_drainage_<key>.gpkg           layer 'review' — predicted ~40 m segs
    review_drainage_<key>_ORIGINAL.gpkg  untouched snapshot (reject = set diff)
    added_drainage_<key>.gpkg            layer 'added'  — empty; draw misses here
    road_rejects_<key>.gpkg              layer 'rejects' — your deleted road segs
    *.qml                                styles
    README_EDIT.md                       QGIS instructions

CLI:
  python notebooks/wellsight_v2/build/_build_drainage_review_package.py --key 613590
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio
import rasterio
from scipy import ndimage as ndi
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS

# Reuse the road extraction primitives so drainage segments behave like road
# segments in QGIS (same chunk length, same skeleton/prune semantics).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "wellsight" / "build"))
from _road_optimize import island_filter, lines_from_skel, prune_merge, skeleton

REGION = DERIV / "tiles" / "data_3x3" / "westernpa_d20"
CHUNK_M = 40.0

# Drainage extraction. Deliberately simpler than the road pipeline: no ridge
# enhancement (drainage is not a ridge feature) and NO reconnect/bridging —
# bridging invents geometry, and an invented channel taught as a positive is a
# worse error here than a gap the reviewer can draw in by hand.
#
# Settings calibrated against hand-drawn 9t drainage on the held-out test blocks
# by `_calibrate_drainage_extraction_9t.py` (Heipke/Wiedemann, 8 m tolerance —
# the same harness `_road_optimize.py` uses, so the F1 is road-comparable).
# Best of 48 configs: completeness 0.824, correctness 0.737, F1 0.778.
#
# island=0 is deliberate. The road pipeline's 100 m island filter scored F1
# 0.635 here because a drainage network is mostly short first-order tributary
# stubs, and the filter deletes them — 27 points of completeness for nothing.
DRAIN_CFG = dict(t=0.50, min_px=60, spur=10.0, island=0.0, skel="zhang")


def sample_mean(arr, tf, line, step=3.0):
    """Mean raster value along a line (skips nodata/-1)."""
    if arr is None or line is None or line.is_empty:
        return np.nan
    inv = ~tf
    H, W = arr.shape
    vals = []
    for t in np.linspace(0, line.length, max(2, int(line.length / step))):
        p = line.interpolate(t)
        c, r = inv * (p.x, p.y)
        r, c = int(r), int(c)
        if 0 <= r < H and 0 <= c < W and arr[r, c] >= 0 and np.isfinite(arr[r, c]):
            vals.append(float(arr[r, c]))
    return round(float(np.mean(vals)), 3) if vals else np.nan


def chunk_line(line: LineString, chunk_m: float):
    if line is None or line.is_empty or line.geom_type != "LineString":
        return []
    if line.length <= chunk_m:
        return [line]
    n = int(np.ceil(line.length / chunk_m))
    edges = np.linspace(0.0, line.length, n + 1)
    out = []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        inner = max(2, int(np.ceil((t1 - t0) / 5.0)) + 1)
        ts = np.linspace(t0, t1, inner)
        seg = LineString([(p.x, p.y) for p in (line.interpolate(t) for t in ts)])
        if not seg.is_empty and seg.length > 0:
            out.append(seg)
    return out


def extract_drainage(pdrain, tf, res, cfg):
    """drainage_prob raster -> list of centreline LineStrings."""
    m = pdrain >= cfg["t"]
    m = ndi.binary_closing(m, np.ones((3, 3)))
    m = ndi.binary_fill_holes(m)
    from skimage.morphology import remove_small_objects
    m = remove_small_objects(m, min_size=cfg["min_px"])
    print(f"  mask: {int(m.sum()):,} px ({m.mean()*100:.3f}% of tile) at "
          f"P(drain) >= {cfg['t']}")
    segs = prune_merge(lines_from_skel(skeleton(m, cfg["skel"]), tf), cfg["spur"])
    segs = island_filter(segs, cfg["island"])
    return segs


REVIEW_QML = """<!DOCTYPE qgis>
<qgis version="3.34" styleCategories="Symbology|Fields|Forms|Default">
  <renderer-v2 type="categorizedSymbol" attr="status" forceraster="0" symbollevels="0" enableorderby="0">
    <categories>
      <category value="keep" symbol="0" label="keep (is drainage)" render="true"/>
      <category value="reject" symbol="1" label="reject (not drainage)" render="true"/>
      <category value="unsure" symbol="2" label="unsure" render="true"/>
      <category value="" symbol="3" label="(other)" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="31,120,220,255"/>
            <Option name="line_width" type="QString" value="0.6"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="1" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="227,26,28,255"/>
            <Option name="line_width" type="QString" value="0.9"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="2" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="255,160,0,255"/>
            <Option name="line_width" type="QString" value="0.7"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
      <symbol name="3" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="150,150,150,255"/>
            <Option name="line_width" type="QString" value="0.4"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <fieldConfiguration>
    <field name="status">
      <editWidget type="ValueMap">
        <config>
          <Option type="Map">
            <Option name="map" type="List">
              <Option type="Map"><Option name="keep" type="QString" value="keep"/></Option>
              <Option type="Map"><Option name="reject" type="QString" value="reject"/></Option>
              <Option type="Map"><Option name="unsure" type="QString" value="unsure"/></Option>
            </Option>
          </Option>
        </config>
      </editWidget>
    </field>
  </fieldConfiguration>
  <defaults>
    <default field="status" expression="'keep'" applyOnUpdate="0"/>
  </defaults>
</qgis>
"""

REJECTS_QML = """<!DOCTYPE qgis>
<qgis version="3.34" styleCategories="Symbology|Default">
  <renderer-v2 type="singleSymbol" forceraster="0" symbollevels="0" enableorderby="0">
    <symbols>
      <symbol name="0" type="line" alpha="1" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1">
          <Option type="Map">
            <Option name="line_color" type="QString" value="240,60,220,255"/>
            <Option name="line_width" type="QString" value="1.0"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
            <Option name="capstyle" type="QString" value="round"/>
            <Option name="use_custom_dash" type="QString" value="1"/>
            <Option name="customdash" type="QString" value="3;2"/>
            <Option name="customdash_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""

README = """# Drainage review — {key}

Goal: give the road model local drainage labels. It is a 3-class model
(bg / road / drainage), but its only drainage training data (`drainage.shp`)
sits at x 620,659-624,000 and this block spans x 613,500-618,000. **No overlap.**
So drainage here is predicted with zero local supervision.

## Layers to load (drag into QGIS, in this order)
1. `hillshade_{key}_1m.tif`                       (basemap)
2. `drainage_prob_{key}_1m.tif`                   (model drainage confidence)
3. `review_drainage/road_rejects_{key}.gpkg`      (magenta dashed — read the note below)
4. `review_drainage/review_drainage_{key}.gpkg`   (predicted drainage — you edit this)
5. `review_drainage/added_drainage_{key}.gpkg`    (empty — you DRAW missed drainage here)

## The magenta layer is the point of this package
`road_rejects_{key}.gpkg` holds the {n_rej} road segments you deleted during the
road review ({km_rej:.1f} km). The model scored them P(road) {p_road:.2f} and
P(drainage) {p_drain:.3f} — it was confident they were roads and had no idea they
might be water. Some of them are almost certainly stream channels.

**Where a magenta line is actually drainage, trace it into `added_drainage`.**
That upgrades it from a generic "not a road" negative into a labelled drainage
positive, which is a much stronger training signal and the fix that made the
3-class model work on 9t in the first place.

## How to correct
- **Wrong drainage** (blue lines that are not channels): toggle editing on
  `review_drainage` and **delete** them. Rejects are recovered by comparing
  against `review_drainage_{key}_ORIGINAL.gpkg`, so deleting is safe and is the
  workflow the corrections builder expects.
- **Unsure**: set `status = 'unsure'` and it is excluded from training.
- **Missed drainage**: draw the centreline in `added_drainage`. Trace the
  channel thalweg, not the bank-to-bank width.
- Save edits (Ctrl+S) and toggle editing off when done.

## Tips
- Sort `review_drainage` by `mean_pdrain` ascending to hit the least-confident
  predictions first — the likeliest false positives.
- `mean_proad` is on the same table. A segment high in **both** is a genuine
  model confusion and is worth adjudicating carefully.
- You do not need full coverage. Partial labels are fine — the corrections
  builder marks unadjudicated ground as `ignore` and never teaches it as
  background.

Segments are ~{chunk:.0f} m so you can flag a bad stretch without splitting lines.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="613590")
    ap.add_argument("--drain-prob", default=None,
                    help="drainage_prob raster (default drainage_prob_<key>_1m.tif)")
    ap.add_argument("--road-prob", default=None,
                    help="road_prob raster, for the mean_proad column")
    ap.add_argument("--road-review", default=None,
                    help="road review dir, to carry over deleted segs (default <block>/review)")
    ap.add_argument("--no-rejects", action="store_true",
                    help="skip the deleted-road cross-check layer")
    ap.add_argument("--gt", default=None,
                    help="GT drainage lines (gpkg path); adds gt_dist_m per segment")
    ap.add_argument("--gt-layer", default="drainage")
    ap.add_argument("--chunk", type=float, default=CHUNK_M)
    ap.add_argument("--thresh", type=float, default=DRAIN_CFG["t"])
    args = ap.parse_args()

    key = args.key
    blk = REGION / key
    out_dir = blk / "review_drainage"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = dict(DRAIN_CFG, t=args.thresh)

    dp = Path(args.drain_prob) if args.drain_prob else blk / f"drainage_prob_{key}_1m.tif"
    if not dp.exists():
        print(f"ERROR: no drainage prob raster at {dp}")
        return 1
    with rasterio.open(dp) as r:
        pdrain = np.clip(r.read(1).astype(np.float32), 0, 1)
        tf, res, crs = r.transform, r.res[0], r.crs
    print(f"drainage prob: {dp.name}")

    rp = Path(args.road_prob) if args.road_prob else blk / f"road_prob_{key}_1m.tif"
    proad = None
    if rp.exists():
        with rasterio.open(rp) as r:
            proad = r.read(1).astype(np.float32)
        print(f"road prob    : {rp.name}")

    # ---- vectorize predicted drainage -------------------------------------
    segs = extract_drainage(pdrain, tf, res, cfg)
    print(f"  {len(segs)} centrelines, {sum(s.length for s in segs)/1000:.2f} km")

    rows, sid = [], 0
    for pid, line in enumerate(segs):
        for seg in chunk_line(line, args.chunk):
            rows.append({
                "seg_id": sid, "parent_id": int(pid), "status": "keep",
                "length_m": round(float(seg.length), 1),
                "mean_pdrain": sample_mean(pdrain, tf, seg),
                "mean_proad": sample_mean(proad, tf, seg),
                "geometry": seg,
            })
            sid += 1
    if not rows:
        print("ERROR: no drainage segments survived extraction — lower --thresh")
        return 1
    review = gpd.GeoDataFrame(rows, crs=crs).to_crs(DST_CRS)

    # Distance to the nearest hand-drawn drainage line, when GT is available.
    # On a block with GT this separates "model agrees with an existing label"
    # from "model found something unlabelled" — the latter is what grows the
    # label set. On a block with no GT every value is null, which is itself the
    # honest signal that nothing here is supervised.
    if args.gt:
        gtp = Path(args.gt)
        if gtp.exists():
            gt = gpd.read_file(gtp, layer=args.gt_layer)
            if gt.crs is None:
                gt = gt.set_crs(DST_CRS)
            gt = gt.to_crs(DST_CRS)
            gt = gt[gt.intersects(review.union_all().buffer(500))]
            if len(gt):
                review["gt_dist_m"] = np.round(
                    review.geometry.apply(lambda g: gt.distance(g).min()), 1)
                near = int((review.gt_dist_m <= 10).sum())
                print(f"  GT: {len(gt)} lines in range; segments within 10 m of "
                      f"a hand-drawn line: {near}/{len(review)} "
                      f"({near/len(review)*100:.1f}%)")
            else:
                review["gt_dist_m"] = None
                print("  GT: no hand-drawn drainage within 500 m of this block")
        else:
            print(f"  GT: {gtp} not found — skipping gt_dist_m")

    rpth = out_dir / f"review_drainage_{key}.gpkg"
    review.to_file(rpth, layer="review", driver="GPKG")
    orig = out_dir / f"review_drainage_{key}_ORIGINAL.gpkg"
    shutil.copyfile(rpth, orig)
    (out_dir / f"review_drainage_{key}.qml").write_text(REVIEW_QML, encoding="utf-8")
    print(f"review : {len(review)} segments (~{args.chunk:.0f} m), "
          f"{review.length.sum()/1000:.2f} km -> {rpth.name}")
    print(f"         snapshot -> {orig.name}")

    # ---- empty 'added' layer ---------------------------------------------
    added = gpd.GeoDataFrame(
        {"status": gpd.pd.Series([], dtype="object"),
         "note": gpd.pd.Series([], dtype="object")},
        geometry=gpd.GeoSeries([], crs=DST_CRS))
    apth = out_dir / f"added_drainage_{key}.gpkg"
    pyogrio.write_dataframe(added, apth, layer="added", geometry_type="LineString")
    print(f"added  : empty draw-here layer -> {apth.name}")

    # ---- carry over the road segments the reviewer deleted ----------------
    n_rej, km_rej, p_road, p_drain = 0, 0.0, float("nan"), float("nan")
    rdir = Path(args.road_review) if args.road_review else blk / "review"
    ro = rdir / f"review_roads_{key}_ORIGINAL.gpkg"
    rc = rdir / f"review_roads_{key}.gpkg"
    if args.no_rejects:
        print("rejects: skipped (--no-rejects)")
    elif ro.exists() and rc.exists():
        o = gpd.read_file(ro)
        c = gpd.read_file(rc)
        rej = o[~o.seg_id.isin(set(c.seg_id))].copy()
        if len(rej):
            rej["mean_pdrain"] = [sample_mean(pdrain, tf, g) for g in rej.geometry]
            if proad is not None:
                rej["mean_proad_now"] = [sample_mean(proad, tf, g) for g in rej.geometry]
            rej["status"] = None          # reviewer marks 'drainage' if it is one
            jpth = out_dir / f"road_rejects_{key}.gpkg"
            rej.to_file(jpth, layer="rejects", driver="GPKG")
            (out_dir / f"road_rejects_{key}.qml").write_text(REJECTS_QML, encoding="utf-8")
            n_rej = len(rej)
            km_rej = rej.length.sum() / 1000
            p_road = float(np.nanmean(rej.mean_proad.values))
            p_drain = float(np.nanmean(rej.mean_pdrain.values))
            print(f"rejects: {n_rej} deleted road segs, {km_rej:.2f} km -> {jpth.name}")
            print(f"         P(road) {p_road:.3f}  P(drainage) {p_drain:.3f}")
    else:
        print("rejects: no road review found — skipping the cross-check layer")

    (out_dir / "README_EDIT.md").write_text(
        README.format(key=key, chunk=args.chunk, n_rej=n_rej, km_rej=km_rej,
                      p_road=p_road, p_drain=p_drain), encoding="utf-8")
    print(f"note   : README_EDIT.md")
    print(f"\nDrainage review package ready: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

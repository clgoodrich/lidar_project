# Threshold sweeps on 9t — pit, pad, road

**Date:** 2026-07-27
**Scripts:**
`notebooks/wellsight_v2/s5_eval/_pit_threshold_products_9t.py`
`notebooks/wellsight_v2/s5_eval/_pad_threshold_products_9t.py`
`notebooks/wellsight_v2/s5_eval/_road_threshold_products_9t.py`
Shared helpers in `notebooks/wellsight_v2/s5_eval/_threshold_common.py`.

## Goal

One question asked identically of all three U-Nets. At each probability cutoff,
how much of the tile does the model claim, and how many held-out hand-drawn
annotations does it find?

Ground truth is hand-drawn annotation only. No DEP well list, no TIGER.
Held-out means the val + test rows of that task's own manifest, so the model
never trained on any scored feature.

The 9t tile is 2,025 ha.

## Held-out sets

| Task | Held out | Extent |
|---|---|---|
| Pit | 127 rims (`pit_outside`) | median floor 26 m² |
| Pad | 194 plats | median 1,623 m², 32.42 ha total |
| Road | 1,220 chunks (`kind='road'`) | 43.07 km |
| Road negatives | 385 drainage / 48 not_road | 9.85 km / 1.67 km |

## The criterion is not the same for all three, and it cannot be

**Pit** — a predicted floor polygon's centroid lies inside the annotated rim.

**Pad** — three criteria, reported together. Carrying the pit rule over
unchanged gave a nonsense answer, and finding out why was the main result of
this pass. See "The pad merging artifact" below.

**Road** — a road is not found or missed as a unit, it is found along part of
its length. Criterion is ≥50% of chunk length within 5 m of a predicted road
pixel.

## Results

### Pit — `pit_prob_floor.tif`, 0.5 m

| thr | polygons | ha | % of tile | found | missed |
|---|---|---|---|---|---|
| 0.05 | — | 70.51 | 3.482 | — | — |
| 0.20 | 1,041 | 4.33 | 0.214 | 126/127 | 1 |
| 0.30 | 827 | 2.82 | 0.139 | 125/127 | 2 |
| 0.40 | 733 | 1.90 | 0.094 | 122/127 | 5 |
| 0.50 | 637 | 1.28 | 0.063 | 113/127 | 14 |

Monotonic and well behaved. Recall is bought cheaply — 0.20 claims a fifth of a
percent of the tile for 99.2% of held-out pits.

### Pad — `plat_prob.tif`, 0.5 m

Full sweep in `data/derivatives/eval_9t_pad_thresholds/pad_threshold_sweep_9t.csv`.

| thr | polygons | ha | % of tile | IoU≥0.3 | pred-centroid-in | gt-centroid-covered |
|---|---|---|---|---|---|---|
| 0.05 | 188 | 1184.78 | 58.508 | 0 | 0 | 194 |
| 0.20 | 1,005 | 514.04 | 25.385 | 59 | 70 | 192 |
| 0.30 | 1,104 | 378.43 | 18.688 | 112 | 109 | 190 |
| 0.40 | 1,090 | 278.24 | 13.740 | 166 | 163 | 187 |
| **0.45** | 1,049 | 235.77 | 11.643 | **178** | 172 | 183 |
| 0.50 | 1,005 | 197.95 | 9.775 | **178** | 176 | 181 |
| 0.60 | 907 | 122.60 | 6.055 | 164 | 171 | 160 |
| 0.70 | 627 | 52.45 | 2.590 | 104 | 135 | 116 |
| 0.90 | 3 | 0.11 | 0.006 | 0 | 0 | 0 |

Best IoU≥0.30 recall is **0.918 (178/194) at 0.45–0.50**, claiming 10–12% of the
tile.

Threshold-free check: every held-out pad has pad-like signal. `max_prob` inside
each pad has min 0.185, p05 0.548, median 0.785. Zero pads below 0.05.

### The pad merging artifact

The first run used the pit rule alone — a prediction's centroid must lie inside
the annotated pad. It reported **0/194 found at threshold 0.05**, the cutoff
that claims 58% of the tile. That is obviously wrong, and the cause is not the
model.

Pad probability has a high background (tile mean 0.162, versus 0.039 for roads).
Lower the cutoff and predictions stop being pad-shaped, merging into a handful
of tile-spanning super-blobs. At 0.05 the entire tile is 188 polygons. A
super-blob's centroid sits in the middle of nowhere, inside no individual pad,
so every pad scores as missed at the very threshold claiming the most ground.

Hence three criteria, which fail in opposite directions:

- `pred_centroid_in_gt` — strict about over-merging, degenerates to 0 when
  predictions merge.
- `gt_centroid_covered` — immune to merging, degenerates to ~everything when the
  cutoff claims most of the tile. An upper bound, not a score.
- `iou >= 0.30` — penalised by **both** failure modes. The only one honest
  across the whole sweep, so it is the headline.

Where they disagree, the disagreement is the finding. At 0.05 the spread is
0 / 0 / 194, which is the signature of total merging.

### Road — `road_prob.tif`, 1 m

Full sweep in `data/derivatives/eval_9t_road_thresholds/road_threshold_sweep_9t.csv`.

| thr | ha | % of tile | found | missed | recall | recall_clean | km covered | drainage claimed | not_road claimed |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 159.10 | 7.857 | 1214 | 6 | 0.995 | 0.992 | 42.80 | 3.9% | 0.0% |
| 0.20 | 101.65 | 5.020 | 1207 | 13 | 0.989 | 0.982 | 42.56 | 2.6% | 0.0% |
| 0.30 | 87.98 | 4.345 | 1202 | 18 | 0.985 | 0.976 | 42.42 | 2.3% | 0.0% |
| 0.50 | 69.54 | 3.434 | 1192 | 28 | 0.977 | 0.962 | 42.10 | 2.1% | 0.0% |
| 0.70 | 50.69 | 2.503 | 1179 | 41 | 0.966 | 0.944 | 41.64 | 1.6% | 0.0% |
| 0.90 | 22.85 | 1.129 | 1033 | 187 | 0.847 | 0.797 | 35.35 | 1.0% | 0.0% |

Monotonic and very flat. Recall stays above 0.95 from 0.05 all the way to 0.80,
so on 9t the road threshold is close to a free parameter and area is the only
thing it really trades.

Threshold-free: `max_prob` along each held-out chunk has median 0.967, p05 0.822.
Only 3 of 1,220 chunks have no road-like signal at all.

**The confusion check works.** Held-out drainage claimed as road falls from 3.9%
to 2.1% across the useful range, and held-out `not_road` is claimed at **0.0% at
every threshold**. Those are hand-drawn negatives, so this is direct evidence the
3-class drainage-negative design did what it was built to do.

### Road leakage warning

Pits and pads are split as whole objects. Roads are split as ~40 m **chunks**,
so **485 of the 1,220 held-out chunks (39.8%) belong to a parent road that also
has chunks in train**. The model has seen the same road 40 m up the line. This
is the long-standing BACKLOG item "split leakage at block boundaries", not
something introduced here.

Every held-out chunk now carries a `clean` flag, true when its entire parent
road was held out — 735 of 1,220 chunks, 221 of 344 parent roads.
`recall_clean` is the number to quote and to compare against pits and pads.

The gap is small. At 0.50 it is 0.977 versus 0.962. Leakage inflates the road
result by roughly 1.5 points, which is real but does not change the conclusion.

## Reading the three together

Do not compare the "% of tile" columns naively. The three targets differ in size
by orders of magnitude, so a bigger claimed area is not automatically worse.

| Task | Best operating point | % of tile claimed | Recall there |
|---|---|---|---|
| Pit | 0.20 | 0.21% | 0.992 |
| Pad | 0.45–0.50 | 10–12% | 0.918 |
| Road | 0.20–0.30 | 4–5% | 0.982 (clean) |

The pad model is the outlier and it is the outlier twice over. Its optimum sits
at a much higher cutoff, and it still claims 10–12% of the tile there. Held-out
pads total 32.42 ha, so at 0.50 the model claims 197.95 ha — about 6x the
held-out pad area. Only 194 of 650 annotated pads are held out, so total
annotated pad area is roughly 110 ha, which still leaves the model claiming
close to 2x. The pad U-Net is genuinely over-claiming area, and that is
consistent with its high probability background.

**This is the strongest argument yet for the pad model as the next target**, not
the pit model. Pit and road are both at ≥0.98 recall for a small fraction of the
tile. Pad is at 0.918 for a tenth of it.

## Outputs

`data/derivatives/eval_9t_pad_thresholds/` (46 MB)
- `pad_threshold_sweep_9t.csv` — full 16-threshold sweep, all three criteria
- `pad_threshold_found_vs_missed_summary_9t.csv`
- `pad_heldout_max_prob_9t.csv` — threshold-free per-pad max probability
- `pad_heldout_found_vs_missed_thr0p{40,50,60,70}_9t.gpkg` + `.qml`
- `pad_missed_bookmarks_thr0p{40,50,60,70}_9t.xml`
- `pad_missed_contactsheet_thr0p{40,50,60,70}_9t.png`

`data/derivatives/eval_9t_road_thresholds/` (15 MB)
- `road_threshold_sweep_9t.csv` — includes `recall_clean`, drainage/not_road rates
- `road_threshold_found_vs_missed_summary_9t.csv`
- `road_heldout_max_prob_9t.csv`
- `road_heldout_found_vs_missed_thr0p{20,30,40,50}_9t.gpkg` + `.qml`
- `road_missed_bookmarks_thr0p{20,30,40,50}_9t.xml`
- `road_missed_contactsheet_thr0p{20,30,40,50}_9t.png`

Rasters (untracked, `data/derivatives/tiles/9t` is gitignored):
- `data/derivatives/tiles/9t/plat_unet/pad_unet_{mask,prob}_thr0p{40,50,60,70}_9t_05.tif`
- `data/derivatives/tiles/9t/road_unet_1m/road_unet_{mask,prob}_thr0p{20,30,40,50}_9t_1m.tif`

GeoPackage layers, per file:
`*_found_vs_missed` (self-styling green/red), `*_found`, `*_missed`,
`centroid_missed` / `midpoint_missed`, `locator_missed`, and for pads
`model_geometry`, for roads `drainage_claimed_as_road`.

Bookmarks import via **View ▸ Show Spatial Bookmark Manager ▸ Import**. All
files verified by round-tripping `QgsBookmarkManager.importFromFile` under
QGIS 3.40.10.

Contact sheets are capped at 60 panels. The cap is printed when it applies and
the full set is always in the GeoPackage.

## Reproduce

```bash
python notebooks/wellsight_v2/s5_eval/_pit_threshold_products_9t.py
python notebooks/wellsight_v2/s5_eval/_pad_threshold_products_9t.py
python notebooks/wellsight_v2/s5_eval/_road_threshold_products_9t.py
```

## Follow-ups added to BACKLOG

- Pad U-Net over-claims area. Highest-value model target now.
- Pad probability background is 4x the road model's. Check whether this is the
  focal-loss under-confidence issue or a genuine class-prior problem.
- Road chunk leakage. `recall_clean` is a workaround, not a fix. The real fix is
  splitting by parent road.

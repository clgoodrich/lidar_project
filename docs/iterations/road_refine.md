# road_refine — post-processing road rasters into clean, connected centerlines

**Status: RETIRED for now (2026-06-08).** Its main job — removing drainage FPs —
is now done *in the model* (3-class bg/road/drainage road U-Net, see
[[road_unet_1m]] §v2), which is more accurate and not terrain-dependent. The
drainage post-filter here was too aggressive (terrain-dependent thresholds) and is
superseded. The script (`_refine_roads_data_3x3.py`) is kept for its still-useful
**vectorization + gap-bridging** (skeletonize → `skan` lines → endpoint snapping)
if/when we want line features again, but it is NOT part of the current pipeline.
Per-block raster outputs of the 3-class model (`road_prob`, `drainage_prob`,
`road_argmax`) are used directly. The stale `roads_<key>_1m.gpkg` / `road_clean_*`
outputs from the 2-class+filter rollout are obsolete.

Original write-up below (the drainage-filter methodology finding is still a useful
record of why a single global concavity threshold can't separate roads from
drainage across terrain — which is what motivated the in-model fix).

---

**(original) Status:** pipeline built + validated on 2 pilot blocks 2026-06-07;
rolled out to all 25 WesternPA `data_3x3` blocks. Script:
`notebooks/wellsight/build/_refine_roads_data_3x3.py`.

## Why
The 1 m road U-Net ([[road_unet_1m]]) produces good per-block `road_prob` rasters
but two artifacts remain, both flagged by the user:

1. **Drainage / waterway false positives.** Incised stream channels are linear
   concave features and read as cut roads to the model.
2. **Fragmentation.** Roads that should be continuous come out in disconnected
   pieces.

## Pipeline (per block, on `road_prob_<key>_1m.tif` + raw `dem_<key>_1m.tif`)
```
prob >= 0.50  ->  remove_small_objects(250)  ->  morphological close(3px)
  ->  skeletonize  ->  skan trace to LineStrings (world coords)
  ->  bearing-aware endpoint gap-bridge (<=25 m, tangents within 35 deg)
  ->  linemerge
  ->  drainage filter (chunked, see below)
  ->  drop kept stubs < 35 m
  ->  re-rasterize kept roads (buffer 1.5 m) + write gpkg + overlay PNG
```

### Connectivity (problem 2)
- Small morphological **closing** (3 px) heals hairline gaps before skeletonizing.
- **Bearing-aware endpoint snapping**: two line endpoints within `--gap` (25 m)
  whose OUTWARD tangents point at each other within `--ang` (35 deg) get a
  straight connector. Greedy, one bridge per endpoint. (247 bridges on 609590.)

### Drainage discrimination (problem 1) — the hard part
The validated cross-section concavity test `_xdrop` (ported from
`_filter_streams_xsec_9t.py`): sample the **raw** DEM perpendicular to each chunk,
`xdrop_m = median( mean(z_left, z_right) - z_center )`. A drainage channel sits in
a V/U (`xdrop > 0`); a graded road-cut is flat-to-convex (`xdrop ~ 0`).

**A single global `xdrop` threshold does not generalize across terrain** — proven
on two pilots (drainage km dropped):

| Strategy | Flat block 604603 | Steep block 609590 | Verdict |
|---|---|---|---|
| `xdrop >= 0.30` | 19.7 km — eats grid roads | 52.0 km — eats some roads | too aggressive |
| `xdrop >= 0.60` | 6.7 km — clean | 15.7 km — channels leak | misses steep drainage |
| hydrology + `xdrop>0` | 23.7 km — eats grid roads | 42.5 km — catches dendritic net | fails on flat |
| **hydrology ∧ `xdrop>=0.35`, or `xdrop>=0.6`** | **12.0 km — grid roads kept** | **23.8 km — dendritic net caught** | **adopted** |

- **Why a global threshold fails:** on FLAT/developed terrain D8 flow routes down
  road **ditches**, so depth-0.3 *and* the naive hydrology test both drop real
  grid roads; on STEEP terrain the shallow channels need a low threshold the flat
  terrain can't tolerate.
- **Adopted rule (combines catchment + concavity):** a chunk is drainage if
  - it **coincides with a mapped D8 stream** (`>=50%` of its length on a stream
    network mapped at flow-accum `>=4000` cells, dilated 3 px) **AND** is at least
    mildly concave (`xdrop >= 0.35`); **OR**
  - it is **deeply concave on its own** (`xdrop >= 0.60`) — headwater hollows
    below the stream threshold.
  - The concavity gate on the hydrology catch is what rejects flat-terrain road
    ditches: D8 routes flow down them, but they are flat-bottomed (`xdrop` low).

D8 streams are built per block with WhiteboxTools (breach least-cost -> d8 pointer
-> flow accumulation -> extract_streams) and cached as
`stream_seed_t4000_<key>_1m.tif`; heavy intermediates (breach, accum) are deleted.

## Outputs (per block dir)
- `roads_<key>_1m.gpkg` — layer `roads` (kept centerlines) + layer `drainage`
  (dropped).
- `road_clean_<key>_1m.tif` — uint8 0/1 cleaned road raster (buffer 1.5 m).
- `road_clean_overlay_<key>_1m.png` — hillshade + kept(red)/drainage(cyan)/bridge(yellow).
- `stream_seed_t4000_<key>_1m.tif` — cached D8 stream network.

## Pilot numbers (combined rule, adopted params)
| Block | terrain | roads kept | drainage dropped | bridges |
|---|---|---|---|---|
| 604603 | flat/agricultural | 45.7 km (387) | 12.0 km (556) | 58 |
| 609590 | steep/incised | 130.3 km (1346) | 23.8 km (1136) | 247 |

**All-25-block totals (2026-06-07, 16.7 min):** roads **1727.9 km kept** /
drainage **346.7 km dropped** / **2413 bridges**. Drainage is **16.7%** of total
vectorized length — vs ~34% under the naive single-threshold variants, confirming
the combined rule is far more conservative (it drops only genuine catchment-backed
channels). Per-block range: roads 11.9–135.1 km, drainage 2.1–43.4 km (highest on
the most incised blocks 618594/613590/618591, as expected). Each block dir has
`roads_<key>_1m.gpkg` (~0.04–1.5 MB; 17 MB total, version-tracked).

## Caveats / next
- Still fragmented (avg ~100 m/line); user opted to KEEP all >35 m fragments
  rather than add a connected-component island filter. A network-island filter
  (drop components totaling < ~150 m) is the obvious next lever if a cleaner map
  is wanted later.
- The drainage rule is tuned on 2 Venango-area blocks; spot-check on a
  northcentral/mckean block before trusting it region-wide (see [[BACKLOG]]).

## Reproduce
```
# pilot one block
python notebooks/wellsight/build/_refine_roads_data_3x3.py --only 609590
# all blocks (builds + caches per-block D8 hydrology)
python notebooks/wellsight/build/_refine_roads_data_3x3.py
# depth-only (no hydrology) fallback
python notebooks/wellsight/build/_refine_roads_data_3x3.py --no-hydro --drop-strong 0.6
```

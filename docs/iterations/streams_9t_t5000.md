# streams_9t_t5000 — 9t stream network + cross-section road filter

**Status:** built + filtered 2026-06-02. Port of the McKean stream pipeline to the single 9t mosaic.

**Goal.** Produce a hydrologically-derived stream network for the 9t tile, then strip out road-like lines, so the remaining channels can be used (a) as a drainage context layer and (b) to disambiguate man-made access-road scars from natural gullies. Mirrors the parameters already validated on the McKean blocks so the products are directly comparable.

## Stage 1 — stream extraction (`build/_build_streams_9t.py`)

DEM-only, via WhiteboxTools. Reuses the already-conditioned `dem_breached_9t_1m.tif` (skips the slow `BreachDepressionsLeastCost` step; only re-breaches if no cached breach exists).

Pipeline:
1. `d8_pointer` on the breached DEM → flow-direction grid.
2. `d8_flow_accumulation` (`out_type=cells`) → how many upslope cells drain through each cell.
3. `extract_streams` with **threshold = 5000 cells** (`t5000`) → raw stream raster.
4. Clean WBT NoData background → 0/1 `uint8` seed raster.
5. `raster_streams_to_vector` → linestrings; CRS forced to **EPSG:6346** (NAD83(2011)/UTM 17N); written as both `.shp` and `.gpkg`.

**Result:** `streams_t5000_9t_1m` = **2693 lines, 274.5 km** total.

Outputs in `data/derivatives/9t/`: `stream_seed_t5000_9t_1m.tif`, `streams_t5000_9t_1m.{shp,gpkg,prj,dbf,shx,cpg}`.

Reproduce: `python notebooks/wellsight/build/_build_streams_9t.py --threshold 5000`

## Stage 2 — cross-section road filter (`build/_filter_streams_xsec_9t.py`)

Removes road-like lines using terrain concavity. **Uses the RAW `dem_9t_1m.tif`, not the breached DEM** — breaching fills channels and would erase the very concavity this test measures.

**Concavity test (`xdrop_m`).** At samples along each (sub)line, take the local tangent, rotate 90°, sample the DEM `perp` meters off each side, and compute `xdrop_m = median( mean(z_left, z_right) − z_center )`. A real channel sits in a V/U valley (`xdrop_m > 0`); a road cut / graded surface is flat-to-convex (`xdrop_m ≤ ~0`). Lines/chunks with `xdrop_m < drop_min` are classed **roadlike** and dropped from the `_kept_` outputs.

Two passes (run together):
- **per-line:** whole linestring gets one verdict. Step 5 m, min length 30 m.
- **per-chunk:** each line is cut into ~25 m chunks, each judged independently (catches lines that are part stream / part road). Step 2.5 m, min length 15 m.

Params used: `--chunk 25 --perp 5 --drop 0.30` (matches McKean).

**Results:**
| Product | Features | Length |
|---|---|---|
| raw `streams_t5000_9t_1m` | 2693 lines | 274.5 km |
| `streams_t5000_9t_kept_xsec` (per-line) | 1497 lines | 97.9 km |
| `streams_t5000_9t_chunked_kept_xsec` (per-chunk) | 4973 chunks | 88.8 km |

Each pass also writes `*_xsec` (all, with `xdrop_m`+`klass` attrs) and `*_roadlike_xsec` (the dropped lines) for inspection.

Reproduce: `python notebooks/wellsight/build/_filter_streams_xsec_9t.py --chunk 25 --perp 5 --drop 0.30`

## Provenance note (why Oil Creek had water class and McKean didn't)

The Oil Creek LAZ tiles came from a survey whose ground class was **hydro-flattened** (ASPRS class 9 = water, class 20 = ignored ground), so streams were partly pre-mapped in the point cloud. The McKean / 9t tiles came from a different survey with **no water classification** — hence this DEM-derived `extract_streams` approach is the only way to get a stream network there. Different surveys, different classification conventions; not a processing error.

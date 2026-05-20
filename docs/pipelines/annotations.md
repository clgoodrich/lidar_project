# Annotations Pipeline

How hand-drawn annotation shapefiles become reprojected, validated, spatially-joined layers usable by every downstream model.

## Source layers

All five layers were hand-drawn in QGIS by the user, in EPSG:4326. They live under `data/derivatives/annotations/` as standard shapefiles:

| Layer | Geometry | Count | What it labels |
|---|---|---|---|
| `pit_inside.shp` | Polygon | 110 | Pit floor (the flat bottom of a wellhead pit) |
| `pit_outside.shp` | Polygon | 111 | Pit outer rim — the outline at the top of the pit wall |
| `plat.shp` | Polygon | 79 | Well pad footprint (the cleared ground around a well) |
| `roads.shp` | LineString | 97 | Access roads |
| `not_roads.shp` | LineString | 37 | Linear landscape features that look like roads but aren't — **hard-negative set** |

The 37 `not_roads` are the killer asset: every prior road extractor in this project struggled with false positives on natural lineaments, and hand-drawn negatives directly address that.

## Step 1 — Reproject + validate + spatial-join

**Script:** `notebooks/wellsight/annotations/_prep_annotations.py`
**Output:** `data/derivatives/annotations/annotations_proj.gpkg`

What it does:

1. Reads each shapefile, runs `geometry.is_valid` check, fixes any invalid geometry with a `buffer(0)` no-op.
2. Reprojects everything from EPSG:4326 to **EPSG:6346** (NAD83(2011) / UTM zone 17N — the working CRS for every raster derived from `output2.las`).
3. Assigns a stable integer `plat_id` to each plat polygon.
4. Pairs each inner pit polygon to its enclosing outer-rim polygon by **maximum area of overlap**, giving each inner pit a `pit_id` and a matched `pit_id_outer`. 110/110 inner pits paired cleanly to a unique outer rim. One outer rim is unmatched (likely a "rim only" annotation).
5. **Constructs a pit-wall layer** as `pit_outside ∖ pit_inside` per matched pair — the donut between the rim and the floor. 110 wall polygons.
6. Spatial-joins `plat_id` onto every other layer:
   - Polygon features (pit_inside, pit_outside, pit_wall) → joined by **centroid** location.
   - Line features (roads, not_roads) → joined by **midpoint** intersection.
7. Writes a 6-layer GeoPackage and prints a coverage summary.

The output GeoPackage has these layers:

```
plat         79 polygons   + plat_id, area_m2, n_pits, n_roads, n_not_roads
pit_inside  110 polygons   + pit_id, plat_id
pit_outside 111 polygons   + pit_id_outer, pit_id (matched), plat_id
pit_wall    110 polygons   + pit_id, plat_id
roads        97 lines      + plat_id (if midpoint inside a plat)
not_roads    37 lines      + plat_id (if midpoint inside a plat)
```

## Step 2 — Labeled rasters + spatial-block splits

**Scripts:**
- `notebooks/wellsight/annotations/_build_pit_dataset.py`
- `notebooks/wellsight/annotations/_build_plat_road_dataset.py`

**Outputs:**
- `data/derivatives/9t/labels_pit_9t_05.tif` — uint8 (0=bg, 1=floor, 2=wall) at 0.5 m, aligned to `dem_9t_05.tif`
- `data/derivatives/9t/labels_plat_9t_05.tif` — uint8 (0/1) plat mask
- `data/derivatives/9t/labels_road_9t_05.tif` — uint8 (0/1) road mask, roads buffered 1.5 m
- `data/derivatives/9t/mask_plat_9t_05.tif` — same as above but binary (legacy name)
- `data/derivatives/9t/pit_blocks_9t.gpkg` — 12×12 spatial-block grid + split column
- `data/derivatives/9t/pit_dataset_manifest.csv` — per-pit table (pit_id, plat_id, block_id, split, centroid_x/y)
- `data/derivatives/9t/plat_dataset_manifest.csv` — per-plat split table
- `data/derivatives/9t/road_dataset_manifest.csv` — per-road-line table
- `data/derivatives/9t/road_classifier_samples.csv` — sample points along every road / not_road line, every 4 m, for the road patch classifier

### Pit label rasterization

Burn order matters: walls first at value 2, then floors at value 1 on top, so floor wins on any overlap. `all_touched=False` to keep the labels conservative.

Resulting class balance on the full 9000 × 9000 tile:

| Class | Pixels | Area (m²) | Share |
|---|---:|---:|---:|
| Background (0) | 80,911,470 | 20,227,868 | 99.89% |
| Floor (1) | 14,691 | 3,673 | 0.018% |
| Wall (2) | 73,839 | 18,460 | 0.091% |

This is the extreme imbalance that motivates focal loss. Both pit classes combined are 0.11% of pixels.

### Spatial-block split

A 12×12 grid (144 cells, 375 m each) across the 4.5 km tile. Each pit-bearing block goes whole to train, val, or test — never split. Assignment is **pit-count balanced** (greedy fill): blocks are shuffled (seed 42), each block goes to whichever split has the largest deficit relative to its 70/15/15 pit-count target.

Resulting pit counts:

| Split | Blocks | Pits |
|---|---:|---:|
| train | 17 | 74 |
| val | 4 | 16 |
| test | 3 | 20 |
| (unused — no pits) | 120 | 0 |

Cross-iteration consistency: **every iteration uses this exact split.** Training and validation can be re-shuffled within those pits; the 20 test pits are never touched until the iteration's final eval.

### Plat split

Independent of the pit split; same logic. 79 plats → 51 train / 16 val / 9 test / 3 unused.

### Road split

97 roads → 63 / 17 / 17. 37 not_roads → 32 / 3 / 2. Per-line splits driven by the line's midpoint's block.

The road *classifier* also samples 6,312 points along the line set every 4 m for patch-classifier training. See `data/derivatives/9t/road_classifier_samples.csv`.

## Caveats worth knowing

- **41 of 110 inner pits sit "off-plat"** — outside any plat polygon. The plat set is incomplete (or some pits are genuinely outside platted pads). For pit modeling this is fine (plat info isn't used as a label), but it limits using `plat_id` as the split-grouping key. We use spatial blocks instead.
- **`pit_outside` had 111 polygons but only 110 inner pits.** One outer rim has no matched inner (likely intentional or annotation noise). It's silently dropped from `pit_wall`.
- **All annotations are user-drawn.** Imperfect boundaries are expected. Don't over-fit metrics to the exact pixel — per-pit IoU is the right level of granularity.
- **Roads are buffered 1.5 m for label rasterization** — that's a half-width of 3 m total, roughly matching access-road width on the ground.

## How to add a new annotation layer

1. Draw in QGIS in any CRS (EPSG:4326 is fine — it'll be reprojected).
2. Drop the .shp + sidecar files in `data/derivatives/annotations/`.
3. Add the layer to `_prep_annotations.py`'s `main()` (load it, validate it, optionally spatial-join `plat_id`).
4. Rerun `_prep_annotations.py` to regenerate `annotations_proj.gpkg`.
5. If the new layer needs a label raster, add it to the appropriate `_build_*_dataset.py` script.

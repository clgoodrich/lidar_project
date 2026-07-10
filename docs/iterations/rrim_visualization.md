# Red Relief Image Map (RRIM) visualization

**Date:** 2026-07-07
**Script:** `notebooks/wellsight/build/_make_rrim.py`
**Tile:** 613590 (9-tile / 3×3 block, 1 m, EPSG:6346, 4500×4500 = 4.5×4.5 km)

## Goal

Add an RRIM terrain visualization to the WellSight toolkit. RRIM encodes slope and
ridge/valley position in one direction-independent composite, so subtle micro-relief
(pit depressions, pad cut-and-fill, road benches, drainages) reads clearly without the
directional bias of a single hillshade.

## Method

Two recipes, selectable by flag:

- **Classic RRIM** (Chiba, Kaneta & Suzuki 2008, default). Base = *differential
  openness* `DO = (openness_pos − openness_neg) / 2`, colored on a diverging ramp
  (concave/valley → teal, flat → gray, convex/ridge → pale yellow). Overlaid with a
  *slope* layer colored white (0°) → vivid red (`slope_hi`, default 40°), multiplied
  over the base. Uses `openness_pos`/`openness_neg` already produced by the derivatives
  pipeline — no recompute.
- **Simple Red Relief** (`--simple`; Auld-Thomas 2022, patent-free). Same slope overlay,
  but base = Local Relief Model (`lrm_11`) instead of openness.

Color stops taken from Auld-Thomas' published recipe (teal `0,158,162` / gray
`138,138,138` / yellow `254,255,172`; slope white → red `182,39,0`). `DO`/`LRM` range is
set per-tile from the p98 of |base| so the palette self-scales to the terrain (WPA is far
gentler than the Maya karst the stops were tuned on). `slope_hi` fixed at 40° (tile slope
p98 ≈ 35°).

## Inputs / provenance

`slope_613590_1m.tif`, `openness_pos_613590_1m.tif`, `openness_neg_613590_1m.tif`
(classic) or `lrm_11_613590_1m.tif` (simple) — all from the standard derivatives build.
Papers: `papers/` → *2008 RedReliefImageMap.pdf*, *2022 A Recipe for Simple Red Relief.pdf*.

## Results

Two builds of the same block (613590):

**1 m (`data_3x3/westernpa_d20/613590/`):**
- `rrim_openness_613590_1m.tif` (44 MB) — classic; differential openness ±5.15°.
- `rrim_simple_613590_1m.tif` (43 MB) — LRM base.
- `rrim_*_1m_preview.png` (2250 px) — committed as the visual record.

**0.5 m native (`data/derivatives/tiles/9t/`, the canonical 9t stack):**
- `rrim_openness_9t_05.tif` (176 MB, 9000×9000) — differential openness ±4.50°.
- `rrim_simple_9t_05.tif` (174 MB) — LRM base.
- `rrim_*_05_preview.png` (1800 px).

**All study blocks (`label_grids/<block>/`, 1 m):** classic RRIM generated for all 8
blocks (4 permian + 4 westernpa); Simple/LRM variant where an `lrm_11` raster exists
(permian_01 + all 4 westernpa). permian_02/03/04 had openness but no slope raster —
slope derived from their DEM with `gdaldem slope -compute_edges`, then classic RRIM built.
The palette self-scales per block: flat Permian desert lands at DO ±1.5° (well pads read
as sharp rectangular platforms, lease-road grid crisp), WPA at ±4–5° (incised stream
valleys in vivid red/teal, full drainage network). Outputs are `rrim_{openness,simple}_
<block>_1m.tif` (~20 MB at 3000², ~41 MB at 4500²) + previews. All gitignored under
`label_grids/**` (tifs and pngs), regenerable.

**Remaining reachable stacks (2026-07-09):** classic + simple built for the top-level
`data/derivatives/` stacks — `9t_1m` (DO ±4.72°), `mk5_1m` (±5.54°),
`mck_e1423n2238_05` (McKean 0.5 m, ±5.13°) — and the four single validation tiles
`607594` / `610594` / `610605` / `616593` (1500², DO ±3.6–5.8°). The singles had no
`openness_pos` raster; it was computed from each tile's DEM with the production
`openness()` (Yokoyama 1998, L = 25 m) from `_build_derivatives.py` and written as
`openness_pos_<tile>_1m.tif` (means ≈ 87–88°, consistent with the existing
`openness_neg` era). All outputs land at the top level (`rrim_{openness,simple}_
<tile>_<sfx>.tif` + previews) and are gitignored there (`data/derivatives/*.tif`,
`*.png`), regenerable.

**E:-hosted stacks (2026-07-09, after the T7 remounted):** classic + simple for all 24
remaining `data_3x3/westernpa_d20` blocks (48 products, 0 failures) and
`northcentral_b19` e1423n2235/e1423n2238 (e1423n2238's missing openness pair computed
from its DEM); classic only for the DEM-only blocks e1426n2236/e1426n2239 (slope via
`gdaldem slope -compute_edges` + openness computed; no `lrm_11`, same precedent as
permian_02–04); and `tiles/mkf_1m` — the full McKean county 1 m stack, 10000²
(classic 122 MB / simple 119 MB, DO ±6.29°; both under the `data/derivatives/**/*.tif`
ignore rule). Preview PNGs (~1.9 MB) tracked as the visual record. **Skipped:**
`tiles/613590_05` — no slope/openness/lrm inputs and the canonical `tiles/9t` 0.5 m
RRIM covers the identical footprint. With this, every stack in the repo that has (or
can derive) inputs now carries an RRIM.

The 0.5 m version is the working product going forward — 4× the pixels resolves the
dendritic drainage as crisp teal threads, road benches as fine linears, and small
depressions that the 1 m build blurred. Classic gives deeper valley contrast; simple/LRM
is flatter but crisper on fine linear features. The full-tile GeoTIFFs are regenerable and
gitignored (the whole `tiles/9t/` dir is ignored); only the 1 m previews are tracked.

## Reproduce

```bash
# 1 m block build (data_3x3)
python notebooks/wellsight/build/_make_rrim.py --tile 613590            # classic
python notebooks/wellsight/build/_make_rrim.py --tile 613590 --simple   # LRM base

# 0.5 m native (canonical 9t stack) — inputs are slope_9t_05.tif etc.
python notebooks/wellsight/build/_make_rrim.py --tile 9t --suffix 05 \
    --dir data/derivatives/tiles/9t                # classic
python notebooks/wellsight/build/_make_rrim.py --tile 9t --suffix 05 \
    --dir data/derivatives/tiles/9t --simple       # LRM base
```

`--suffix` selects the input resolution token (`1m` for the data_3x3 build, `05` for the
0.5 m 9t stack); filenames are `<name>_<tile>_<suffix>.tif`.

## Next

- Zoom to known-well locations from `output_wells.csv` to confirm pit/pad RRIM signatures
  (depressions should read as teal cores ringed in red).
- If useful for annotation, consider RRIM as an extra visual layer in the labeling stack
  (not a model input — it is derived from existing bands).

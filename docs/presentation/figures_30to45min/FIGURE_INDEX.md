# Figure index

Every image in this folder: what it shows, where its numbers come from, and which
script rebuilds it. 77 images, 10 builders.

All builders are re-runnable and read from data on disk. Nothing is hand-drawn
except the pipeline diagram, and nothing carries a typed-in number except the two
classical AUC values, which are flagged where they appear.

---

## The study site

Most of the map images are the same **300 m square in Venango County**:

```
41.492640 N, -79.546127 W  ->  621359.6 E, 4594467.4 N (EPSG:6346)
9t tile, 1,467 m inside the nearest tile edge, 0.5 m data
```

Using one place for everything means the derivative images, the annotation
images, the probability images and the argmax images are all literally the same
ground. A viewer can carry what they learned from one slide to the next.

To move the site, change `LAT`, `LON` and `SIDE_M` at the top of any builder.
Each writes into `venango_site_<coords>/`, so a new location does not overwrite
an old one.

---

## 1. Deck-level figures — `./`

| image | what it shows | builder |
|---|---|---|
| `locator_study_areas_pa.png` | 6 Venango tiles, McKean, and an extent table for all seven | `_build_presentation_figures.py` |
| `pipeline_diagram_classical_and_unet_branches.png` | schematic. **Needs redrawing as one path** — the outline cut the classical branch | `_build_presentation_figures.py` |
| `annotation_growth_pit_splits_426_527_712.png` | 426 → 527 → 712 pit floors, split composition each time | `_build_presentation_figures.py` |
| `annotation_growth_pad_splits_650_995_9t.png` | 650 → 995 pads; the two 995 bars hold the same pads with different splits | `_build_presentation_figures.py` |
| `annotation_schema_one_pad_one_pit_9t_05.png` | one pad with its floors and road, then floor/rim/full on one pit | `_build_presentation_figures.py` |
| `spatial_block_split_grid_12x12_9t_ann712.png` | 144 blocks by split, plus block-share against pit-share | `_build_presentation_figures.py` |
| `threshold_sweep_flagged_area_vs_recall_pit_pad_road_9t.png` | **the headline.** flagged area vs recall, all three tasks | `_build_presentation_figures.py` |
| `nisar_gcov_hh_hv_clip_9t_10m_20260120.png` | NISAR HH / HV / HH−HV over 9t | `_build_presentation_figures.py` |
| `classical_vs_unet_pit_detection_same_scene_9t.png` | **unused.** The outline cut the classical branch; kept on disk | `_build_presentation_figures.py` |
| `rrim_formula_card_chiba2008_9t_05.png` | how RRIM is computed, with Chiba et al. 2008 cited | `_build_rrim_formula_card.py` |
| `pit_split_held_out_blocks_9t.png` | which pits the model was never allowed to see | `_build_split_and_undecided.py` |
| `pit_outcomes_matched_undecided_missed_9t.png` | what it found, flagged, and missed, whole tile | `_build_split_and_undecided.py` |
| `pit_undecided_review_queue_zoom_9t.png` | the review queue up close, on RRIM | `_build_split_and_undecided.py` |
| `road_chunking_40m_cuts_9t_700m.png` | roads cut into ~40 m chunks, cut points marked | `_build_road_chunking.py` |
| `road_chunking_40m_by_split_9t_700m.png` | the same chunks coloured by train / val / test | `_build_road_chunking.py` |

## 2. The site, every way we look at it — `venango_site_41p492640N_79p546127W/`

**Twelve views of the same ground**, each standalone with scale bar and north
arrow. Builder: `_build_derivative_panel.py`.

```
_300m_aerial_9t_05.png          ESRI World Imagery — solid canopy, ground invisible
_300m_hillshade_9t_05.png       the standard shaded relief
_300m_dem_9t_05.png             bare-earth elevation
_300m_slope_9t_05.png           slope
_300m_lrm_5_9t_05.png           local relief, 5 m window — fine texture
_300m_lrm_25_9t_05.png          local relief, 25 m window — larger forms
_300m_tpi_05_9t_05.png          topographic position
_300m_openness_pos_9t_05.png    positive openness — convex features
_300m_openness_neg_9t_05.png    negative openness — concave; this is where pits live
_300m_roughness_11_9t_05.png    roughness
_300m_rrim_9t_05.png            Red Relief Image Map
_300m_chm_9t_05.png             canopy height — the forest hiding it all
```

The aerial panel is the argument for the whole project in one image: from above
it is unbroken canopy, and every other panel shows roads, benches, channels and
depressions on the same 300 m.

**Aerial imagery is fetched live from ESRI World Imagery** and is visual context
only — it is used in no analysis. There is no aerial photography in the
repository. `rgb3_9t_05.tif` looks like it might be and is not: it is a 3-band
composite of derivatives built to feed YOLO.

**Five annotation views on the RRIM base.** Builder:
`_build_rrim_annotation_series.py`.

```
_300m_rrim_drainage_9t_05.png   17 drainage lines
_300m_rrim_roads_9t_05.png       7 road lines
_300m_rrim_pits_9t_05.png        2 pit floors
_300m_rrim_pads_9t_05.png        4 pads
_300m_rrim_all_9t_05.png         all four together
```

RRIM is the base because it shows concave and convex at once with no lighting
direction — a hillshade hides whatever faces away from its light, which is the
wrong property when you are showing where a hand-drawn polygon sits relative to
the landform. Annotation colours deliberately avoid RRIM's own red and cyan.

**Four probability surfaces and four argmax maps.** Builder:
`_build_probability_surfaces.py`.

| image | source raster | note |
|---|---|---|
| `_300m_prob_pit_9t.png` | `pit/unet_v2/pit_prob_floor.tif` | max p 0.95 here |
| `_300m_prob_pad_9t.png` | `pad/unet/pad_prob.tif` | max p 0.89 |
| `_300m_prob_road_9t.png` | `road/sweep_202607/cldice/road_prob.tif` | 1 m |
| `_300m_prob_drainage_9t.png` | `drainage/unet_1m/drainage_prob.tif` | 1 m |
| `_300m_argmax_pit_9t.png` | `pit/unet_v2/pit_argmax.tif` | floor + wall |
| `_300m_argmax_pad_9t.png` | `pad/unet/pad_argmax.tif` | binary |
| `_300m_argmax_road_9t.png` | `road/unet_1m_recall/road_argmax.tif` | road + drainage |
| `_300m_argmax_drainage_9t.png` | `drainage/unet_1m/drainage_argmax.tif` | drainage-positive model |

Probability is what the network outputs; argmax is what it commits to once a
decision is forced. Showing both is the cleanest way to explain why a threshold
is a choice and not a detail.

Pixels below probability 0.05 are not drawn — a pale wash over the whole tile
makes the model look far less certain than it is.

**Road and drainage share one 3-class model**, so their argmax rasters carry both
classes. The two are the same architecture with the focal weights flipped, which
is why each rejects the other's class almost perfectly.

## 3. Out of domain — `tile_613590/`

Builder: `_build_613590_outcomes.py`. A tile no model ever trained on.

| image | what it shows |
|---|---|
| `roads_613590_generated_network_t030.png` | the generated network: 3,693 segments, 231.4 km |
| `roads_613590_generated_vs_tiger.png` | the same against TIGER: 39 features, 40.0 km — **5.8x more road** |
| `roads_613590_found_vs_missed_added_thr0p50.png` | found vs missed on the informative subset only |
| `pit_pad_candidates_613590.png` | pit and pad candidates, transferred with no retraining |

**The caution that belongs on the slide.** 613590's road truth splits by `src`.
`613590_review_r2` (4,004 chunks) is a previous model's own output that a human
vetted, and every model scores 0.96-1.00 on it — that subset ranks nothing.
`613590_added_r2` (1,496 chunks) was drawn from scratch on roads the model
missed, so it is the only informative half and it is adversarially hard by
construction. The found-vs-missed image uses **only** the added subset, and says
so on its face.

The road vectorisation comes from `roads_studio/exports/faithful_613590_deployed_t030.gpkg`
— the "faithful" extraction, which strips and traces without inventing or
deleting. Earlier island-filtering and reconnection attempts all produced
"you're deleting roads" regressions.

## 4. Point-cloud cross-sections — `cross_sections/`

Builder: `notebooks/wellsight_v2/s7_analysis/_cross_section_classification.py`.

Cut a line anywhere, buffer it left and right, and project every return in the
corridor onto the line, so the figure reads as though all of them lay exactly on
the cut. This is not an axis-aligned slice — the line can run at any azimuth.

| image | what it shows |
|---|---|
| `cross_section_pit_616591_72m_az172_w2p0.png` | a 104 m² annotated pit, cut along its long axis; 2,526 returns, 663 unassigned → 284 |
| `cross_section_pad_621594_357m_az5_w2p0.png` | an annotated pad on a 9t tile; 2,735 returns |
| `cross_section_venango_41p484384N_79p518911W_622593_200m_az90_w3p0.png` | the 41.484384 N, -79.518911 W site, 200 m east–west |

Each figure has four panels: a locator map of the corridor built from the ground
returns in the crop, the points **as delivered** (two classes), the points
**reclassified** by height above ground, and the ground surface on its own
vertical scale — because a 1.5 m pit is invisible against 25 m of canopy.

Classification follows the USGS 3DEP Lidar Base Specification bands (ASPRS 3 / 4
/ 5 at 2 m and 5 m). Returns below the surface are split into coherent and
isolated by fitting a local plane and measuring the residual, **not** the raw
vertical range — on a 20% hillside a 2 m radius spans 0.4 m of genuine relief,
so a range test throws away real surfaces for being tilted.

```bash
python notebooks/wellsight_v2/s7_analysis/_cross_section_classification.py --pit --tile 616591
python notebooks/wellsight_v2/s7_analysis/_cross_section_classification.py --center 623647.2,4593589.3 --azimuth 90 --length 200 --width 3
```

## 5. Site imagery on demand — `venango_site_<coords>/`

Builder: `notebooks/wellsight_v2/s7_analysis/_build_site_rrim_image.py`. Give it
a latitude and longitude and it finds whichever RRIM in the repo covers that
point, picks the finest resolution available, and writes a figure plus a
georeferenced GeoTIFF of the same extent.

```bash
python notebooks/wellsight_v2/s7_analysis/_build_site_rrim_image.py --lat 41.484384 --lon -79.518911 --side 200
```

---

## A note on figure footers

As of 2026-09-18 there is **no text along the bottom of any figure except a
method citation**, and only where the rendering itself comes from a paper:

```
RRIM              Chiba et al. 2008
openness          Yokoyama et al. 2002
optical panel     ESRI World Imagery, visual context only
```

Coordinates, CRS, source paths and pixel counts were removed from the images.
They live in this index instead.

Two caveats were **moved to the top of their figure rather than deleted**,
because they change how the figure should be read and a footer can be cropped
off a slide:

- `rrim_vs_prob/*` — the window was chosen by density of above-threshold pixels,
  not by eye, and is a best case by construction.
- `tile_613590/roads_613590_found_vs_missed_added_thr0p50.png` — scored on the
  `613590_added_r2` subset only.

---

## Sources

```
qgis/annotations/annotations_proj.gpkg          all annotation counts
data/9t/derived/05/                              derivatives, labels, blocks, manifests
data/9t/models/{pit,pad,road,drainage}/          probability and argmax rasters
data/9t/results/pit/centroid_matching/           matched / undecided / missed
data/613590/, data/westernpa_d20/613590/         out-of-domain products
roads_studio/exports/                            faithful road vectorisation
docs/iterations/LEADERBOARD.md                   every model metric
literature/CITATIONS.md                          Chiba 2008, Yokoyama 2002
```

## Known gaps

- **The pipeline diagram still shows two branches.** The outline cut the
  classical branch on 2026-09-17; it needs redrawing as one path.
- **No pit or pad probability raster exists for 613590** — only extracted
  candidates. Building one needs `features_613590_05.tif` restored from a mirror
  first; it was removed in the 2026-09-18 raster cleanup.
- **The undecided layer is ann527-era** (2026-08-05, precision 0.699, recall
  0.949). The pit model was retrained on ann712 on 2026-09-17, so some of the 207
  undecided candidates may already be annotated. Re-run
  `s5_eval/_build_undecided_pit_candidates_9t.py` to refresh it.
- **`road_chunks_9t.gpkg` spans far beyond 9t** because `roads.shp` runs from Oil
  Creek to McKean. Any density search over it must be clipped to the tile first,
  or the chosen window falls outside the hillshade.

## Rebuilding

```bash
python docs/presentation/figures_30to45min/_build_presentation_figures.py
python docs/presentation/figures_30to45min/_build_derivative_panel.py
python docs/presentation/figures_30to45min/_build_rrim_annotation_series.py
python docs/presentation/figures_30to45min/_build_rrim_formula_card.py
python docs/presentation/figures_30to45min/_build_probability_surfaces.py
python docs/presentation/figures_30to45min/_build_split_and_undecided.py
python docs/presentation/figures_30to45min/_build_road_chunking.py
python docs/presentation/figures_30to45min/_build_613590_outcomes.py
```

`figure_notes_what_each_image_shows.md` in this folder carries the longer
write-up for the nine original deck figures, including the exact numbers each
one puts on screen.

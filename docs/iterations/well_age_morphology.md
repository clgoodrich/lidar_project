# well_age_morphology — does pad/pit geometry encode drilling era?

**Date:** 2026-07-19 · **Script:** `notebooks/wellsight_v2/s7_analysis/_well_age_morphology.py` · **Outputs:** `data/derivatives/experiments/well_age_morphology/`

## Goal

PA DEP spud dates are missing exactly where we need them: 92% of the DEP Orphan
List in Venango County carries the `1800-01-01` "historic, date unknown"
sentinel (997 of 1,079 orphans; only 82 have real dates). Question: can pad/pit
surface morphology recover an era signal, calibrated on the wells that DO have
real dates, so undated wells could be binned by age?

## Inputs / provenance

- `data/derivatives/venango_wells_all.gpkg` — 20,108 Venango wells (PA DEP Oil
  & Gas locations). Date fields: `SPUD_DATE` 92.3% populated but 8,054 rows are
  the 1800 sentinel; `PERMIT_DAT` 86.1%; `DATE_PLUGG` 35.6%.
- `data/derivatives/annotations/plat.shp` — 1,053 rows, of which **58 have
  null geometry** (QGIS delete artifacts; true pad count 995 — this run
  resolved the "stale gpkg" BACKLOG item as a misdiagnosis); `pit_inside.shp`
  — 426 pits. EPSG:6346.
- Wells restricted to within 200 m of any annotation (n = 1,176) so "no pad
  match" means absence, not un-annotated ground.

## Params

Match radius 50 m (DEP historic positional uncertainty default, data dictionary
note 2). Morphology per pad: area, perimeter, compactness 4πA/P², elongation
(min-rotated-rect aspect), wells-sharing-pad; per well: has_pad, has_pit flags.
Era bins: pre-1956 / 1956–1979 / 1980–1999 / 2000+.

## Results

**Population caveat first:** the annotated area is dominated by permit-era
wells — 1,118 real-dated vs only **46 sentinel-1800** wells. No real-dated well
in the area predates 1956 (expected: PA permitting began 1956). Era n: 407
(1956–79), 195 (1980–99), 13 (2000+).

**Within the dated range, morphology carries a real but weak era signal**
(n = 615 pad-matched dated wells; Spearman vs spud year):

| Feature | ρ | p |
|---|---|---|
| perimeter | −0.273 | 6e-12 |
| wells_on_pad | −0.258 | 8e-11 |
| compactness | +0.232 | 6e-9 |
| area | −0.203 | 4e-7 |
| elongation | +0.05 | 0.22 (ns) |

Direction: newer wells in this field sit on *smaller, rounder, less shared*
pads — consistent with 1980s single-well conventional pads vs older multi-well
lease clusters. Kruskal–Wallis across era bins agrees (all p < 0.004 except
elongation).

**Binning power is modest.** A 5-fold cross-validated random forest separating
1956–79 from 1980–99 (n = 602): balanced accuracy **0.609 ± 0.038**, ROC-AUC
**0.660**. Better than chance, far from decision-grade. Top features:
compactness (0.29), elongation (0.22), perimeter (0.21).

**The deployment contrast is underpowered.** Dated-modern vs sentinel-historic
(the case we actually care about): no feature significant (all p > 0.13), but
only 20 sentinel wells have a matched pad — the historic population barely
overlaps the annotated area.

## Interpretation

1. Age is partially coded in: use real `SPUD_DATE` (excluding the 1800
   sentinel) + `DATE_PLUGG` + status class directly where present.
2. Morphology alone, with current 2-D shape features, is a weak binner
   (AUC 0.66). Not useless — usable as a prior/covariate — but not a
   classifier to assign era bins per well.
3. The interesting population (sentinel-1800 historic orphans) is mostly
   outside the annotation footprint. Any morphology-vs-era conclusion for them
   needs annotations where they live, or DEM-derived features (pit depth,
   pad cut/fill volume) that don't depend on hand polygons.

## Next steps (added to BACKLOG)

- Add DEM-derived per-well features (depth_in_sink at well, pad cut/fill
  volume, road-width at nearest road) — 2-D outlines may under-represent the
  era signal that 3-D relief carries.
- Annotate a block with a high sentinel-1800 density to power the
  historic-vs-modern contrast (current n = 46/20).
- If binning is pursued: two coarse bins (permit-era vs pre-permit) via the
  status taxonomy + sentinel flag is already 100% "accurate" by construction —
  morphology only needs to resolve *within* pre-1956, which requires the above.

## QGIS deliverable (added 2026-07-19)

`data/derivatives/experiments/well_age_morphology/well_age_morphology.gpkg`
(EPSG:6346, default styles embedded in `layer_styles` — drag into QGIS and it
renders colored). Built by
`notebooks/wellsight_v2/s7_analysis/_export_well_age_qgis.py`. Layers:

- `wells_annotated_area` — 1,176 catalog wells near annotations, colored by
  era (orange 1956–79, green 1980–99, blue 2000+, red historic-undated,
  gray no-date).
- `pads_age` — 995 pads colored by matched-well age class (`age_class`);
  508 are "no catalog well within 50 m" — mostly pads in survey blocks
  outside Venango County (plat.shp is repo-wide, the catalog is county-only).
- `wells_venango_all` — full 20,108-well catalog by date class; shows the
  historic (sentinel) wells clustering SW of the 9t footprint.

Static preview: `fig_map_context.png` (county overview + 9t era map).

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_well_age_morphology.py
python notebooks/wellsight_v2/s7_analysis/_export_well_age_qgis.py
```

# Session Resume — WellSight Paper & Pipeline Work

**Last updated:** 2026-05-01
**Status:** Enriched well dataset acquired, pipeline parameters literature-grounded, all detectors re-run, presentation generated

---

## Most Recent Session (2026-04-29 → 2026-05-01)

### 1. Well Status Identification Problem
User asked: how do we distinguish active vs abandoned vs orphaned wells, and can we get ground-level imagery?
- **LiDAR alone cannot distinguish well status** — that's an administrative/legal classification from PA DEP
- The original DEP orphan dataset (`output_wells.csv`, 84 wells) and USGS dataset (4,786 wells) are both attribute-sparse: just coordinates + "Orphan" status
- Aerial imagery won't help in heavy Appalachian canopy — boots-on-the-ground field verification needed

### 2. Acquired Enriched Well Dataset from PASDA
Downloaded **PA DEP Oil & Gas Locations** (April 2026 release) from PASDA:
- **223,742 wells statewide**, 42 attribute fields
- **20,108 wells in Venango County** with: SPUD date (92%), operator (99.9%), well type, status (10 categories), permit/plugged dates, surface elevation
- Saved as:
  - `data/derivatives/venango_wells_all.gpkg` (full Venango, EPSG:6346)
  - `data/derivatives/wells_in_tile_enriched.gpkg` (1,109 wells clipped to LiDAR tile)
- Source zips in `data/files/`: `OilGasLocations2026_04.zip`, `OilGasLocations_ConvUnconv2026_04.zip`, `PADEP_HistoricOilGasWells_ALL.zip`
- Also: Historic Wells from WPA mine maps (`data/files/HistoricWells/`)
- Tile status breakdown: 634 Active, 276 Plugged, 167 Abandoned, 20 Orphan, 12 Not Drilled

### 3. Built Well Status Comparison Maps
- `data/derivatives/wells_by_status_hillshade.png` — overview of 1,109 wells by status on hillshade
- `data/derivatives/well_status_comparison_zoom.png` — 300m zoom windows comparing Orphan vs Active vs Plugged vs Abandoned
- 20 orphan wells in tile are mostly 1970s T R Potts lease oil wells managed by PA DEP

### 4. Literature-Grounded Parameter Audit & Adjustments (v0.6)
Full audit of all pipeline parameters against published literature. Most were already supported. Four adjusted:

| Parameter | Old | New | Citation |
|-----------|-----|-----|----------|
| Pad slope threshold | 5.0° | **8.0°** | Drohan & Brittingham (2012, Env Mgmt 49:1061) |
| Pad minimum area | 80 m² | **100 m²** | Hammack et al. (2014, NETL) |
| Pit blob max_sigma | 3.5 | **5.0** | Hammack et al. (2014, NETL reserve pits) |
| Positional uncertainty | 100m | 100m (kept; 200m for pre-1950 noted) | Kang et al. (2014, NETL/DOE) |

Files modified:
- `notebooks/03_pad_detector.ipynb` — slope + area params with citations
- `notebooks/03c_pit_detector.ipynb` — blob max_sigma extended, num_sigma 6→8
- `notebooks/03_road_detector.ipynb` — citation comments added
- `docs/04_feature_detection_design_spec.md` — threshold table updated
- `docs/analysis_log.md` — full v0.6 entry with all citations

### 5. Generated Presentation
- `WellSight_Presentation.pptx` — 16 slides, dark theme, tables + images on every slide
- Built via `_build_presentation.py` (python-pptx)
- Slides: Title, Problem, Why LiDAR, Study Area, Three Detectors, Terrain Derivatives, Pit Results, Pit Morphology, Road Results, Well Enrichment, Active vs Orphaned comparison, Literature Parameters, Ensemble Performance, Challenges, Future Work, Summary
- 44 MB due to embedded PNGs from `data/derivatives/` and project root
- Under 75 words per slide, heavy use of tables and graphics

### 6. Re-ran All Three Detector Notebooks

**Pad detector v0.6:** 3,844 raw → 4 after gates, 3/4 within 100m of well. Area 115-789 m² (realistic). The area_min increase (80→100) eliminated many small false positives.

**Pit detector (extended blob):** 2,504 candidates (up from 2,387), 767 probable (up from 667). Precision @ 10m: 15.7% (up from 14.7%). OOB: 0.9223. Max radius: 4.95m.

**Road detector:** Output unchanged (only citation comments added). 191 segments, 164/191 within 100m of well.

### Literature References Confirmed for Existing Parameters
- DEM 1m: Hesse (2010), Doneus (2013)
- TPI 5/15/25.5m: Weiss (2001), De Reu et al. (2013)
- LRM 5/11/25/51: Hesse (2010), Bofinger et al. (2006)
- Roughness 11×11: Riley et al. (1999), Grohmann et al. (2011)
- Openness 25m: Yokoyama et al. (2002), Doneus (2013)
- Ridge sigmas 1/2/3: White et al. (2010)
- Blob LoG 0.8-5.0: API standards, Hammack et al. (2014)

---

## Previous Session (2026-04-21)

### Pit Morphology & Paper Work
- Extracted physical parameters for all 861 annotated pits (depth, radius, volume, etc.)
- Anomaly detection on training labels: 90 pits (10.5%) flagged
- Pit rim polygons via radial spoke algorithm: 853 polygons
- Geomorphon enclosure implementation: improved PR-AUC 0.212 → 0.279 (+31%)
- Paper skeleton generated: `WellSight_Paper_skeleton_v3.docx`
- Pipeline notebook: `notebooks/wellsight_morphology_pipeline.ipynb`

---

## Key Files

### Data
| File | What |
|------|------|
| `data/derivatives/venango_wells_all.gpkg` | 20,108 Venango wells with full attributes (EPSG:6346) |
| `data/derivatives/wells_in_tile_enriched.gpkg` | 1,109 wells in LiDAR tile with SPUD, operator, status |
| `data/derivatives/candidates/candidates_pads.gpkg` | 4 pad candidates (v0.6) |
| `data/derivatives/candidates/candidates_pits.gpkg` | 2,504 pit candidates (extended blob) |
| `data/derivatives/candidates/candidates_roads.gpkg` | 191 road segments |
| `data/derivatives/pit_1m_candidates_ensemble.gpkg` | 628k ranked candidates (main pipeline) |
| `data/derivatives/pit_1m_morphology_audit.gpkg` | 856 pits with morphology + anomaly scores |

### Maps
| File | What |
|------|------|
| `data/derivatives/wells_by_status_hillshade.png` | All 1,109 wells by status on hillshade |
| `data/derivatives/well_status_comparison_zoom.png` | Zoom comparison of well statuses |

### Paper
| File | What |
|------|------|
| `WellSight_Paper_skeleton_v3.docx` | Skeleton for manual writing |
| `WellSight_Paper_v5.docx` | Full text version (may need updating) |

### Pipeline Scripts (in `notebooks/wellsight/`)
| File | What |
|------|------|
| `_build_wellsight_notebook.py` | Generates consolidated pipeline notebook |
| `_pit_pipeline_1m.py` | 1m detection pipeline |
| `_pit_morphology_audit_1m.py` | Morphology extraction + anomaly scoring |
| `_build_paper_docx.py` | Generates paper docx |

---

## Still To Do

### Immediate
1. **Era-dependent positional uncertainty** — use SPUD dates from enriched dataset: 200m for pre-1950, 100m for post-1950
2. **Confidence scoring weights** — derive from feature importance or cross-validation (currently arbitrary)
3. **Confidence tier cutoff (0.70)** — should be set by ROC analysis
4. **ML hyperparameter tuning** — formal CV for XGBoost/LightGBM params

### Paper
5. **Write paper body** in skeleton docx
6. **Future Work section:** geomorphons, U-Net, land cover, field validation
7. **Add ground-truth imagery** — consider NETL/DOE public domain well photos

### Data
8. **PA DEP OGRE reports** — browser-based interactive reports have per-well production data, could enrich further:
   - Well Inventory: `https://greenport.pa.gov/ReportExtracts/OG/OilGasWellInventoryReport`
   - Production: `https://greenport.pa.gov/ReportExtracts/OG/OilGasWellProdReport`
   - PASDA ArcGIS REST: `https://mapservices.pasda.psu.edu/server/rest/services/pasda/DEP/MapServer` (Layer 22)

---

## Paper Scope Rules
- STOP at morphology stats and anomaly detection. Geomorphons/spokes/rim polygons → Future Work only.
- Use "we" consistently, direct style, honest about failures, specific numbers inline.
- Figures inline, not appendix. Calibri 11pt, black, Heading 1/2.

## Key Numbers
| Metric | Value |
|--------|-------|
| Annotated pits | 861 |
| Ensemble ROC-AUC | 0.905 |
| Ensemble PR-AUC | 0.212 |
| Venango wells (enriched) | 20,108 |
| Wells in tile (enriched) | 1,109 |
| Pad candidates (v0.6) | 4 |
| Pit candidates (extended) | 2,504 |
| Road candidates | 191 |

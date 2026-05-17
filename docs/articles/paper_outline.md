# WellSight: LiDAR-Based Detection of Orphaned Oil and Gas Well Pits in Western Pennsylvania

## Paper Outline — Term Paper

> **Target length:** ~5,000–6,000 words (excluding references and appendices)
> **Format:** Academic term paper
> **Citation style:** APA 7th edition (author-date; standard for GIS/remote sensing)
> **Author:** Ryan (University of Houston)
> **Date:** April 2026
> **Starting point:** Clean start from `development_history.md` + `methodology.md`

---

## Document Status Key

Throughout this outline, the following tags indicate the content status of each
section and subsection:

| Tag | Meaning |
|-----|---------|
| `[SOURCE: dev_history]` | Content lives in `development_history.md` — needs to be written into prose |
| `[SOURCE: methodology]` | Content lives in `methodology.md` — needs to be written into prose |
| `[SOURCE: ramachandran]` | Content from the Ramachandran et al. (2024) comparative analysis |
| `[NEEDS WRITING]` | No existing content — must be written from scratch |
| `[CITE NEEDED]` | A specific citation must be located and verified before finalizing |
| `[VERIFY]` | A factual claim that needs independent verification |

---

## Outline Structure

### Abstract
**~200–250 words | `[NEEDS WRITING]` — write last, after all sections are final**

The abstract should cover:

- **Problem statement:** Pennsylvania's estimated 200,000+ undocumented abandoned
  oil and gas wells; inadequacy of existing state records (PA DEP covers ~8,840
  orphaned wells statewide; only 31% of documented coordinates land within 10m of
  visible LiDAR features)
- **Approach in one sentence:** A four-stage pipeline — terrain derivative
  generation, template-based candidate generation via normalized cross-correlation,
  gradient-boosted ensemble classification (XGBoost + LightGBM) on 88
  terrain-derived features, and isotonic-calibrated probability ranking
- **Key result:** ROC-AUC 0.987, PR-AUC 0.722 on the primary study tile;
  76% recall at 92% precision (proba ≥ 0.70); 35 novel candidate locations
  identified on an adjacent tile with zero documented wells
- **Significance:** LiDAR-based morphological detection outperforms satellite
  imagery approaches in forested Appalachian terrain (cite Ramachandran et al.,
  2024; Appalachian basin results: 0.647 precision, 0.552 recall
  `[VERIFY: source of Appalachian numbers]`)

---

### 1. Introduction
**~800–1,000 words | `[NEEDS WRITING]`**

The introduction should set up the problem, briefly justify the approach, and
state the contribution — nothing more.

#### 1.1 The Orphaned Well Problem
**~300 words**

- Pennsylvania as birthplace of American oil industry (Drake Well, 1859)
  `[CITE NEEDED: PA DEP orphaned well program documentation]`
- Scale of the problem: 200,000+ estimated undocumented wells statewide
  `[CITE NEEDED: PA DEP estimate source — Kang et al. 2014 or similar]`
- Environmental and safety hazards: methane emissions, groundwater contamination,
  physical hazards `[CITE NEEDED]`
- Current state records cover only a fraction; documented coordinates are
  unreliable (WPA-era survey precision of 30–100+ meters)

#### 1.2 Why LiDAR?
**~300 words**

- Wells are hidden under dense forest canopy — invisible to optical satellite
  imagery in Appalachian terrain
- The only surface evidence: subtle circular depressions (collapsed well cellars),
  typically 1–5 meters across, less than 1 meter deep
- Airborne LiDAR penetrates canopy and resolves sub-meter terrain features
- Existing deep learning approaches using satellite imagery (Ramachandran et al.,
  2024) show poor Appalachian performance — 0.647 precision, 0.552 recall
  `[SOURCE: ramachandran]` `[VERIFY: source of Appalachian numbers]`
- Brief mention of archaeological precedent for LiDAR-based feature detection
  (Trier et al., Freeland et al.) `[CITE NEEDED]`

#### 1.3 Contribution
**~200 words**

- State what WellSight does: a complete pipeline from raw LAS point cloud to
  ranked candidate well locations with calibrated probability estimates
- State what is novel: template-learned pit morphology as the candidate generator;
  multi-epoch temporal persistence features; spatially honest evaluation via
  GroupKFold; demonstration of cross-tile blind application
- State the paper's scope: describe the pipeline, report results on one annotated
  tile and one blind tile, discuss limitations and generalization challenges

---

### 2. Study Area and Data
**~600–800 words | `[SOURCE: methodology §2]` + `[SOURCE: dev_history §1, §3, §9]`**

#### 2.1 Study Region
**~200 words**

- Venango County, western Pennsylvania — Appalachian Plateau
- Terrain character: moderate to steep slopes, deeply incised stream valleys,
  dense deciduous/mixed forest
- Historical context: 150+ years of oil and gas extraction; Drake Well (1859)
  `[CITE NEEDED: historical reference]`
- Why this region: highest concentration of legacy oil and gas activity in PA;
  terrain representative of the broader detection challenge

#### 2.2 LiDAR Datasets
**~300 words**

- **Primary (2019):** USGS 3DEP Western PA flight
  - LAS 1.4, point format 7, EPSG:6346 (NAD83(2011) / UTM 17N)
  - ~4 pts/m², supporting 0.5m raster resolution
  - Primary tile: `output3.las` — 1.5 km × 1.5 km, 8.96M points
  - Blind test tile: `output2.las` — adjacent, 9.72M points, zero documented wells
  `[SOURCE: methodology §2.2]`
- **Secondary (2008):** PAMAP program
  - Originally EPSG:2271 (PA State Plane North, US survey feet)
  - Reprojected to EPSG:6346, Z converted (× 0.3048006096)
  - ~0.6 pts/m², 1m resolution ceiling
  - No vertical alignment correction — datasets kept separate
  `[SOURCE: methodology §2.2–2.3]`

#### 2.3 Well Records and Ground Truth
**~200 words**

- PA DEP orphaned well records: 107 wells in the study tile footprint
  - Used for reference/cross-validation only — NOT as training labels
  - Only 31% land within 10m of visible LiDAR features
  - 87% of expert-annotated pits have NO DEP record within 100m
  `[SOURCE: dev_history §9]`
- Expert annotations created in QGIS over hillshade:
  - 90 pit points (collapsed well cellars) — positive training labels
  - 88 pad polygons (leveled clearings) — spatial prior features
  - 96 road lines (abandoned access roads, 19.6 km) — spatial prior features
  `[SOURCE: methodology §5]`

---

### 3. Methods
**~1,500–1,800 words | `[SOURCE: methodology §3–9]`**

This is the technical core of the paper. The methodology.md already has this
content in specification form; the task here is converting it to narrative prose
while keeping the detail level appropriate for a term paper (not a full
reproducibility document).

#### 3.1 Terrain Derivative Generation
**~400 words**

- Point cloud → DEM via PDAL TIN interpolation (ground returns only)
- DSM from first-return maximum; CHM = DSM − DEM
- Derivative stack (all computed via scipy.ndimage unless noted):
  - Local Relief Model (LRM) at 4 scales (2.5m, 5m, 12.5m, 25m) — residual
    micro-topography after trend removal; the primary pit-detection channel
  - Topographic Position Index (TPI) at 3 radii (5m, 15m, 25.5m)
  - Topographic openness (Yokoyama et al., 2002) — positive and negative, 25m
    search distance `[CITE NEEDED: Yokoyama et al. 2002]`
  - Roughness (elevation σ in ~5m window)
  - Local relief (max−min in 10m disk)
  - Hillshade and slope via WhiteboxTools
  - Ground point density and mean intensity via laspy
- Resolution: 0.5m for 2019 data, 1.0m for 2008 PAMAP
- Same derivative stack built for both epochs independently
  `[SOURCE: methodology §4]`

> **Note for writing:** A summary table of all derivative channels with their
> physical scale and computation method would be appropriate here — draw from
> methodology.md §4.2 but condense to a single table.

#### 3.2 Template-Based Candidate Generation
**~400 words**

This is the methodological heart of the paper — the thing that makes WellSight
different from a generic "throw ML at a raster" approach. Needs careful
explanation because most readers won't have encountered template matching applied
to geomorphology.

- **Template learning:**
  - Extract 31×31 cell windows (15.5m at 0.5m) from 6 channels around each of
    90 annotated pits
  - Auto-snap to local LRM_5 minimum within 2m (corrects annotation imprecision)
  - Subtract per-window mean (depth normalization)
  - Median across all 90 → canonical pit template
  `[SOURCE: methodology §6.1]`
- **Sub-type discovery:**
  - PCA(5) + KMeans(3) on LRM_5 cutouts → 3 morphological sub-types
  - Small clean bowls (~20), classic bowls (~40), asymmetric with spoil berms (~30)
  - Median template per cluster
  `[SOURCE: methodology §6.2]`
- **Scanning:**
  - Normalized cross-correlation (NCC) on 4 channels, averaged
  - Peak extraction via `peak_local_max` (5m NMS radius)
  - Threshold at 25th percentile of scores at known pits
  - Result: ~13,000 candidates per 1.5 km × 1.5 km tile
  - 88/90 annotated pits captured (98% recall at candidate stage)
  `[SOURCE: methodology §6.3–6.5]`

> **Note for writing:** Include the learned template image if available (the
> "canonical pit" with central depression and slight outer rim). This is a
> strong visual and conveys the method intuitively.

#### 3.3 Feature Engineering
**~300 words**

- 88 features per candidate, organized into 12 groups
- **Window geometry:** Inner ring (≤2.5m from center = "pit bottom") vs. rim ring
  (6–7.5m annulus = "surrounding terrain") — contrast between these drives most
  features
- **Core feature groups (brief, not exhaustive):**
  - 2019 depth/symmetry (30 features): inner min, inner mean, rim mean,
    rim-minus-inner contrast, radial std across 6 terrain channels
  - 2008 temporal features (24 features): same statistics on 2008 derivatives
  - Temporal persistence (1 feature): pit depth present in both epochs
  - Morphological Gaussian-bowl analysis (11 features): eigenvalue-based shape
    descriptors, radial monotonicity, fit residual
  - Multi-template NCC scores (4 features)
  - Pad/road spatial priors (3 features): distance to nearest annotated pad/road
- **The prior problem:** `dist_pad_m` accounts for ~40% of feature importance but
  requires expert annotations unavailable on new tiles — this is the central
  tension for generalization
  `[SOURCE: methodology §7]`

> **Note for writing:** A feature group summary table (group name, count, top
> feature, importance %) would be effective here. Draw from methodology.md §7.2
> and dev_history §15.

#### 3.4 Model Training and Evaluation
**~300 words**

- **Spatial cross-validation:** GroupKFold with 8 spatial clusters of pits across
  5 folds — ensures geographic separation between train and test sets; accounts
  for spatial autocorrelation that inflates standard CV metrics
  `[SOURCE: methodology §8.1]`
- **Models:** XGBoost and LightGBM with class imbalance weighting
  (~80:1 negative:positive ratio) `[SOURCE: methodology §8.2–8.3]`
- **Ensemble:** Simple average of XGB + LGBM probabilities (HistGradientBoosting
  tested and dropped — underperformed by ~0.10 PR-AUC)
- **Calibration:** Isotonic regression on OOF predictions → thresholds correspond
  to actual precision (e.g., proba ≥ 0.70 → ~92% of candidates above this
  threshold are real pits)
  `[SOURCE: methodology §9]`

> **Note for writing:** Briefly explain WHY spatial CV matters — one sentence
> showing the gap between naive OOB (0.93 ROC) and honest GroupKFold (0.94 ROC
> but 0.48 vs 0.44 PR-AUC) is sufficient. Don't belabor.

---

### 4. Results
**~1,000–1,200 words | `[SOURCE: dev_history §6, §7, §9, §15–16]` + `[SOURCE: methodology §9–12]`**

#### 4.1 Model Performance Progression
**~300 words**

- Table showing the model evolution (draw from dev_history Appendix):
  - RF baseline → XGB w/ spatial CV → +2008 temporal + priors → +morphology →
    ensemble + calibration
  - Highlight the two biggest jumps: spatial CV honesty (+0.04 PR-AUC, exposed
    optimistic OOB) and 2008 temporal + pad priors (+0.20 PR-AUC, largest single
    improvement)
- Final performance table at multiple thresholds (from methodology §9.3):
  - proba ≥ 0.50: 89% recall, 81% precision
  - proba ≥ 0.70: 76% recall, 92% precision
  - proba ≥ 0.90: 53% recall, 98% precision
  `[SOURCE: methodology §9.3]`

#### 4.2 What the Model Learned
**~300 words**

- Top features by importance: pad proximity (~40%), 2008 temporal depth, negative
  openness contrast, LRM contrast, morphological depth
  `[SOURCE: methodology §9.4]`
- The physical interpretation: the model is detecting symmetric, temporally
  persistent, concentric depressions inside cleared areas — exactly what a
  collapsed well cellar looks like
- 3D point cloud signature: scattering peaks at bowl walls (3–5m from center),
  not center or surroundings — the concentric ring gradient is a genuine physical
  signature of collapsed cellars, independent of raster features
  `[SOURCE: dev_history §11]`
- What proved uninformative: intensity, return counts, scan angle, Z-range —
  the signal is terrain **shape**, not LiDAR **radiometry**
  `[SOURCE: dev_history §14]`

#### 4.3 Cross-Tile Application
**~300 words**

- **The generalization challenge:** removing pad/road priors drops PR-AUC from
  0.722 to 0.604 `[SOURCE: methodology §10.1]`
- **Output2 (adjacent tile, blind application):**
  - Zero documented wells in this tile
  - 35 candidates at proba ≥ 0.50; 25 at proba ≥ 0.70
  - All predictions are novel discoveries by definition
  - No ground truth available — field verification needed
  `[SOURCE: methodology §10.3]`
- **Calibration transfer failure:** Isotonic calibration fit on training tile
  compressed scores too aggressively on new tiles (calibrated p99 = 0.12 on test
  tiles). Raw ensemble scores with empirical thresholds perform better cross-tile.
  `[SOURCE: dev_history §10]`

#### 4.4 DEP Record Cross-Reference
**~200 words**

- Only 31% of DEP well coordinates land within 10m of visible LiDAR features
- 87% of expert-annotated pits have NO DEP record within 100m
- Implication: the state database is severely incomplete for this region; the
  LiDAR-based pipeline finds features the state doesn't know about
- Two high-density orphan tiles tested (616593: 204 DEP wells; 610594: 163 DEP
  wells) — model predictions spatially correlate with DEP clusters but also
  identify locations without records
  `[SOURCE: dev_history §9]`

---

### 5. Discussion
**~800–1,000 words | `[NEEDS WRITING]` (synthesize from both source docs + ramachandran analysis)**

#### 5.1 Methodological Lessons
**~400 words**

- **Template matching as candidate generation was the breakthrough:** 98% recall
  at the candidate stage set the ceiling for everything downstream. Without it,
  the ML models had nothing meaningful to classify.
  `[SOURCE: dev_history §15]`
- **Temporal persistence is a powerful discriminator:** Real pits exist across
  decades; recent disturbances (tree throws, erosion) do not. The 2008 PAMAP
  data, despite being sparser and older, provided the single biggest
  feature-engineering improvement (+0.20 PR-AUC when combined with pad priors).
- **Spatial CV exposed optimistic evaluation:** Standard OOB scoring on Random
  Forest missed a 0.05 AUC gap from spatial autocorrelation. GroupKFold is
  essential for any geospatial ML pipeline — and this is an underappreciated
  point in the remote sensing literature.
- **What didn't work and why:** Pad detection (shapes too irregular after 150
  years), point cloud stacking (terrain-dependent vertical bias), hard-negative
  mining (negatives already well-separated), intensity-based features (no signal).
  `[SOURCE: dev_history §14]`

#### 5.2 The Generalization Problem
**~300 words**

- The dominant feature (pad proximity) is the model's greatest strength AND its
  greatest limitation — powerful where annotations exist, useless where they don't
- Geographic transfer: Venango → McKean (120 km, similar terrain) showed
  significant performance degradation despite ecological similarity
- The diminishing returns curve suggests 150–300 pits across 2–3 tiles as the
  training sweet spot `[SOURCE: dev_history §15]`
- Comparison to Ramachandran et al. (2024): their continental-scale satellite
  approach works where wells are visible from above (arid/open basins) but fails
  in Appalachian forest (0.647 precision, 0.552 recall `[VERIFY]`) — exactly
  where WellSight is designed to operate `[SOURCE: ramachandran]`

#### 5.3 Practical Implications
**~200 words**

- At current processing speed (~5 min/tile), the entire western PA oil region
  (~500 tiles) could be scanned in ~40 hours of compute
- Even a 50% field confirmation rate on the 35 output2 candidates would represent
  significant new well discoveries
- Ranked candidate lists with calibrated probabilities could directly inform
  PA DEP's well plugging prioritization
  `[SOURCE: dev_history §17]`

---

### 6. Limitations and Future Work
**~400–500 words | `[SOURCE: methodology §14]` + `[SOURCE: dev_history §17]`**

#### 6.1 Current Limitations
**~200 words**

- Small training set (90 annotated pits on one tile at full resolution; 675 total
  across regions at reduced resolution)
- Pad prior dominance limits autonomous cross-tile operation
- No field validation — all results are LiDAR-predicted, not ground-truthed
- Point annotations only — pit size not directly labeled
- Single 2019 flight vintage for primary analysis; 2008 data is sparse
- Flight-line intensity artifacts unresolved at mosaic scale

#### 6.2 Recommended Next Steps
**~200 words**

- **Near-term:** Negative labeling (mark obvious FPs), slope filter (reject
  candidates on slopes >20–25°), rasterized 3D eigenvalue features (scattering,
  verticality_std) as XGB inputs
- **Medium-term:** Train a pad detector (CNN or XGB) to replace expert pad
  annotations as a prior — this closes the autonomy loop; CNN on stacked windows
  once >200 positive labels available
- **Long-term:** Statewide scanning of all western PA 3DEP coverage; field
  verification of highest-confidence predictions; integration with PA DEP
  remediation programs
  `[SOURCE: dev_history §17]` + `[SOURCE: methodology §14.2]`

---

### 7. Conclusion
**~200–300 words | `[NEEDS WRITING]`**

- Restate the problem and what WellSight demonstrated
- The core finding: collapsed well cellars have a detectable morphological
  signature in LiDAR-derived terrain surfaces, and that signature can be learned
  from a modest number of expert annotations and applied systematically
- The detection signal is terrain **shape** (LRM, TPI, openness, 3D scattering),
  not LiDAR **radiometry** (intensity, return counts)
- The pipeline produces actionable ranked candidate lists suitable for field
  verification and remediation prioritization
- The approach fills a gap that satellite-based methods cannot address in forested
  Appalachian terrain

---

### References
**`[CITE NEEDED]` — all citations require live verification before finalizing**

Known references to include (verify formatting, DOIs, and full author lists):

| Short Key | Likely Full Citation | Used For |
|-----------|---------------------|----------|
| Ramachandran et al. 2024 | Ramachandran, N., Irvin, J., et al. (2024). *Nature Communications*, 15(1), 7036. DOI: 10.1038/s41467-024-50334-9 | Satellite DL comparison; Appalachian performance `[VERIFY: Appalachian numbers source]` |
| Yokoyama et al. 2002 | Yokoyama, Shirasawa, Pike (2002) | Topographic openness algorithm |
| Pingel et al. 2013 | Pingel, Clarke, McBride (2013) | SMRF ground classification |
| Zhang et al. 2016 | Zhang et al. (2016) | CSF ground classification |
| Chambers 2017 | Chambers (2017) | LiDAR terrain analysis |
| ASPRS LAS 1.4 | ASPRS LAS 1.4-R15 specification | Point cloud format standard |
| USGS LBS 2025 | USGS Lidar Base Specification 2025 rev. A | Data acquisition standard |
| PA DEP | PA DEP orphaned well program docs | Problem scale, well records |
| Kang et al. 2014 | Kang et al. (2014) `[VERIFY year and authors]` | 200,000+ undocumented well estimate |
| Pekney et al. | NETL Pekney/Sams/Reeder/Veloski | NETL orphaned well detection work |
| Trier et al. 2019 | Trier, Cowley, Waldeland (2019) `[VERIFY]` | Archaeological LiDAR precedent |
| Freeland et al. 2016 | Freeland et al. (2016) `[VERIFY]` | Archaeological LiDAR precedent |

---

### Appendices (Optional — include if page budget allows)

#### Appendix A: Model Version Progression Table
A condensed version of the version table from dev_history (v1 RF through v11 hotspots).
Useful for showing the iterative development process, which is part of the story
for a term paper. `[SOURCE: dev_history Appendix]`

#### Appendix B: Feature Importance Rankings
Top 15–20 features by XGBoost gain, with physical interpretation.
`[SOURCE: methodology §9.4]` + `[SOURCE: dev_history §15]`

#### Appendix C: Pipeline Scripts Reference
Condensed script-to-purpose mapping.
`[SOURCE: methodology §13]`

---

## Writing Notes and Open Questions

### Content Allocation Budget

| Section | Target Words | % of Paper |
|---------|-------------|------------|
| Abstract | 200–250 | 4% |
| 1. Introduction | 800–1,000 | 17% |
| 2. Study Area & Data | 600–800 | 12% |
| 3. Methods | 1,500–1,800 | 30% |
| 4. Results | 1,000–1,200 | 20% |
| 5. Discussion | 800–1,000 | 17% |
| 6. Limitations & Future Work | 400–500 | — |
| 7. Conclusion | 200–300 | — |
| **Total** | **~5,500–6,850** | |

### Figures and Tables

| # | Content | Purpose | Source |
|---|---------|---------|--------|
| **Fig. 1** | Study area map — Venango County within PA, output3 + output2 tile footprints | Orients the reader geographically | QGIS export or create new |
| **Fig. 2** | Learned pit template — canonical 31×31 median cutout (LRM_5 channel) showing central depression and rim | The "aha" visual — what a collapsed cellar looks like in LiDAR | `_pit_template_match.py` output |
| **Fig. 3** | Hillshade crop with annotated pits overlaid — a few visible pits in terrain context | Demonstrates visual identifiability vs. need for systematic detection | QGIS screenshot |
| **Table 1** | Model performance progression — RF → XGB → +2008/priors → +morph → ensemble | Tells the iterative improvement story | Both source docs |
| **Table 2** | Final precision/recall at multiple thresholds (0.30–0.90) | The "deliverable" — what a field team would get | methodology.md §9.3 |
| **Fig. 4** | Cross-tile prediction map — output2 candidates overlaid on hillshade | Shows actionable results on unseen terrain | Pipeline overlay PNG |

**Optional (if page budget allows):**
- Feature importance bar chart (top 10 features by XGBoost gain)
- DEP cross-reference summary table (31%/62%/87% statistics)

### Resolved References

**Ramachandran et al. (primary comparison paper):**

> Ramachandran, N., Irvin, J., Omara, M., Gautam, R., Meisenhelder, K.,
> Rostami, E., Sheng, H., Ng, A. Y., & Jackson, R. B. (2024). Deep learning
> for detecting and characterizing oil and gas well pads in satellite imagery.
> *Nature Communications*, *15*(1), 7036.
> https://doi.org/10.1038/s41467-024-50334-9

**Note:** The paper validates on Permian and Denver-Julesburg basins
(Precision 0.955, Recall 0.904). The Appalachian performance numbers
(0.647 precision, 0.552 recall) cited in our prior analysis need source
verification — they may be from supplementary material or a separate
deployment analysis. Marked `[VERIFY]` in the outline wherever cited.

### Next Steps

1. Ryan confirms this outline structure works
2. Begin writing §1 (Introduction) and §3 (Methods) — the two sections
   that set up the paper's argument and technical contribution
3. Locate and verify all `[CITE NEEDED]` references via web search
4. Ryan provides or generates the four figures and confirms availability
5. Draft remaining sections, write abstract last

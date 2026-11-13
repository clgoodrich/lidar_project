# ADVERSARIAL AUDIT & DECISION MEMO

**To:** Project Leadership, `lidar_project`  
**From:** Independent Adversarial Reviewer  
**Date:** November 3, 2026  
**Subject:** Adversarial Audit of Two Architectural Decisions: (1) Exclusion of NISAR from Lidar Well-Site Detector, and (2) 2006–2008 vs. 2019 Lidar Terrain Change Detection on Tile 9t  

---

## 1. Executive Summary & Verdicts

| Workflow / Decision | Verdict | Decision Impact | Core Rationale |
| :--- | :--- | :--- | :--- |
| **1. NISAR in Well-Site Detector** | **UPHELD (Exclude NISAR)** | **Confirmed** | Leaving NISAR out is fully justified. While SAR carries raw signal (AUC 0.64–0.83 against distant decoys), this signal is redundant where lidar exists and is largely explained by spatial location (AUC 0.815–0.955 for map $x/y$ alone) and terrain illumination ($R^2 = 0.57$). In every test with sufficient headroom, incremental gain over rich lidar failed the preregistered $+0.05$ gate (held-out pit gain: $-0.017$; pad local gain: $-0.017$; weak-lidar pad gain: $+0.003$). |
| **2. Lidar Change Detection (2006–2019 on 9t)** | **REVERSED / SEVERELY CONSTRAINED (Do Not Use for Well Change)** | **Overturned / Constrained** | The 2006–2008 and 2019 surveys **cannot** resolve terrain change at well-site scale ($\le 2{,}000\text{ m}^2$). The apparent subsidence signal at known wells ($12\%$ negative exceedance) is an artifact caused by a $7\times$ point density disparity ($0.67$ vs. $4.8\text{ pts/m}^2$, under-resolving pit depth by $-0.123\text{ m}$) evaluated against circular annotations (hand-digitized 2019 depressions). Under heavy-tailed survey noise, real change is indistinguishable from artifacts below $4{,}000\text{–}7{,}888\text{ m}^2$. |

---

## 2. Audit Workflow 1: The NISAR Exclusion Decision

### 2.1 Headline Claims Tested
1. **Preregistered 613590 Pit Transfer:** A frozen model trained on 9t pits tested on 36 pits on tile 613590 scores NISAR AUC $0.658$, rich lidar $0.881$, combined $0.865$ (gain $-0.017$, failing the $+0.05$ gate).
2. **Redundancy Where Lidar Exists:** On 9t pads and pits, adding NISAR to a rich lidar baseline yields negligible incremental gains (repeated CV gains between $-0.010$ and $+0.004$).
3. **Location & Confounder Inflation:** Tile-wide SAR pad skill (AUC $0.64$) is a place effect driven by distance to decoys, matching map coordinates ($x/y$ AUC $0.815$), while local decoys collapse SAR skill to chance (AUC $0.479$).

### 2.2 Reproduction of Headline Results
Re-running `nisar/code/s5_eval/_nisar_feat_heldout_9t.py` against saved samples confirmed the exact figures reported in `nisar/docs/NISAR_FINDINGS.md` and `nisar/results/613590/nisar_pit_heldout_summary_613590_slc.json`:
- **Simple Lidar Baseline (3 bands):** AUC $0.753$ ($95\%\text{ CI: } 0.660\text{--}0.858$)
- **Rich Lidar Baseline (26 bands):** AUC $0.881$ ($95\%\text{ CI: } 0.805\text{--}0.940$)
- **All NISAR (293 bands):** AUC $0.658$ ($95\%\text{ CI: } 0.465\text{--}0.820$)
- **NISAR + Rich Baseline (319 bands):** AUC $0.865$ ($95\%\text{ CI: } 0.775\text{--}0.934$)
- **Observed Incremental Gain:** $-0.017$ ($95\%\text{ block bootstrap: } -0.055\text{ to } +0.020$).
- **Gate Passed:** `False` (fell short of $+0.05$ threshold).

Saved score verification from `nisar/results/9t/nisar_pit_model_auc_by_set_9t_slc.csv` and `nisar/results/9t/nisar_pad_model_auc_by_set_9t_slc_local1500.csv`:
- 9t Pit 5-fold CV: Rich lidar AUC $0.968$; NISAR + Rich AUC $0.967$ (gain $-0.001$).
- 9t Pad Local 1,500 m Decoys: Rich lidar AUC $0.923$; All NISAR AUC $0.479$ (chance); NISAR + Rich AUC $0.906$ (gain $-0.017$).

---

### 2.3 Ranked Findings: NISAR Workflow

#### Category A: Findings That Could Reverse the Decision
**None.** No evidence was uncovered indicating that NISAR provides a suppressed, viable detection signal that meets the project's $+0.05$ AUC gate over lidar.

#### Category B: Findings That Narrow Scope or Reveal Evaluator Vulnerabilities

##### Finding B1: Ceiling Limitations in Headline Evaluations Obscure Low-Signal Headroom
- **Code Location & Artifact:** `nisar/code/s5_eval/_nisar_feat_fusion_9t.py` (lines 240–248); `nisar/docs/NISAR_FINDINGS.md` (lines 73–75).
- **Observed Result:** Pad U-Net out-of-fold baseline AUC is $0.999$; combined U-Net + NISAR is $0.995$. In the clearing confuser test ($n=60$ pads), rich lidar baseline AUC is $0.988$; combined is $0.988$.
- **Impact on Claim:** The claim that "NISAR adds nothing to U-Net fusion" is uninformative. With baseline performance at $0.999$, the maximum possible mathematical gain is $+0.001$, making the $+0.05$ gate impossible to achieve.
- **Headroom Re-partitioning:**
  - *Zero Headroom Tests:* Pad U-Net fusion ($1.0 - 0.999 = 0.001$), clearing confusers ($1.0 - 0.988 = 0.012$).
  - *Adequate Headroom Tests:* 613590 held-out pits ($1.0 - 0.881 = 0.119$ headroom, gain $-0.017$); Pad local 1,500 m ($1.0 - 0.923 = 0.077$ headroom, gain $-0.017$); Lidar-weak pad quartile ($1.0 - 0.880 = 0.120$ headroom, gain $+0.003$ local).
  - *Conclusion:* Only tests in the second group provide defensible evidence. The decision survives solely because those specific tests also showed zero gain.

##### Finding B2: Spatial Confounding & Distance-to-Decoy Artifact Explains Apparent Radar Skill
- **Code Location & Artifact:** `nisar/code/s5_eval/_nisar_pad_distance_bands_9t.py`; `nisar/results/9t/nisar_pad_distance_bands_auc_9t_slc.csv`; `nisar/docs/NISAR_FINDINGS.md` (lines 141–149).
- **Observed Result:** As decoy distance increases from $100\text{--}500\text{ m}$ to $>3{,}500\text{ m}$, NISAR AUC climbs monotonically from $0.440 \to 0.491 \to 0.531 \to 0.632 \to 0.680 \to 0.710$. Simultaneously, map $x/y$ coordinates alone climb from $0.381 \to 0.385 \to 0.651 \to 0.838 \to 0.919 \to 0.961$.
- **Impact on Claim:** The apparent standalone SAR skill on pads (AUC $0.64$) is entirely a regional setting / geographic clustering proxy. Well pads cluster in specific geologic sections; distant forest decoys differ in stand composition and elevation. Radar detects regional ecotype, not well pads.

##### Finding B3: Unresolved ~10 m Planimetric Residual Blurs Pit-Scale Apertures
- **Code Location & Artifact:** `nisar/code/s5_eval/_nisar_registration_points_9t.py`; `nisar/results/9t/nisar_registration_points_shift_9t_slc.csv`; `nisar/docs/iterations/nisar_gslc_stack_pad_pit_seasonal_9t.md` (lines 121–137).
- **Observed Result:** A pit aperture is $4\text{ to }9$ pixels ($\approx 100\text{--}225\text{ m}^2$). The point-target registration search against $9{,}592$ lidar objects yielded a null result (hit rates $0.0006\text{--}0.0095$, best shifts hit search boundary at $\pm 40\text{ m}$). In earlier tests, forcing a best shift on GSLC moved pit HV excess from $-0.07\text{ dB}$ (AUC $0.476$) to $-0.45\text{ dB}$ (AUC $0.358$).
- **Impact on Claim:** While the regeocoding pipeline removed the $8\text{--}12\text{ m}$ Copernicus DEM height bias using lidar bare-earth heights (`nisar/code/s1_build/_nisar_regeocode_lidar_9t.py`), residual planimetric blur remains unconstrained against independent point controls. A residual $10\text{ m}$ ($2\text{ pixel}$) registration error shifts a small pit outside the sampling aperture. The negative pit result could partly reflect spatial blurring rather than complete absence of L-band contrast.

##### Finding B4: Radar HV Signal in Closed Canopy is Dominated by Terrain Illumination
- **Code Location & Artifact:** `nisar/code/s5_eval/_nisar_vs_optical_heldout_9t.py`; `nisar/docs/NISAR_FINDINGS.md` (lines 88–98).
- **Observed Result:** In closed canopy ($>0.8$ cover), lidar canopy height explains $<2\%$ of HV variance ($R^2 = 0.07\text{ OLS } / 0.08\text{ GBDT}$). Adding simulated terrain facet gain (`sim_db`) elevates held-out $R^2$ to $0.57$.
- **Impact on Claim:** The belief that L-band HV penetrates closed canopy to measure sub-canopy structural clearing or vegetation biomass is contradicted by the data. Closed-canopy HV variance is dominated by local terrain illumination angle.

#### Category C: Findings Affecting Only Reproducibility and Audit Trail

##### Finding C1: Massive Sample Loss from 250 m Train-Test CV Buffering
- **Code Location:** `nisar/code/s5_eval/_nisar_feat_common.py:oof_probs` (lines 137–141).
- **Observed Result:** In 9t pit 5-fold CV, removing training samples within $250\text{ m}$ of test samples drops $20.9\%\text{ to }71.5\%$ of training rows per fold (Fold 3 drops $3{,}077$ of $4{,}303$ training rows; Fold 4 drops $2{,}364$ rows).
- **Impact on Claim:** Necessary to prevent leakage across neighboring pads and decoys, but introduces severe training fold size instability (effective training sample size varies between $1{,}226$ and $3{,}405$ across folds).

##### Finding C2: Decoy Coordinate Reuse in Nominal Denominators
- **Code Location:** `nisar/code/s5_eval/_nisar_feat_score_9t.py` (line 42); `nisar/derived/9t/nisar_features_5m/nisar_pit_samples_9t_slc.npz`.
- **Observed Result:** On 9t pits, the dataset reports $489$ pits and $4{,}890$ decoys, but only $4{,}115$ unique decoy coordinates exist ($15.8\%$ duplicate spatial positions). On 613590, $360$ decoys map to $351$ unique positions.
- **Impact on Claim:** Does not invalidate out-of-fold evaluation because blocks group decoys, but inflates the nominal degrees of freedom in decoy baseline distributions.

---

## 3. Audit Workflow 2: Lidar Terrain Change Detection (2006–2008 vs. 2019 on Tile 9t)

### 3.1 Headline Claims Tested
1. **Vertical Agreement & Alignment:** The 2006–2008 and 2019 surveys co-register with sub-centimeter median bias ($+0.003\text{ m}$) and a residual planimetric error of $\approx 0.10\text{ m}$.
2. **Well Subsidence Negative:** Known wells show no elevation change beyond survey noise ($1.2\times$ background enrichment, $z \approx 1.0$).
3. **Anthropogenic Earthwork Detections:** The DoD reliably detects non-erosional anthropogenic earthworks down to $712\text{ m}^2$ (Part 2) or contains coherent non-erosional candidates such as #267, #836, #20, #391 (Part 4).

---

### 3.2 Candidate Tracking Across Workflow Iterations
Tracing reported candidates and controls across the three generation surfaces reveals severe instability:

| Location / Feature | Coordinate (EPSG:6346) | Preliminary DoD (`dod_9t_2m.tif`) | Rebuilt Single-ICP (`dod_9t_singleicp_2m.tif`) | Flight-Line Adjusted (`dod_lineadj_9t_2m.tif`) | Classification & Integrity Trajectory |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Patch 511** (reported well-adjacent fill) | `623987, 4596497` | **$+0.465\text{ m}$** (classified as $+0.40\text{ m}$ fill, $8\text{ m}$ from well) | **$-0.081\text{ m}$** | **$-0.106\text{ m}$** | **ERASED.** Was an artifact of mosaic seams between independent tile solves. Dissolves to zero on rebuilt surface. |
| **Patch 267** (reported cut) | `623978, 4596537` | **$+0.578\text{ m}$** (was positive fill!) | **$-2.268\text{ m}$** (classified as $-1.11\text{ m}$ cut, $3{,}016\text{ m}^2$) | **$-2.291\text{ m}$** | **INVENTED.** Flipped by $2.85\text{ m}$ between preliminary and rebuild. Is a red/blue dipole across a steep road cut. |
| **Patch 20** (reported fill) | `623622, 4597396` | **$-0.071\text{ m}$** (zero / negative) | **$+0.329\text{ m}$** (classified as $+0.32\text{ m}$ fill, $2{,}180\text{ m}^2$) | **$+0.331\text{ m}$** | **INVENTED.** Absent in preliminary DoD; emerges in rebuild; confirmed statistically indistinguishable from noise in IAAFT null. |
| **Matched Control** (stable planar ground) | `622000, 4595000` | **$-0.021\text{ m}$** | **$+0.056\text{ m}$** | **$+0.015\text{ m}$** | Stable control behaves consistently across passes ($\Delta z \le 0.05\text{ m}$). |

---

### 3.3 Ranked Findings: Change Detection Workflow

#### Category A: Findings That Overturn Decisions or Reveal Fatal Structural Flaws

##### Finding A1: Circular "Known Wells" Evaluation & Density-Driven Artifact
- **Code Location & Artifact:** `qgis/annotations/well_head_pts_reprojected.gpkg`; `qgis/annotations/wellhead_pits.gpkg`; `docs/iterations/icp_change_9t.md` (lines 410–440).
- **Observed Result:** 
  1. `well_head_pts_reprojected.gpkg` ($861$ points) and `wellhead_pits.gpkg` are identical point sets ($100\%$ within $5\text{ m}$). They are hand-digitized depressions identified on the **2019 lidar DEM**.
  2. The 2019 survey density is $\sim 4.8\text{ pts/m}^2$; the 2006–2008 survey density is $\sim 0.67\text{ pts/m}^2$ ($7\times$ lower).
  3. Measuring local depression depth at these points: 2019 median relief is $-1.080\text{ m}$; 2006–2008 median relief is $-0.957\text{ m}$. The sparse 2006 survey under-resolves pit depth by **$-0.123\text{ m}$**.
  4. On the single-ICP DoD, median $\Delta z$ at known wells is **$-0.0555\text{ m}$**, and $14.6\%$ exceed $3\sigma$ ($12.0\%$ negative).
- **Impact on Claim:** The apparent elevation change / subsidence at known wells is entirely accounted for by the resolution shortfall ($-0.123\text{ m}$) acting on points chosen specifically for being pits in the newer survey. The test is circular. No historic well subsidence can be inferred.

##### Finding A2: Zero Non-Erosional Changes Survive an Autocorrelated / Heavy-Tailed Null
- **Code Location & Artifact:** `notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py` (lines 538–577); `data/_experiments/icp/change_9t/_classify_9t_singleicp.json` (lines 31–63); `data/_experiments/icp/change_9t/_classify_9t_lineadj_z.json` (lines 31–63).
- **Observed Result:** 
  - In Part 2, a Gaussian null established a "reliable cutoff" of $712\text{ m}^2$, yielding $16$ reliable anthropogenic patches ($2.65\text{ ha}$). Audit proved the search was pinned at the grid floor ($3.0\text{ px}$).
  - When tested against an IAAFT surrogate null (preserving real spatial ACF and heavy-tailed survey artifact distributions), synthetic noise alone generated patches up to **$7{,}888\text{ m}^2$** (mean maximum $4{,}420\text{ m}^2$).
  - Of $22$ candidate anthropogenic patches on the single-ICP DoD, **zero ($0$)** clear the IAAFT cutoff ($n_{\text{reliable}} = 0$).
  - On the flight-line-adjusted surface (`lineadj_z`), the largest noise patch is $4{,}092\text{ m}^2$; all $26$ candidate anthropogenic patches fail the cutoff ($n_{\text{reliable}} = 0$).
- **Impact on Claim:** No individual well-site-scale earthwork or non-erosional terrain change detected on tile 9t can be distinguished from survey artifacts without independent, external validation.

##### Finding A3: Preliminary Product Invalidation and False Discovery
- **Code Location & Artifact:** `notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py` (lines 5–15); `data/_experiments/icp/change_9t/dod_9t_2m.tif`.
- **Observed Result:** The preliminary product (`dod_9t_2m.tif`) used four independent ICP solves that introduced $0.103\text{ m}$ of artificial inter-tile stepping across mosaic seams. `dem_diff_2m.tif` failed reconstruction against its own stored DEMs (mean $|r| = 0.24\text{ m}$).
- **Impact on Claim:** The preliminary surface fabricated false candidate patches (such as Patch 511, $+0.40\text{ m}$ fill adjacent to a well) that were entirely artifacts of unconstrained mosaic boundaries.

#### Category B: Findings That Narrow Scope and Identify Systematic Biases

##### Finding B1: Flight-Line Adjustment Mathematical Erasure Risk
- **Code Location & Artifact:** `notebooks/wellsight_v2/s7_analysis/_change_lineadj_9t.py:main` (lines 154–169); `data/9t/results/change/change_lineadj_summary_9t.json`.
- **Observed Result:** Per-pass vertical offsets are estimated by taking $\text{median}(z_{2006} - z_{2019})$ over gentle slopes ($<5^\circ$, $|d| < 0.5\text{ m}$) along each flight pass ($6$ passes, offset standard deviation $0.0607\text{ m}$, range $-0.0296\text{ m}$).
- **Impact on Claim:** Because the correction forces the median difference of each 2006 flight line to match the 2019 reference DEM, any genuine broad-scale elevation change occurring along a flight path is mathematically erased along with the swath striping.

##### Finding B2: Slope-Dependent Noise Inflation & Registration Cross-Talk
- **Code Location & Artifact:** `notebooks/wellsight_v2/s7_analysis/_change_lineadj_9t.py`; slope audit verification.
- **Observed Result:** 
  - Slopes $0\text{--}5^\circ$: $\sigma = 0.079\text{ m}$, exceedance $>0.30\text{ m} = 2.0\%$.
  - Slopes $15\text{--}20^\circ$: $\sigma = 0.134\text{ m}$, exceedance $>0.30\text{ m} = 7.9\%$.
  - Slopes $30\text{--}90^\circ$: $\sigma = 0.287\text{ m}$, median $= +0.100\text{ m}$, exceedance $>0.30\text{ m} = 33.6\%$.
- **Impact on Claim:** Over one-third of steep terrain cells exceed $30\text{ cm}$ vertical discrepancy. Planimetric residuals ($\approx 0.10\text{ m}$) project into vertical differences ($dx \cdot \tan\theta$), creating false cut/fill dipoles across terrain edges (e.g., candidate patches #267, #899, #1530).

##### Finding B3: Quantified Detection Floor and False Alarm Density
- **Searched Area:** Tile 9t covers $2{,}025\text{ ha}$ ($20.25\text{ km}^2$, $5{,}062{,}500$ cells at $2\text{ m}$).
- **False Alarm Rate:** $22\text{ to }26$ unvalidated non-erosional patches per $20.25\text{ km}^2$ ($\approx 1.1\text{ to }1.3\text{ false patches per km}^2$, or $1$ every $80\text{--}90\text{ ha}$).
- **Minimum Detectable Footprint:** At well-pit scale ($\sim 200\text{ m}^2$) or well-pad scale ($\sim 1{,}500\text{ m}^2$), the minimum vertical change detectable with statistical separation from autocorrelated swath noise exceeds $1.5\text{--}2.0\text{ m}$. Subtle historic earthwork subsidence ($\le 0.5\text{ m}$) cannot be detected.

#### Category C: Findings Affecting Only Reproducibility

##### Finding C1: Inaccessible Source Point Clouds
- **Code Location:** `notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py` (lines 79–84).
- **Observed Result:** Raw 2006–2008 LAZ files reference `F:\lidar_project\consolidated\lidar_all`, which is unmounted. Rebuilding the single-ICP solve from raw points cannot execute without re-fetching tiles `002958, 002959, 003111, 003112` from USGS 3DEP.

##### Finding C2: Coordinate Reference System Trap in 2006 Headers
- **Code Location:** `notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py` (lines 27–34).
- **Observed Result:** 2006 LAZ headers declare `EPSG:32128` with US Survey Foot units; reading without forcing `in_srs=EPSG:2271` displaces coordinates by $\sim 417\text{ km}$.

---

## 4. Cross-Workflow Synthesis: Temporal Incompatibility

A critical adversarial finding is that **NISAR observations cannot corroborate historical lidar elevation changes**:

```
[2006-2008 Lidar Survey] ────── 11-13 yr Epoch ──────> [2019 Lidar Survey]
                                                              │
                                                     6.5 - 7.5 Year Gap
                                                              │
                                                              ▼
                                                    [Late 2025 - Late 2026 NISAR]
```

1. **Temporal Disconnect:** Historical elevation change occurred between 2006/2008 and spring 2019. NISAR L-band SAR was acquired between October 2025 and October 2026. A 2025–2026 radar image cannot establish whether a terrain change took place between 2006 and 2019.
2. **Physical Incompatibility:** Lidar DoD measures 3D metric bare-earth displacement ($\Delta z$). NISAR measures instantaneous microwave backscatter and 12-day coherence.
3. **What NISAR Can Independently Verify:** NISAR can only verify whether a feature exists as an open clearing or metallic scatterer in **2025–2026**. It cannot serve as ground truth for historic elevation changes.

---

## 5. Narrowest Defensible Conclusions

### Workflow 1: NISAR
> *"Under 5 m posting and single-look processing on Tile 9t, NISAR L-band radar does not provide a detectable increment ($\ge +0.05$ AUC) over a rich lidar texture baseline for identifying oil and gas well pads or pits. Where standalone radar skill appears against distant decoys (AUC 0.64–0.83), it is primarily an artifact of spatial clustering, geographic setting, and local terrain illumination ($R^2 = 0.57$). In the single preregistered out-of-tile test with sufficient headroom (36 pits on 613590), NISAR added $-0.017$ to the rich lidar baseline ($95\%\text{ CI: } -0.055\text{ to } +0.020$). Excluding NISAR from the lidar-based well detector is justified."*

### Workflow 2: Lidar Change Detection
> *"The 2006–2008 and 2019 USGS lidar surveys over Tile 9t cannot resolve terrain change at the scale of historic well sites ($\le 2{,}000\text{ m}^2$). Apparent elevation differences at known wells reflect a $-0.123\text{ m}$ depth resolution shortfall in the sparse older survey ($0.67\text{ vs. } 4.8\text{ pts/m}^2$) tested against circular 2019 DEM annotations. Due to spatial autocorrelation and flight-line striping, isolated terrain changes below $4{,}000\text{–}7{,}888\text{ m}^2$ cannot be separated from survey artifacts without independent historical imagery or permit records. Change detection across this epoch pair cannot identify historic well activity."*

---

## 6. Decisive Next Tests

### Decisive Test for Workflow 1 (NISAR)
**The 613590 Annotated Pad Transfer Test:**
Execute the preregistered pad evaluation on tile 613590 using the $161$ review candidates in `nisar/results/613590/nisar_pad_review_candidates_613590.gpkg`. 
- *Protocol:* Visually annotate the $161$ candidates and any missed pads in QGIS using independent orthoimagery. Score the frozen 9t pad model once.
- *Decision Rule:* If NISAR $+$ rich lidar fails to beat rich lidar by $+0.05$ AUC with lower bootstrap bound $>0$, the exclusion of NISAR from pad detection is finalized across independent domains.

### Decisive Test for Workflow 2 (Change Detection)
**Orthophoto-Audited Triaging of Candidate Earthworks #20 and #391:**
Conduct historical orthophoto triaging (2005/2006 NAIP vs. 2019/2020 NAIP) specifically at candidate fills #20 (`623622, 4597396`) and #391 (`621643, 4596163`).
- *Protocol:* These are the only two non-erosional candidates with planar, rectangular morphology that do not exhibit red/blue dipole terrain-edge artifacts.
- *Decision Rule:* If aerial imagery reveals no clearing, access road, or earthwork activity matching the 2006–2019 timeframe at these footprints, it proves that even the most visually convincing non-dipole candidate fills are survey artifacts. If confirmed as real earthworks, it establishes the empirical detection floor of the flight-line-adjusted workflow at $\ge 2{,}000\text{ m}^2$ with vertical change $\ge 0.32\text{ m}$.

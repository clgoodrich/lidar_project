# From Detection to Attribution: Physically-Coupled, Cross-Domain Monitoring of Ephemeral-Channel Geomorphic Change from Terrain Alone

**NASA ROSES-2025 F.5: Future Investigators in NASA Earth and Space Science and Technology (FINESST)**
**Target division:** Earth Science Division (EARTH25), Antarctic cryosphere / climate
**Proposal deadline:** 14 July 2026 (11:59 PM EDT)
**Structure:** Graduate student = Future Investigator (FI), primary author and intellectual lead; faculty advisor = PI of record. Award up to ~$50,000/yr for up to 3 years.

> **Summary.** This project will transform an existing Antarctic stream-change *monitor* into an
> *explanatory and predictive* tool. Building on Barlow (2026), which mapped two decades of
> ephemeral-channel geomorphic change across the McMurdo Dry Valleys, the proposed work will
> **(O1)** attribute that change to its physical/climate drivers, **(O2)** generalize the
> terrain-only detector across sensors and valleys, and **(O3)** deliver calibrated per-pixel
> uncertainty. The change-detection foundation is already operational and validated against
> Barlow's published uncertainty ranges, with an initial driver signal shown in §4.

---

## 1. Background and the Gap

The **McMurdo Dry Valleys (MDVs)** are Earth's largest ice-free Antarctic desert and, for a
century, were considered the planet's most geomorphologically stable landscape. That assumption
is breaking down: in an energy-limited system, small increases in solar absorption and
permafrost degradation translate directly into **ephemeral summer streams** that flow for a few
weeks each year, move sediment, and reshape channels. These streams are the most sensitive
measurable indicator of climate change in the most stable place on Earth, a continental-scale
"climate canary."

**Barlow (2026)** [1] established the measurement foundation in three transferable pillars:

1. **Terrain-only semantic segmentation:** a U-Net delineates stream boundaries from DEM
   derivatives alone (elevation, slope, aspect most informative; no water/color signal),
   so it works in channels that are dry 11 months a year.
2. **Satellite-DEM validation:** point-to-plane ICP alignment, **Laplacian** error modeling,
   and outlier-robust **NMAD** uncertainty prove free REMA satellite DEMs are accurate enough
   for centimeter-to-meter stream-corridor change detection.
3. **Multi-epoch change detection:** DEM-of-Difference (DoD) inside segmented stream masks,
   level-of-detection thresholds (LOD95 = 1.96 × NMAD), and per-stream erosion/deposition and
   acceleration rates across four valleys and three epochs (2001 & 2014 lidar, 2021–23 REMA).

**The gap.** Barlow's dissertation ends at *description*: it maps **where** change is happening
(Denton Hills is the erosion hotspot; parts of Taylor Valley are accelerating) but explicitly
defers two threads to future work: **(a) coupling geomorphic change to physical/climate drivers**,
and **(b) generalizing the model beyond the MDVs.** A Future Investigator project lives precisely
in that gap: turning a *monitor* into an *explanatory and predictive* tool (Fig. 1). This is a
genuine scientific increment, not a replication.

![Fig 1](finesst_figures/fig5_workflow.png)
***Figure 1.*** *From detection (Barlow 2026; the first four stages) to the proposed attribution
and prediction science (last two stages, the new contribution of this project).*

---

## 2. Objectives and Hypotheses

| # | Objective | Hypothesis | Increment over Barlow |
|---|---|---|---|
| **O1** | **Attribution (headline science).** Pair per-stream gross/net/acceleration rates with energy-balance drivers, air/ground temperature, insolation, **positive-degree-days (PDD)**, melt-season discharge, glacier mass balance, active-layer depth, from MDV-LTER + ERA5/AMPS reanalysis. | **H1:** Geomorphic flux is governed by *cumulative melt energy*, not raw water volume; a PDD/insolation-based energy model predicts per-stream gross rate better than discharge alone (and explains the residual scatter in Fig. 4). | Listed verbatim as Barlow future work; never quantified. |
| **O2** | **Cross-sensor & cross-valley generalization.** Make the terrain-only segmenter robust across sensors (lidar 2001/2014 ↔ REMA) and all four valleys; quantify and **correct the lidar→satellite domain shift** that limits the satellite epoch. | **H2:** A sensor-aware normalization (per-pixel slope/aspect-conditioned bias correction) closes most of the lidar–REMA F1 gap, recovering near-lidar segmentation on REMA. | Barlow flags sensor generalization as future work. |
| **O3** | **Calibrated uncertainty.** Extend the Laplacian/NMAD/LOD framework into a **per-pixel, sensor-aware confidence layer** so every change map ships with calibrated uncertainty. | **H3:** Conditioning NMAD on slope, aspect, and sensor yields LOD maps whose empirical exceedance matches the nominal 95%, a trustworthy-EO product. | Barlow uses a single global NMAD per epoch-pair. |

**Predictive payoff (ties O1–O3 together):** a model that, given a driver field, predicts *where
acceleration migrates next*, the actionable form of the "climate canary."

---

## 3. Methodology

**Data (free/public; see §6).** Elevation backbone: MDV airborne
lidar 2001 (NASA ATM, 2 m) + 2014 (NCALM, 1 m), and REMA v2.0 (2 m, 2021–23). Per-epoch
derivatives, elevation, slope, aspect, **profile curvature** (signed), **MFD flow accumulation**,
lidar intensity. Drivers: MDV-LTER meteorology (Lake Bonney), **21 stream-discharge gauges**,
glacier mass balance (7 glaciers), continuous soil T/EC/VWC (active-layer proxy); ERA5 monthly
1993–2024 and AMPS 2.67-km for spatial gap-fill. Labels: MCM-LTER stream centerlines (public
stand-in for Barlow's access-gated 217 hand-digitized tiles, see §7 risk).

**O1, Attribution.** For each gauged stream and epoch, the proposed work will (i) compute
gross/net geomorphic rate by DoD inside the channel mask (operational, Fig. 2); (ii) build a
per-stream **energy time series**, melt-season PDD and incoming shortwave
from LTER + ERA5/AMPS, cumulative discharge, and active-layer depth; (iii) fit hierarchical
regression / random-forest models of rate vs. drivers, with leave-one-stream-out cross-validation;
and (iv) test H1 by comparing an energy-balance predictor against discharge-only (the raw-discharge
relationship in Fig. 5 is real but incomplete). Acceleration (3-epoch
Taylor streams) will be regressed against driver *trends*.

**O2, Generalization.** The work will quantify the lidar→REMA domain shift over stable terrain as
a function of slope/aspect, learn a correction, retrain/fine-tune the segmenter with sensor
augmentation, and evaluate F1 across all four valleys and both sensor regimes. The FI's prior work
applying this architecture to a different landscape (§5) shows it transfers across sensors and biomes.

**O3, Calibrated uncertainty.** The work will replace the single global NMAD with NMAD conditioned
on (slope, aspect, sensor), emit a per-pixel LOD raster, and validate calibration by checking that
observed sub-LOD residual fractions match nominal confidence on held-out stable terrain
(Fig. 4 shows the global version; Laplacian fits the residuals far better than Gaussian).

**Reproducibility/QC.** The pipeline is fully scripted, input data and all derivatives regenerate
from source, with robust statistics and CRS checks enforced at every step (e.g., an early QC
catch, a 2001 nodata bug inflating NMAD to 2.7 m, was identified and fixed).

---

## 4. Preliminary Results

The change-detection foundation the proposed work builds on is already operational. A reproduction
of Barlow's change detection on Taylor Valley falls **inside her published uncertainty ranges**
(below), and an initial driver analysis surfaces the first attribution signal that O1 will develop.

**(a) Change detection across all three epochs (Fig. 2).**

![Fig 2](finesst_figures/fig1_dod_maps.png)
***Figure 2.*** *DEM-of-Difference over the same Taylor Valley stream-corridor window, only
|Δz| > LOD95 shown. (a) 2001→2014 lidar–lidar; (b) 2014→2021-23 lidar–REMA. Coherent
erosion/deposition patterns emerge above the noise floor; REMA auto-reprojected from EPSG:3031
to the lidar grid. The large flat signal in (a) is Lake Fryxell's ~1.5 m level rise, detected
and excluded from all stream rates by an automated standing-water screen.*

| Epoch pair | NMAD | LOD95 | Barlow's published range | In range? |
|---|---|---|---|---|
| 2001→2014 (lidar–lidar) | 0.21 m | 0.41 m | NMAD 0.07–0.46 / LOD95 0.15–0.92 | ✅ |
| 2014→2021-23 (lidar–REMA) | 0.23 m | 0.44 m | NMAD 0.19–0.53 / LOD95 0.37–1.04 | ✅ |

Point-to-point **ICP** converged with fitness 0.95 m² (mean-squared correspondence distance) and
improved DoD NMAD on high-relief windows; on the flat valley floor it correctly added no benefit,
exactly the relief-dependence Barlow's point-to-plane ICP exhibits.

**(b) Per-stream rates (Fig. 3), the masked products O1 consumes.**

![Fig 3](finesst_figures/fig2_per_stream_rates.png)
***Figure 3.*** *Per-stream **specific** (area-normalized, mm/yr) gross and net sediment-flux
rates for six gauged Taylor Valley streams, both epochs, channels masked to MCM-LTER centerlines.
Specific rates are used because the valid-data footprint differs between epochs (the 2001 ATM
lidar swath is narrower than REMA coverage), so raw m³/yr totals would confound real change
with coverage.*

**(c) Robust error model (Fig. 4), the basis for O3.**

![Fig 4](finesst_figures/fig3_error_model.png)
***Figure 4.*** *Stable-terrain DoD residuals are sharply **Laplacian**, not Gaussian, the fat
tails would inflate a σ-based LOD. This reproduces Barlow's NMAD/Laplacian finding and is the
launch point for the proposed per-pixel calibrated-uncertainty layer (O3).*

**(d) A first attribution signal (Fig. 5).**

![Fig 5](finesst_figures/fig4_attribution.png)
***Figure 5.*** *Per-stream geomorphic rate vs. mean gauged melt discharge (log-log; lake-level
signal screened out). In the lidar–lidar epoch the **specific (area-normalized) rate scales
strongly with discharge: Pearson r = +0.95 (p = 0.004), Spearman ρ = +0.94 (p = 0.005)**, and
the relationship survives leaving out any single stream. The REMA epoch shows no coherent
relation under sparse post-2015 gauge coverage (48–362 gauged days per stream) and is plotted
without a fit. This motivates O1 directly: where gauges are dense the melt–sediment link is
strong, so the proposed work will replace patchy gauging with **modeled melt energy**
(PDD/insolation/active-layer) to extend attribution across epochs and valleys, turning
correlation into attribution.*

---

## 5. FI Qualifications

The FI has independently built and operated this exact toolchain, U-Net semantic segmentation on
lidar-derived terrain rasters, ICP co-registration, and DEM-of-Difference change analysis, on an
unrelated landscape (channels, roads, and disturbance scars detected from elevation alone in the
Appalachian Plateau). That prior work shows the architecture transfers across sensors and biomes,
directly de-risking **O2**, and that the FI already commands the full pipeline end to end.

---

## 6. Data Requirements and Availability

Every dataset required for the proposed work is **free/public** and already in hand (regenerable
from source via scripted pipelines), so data availability poses no schedule risk. The single
access-gated dependency is Barlow's training labels (mitigated below and in §7).

| Category | Source | Availability |
|---|---|---|
| **A. Terrain:** MDV lidar 2001 (ATM/ScienceBase) + 2014 (NCALM/OpenTopography); REMA 2021-23 (PGC) | free/public | ✅ in hand |
| Per-epoch derivatives (elev/slope/aspect/curv/MFD-flow/intensity) | scripted from terrain | ✅ demonstrated (Taylor pilot) |
| **B. Labels:** MCM-LTER stream centerlines (QC) | EDI `knb-lter-mcm.6007` | ✅ in hand |
| Barlow's 217 hand-digitized tiles | author-gated | ⚠️ **lone access-gated dependency** (see §7) |
| **C. Drivers:** LTER met, 21 discharge gauges, glacier mass balance, soil/active-layer | EDI | ✅ in hand |
| Reanalysis: ERA5 monthly 1993-2024; AMPS 2.67 km | CDS; GDEX | ✅ in hand |
| **D. Cross-valley:** all four valleys, both lidar + REMA | OpenTopography/PGC | ✅ DEMs in hand; per-valley stacks to build |
| **E. Validation:** WorldView/Maxar (label QC); published rates | PGC (restricted); literature | optional / cross-check vs Barlow |

---

## 7. Management, Timeline, Risks, and Data Management Plan

**FI role & development.** The FI is intellectual lead and primary author; the advisor (PI of
record) provides domain mentorship. Development plan: present at AGU (cryosphere) and an ISAES/SCAR
venue; co-author the attribution paper (O1) as a stand-alone publication; complete graduate
coursework in Bayesian/hierarchical modeling and remote-sensing uncertainty.

**Timeline (3 years).**

| Period | Milestones |
|---|---|
| **Yr 1** | Full driver harmonization (PDD/insolation/active-layer series per gauged stream); O1 attribution model on Taylor Valley (extending the Fig. 5 signal); calibrated-uncertainty prototype (O3). **Deliverable:** attribution manuscript drafted. |
| **Yr 2** | Cross-sensor domain-shift correction + segmenter generalization across all four valleys (O2); apply attribution model basin-wide; AGU presentation. **Deliverable:** O2 paper. |
| **Yr 3** | Predictive model (where acceleration migrates next); 3-epoch acceleration attribution; calibrated-uncertainty product release (O3). **Deliverable:** synthesis/prediction paper + public data products. |

**Risks & mitigations.** (1) *Barlow's label tiles are access-gated* → mitigation: LTER centerlines
already work as a QC stand-in (Fig. 2–3 built on them); plan to request the tiles and, failing that,
re-digitize a comparable training set (the FI's prior work shows label generation is in hand). (2) *REMA's
uneven post-2014 coverage* → prioritize Taylor Valley (full 3-epoch coverage) for acceleration; treat
other valleys as 2-epoch. (3) *Discharge gauge gaps* → ERA5/AMPS energy reanalysis fills spatial/temporal
holes (a core reason O1 uses melt energy, not just gauges).

**Data Management Plan.** All input data are free/public (NASA ATM, NCALM/OpenTopography, PGC REMA,
MCM-LTER/EDI, Copernicus ERA5, AMPS/GDEX), cited per source. Derived products, change-detection
rasters, per-stream rate tables, calibrated-uncertainty layers, and stream-boundary polygons, will
be released open-access (DoIs via Zenodo / EDI) with the processing code (PDAL/WhiteboxTools/GDAL +
Python). Heavy regenerable rasters are excluded from version control; lightweight scripts, figures,
and tables are tracked. Outputs follow ASPRS/OGC standards and carry explicit CRS, method, and
uncertainty metadata (per NASA open-science/trustworthy-EO guidance).

---

## References

[1] Barlow, M. C. (2026). *A Comprehensive Spatial Analysis of Stream Boundary and Geomorphological
Change Detection: McMurdo Dry Valleys, Antarctica.* PhD Dissertation, Dept. of Civil & Environmental
Engineering, University of Houston (chair: C. L. Glennie). 240 pp.

[2] Barlow, M. C., Zhu, X., & Glennie, C. L. (2022). Stream Boundary Detection of a Hyper-Arid, Polar
Region Using a U-Net Architecture: Taylor Valley, Antarctica. *Remote Sensing* 14(1):234.
doi:10.3390/rs14010234. *(Dissertation Chapter 4, proof of concept.)*

[3] Höhle, J., & Höhle, M. (2009). Accuracy assessment of digital elevation models by means of robust
statistical methods. *ISPRS J. Photogramm. Remote Sens.* 64(4):398–406. *(NMAD / robust DEM error.)*

[4] Howat, I. M., et al. (2019). The Reference Elevation Model of Antarctica (REMA). *The Cryosphere*
13:665–674. *(REMA.)*

[5] Ronneberger, O., Fischer, P., & Brox, T. (2015). U-Net: Convolutional Networks for Biomedical Image
Segmentation. *MICCAI* 234–241.

[6] McMurdo Dry Valleys LTER. Stream discharge, meteorology, glacier mass-balance, and soil datasets,
Environmental Data Initiative (EDI), `knb-lter-mcm.*`.

[7] Hersbach, H., et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.* 146:1999–2049.

---

*Draft S/T/M section. Figures generated by `barlow/build/_finesst_figures.py`. Not a submitted
proposal.*

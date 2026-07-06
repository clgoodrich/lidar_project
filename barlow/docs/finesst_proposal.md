# From Detection to Attribution: Linking Two Decades of Antarctic Stream-Channel Change to Its Climate Drivers, from Terrain Data Alone

> **Summary.** This project turns an existing Antarctic stream-change *monitor* into a tool
> that *explains* change. Barlow (2026) mapped two decades of stream-channel change across
> the McMurdo Dry Valleys; the proposed work asks the next questions. **(O1)** Which climate
> drivers control that change? **(O2)** What is changing geomorphologically *outside* the
> channels — across the whole valley floor — and do different kinds of change answer to
> different drivers? **(O3)** Can every change map carry an honest, per-pixel error bar?

---

## 1. Background and the Gap

The **McMurdo Dry Valleys (MDVs)** are Earth's largest ice-free Antarctic desert and, for a
century, were considered the planet's most geomorphologically stable landscape. That assumption
is breaking down. The system is **energy-limited** — there is plenty of frozen water but barely
enough heat to melt it — so even small increases in absorbed sunlight, together with thawing
permafrost, translate directly into **ephemeral summer streams**: channels that flow for only a
few weeks each year, move sediment while they do, and reshape themselves in the process. These streams are the most sensitive
measurable indicator of climate change in the most stable place on Earth, a continental-scale
"climate canary."

**Barlow (2026)** [1] established the measurement foundation in three transferable pillars:

1. **Terrain-only semantic segmentation:** a U-Net delineates stream boundaries from DEM
   derivatives alone (elevation, slope, aspect most informative; no water/color signal),
   so it works in channels that are dry 11 months a year.
2. **Satellite-DEM validation:** free REMA satellite DEMs are proven accurate enough for
   centimeter-to-meter stream-corridor change detection, using **ICP** (iterative closest
   point — sliding one 3-D surface onto another until they match) for alignment and **NMAD**
   (normalized median absolute deviation — a standard deviation that ignores outliers) for
   honest error bars; the errors follow a **Laplacian** (sharp-peaked, heavy-tailed)
   distribution rather than a Gaussian, which is why the robust statistic is required.
3. **Multi-epoch change detection:** subtract one epoch's DEM from another
   (**DEM-of-Difference, DoD**) inside the segmented stream masks, and count only elevation
   changes exceeding the **level of detection** (LOD95 = 1.96 × NMAD — the smallest change
   distinguishable from measurement noise at 95% confidence). This yields per-stream
   erosion/deposition and acceleration rates across four valleys and three epochs
   (2001 & 2014 lidar, 2021–23 REMA).

**The gap.** Barlow's dissertation ends at *description*, and at the channel edge. It maps
**where** in-channel change is happening (Denton Hills is the erosion hotspot; parts of Taylor
Valley are accelerating), but it explicitly defers **coupling that change to physical/climate
drivers** to future work — and its change analysis is masked to the stream channels, so
everything the elevation differencing measures *outside* them (thawing ground, slopes, fans,
lake margins) is discarded unexamined. A Future Investigator project lives precisely in that
gap: explain the change, and stop throwing most of the measurement away. This is a genuine
scientific increment, not a replication.

**Relevance to NASA.** The 2001 baseline epoch is NASA data — an ATM airborne lidar campaign —
that has never been fully exploited for surface change. The proposed work converts that NASA
archive, the free REMA satellite record, and reanalysis into a continuing, uncertainty-calibrated
measurement of climate-driven surface change in Earth's largest ice-free Antarctic region,
serving the Earth Science Division's cryosphere and Earth-surface-change focus areas. The
methodological deliverables generalize: terrain-only feature detection and calibrated
per-pixel change thresholds (O3) apply to any elevation-differencing record, including those
produced by ICESat-2 and NISAR. The MDVs are also the canonical terrestrial analog for
cold-desert planetary surfaces — a long-standing NASA investment this project extends with
open, reusable tools. The FI development itself is Division-aligned: open geospatial data,
machine learning on remote sensing, and honest uncertainty quantification.

---

## 2. Objectives and Hypotheses

| # | Objective | Hypothesis | Increment over Barlow |
|---|---|---|---|
| **O1** | **Attribution (headline science).** Match each stream's measured change rate against candidate drivers — temperature (as **positive degree-days, PDD**: a running total of melting weather), sunlight, discharge, glacier mass balance, thaw depth — from the MDV-LTER network plus ERA5/AMPS. | **H1:** *cumulative melt energy*, not water volume alone, controls sediment movement — a heat-based model predicts each stream's rate better than discharge and explains the scatter discharge leaves behind. | Listed verbatim as Barlow future work; never quantified. |
| **O2** | **Landscape-wide geomorphic change.** Extend change detection from the channel masks to the full valley-floor surface; classify significant change by process type — channel migration, thaw-driven subsidence (**thermokarst**), slope movement, fan/delta growth, lake-margin shift; attribute each type to its drivers. | **H2:** different process types answer to different drivers — channel change tracks melt energy and discharge, while thermokarst tracks summer thaw depth. Each type should carry a distinct driver fingerprint. | Barlow's change analysis is confined to the detected channel outlines; the rest of the DoD measurement is discarded. |
| **O3** | **Calibrated uncertainty.** Replace the single valley-wide noise estimate with a per-pixel threshold that accounts for slope, aspect, and sensor. | **H3:** a 95% threshold built this way behaves like one — on unchanged ground, only ~5% of pixels exceed it. | Barlow uses a single global NMAD per epoch-pair. |

**Predictive payoff (ties O1–O3 together):** a model that, given a driver field, predicts *where
acceleration migrates next*, the actionable form of the "climate canary."

---

## 3. Methodology

**Data (all free/public; see §5).** Three elevation snapshots form the backbone: 2001 airborne
lidar (NASA ATM, 2 m), 2014 airborne lidar (NCALM, 1 m), and the REMA satellite DEM (2 m,
2021–23). From each snapshot the pipeline derives the terrain layers the detector reads:
elevation, slope, aspect, curvature, flow accumulation (a "where water would go" map), and
lidar intensity. Driver data come from the MDV-LTER station network — meteorology, 21
stream-discharge gauges, mass balance for 7 glaciers, and soil temperature/moisture (a proxy
for summer thaw depth) — with the ERA5 and AMPS weather models filling the gaps between
stations. Training labels: the public MCM-LTER stream centerlines, standing in for Barlow's
access-gated 217 hand-digitized tiles (§6 risk).

**O1, Attribution.** For each gauged stream and epoch: (i) measure the change rate — the DoD
inside its channel mask; (ii) build the stream's **energy
history** (PDD, sunlight, discharge, thaw depth) from LTER stations plus ERA5/AMPS; (iii) fit
hierarchical regression and random-forest models relating rate to drivers, always validating on
streams held out of fitting; (iv) test H1 head-to-head — does melt energy predict rates better
than water volume alone? For the Taylor streams with all three epochs, the *change* in rate
(acceleration) is compared against the *trend* in each driver.

**O2, Landscape-wide change.** The DoD already measures the entire surface; the channel mask
simply discards most of it. The work will apply the O3 per-pixel thresholds to the full valley
floor, extract coherent patches of significant change, and classify them by process type from
their morphology and setting (slope position, proximity to channels and lakes, ice-cored
terrain). Each type's rates then enter the O1 driver models separately, testing H2's prediction
of distinct driver fingerprints. The FI's prior work classifying terrain-disturbance features
by type on a completely different landscape (§4) shows this move is in hand.

**Sensor continuity (supporting method, not an objective).** The record continues past the
last lidar flight (2014) only on REMA, and satellite elevations disagree with lidar in
terrain-dependent ways (a **domain shift**). The work will measure that disagreement over
unchanged ground as a function of slope and aspect and correct it before any cross-sensor
differencing — a prerequisite for O1–O3. Extension beyond Taylor Valley proceeds where REMA
quality supports it.

**O3, Calibrated uncertainty.** The work will replace the single global noise estimate with one
that varies by slope, aspect, and sensor, and publish it as a per-pixel detection-threshold map.
Calibration will be verified the honest way: on held-out ground that did not change, a 95%
threshold should be exceeded by only ~5% of pixels.

**Reproducibility/QC.** The pipeline is fully scripted; input data and all derivatives
regenerate from source, with robust statistics and CRS checks enforced at every step.

---

## 4. FI Qualifications

The FI has independently built and operated this exact toolchain, U-Net semantic segmentation on
lidar-derived terrain rasters, ICP co-registration, and DEM-of-Difference change analysis, on an
unrelated landscape (channels, roads, and disturbance scars detected from elevation alone in the
Appalachian Plateau). That prior work shows the architecture transfers across sensors and biomes,
that classifying terrain disturbance by process type (the core move of **O2**) is demonstrated,
and that the FI commands the full pipeline end to end.

---

## 5. Data Requirements and Availability

Every dataset required for the proposed work is **free/public**, so data availability poses no
schedule risk. The single access-gated dependency is Barlow's training labels (mitigated below
and in §6).

| Dataset (source) | What it shows | Role in the proposed work | Availability |
|---|---|---|---|
| **2001 airborne lidar**, 2 m (NASA ATM, via USGS) | Valley-floor surface in 2001 | Baseline epoch for all change detection | public, free |
| **2014 airborne lidar**, 1 m (NCALM, via OpenTopography) | Same terrain 13 yr later at benchmark accuracy | Reference epoch; anchors the error model | public, free |
| **REMA satellite DEM**, 2 m, 2021-23 (PGC/Maxar stereo) | Most recent surface, continent-wide | Extends the record past the last lidar flight (sensor-continuity correction, §3) | public, free |
| Per-epoch terrain derivatives (slope/aspect/curvature/MFD-flow/intensity) | Channel-diagnostic terrain form | Input features the U-Net segmenter reads | computed from the DEMs |
| **LTER stream gauges**, 21 streams, daily, 1990s-present (EDI) | Meltwater each stream carried | Direct discharge driver for O1 | public, free |
| **LTER meteorology** (EDI) | Air temperature, radiation, wind | PDD + insolation melt-energy drivers (O1/H1) | public, free |
| **LTER glacier mass balance**, 7 glaciers (EDI) | Seasonal ice gain/loss per glacier | Links stream water supply to its source | public, free |
| **LTER soil temperature/moisture** (EDI) | Summer thaw depth | Active-layer driver (O1/H1) | public, free |
| **ERA5** monthly (Copernicus CDS); **AMPS** 2.67 km (NCAR GDEX) | Continuous modeled atmosphere | Gap-fills drivers between stations and to ungauged streams; AMPS cross-checks ERA5 | public, free |
| **MCM-LTER stream channel polygons** (EDI `knb-lter-mcm.6007`) | Mapped channel of every named stream | Per-stream rate masks + label stand-in | public, free |
| **Barlow's 217 hand-digitized tiles** (author-gated) | Expert-traced channel boundaries | Gold-standard U-Net training labels | ⚠️ **lone access-gated dependency** (see §6) |
| **Cross-valley DEMs**, all four valleys (OpenTopography/PGC) | Terrain beyond Taylor Valley | Extension beyond Taylor Valley where coverage allows | public, free |
| WorldView/Maxar imagery; published rates (PGC restricted; literature) | Visual ground truth; independent rates | Optional label QC / cross-check vs Barlow | optional |

---

## 6. Management, Timeline, Risks, and Data Management Plan

**FI role & development.** The FI is intellectual lead and primary author; the advisor (PI of
record) provides domain mentorship. Development plan: present at AGU (cryosphere) and an ISAES/SCAR
venue; co-author the attribution paper (O1) as a stand-alone publication; complete graduate
coursework in Bayesian/hierarchical modeling and remote-sensing uncertainty.

**Timeline (3 years).**

| Period | Milestones |
|---|---|
| **Yr 1** | Change-detection chain built from public data; lidar–REMA disagreement measured and corrected; full driver harmonization (PDD/insolation/active-layer series per gauged stream); O1 attribution model on Taylor Valley; calibrated-uncertainty prototype (O3). **Deliverable:** attribution manuscript drafted. |
| **Yr 2** | Landscape-wide change detection + process-type classification on Taylor Valley (O2), gated by the O3 thresholds; per-type driver attribution; AGU presentation. **Deliverable:** O2 paper. |
| **Yr 3** | Predictive model (where acceleration migrates next); 3-epoch acceleration attribution; extension beyond Taylor Valley where REMA supports it; calibrated-uncertainty product release (O3). **Deliverable:** synthesis/prediction paper + public data products. |

**Risks & mitigations.** (1) *Barlow's label tiles are access-gated* → mitigation: the public LTER
centerlines serve as a stand-in; plan to request the tiles and, failing that,
re-digitize a comparable training set (the FI's prior work shows label generation is in hand). (2) *REMA's
uneven post-2014 coverage* → prioritize Taylor Valley (full 3-epoch coverage) for acceleration; treat
other valleys as 2-epoch. (3) *Discharge gauge gaps* → ERA5/AMPS energy reanalysis fills spatial/temporal
holes (a core reason O1 uses melt energy, not just gauges). (4) *Outside the channels, change may
sit below the detection threshold* → then O2 narrows back to in-channel change and the
landscape-wide result is reported as a calibrated null — itself a quantitative statement about
how spatially confined active change currently is.

**Data Management Plan.** All input data are free/public (NASA ATM, NCALM/OpenTopography, PGC REMA,
MCM-LTER/EDI, Copernicus ERA5, AMPS/GDEX), cited per source. Derived products, change-detection
rasters, per-stream rate tables, process-classified change maps, calibrated-uncertainty layers,
and stream-boundary polygons, will
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

*Draft S/T/M section, written as a plan only (no preliminary work presented). Not a submitted
proposal.*

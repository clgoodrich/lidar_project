# From Detection to Attribution: Linking Two Decades of Antarctic Stream-Channel Change to Its Climate Drivers, from Terrain Data Alone

**NASA ROSES-2025 F.5: Future Investigators in NASA Earth and Space Science and Technology (FINESST)**
**Target division:** Earth Science Division (EARTH25), Antarctic cryosphere / climate
**Proposal deadline:** 14 July 2026 (11:59 PM EDT)
**Structure:** Graduate student = Future Investigator (FI), primary author and intellectual lead; faculty advisor = PI of record. Award up to ~$50,000/yr for up to 3 years.

> **Summary.** This project turns an existing Antarctic stream-change *monitor* into a tool
> that *explains and predicts* change. Barlow (2026) mapped two decades of stream-channel
> change across the McMurdo Dry Valleys; the proposed work asks the next questions.
> **(O1)** Which climate drivers control that change? **(O2)** Can the terrain-only detector
> work as well on free satellite data as it does on airborne lidar, across all four valleys?
> **(O3)** Can every change map carry an honest, per-pixel error bar? The measurement
> foundation is already running and reproduces Barlow's published uncertainty ranges, and a
> first driver signal is shown in §4.

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
| **O1** | **Attribution (headline science).** Match each stream's measured change rate against the factors that could be driving it: air and ground temperature, sunshine, **positive degree-days (PDD** — a running total of how much warm weather the season delivered**)**, melt-season water flow, glacier mass balance, and summer thaw depth. All driver data come from the MDV-LTER station network plus the ERA5/AMPS weather models. | **H1:** What controls how much sediment a stream moves is *cumulative melt energy* — the total melting heat the season delivered — not simply how much water passed through. A heat-based model should predict each stream's rate better than water volume alone, and explain the scatter that water volume leaves behind. | Listed verbatim as Barlow future work; never quantified. |
| **O2** | **Cross-sensor & cross-valley generalization.** The detector works best on airborne lidar. Measure exactly how the satellite DEMs disagree with lidar (the **domain shift**), correct for it, and show the detector performs nearly as well on satellite data — across all four valleys, not just Taylor. | **H2:** Most of the lidar-vs-satellite performance gap is predictable, terrain-dependent measurement bias. Correcting that bias per pixel (using slope and aspect) recovers near-lidar accuracy on REMA. | Barlow flags sensor generalization as future work. |
| **O3** | **Calibrated uncertainty.** Replace the single valley-wide noise estimate with a per-pixel one that accounts for slope, aspect, and sensor — so every change map ships with an error bar you can defend. | **H3:** A 95%-confidence detection threshold built this way actually behaves like one: on ground that did not change, only ~5% of pixels exceed it. | Barlow uses a single global NMAD per epoch-pair. |

**Predictive payoff (ties O1–O3 together):** a model that, given a driver field, predicts *where
acceleration migrates next*, the actionable form of the "climate canary."

---

## 3. Methodology

**Data (all free/public; see §6).** Three elevation snapshots form the backbone: 2001 airborne
lidar (NASA ATM, 2 m), 2014 airborne lidar (NCALM, 1 m), and the REMA satellite DEM (2 m,
2021–23). From each snapshot the pipeline derives the terrain layers the detector reads:
elevation, slope, aspect, curvature, flow accumulation (a "where water would go" map), and
lidar intensity. Driver data come from the MDV-LTER station network — meteorology, 21
stream-discharge gauges, mass balance for 7 glaciers, and soil temperature/moisture (a proxy
for summer thaw depth) — with the ERA5 and AMPS weather models filling the gaps between
stations. Training labels: the public MCM-LTER stream centerlines, standing in for Barlow's
access-gated 217 hand-digitized tiles (§7 risk).

**O1, Attribution.** For each gauged stream and epoch, the proposed work will (i) measure the
stream's change rate — the DoD inside its channel mask (already operational, Fig. 2); (ii) build
that stream's **energy history**: how much warm weather (PDD), sunlight, water flow, and thaw
depth it experienced, from the LTER stations plus ERA5/AMPS; (iii) fit statistical models
(hierarchical regression and random forests) relating rate to drivers, always testing each model
on streams it never saw during fitting; and (iv) test H1 head-to-head — does melt energy predict
the rates better than water volume alone? (The water-only relationship in Fig. 5 is real but
incomplete.) For the Taylor streams with all three epochs, the *change* in rate (acceleration)
will be compared against the *trend* in each driver.

**O2, Generalization.** The work will first measure how the satellite and lidar elevations
disagree over ground that has not changed, and how that disagreement depends on slope and
aspect. It will then learn a correction for the disagreement, retrain the segmenter with both
sensors represented in its training data, and score accuracy (F1) across all four valleys and
both sensor types. The FI's prior work applying this same architecture to a completely
different landscape (§5) shows it transfers across sensors and biomes.

**O3, Calibrated uncertainty.** The work will replace the single global noise estimate with one
that varies by slope, aspect, and sensor, and publish it as a per-pixel detection-threshold map.
Calibration will be verified the honest way: on held-out ground that did not change, a 95%
threshold should be exceeded by only ~5% of pixels. (Fig. 4 shows today's valley-wide version.)

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
***Figure 2.*** *Elevation change over the same Taylor Valley stream-corridor window in two
periods: (a) 2001→2014, comparing two lidar surveys; (b) 2014→2021-23, comparing lidar against
the REMA satellite DEM. Red = surface lowered (erosion), blue = surface raised (deposition).
Pixels are drawn only where the change exceeds the detection floor (LOD95) — i.e., is too large
to be measurement noise — and coherent erosion/deposition patterns emerge above that floor.
The broad flat patch in (a) is not sediment at all: Lake Fryxell rose ~1.5 m between surveys,
and an automated standing-water screen detects such flat water surfaces and excludes them from
every stream-rate statistic.*

| Epoch pair | NMAD | LOD95 | Barlow's published range | In range? |
|---|---|---|---|---|
| 2001→2014 (lidar–lidar) | 0.21 m | 0.41 m | NMAD 0.07–0.46 / LOD95 0.15–0.92 | ✅ |
| 2014→2021-23 (lidar–REMA) | 0.23 m | 0.44 m | NMAD 0.19–0.53 / LOD95 0.37–1.04 | ✅ |

ICP alignment behaved exactly as Barlow's published version does: it tightened the error budget
on steep, high-relief windows and correctly added no benefit on the flat valley floor (alignment
needs terrain shape to grip onto). Convergence fitness was 0.95 m² mean-squared point distance.

**(b) Per-stream rates (Fig. 3), the masked products O1 consumes.**

![Fig 3](finesst_figures/fig2_per_stream_rates.png)
***Figure 3.*** *How much sediment each of six gauged Taylor Valley streams moved, per year, in
each period. Rates are reported per square meter of channel (mm/yr of surface change) rather
than as raw m³/yr totals: the surveys do not all cover the same footprint (the 2001 lidar swath
is narrower than the satellite coverage), and a per-area rate cannot be inflated simply because
one survey saw more ground.*

**(c) Robust error model (Fig. 4), the basis for O3.**

![Fig 4](finesst_figures/fig3_error_model.png)
***Figure 4.*** *The measurement noise, profiled on ground that should not have changed at all.
The error histogram is sharply peaked with heavy tails (a **Laplacian** shape), not the familiar
bell curve: a handful of large outliers would wildly inflate a naive standard-deviation-based
detection threshold, which is why the outlier-resistant NMAD is used instead. This reproduces
Barlow's error-model finding and is the launch point for the proposed per-pixel
calibrated-uncertainty layer (O3).*

**(d) A first attribution signal (Fig. 5).**

![Fig 5](finesst_figures/fig4_attribution.png)
***Figure 5.*** *The first attribution signal: each stream's sediment-movement rate plotted
against how much meltwater it carried (mean gauged discharge; both axes logarithmic; the lake
signal from Fig. 2 screened out). In the 2001→2014 period the relationship is strong —
correlation **r = +0.95 (p = 0.004)**, rank correlation **ρ = +0.94 (p = 0.005)** — and it
survives dropping any single stream, so it is not driven by one outlier. The satellite period
shows no coherent relation, but for an instructive reason: after 2015 the stream gauges ran
only sporadically (48–362 recorded days per stream), so the water axis itself is unreliable
there, and no trend line is fit. That is precisely the motivation for O1: where gauge data are
dense the melt–sediment link is strong, so the proposed work replaces patchy gauging with
**modeled melt energy** (degree-days, sunlight, thaw depth) to extend the analysis across all
epochs and valleys.*

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

| Dataset (source) | What it shows | Role in the proposed work | Status |
|---|---|---|---|
| **2001 airborne lidar**, 2 m (NASA ATM, via USGS) | Valley-floor surface in 2001 | Baseline epoch for all change detection | ✅ in hand |
| **2014 airborne lidar**, 1 m (NCALM, via OpenTopography) | Same terrain 13 yr later at benchmark accuracy | Reference epoch; anchors the error model | ✅ in hand |
| **REMA satellite DEM**, 2 m, 2021-23 (PGC/Maxar stereo) | Most recent surface, continent-wide | Extends the record past the last lidar flight; the sensor O2 must generalize to | ✅ in hand |
| Per-epoch terrain derivatives (slope/aspect/curvature/MFD-flow/intensity) | Channel-diagnostic terrain form | Input features the U-Net segmenter reads | ✅ scripted; demonstrated (Taylor pilot) |
| **LTER stream gauges**, 21 streams, daily, 1990s-present (EDI) | Meltwater each stream carried | Direct discharge driver for O1 (source of the Fig. 5 signal) | ✅ in hand |
| **LTER meteorology** (EDI) | Air temperature, radiation, wind | PDD + insolation melt-energy drivers (O1/H1) | ✅ in hand |
| **LTER glacier mass balance**, 7 glaciers (EDI) | Seasonal ice gain/loss per glacier | Links stream water supply to its source | ✅ in hand |
| **LTER soil temperature/moisture** (EDI) | Summer thaw depth | Active-layer driver (O1/H1) | ✅ in hand |
| **ERA5** monthly 1993-2024 (Copernicus CDS); **AMPS** 2.67 km (NCAR GDEX) | Continuous modeled atmosphere | Gap-fills drivers between stations and to ungauged streams; AMPS cross-checks ERA5 | ✅ in hand |
| **MCM-LTER stream channel polygons** (EDI `knb-lter-mcm.6007`) | Mapped channel of every named stream | Per-stream rate masks (used in Figs. 3/5) + label stand-in | ✅ in hand |
| **Barlow's 217 hand-digitized tiles** (author-gated) | Expert-traced channel boundaries | Gold-standard U-Net training labels | ⚠️ **lone access-gated dependency** (see §7) |
| **Cross-valley DEMs**, all four valleys (OpenTopography/PGC) | Terrain beyond Taylor Valley | O2 generalization test bed | ✅ DEMs in hand; per-valley stacks to build |
| WorldView/Maxar imagery; published rates (PGC restricted; literature) | Visual ground truth; independent rates | Optional label QC / cross-check vs Barlow | optional |

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

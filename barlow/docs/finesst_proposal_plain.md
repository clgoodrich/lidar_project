# From Detection to Attribution: Tracking and Explaining Landscape Change in Antarctica's Dry Valleys from Terrain Alone

> **Summary.** A tool exists that *finds* where Antarctic streams are reshaping the land, but it
> stops at location: it says where, never why. This project starts at that line. The work will
> connect the measured change to the processes driving it (heat, melt, thawing ground), widen
> the view from the stream channels to everything changing on the valley floors, and attach a
> real uncertainty value to every pixel.

---

## 1. The setup and the gap

The **McMurdo Dry Valleys (MDVs)** are the largest ice-free region in Antarctica, a cold polar
desert of bare rock and gravel. For roughly a century they were treated as the most
geomorphically stable place on Earth, but that's no longer holding. The system sits right at the
energy threshold for melting, so small increases in absorbed heat are enough to melt ice and
degrade permafrost. The visible result is **ephemeral streams**: channels that flow for a few weeks
each summer, transport sediment, and reshape the channel before going dry again.

Those streams are the clearest climate signal available in an otherwise stable landscape. If they
accelerate, that's an early indicator worth taking seriously.

**Barlow (2026)** [1] built the tool that measures them, and it rests on three components worth
naming:

1. **Terrain-only segmentation.** A **U-Net** (an image-segmentation CNN) traces stream channels
   from the shape of the ground alone (elevation, slope, aspect). There's no water signal to key
   off, since the channels are dry most of the year.
2. **Validating the free satellite data.** Airborne lidar is the accuracy benchmark but only exists
   for 2001 and 2014. Extending past 2014 means using **REMA** (free satellite elevation models).
   She showed REMA is good enough via **ICP** (a 3D alignment method) and **NMAD** (a
   median-based, outlier-robust spread estimate that's far more reliable here than standard
   deviation).
3. **Measuring change.** Differencing an old elevation surface from a newer one inside the channels
   gives a **DEM-of-Difference (DoD)**. Only changes above the noise floor
   (**LOD95 = 1.96 × NMAD**) count. Summed per stream, that yields erosion/deposition rates and
   even acceleration.

**The gap.** Barlow's work ends at *description*, and at the channel edge. It maps **where**
in-channel change happens (Denton Hills erodes hardest; parts of Taylor Valley are accelerating)
but leaves the **drivers** for future work — and everything the elevation differencing measures
*outside* the channels (thawing ground, slopes, fans, lake edges) gets thrown away by the
channel mask. That's the natural space for a Future Investigator project: explain the change,
and stop discarding most of the measurement.

---

## 2. What we need to do

In one sentence: measure how fast the Dry Valleys' surfaces are changing — the stream channels
first, and the whole valley floor with them — then explain those rates with heat and melt, so
the map stops just *describing* change and starts *predicting* it. That breaks into three
concrete objectives:

| # | Objective | Hypothesis | Why it's new |
|---|---|---|---|
| **O1** | **Attribution (the headline).** Relate each stream's change rate to its drivers: temperature, insolation, **positive-degree-days (PDD)** (cumulative above-freezing heat), melt-season discharge, glacier melt, and active-layer (thaw) depth, drawn from the LTER field network plus ERA5/AMPS reanalysis. | **H1:** Change is governed by *cumulative melt energy*, not raw water volume. An energy-based model outperforms a discharge-only model and explains the scatter discharge leaves behind. | Barlow lists this as future work; it hasn't been quantified. |
| **O2** | **Whole-landscape change.** Run the change detection over the entire valley floor, not just inside the channel outlines, and sort each patch of significant change by the process behind it: channel shift, ground-ice thaw (**thermokarst**), slope movement, fan growth, lake-edge change. Then test each kind against its own drivers. | **H2:** Different kinds of change answer to different drivers — channels follow melt energy and water; thaw-driven sinking follows how deep the ground thaws each summer. | Barlow's analysis keeps only what's inside the channel masks; the rest of the measurement is discarded. |
| **O3** | **Calibrated uncertainty.** Replace the single global noise value with a **per-pixel, sensor-aware** one, so every change map carries a defensible confidence layer. | **H3:** Conditioning NMAD on slope, aspect, and sensor produces a 95% bound that actually holds 95% of the time. | Barlow uses one global value per epoch pair. |

**The unifying payoff:** a model that takes a driver field and predicts **where acceleration
migrates next**, which is the operationally useful form of the climate-indicator idea.

---

## 3. The data: what we'll use, where it's from, what it shows

Everything below is free and public (the one exception is
flagged). The datasets fall into three jobs: **snapshots of the ground** (to measure change),
**drivers** (to explain it), and **labels** (to know where the streams are).

**Three snapshots of the ground.** Change detection needs the same terrain measured at different
times. We have three epochs:

| Dataset | Where it's from | What it shows | What it does for us |
|---|---|---|---|
| **2001 airborne lidar** (2 m) | NASA Airborne Topographic Mapper survey (via USGS) | The valley floors as they were in 2001 | The baseline: every change is measured against this starting surface |
| **2014 airborne lidar** (1 m) | NCALM flight campaign (via OpenTopography) | The same terrain 13 years later, at the highest accuracy available | The benchmark epoch: sharpest data, anchors the noise model, midpoint of the record |
| **REMA satellite DEM** (2 m, 2021–23) | Polar Geospatial Center, built from Maxar stereo imagery | The most recent surface, covering all of Antarctica | Extends the record past the last lidar flight; since no new lidar is planned, this is the future of monitoring — which is why the lidar-vs-REMA correction in §4 matters |

From each snapshot we compute the terrain layers the detector reads: slope, aspect, **profile
curvature** (signed, so concave channels separate from convex ridges), **MFD flow accumulation**
(where water would collect), and lidar intensity.

**Drivers: the "why" variables.** O1 tests whether melt energy explains the measured change, so we
need the energy and water records:

| Dataset | Where it's from | What it shows | What it does for us |
|---|---|---|---|
| **Stream gauges** (21 streams, daily, 1990s–present) | McMurdo LTER field network (via EDI) | How much meltwater each stream actually carried, day by day | The direct water driver for O1 |
| **Meteorology stations** | McMurdo LTER (via EDI) | Air temperature, solar radiation, wind on the valley floors | Builds the melt-energy drivers: positive-degree-days and insolation |
| **Glacier mass balance** (7 glaciers) | McMurdo LTER (via EDI) | How much ice each glacier gained or lost per season | Ties each stream's water supply to its source glacier |
| **Soil temperature and moisture** | McMurdo LTER (via EDI) | How deep the ground thaws each summer | The active-layer driver: thawed banks erode more easily |
| **ERA5 reanalysis** | ECMWF Copernicus Climate Data Store | Continuous modeled weather for every point, 1993–present | Fills the gaps between stations, and between gauged and ungauged streams |
| **AMPS forecasts** (2.67 km) | NCAR (via GDEX) | Antarctic-specific high-resolution atmosphere | Cross-checks ERA5 in the valleys' complicated terrain |

**Labels: where the streams are.**

| Dataset | Where it's from | What it shows | What it does for us |
|---|---|---|---|
| **Stream channel polygons** | McMurdo LTER GIS (EDI `knb-lter-mcm.6007`) | The mapped channel of every named stream | Masks the change maps to actual channels and stands in as training labels |
| **Barlow's 217 hand-drawn tiles** | Her research group (not public) | Expert-traced channel boundaries used to train her U-Net | The gold-standard training set, **the one access-gated item**; §6 covers the fallback |
| **High-res satellite imagery** (optional) | Polar Geospatial Center | Visual ground truth | Spot-checking labels and odd change patches |

---

## 4. How we'll do it

The data above feed three work packages, one per objective.

**O1, attribution.** For each gauged stream and epoch: **(i)** take the change rate from the
DoD inside the channel; **(ii)** assemble a per-stream **energy time
series** (PDD, insolation, discharge, thaw depth); **(iii)** fit rate-vs-driver models
(hierarchical regression and random forest) with leave-one-stream-out validation; and **(iv)** test
H1 directly: energy-based model against discharge-only. For
streams with three time points, regress *acceleration* against *driver trends*.

**O2, whole-landscape change.** The DoD already measures the whole surface; the channel mask
throws most of it away. Apply the O3 per-pixel thresholds to the full valley floor, pull out
the patches of change that clear them, and classify each patch by process type from its shape
and setting (on a slope? next to a lake? ice-cored ground?). Each type's rates then get their
own driver test in O1. Prior work (§5) classifying terrain disturbance by type on a different
landscape shows this move is in hand.

**Sensor continuity (a method, not an objective).** The record only continues past 2014 on
REMA, and satellite elevations disagree with lidar in terrain-dependent ways. Measure that
disagreement over stable ground (by slope and aspect) and correct it before any differencing
that mixes sensors. Expand beyond Taylor Valley where REMA quality allows.

**O3, uncertainty.** Replace the global NMAD with one conditioned on (slope, aspect, sensor),
output it as a per-pixel layer, and verify calibration by confirming the 95% bound is exceeded
about 5% of the time on stable ground.

**Reproducibility.** The pipeline is fully scripted: re-run from source and the outputs match, with
robust statistics and CRS checks enforced throughout.

---

## 5. FI qualifications

The FI has built and run this same class of machinery (U-Net segmentation on terrain layers, ICP
alignment, DoD change detection) on a very different landscape: detecting channels, roads, and
disturbance scars in the Appalachian Plateau from elevation alone. That shows the approach
transfers across sensors and biomes, that sorting disturbance features by type (O2's core move)
is demonstrated, and that the FI can operate the full pipeline end to end.

---

## 6. Plan, timeline, risks, and data sharing

**My role and development.** I'm the lead and main author; my advisor mentors and is PI of record.
I'll present at AGU and a SCAR/ISAES Antarctic venue, publish the O1 attribution result as its own
paper, and take coursework in Bayesian/hierarchical modeling and remote-sensing uncertainty.

**Timeline (3 years).**

| Year | Deliverables |
|---|---|
| **Yr 1** | Build the change-detection chain from public data; build the per-stream driver time series; first O1 attribution model on Taylor Valley; prototype the per-pixel uncertainty layer (O3). Output: attribution paper drafted. |
| **Yr 2** | Whole-landscape change detection and process classification on Taylor Valley (O2), gated by the O3 thresholds; driver tests per change type; AGU talk. Output: O2 paper. |
| **Yr 3** | Predict where acceleration migrates next; full three-epoch acceleration attribution; extend beyond Taylor Valley where REMA supports it; release the uncertainty product (O3). Output: synthesis/prediction paper plus public datasets. |

**Risks and mitigations.** **(1)** *Barlow's training labels are gated.* Request them from her
group; if that stalls, the public LTER centerlines serve as a stand-in, and the
FI's prior work shows label-building from scratch is in hand. **(2)** *REMA coverage after 2014 is
uneven.* Prioritize Taylor Valley (full three-epoch coverage) for the acceleration work; treat
other valleys as two-epoch. **(3)** *Gauge records have gaps.* That's a core reason O1 relies on
melt *energy* from reanalysis rather than raw gauge discharge alone. **(4)** *Outside the
channels, change may be too small to clear the detection threshold.* Then O2 narrows back to
in-channel change and the whole-landscape result is reported as a calibrated null — which is
itself a statement about how confined active change currently is.

**Data sharing.** All inputs are free/public and cited. My outputs (change maps classified by
process type, per-stream rate tables, uncertainty layers, stream-boundary polygons) will be released open-access (DOIs via
Zenodo/EDI) alongside the code. Heavy regenerable rasters stay out of version control; scripts,
figures, and tables are tracked. Everything carries explicit CRS, method, and uncertainty metadata,
consistent with NASA's open-science requirements.

---

## References

[1] Barlow, M. C. (2026). *A Comprehensive Spatial Analysis of Stream Boundary and Geomorphological
Change Detection: McMurdo Dry Valleys, Antarctica.* PhD Dissertation, Univ. of Houston (chair:
C. L. Glennie). 240 pp.

[2] Barlow, M. C., Zhu, X., & Glennie, C. L. (2022). Stream Boundary Detection of a Hyper-Arid,
Polar Region Using a U-Net Architecture: Taylor Valley, Antarctica. *Remote Sensing* 14(1):234.
doi:10.3390/rs14010234. *(Dissertation Ch. 4, the proof of concept.)*

[3] Höhle, J., & Höhle, M. (2009). Accuracy assessment of DEMs by means of robust statistical
methods. *ISPRS J. Photogramm. Remote Sens.* 64(4):398–406. *(Origin of NMAD.)*

[4] Howat, I. M., et al. (2019). The Reference Elevation Model of Antarctica (REMA). *The
Cryosphere* 13:665–674.

[5] Ronneberger, O., Fischer, P., & Brox, T. (2015). U-Net: Convolutional Networks for Biomedical
Image Segmentation. *MICCAI* 234–241.

[6] McMurdo Dry Valleys LTER datasets (stream discharge, meteorology, glacier mass balance, soil),
Environmental Data Initiative, `knb-lter-mcm.*`.

[7] Hersbach, H., et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.*
146:1999–2049.

---

*Plain-language version of `finesst_proposal.md`: same plan, more direct voice. Written as a
plan only (no preliminary work presented). Not a submitted proposal.*

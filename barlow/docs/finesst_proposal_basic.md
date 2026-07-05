# Measuring and Explaining Stream-Channel Change in the McMurdo Dry Valleys, Antarctica

**NASA ROSES F.5: Future Investigators in NASA Earth and Space Science and Technology (FINESST)**
**Target division:** Earth Science Division — Antarctic cryosphere / climate
**Structure:** Graduate student = Future Investigator (FI), intellectual lead and primary author; faculty advisor = PI of record. Award up to ~$50,000/yr for up to 3 years.

> **Summary.** The McMurdo Dry Valleys hold the only streams in Antarctica that flow over
> open ground. They flow for a few weeks each summer, and they are changing. A 2026
> dissertation (Barlow) mapped two decades of that change but stopped short of explaining
> it. This project proposes to (1) identify which climate drivers control the change,
> (2) make the detection method work on free satellite elevation data so monitoring can
> continue without new airborne surveys, and (3) attach an honest, per-pixel error bar to
> every change map. This document is a plan. No results are claimed here; the sections
> below state plainly what exists, what does not, what the work needs, and what could
> go wrong.

---

## 1. Background

The **McMurdo Dry Valleys (MDVs)** are the largest ice-free region of Antarctica. For most
of a century they were treated as the most stable landscape on Earth. That view is now in
question. The valleys are **energy-limited**: frozen water is everywhere, but there is
barely enough summer heat to melt any of it. A small warming therefore produces a direct,
measurable response — **ephemeral streams** (channels that flow only during the brief melt
season) carry more water, move more sediment, and reshape their own beds.

**What already exists.** Barlow (2026) built the measurement foundation:

- A neural network (**U-Net**) that finds stream channels from terrain shape alone —
  elevation, slope, aspect — with no need for water or color in the data. This matters
  because the channels are dry 11 months of the year.
- Evidence that the free, continent-wide **REMA** satellite elevation model is accurate
  enough to detect stream-corridor change, once aligned to airborne lidar.
- Maps of elevation change (erosion and deposition) across four valleys and three survey
  epochs: 2001 airborne lidar, 2014 airborne lidar, and 2021–23 satellite data.

**What does not exist.** The dissertation is descriptive. It shows *where* change happened.
It does not test *why* — which climate variables drive the change — and it does not
demonstrate that the detector works well on satellite data across all valleys. Both are
named in the dissertation as future work. This proposal is that future work.

---

## 2. Objectives

**O1 — Attribution.** Determine which climate drivers control each stream's rate of
geomorphic change. Candidate drivers: air temperature (summed as **positive degree-days**,
a running total of melting weather), incoming sunlight, meltwater discharge, glacier mass
balance, and summer soil-thaw depth.
*Hypothesis: cumulative melt energy predicts sediment movement better than water volume
alone.* This is testable and falsifiable — if discharge alone predicts just as well, the
hypothesis fails and that is a publishable answer too.

**O2 — Generalization to satellite data.** Measure exactly how satellite elevation data
disagree with airborne lidar over unchanged ground (the **domain shift**), correct for it,
and retrain the detector so it performs comparably on both. The stakes are practical: no
further airborne lidar campaigns are scheduled for the MDVs. If monitoring is to continue,
it must run on satellite data.

**O3 — Calibrated uncertainty.** Replace the single valley-wide noise estimate used today
with a per-pixel detection threshold that accounts for slope, aspect, and sensor. The test
of success is strict: on ground that did not change, a 95%-confidence threshold should be
exceeded by roughly 5% of pixels — no more, no less.

Together the three objectives turn a one-time survey into a continuing, self-checking
monitoring capability with an explanatory model behind it.

---

## 3. Planned approach

**O1 (Years 1–2).**
1. Compute each gauged stream's change rate: difference two elevation epochs
   (**DEM-of-Difference**), keep only changes larger than the detection floor, sum inside
   the stream's channel outline, normalize by channel area and by years elapsed.
2. Build each stream's driver history from the MDV-LTER station records (meteorology,
   21 stream gauges, 7 glacier mass-balance series, soil temperature) and from the ERA5
   and AMPS weather models where station coverage has gaps.
3. Fit two model families — hierarchical regression (interpretable) and random forest
   (flexible) — relating rate to drivers. Validate only on streams held out of fitting.
   Agreement between the two families is the sanity check.
4. Test the melt-energy hypothesis directly against the water-volume alternative.

**O2 (Year 2).**
1. Quantify satellite-vs-lidar elevation disagreement over stable ground, broken down by
   slope and aspect.
2. Apply the learned correction, retrain the detector with both sensors represented in
   its training data, and score accuracy on all four valleys, both sensors.

**O3 (Years 1–3, alongside).**
1. Model the measurement noise as a function of slope, aspect, and sensor instead of one
   global number.
2. Publish the result as a per-pixel threshold map and verify the 5%-on-stable-ground
   property on held-out terrain.

**Methods note.** All elevation differencing uses robust statistics (**NMAD**, an
outlier-resistant standard deviation) because elevation errors in this terrain are known
to be heavy-tailed; a naive standard deviation would be inflated by a handful of blunders.

---

## 4. What the project needs

**Data.** Everything required is free and public except one item.

| Need | Source | Availability |
|---|---|---|
| 2001 airborne lidar DEM (2 m) | NASA ATM via USGS ScienceBase | public, free |
| 2014 airborne lidar DEM (1 m) + point cloud | NCALM via OpenTopography | public, free |
| REMA satellite DEM (2 m, 2021–23) | Polar Geospatial Center / AWS | public, free |
| Stream discharge, 21 gauges (daily) | MCM-LTER via EDI | public, free |
| Meteorology, glacier mass balance, soil temperature | MCM-LTER via EDI | public, free |
| ERA5 reanalysis; AMPS Antarctic weather model | Copernicus CDS; NCAR GDEX | public, free |
| Stream channel outlines (labels) | MCM-LTER via EDI | public, free |
| Barlow's hand-digitized training tiles | dissertation author | **author-gated — must be requested** |

**Labels.** The detector needs training examples. The public LTER channel outlines are a
workable starting set. The gold-standard set — the dissertation author's hand-digitized
tiles — is not published and must be requested directly. If that request fails, a
comparable set will be re-digitized by hand. This costs weeks, not months, and is
budgeted in Year 1.

**Computing.** A single workstation GPU is sufficient for training the segmentation
models; the elevation processing is CPU-bound and modest. No supercomputer allocation is
required. Full-valley raster stacks run to tens of gigabytes and need local storage, not
specialized infrastructure.

**Skills and mentoring.** The FI has built terrain-segmentation and change-detection
pipelines on non-Antarctic data but is new to Antarctic hydrology and to hierarchical
statistical modeling. The plan includes graduate coursework in Bayesian/hierarchical
methods and mentorship from the advisor on polar geomorphology. This is a genuine gap,
stated as one; closing it is part of what a FINESST award is for.

**Community contact.** The dissertation author has been contacted and is responsive.
Continued cooperation is helpful but not load-bearing: every analysis in this plan can
proceed from public data alone.

---

## 5. Honest assessment

**What could go wrong, and what happens then.**

1. **The attribution signal may be weak.** With ~20 gauged streams and three epochs, the
   sample is small. If no driver clearly outperforms the others, the deliverable becomes
   a rigorous null result with calibrated uncertainty — less exciting, still useful, and
   still publishable. The risk is to impact, not to feasibility.
2. **Gauge records are patchy after 2015.** Stream gauging in the MDVs declined; some
   streams have only a few dozen recorded days in the satellite epoch. This is precisely
   why O1 leans on modeled melt energy (which is continuous everywhere) rather than
   gauges alone — but it means the discharge side of the hypothesis test is weakest in
   the most recent period, and the proposal accepts that.
3. **Satellite coverage is uneven.** REMA quality varies by location and date. Taylor
   Valley has the best three-epoch coverage and will anchor any acceleration claims;
   other valleys may support only two epochs. Conclusions will be scoped accordingly.
4. **The label request may be declined.** Mitigation is above (re-digitize). This adds
   Year-1 labor but does not block the science.
5. **The detector may not close the sensor gap (O2).** If accuracy on satellite data
   stays meaningfully below lidar after bias correction and retraining, that result is
   reported with the measured gap — a negative result here is a real contribution,
   because it tells the community what satellite-only monitoring can and cannot see.

**What this proposal does not claim.** No preliminary results are presented. The
dissertation being extended is the prior work; the FI's contribution begins at award.
The hypotheses may be wrong. The plan is designed so that every objective produces a
defensible, publishable answer whether its hypothesis survives or not.

**Why it is worth doing anyway.** The MDV streams are the most direct, physically
measurable climate response in the most stable landscape on Earth, and the data to study
them — two lidar epochs, a growing satellite record, and 30 years of LTER station
records — already exist and are free. The missing ingredients are the driver analysis,
the sensor bridge, and the error bars. Those are exactly the size of a three-year
graduate project.

---

## 6. Timeline and deliverables

| Period | Work | Deliverable |
|---|---|---|
| **Yr 1** | Rebuild the change-detection chain from public data; harmonize driver records per stream; secure or rebuild training labels; first attribution model (Taylor Valley) | Attribution manuscript drafted; labeled training set archived |
| **Yr 2** | Sensor domain-shift measurement + correction; detector retrained and scored across all four valleys and both sensors; attribution extended basin-wide | Generalization paper; AGU presentation |
| **Yr 3** | Per-pixel calibrated-uncertainty product; three-epoch acceleration analysis; synthesis | Synthesis paper; public data products with DOIs |

---

## 7. Data management and open science

All inputs are public and cited to source (NASA ATM, NCALM/OpenTopography, PGC REMA,
MCM-LTER/EDI, Copernicus ERA5, AMPS/GDEX). All derived products — change rasters,
per-stream rate tables, uncertainty layers, channel outlines, and processing code — will
be released open-access with DOIs (Zenodo / EDI). Heavy regenerable rasters stay out of
version control; scripts, tables, and figures are tracked. Products carry explicit
coordinate-system, method, and uncertainty metadata.

---

## References

[1] Barlow, M. C. (2026). *A Comprehensive Spatial Analysis of Stream Boundary and
Geomorphological Change Detection: McMurdo Dry Valleys, Antarctica.* PhD Dissertation,
University of Houston (chair: C. L. Glennie).

[2] Barlow, M. C., Zhu, X., & Glennie, C. L. (2022). Stream Boundary Detection of a
Hyper-Arid, Polar Region Using a U-Net Architecture: Taylor Valley, Antarctica.
*Remote Sensing* 14(1):234.

[3] Höhle, J., & Höhle, M. (2009). Accuracy assessment of digital elevation models by
means of robust statistical methods. *ISPRS J. Photogramm. Remote Sens.* 64(4):398–406.

[4] Howat, I. M., et al. (2019). The Reference Elevation Model of Antarctica (REMA).
*The Cryosphere* 13:665–674.

[5] Ronneberger, O., Fischer, P., & Brox, T. (2015). U-Net: Convolutional Networks for
Biomedical Image Segmentation. *MICCAI* 234–241.

[6] McMurdo Dry Valleys LTER. Stream, meteorology, glacier, and soil datasets.
Environmental Data Initiative (EDI), `knb-lter-mcm.*`.

[7] Hersbach, H., et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.*
146:1999–2049.

---

*Plan-only draft ("basic" variant): no preliminary results, no figures. Companion
variants with preliminary work: `finesst_proposal.md` (formal) and
`finesst_proposal_plain.md` (plain language). Not a submitted proposal.*

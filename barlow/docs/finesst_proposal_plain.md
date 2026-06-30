# From Detection to Attribution: Tracking (and Explaining) Stream Change in Antarctica from Terrain Alone

**NASA ROSES-2025 F.5 — Future Investigators in NASA Earth and Space Science and Technology (FINESST)**
**Division:** Earth Science (EARTH25) — Antarctic cryosphere / climate
**Deadline:** 14 July 2026 (11:59 PM EDT)
**Who's who:** Grad student = Future Investigator (FI), main author and brains of the project; advisor = PI on paper. Up to ~$50k/yr for up to 3 years.

> **The pitch in one breath.** There's already a tool that *finds* where Antarctic streams are
> reshaping the land. It stops there — it tells you *where*, never *why*. This project picks up
> exactly at that line: I'll connect the change to the things driving it (heat, melt, thawing
> ground), make the detector work across different sensors and valleys, and put a real
> uncertainty number on every pixel. I've already rebuilt and checked the existing tool myself and
> seen the first hint of the "why" signal — so this isn't a someday idea, it's a next-step I'm
> ready to run.

---

## 1. The setup (and the gap I'm filling)

The **McMurdo Dry Valleys (MDVs)** are the biggest ice-free patch of Antarctica — a cold rocky
desert that looks like Mars. For about a century everyone treated it as the most *boring*
landscape on Earth, geologically: nothing moves. That's changing. The system runs right at the
edge of freezing, so it doesn't take much extra heat to start melting ice and thawing the frozen
ground (permafrost). When that happens you get **ephemeral streams** — little rivers that switch
on for a few weeks each summer, shove sediment around, then vanish till next year.

Those streams are basically a **climate canary**: the most sensitive thing you can measure in the
most stable place on Earth. If they're speeding up, that's an early warning sign.

**Barlow (2026)** [1] built the tool that measures them, and it stands on three pieces worth
knowing by name:

1. **Terrain-only segmentation.** A **U-Net** (a standard image-segmentation neural net) traces
   stream channels using *only the shape of the ground* — elevation, slope, aspect. No looking
   for blue water, because these channels are dry 11 months a year.
2. **Trusting the free satellite data.** Airborne lidar is gold-standard but only exists for 2001
   and 2014. To go past 2014 you need **REMA** (free satellite elevation maps). She proved REMA is
   accurate enough using **ICP** (lines two 3D datasets up) plus **NMAD** (a median-based spread
   measure that ignores outliers — way more honest than standard deviation here).
3. **Measuring change.** Subtract an old elevation map from a new one inside the stream channels —
   that's a **DEM-of-Difference (DoD)**. Only count changes bigger than the noise floor
   (**LOD95 = 1.96 × NMAD**). Add it up per stream → erosion/deposition rates, even acceleration.

**Here's the gap.** Barlow's work ends at *describing* — it shows **where** stuff is happening
(Denton Hills erodes the hardest; parts of Taylor Valley are speeding up) but flat-out says two
things are left for later: **(a)** connect the change to its physical/climate **drivers**, and
**(b)** make the model work **beyond just the MDVs**. That "left for later" is exactly where a
Future Investigator project belongs — turning a *thing that watches* into a *thing that explains
and predicts* (Fig. 1).

![Fig 1](finesst_figures/fig5_workflow.png)
***Figure 1.*** *Left half (detect): Barlow's pipeline, which I've already rebuilt and checked.
Right half (explain + predict): the new work I'm proposing.*

---

## 2. What I'll actually do (objectives + the bets I'm making)

| # | Objective | The bet (hypothesis) | Why it's new |
|---|---|---|---|
| **O1** | **Attribution — the headline.** Line up each stream's change rate against the drivers: temperature, sunlight, **positive-degree-days (PDD)** (basically a running total of "how much above-freezing heat happened"), melt-season flow, glacier melt, and how deep the ground thaws (active layer). Pull these from the LTER field network + ERA5/AMPS weather reanalysis. | **H1:** What controls the change is **total melt energy**, not just how much water ran. A heat-based model beats a flow-only model and explains the leftover scatter in Fig. 5. | Barlow literally lists this as future work; nobody's quantified it. |
| **O2** | **Make it generalize.** Get the terrain-only detector working across *both* lidar (2001/2014) and REMA satellite data, and across all four valleys. The tricky part is the **domain shift** — lidar and satellite "see" the ground slightly differently, and that gap hurts the satellite years. | **H2:** A sensor-aware correction (adjust for slope/aspect, per pixel) closes most of that lidar-vs-REMA gap. | Barlow flags sensor generalization as future work. |
| **O3** | **Honest uncertainty.** Right now there's one noise number for a whole map. I'll make it **per-pixel and sensor-aware**, so every change map ships with a real confidence value. | **H3:** If you let the noise number depend on slope, aspect, and sensor, the "95% confident" line actually holds up 95% of the time. | Barlow uses a single global number per epoch pair. |

**The payoff that ties it together:** a model that takes a driver map and predicts **where the
acceleration moves next** — the actually-useful version of the climate-canary idea.

---

## 3. How I'll do it

**Data (all free/public, and I already pulled it — see §6).** Elevation: MDV lidar 2001
(2 m) + 2014 (1 m), and REMA satellite (2 m, 2021–23). From each I build the usual terrain
layers — elevation, slope, aspect, **profile curvature** (signed, so it tells concave channel from
convex ridge), **MFD flow accumulation** (where water would pool), and lidar intensity. Drivers:
LTER weather, **21 stream gauges**, glacier melt for 7 glaciers, and continuous soil
temperature/moisture (my stand-in for how deep the ground thaws); plus ERA5 + AMPS weather to fill
spatial gaps. Labels: LTER stream centerlines (public stand-in for Barlow's private hand-drawn
training tiles — that's the one catch, covered in §7).

**O1 — attribution.** For every gauged stream and time period I'll: **(i)** get the change rate
from the DoD inside the channel (already working — Fig. 2); **(ii)** build a per-stream **energy
time series** (PDD, sunlight, flow, thaw depth); **(iii)** fit models (hierarchical regression /
random forest) of rate-vs-drivers, leaving one stream out at a time to check they actually predict;
**(iv)** test H1 head-to-head: heat-based model vs. flow-only. Fig. 5 is the teaser — the flow
relationship is real but messy, which is the whole reason to bring in melt energy. For the streams
with three time points, I'll regress *acceleration* against *driver trends*.

**O2 — generalize.** Measure the lidar-vs-REMA difference over ground that *didn't* change, see
how it depends on slope/aspect, learn a correction, retrain the U-Net with both sensors mixed in,
then score it (F1) across all four valleys and both sensors. My WellSight work (§5) already shows
this same architecture surviving a totally different landscape, so this isn't a leap of faith.

**O3 — uncertainty.** Swap the one-number noise estimate for one that depends on (slope, aspect,
sensor), output it as a per-pixel map, and check it's honest by confirming the "95% line" is
actually crossed ~5% of the time on stable ground. Fig. 4 is the global version of this idea.

**Reproducibility.** The whole thing is scripted end-to-end — re-run from raw data and you get the
same outputs. (Sanity check that paid off: an early bug had bad nodata values blowing the noise up
to 2.7 m; QC caught it and I fixed it before trusting any number.)

---

## 4. Proof I can pull this off (preliminary work)

This is the part that makes the proposal real instead of hopeful: **I already rebuilt Barlow's
change-detection pipeline myself and got numbers that land inside her published ranges**, then took
one exploratory step into the new O1 science. To be clear — this is feasibility work I did to show
I'm ready, *not* the funded project itself.

**(a) Change detection, all three time periods (Fig. 2).**

![Fig 2](finesst_figures/fig1_dod_maps.png)
***Figure 2.*** *DoD maps for Taylor Valley stream corridors, showing only changes bigger than the
noise floor. Left: 2001→2014 (lidar vs lidar). Right: 2014→2021-23 (lidar vs REMA satellite).
Red = erosion, blue = deposition. Real patterns pop out above the noise.*

| Time period | NMAD (noise) | LOD95 (detection floor) | Barlow's range | Match? |
|---|---|---|---|---|
| 2001→2014 (lidar–lidar) | 0.21 m | 0.41 m | NMAD 0.07–0.46 / LOD95 0.15–0.92 | ✅ |
| 2014→2021-23 (lidar–REMA) | 0.23 m | 0.44 m | NMAD 0.19–0.53 / LOD95 0.37–1.04 | ✅ |

**ICP** (the alignment step) behaved exactly like it should: it helped on hilly windows and
correctly did nothing on the flat valley floor where there's no 3D shape to grab onto.

**(b) Per-stream rates (Fig. 3) — the exact input O1 needs.**

![Fig 3](finesst_figures/fig2_per_stream_rates.png)
***Figure 3.*** *Per-stream rates for six gauged Taylor Valley streams. "Gross" = total hustle
(erosion + deposition); "Net" = which way it leans (+ building up / − wearing down).*

**(c) The noise is Laplacian, not Gaussian (Fig. 4) — basis for O3.**

![Fig 4](finesst_figures/fig3_error_model.png)
***Figure 4.*** *The leftover differences on stable ground are sharply peaked with fat tails —
that's a **Laplacian**, not the bell curve everyone defaults to. If you assumed a bell curve (use
σ), the outliers would fake-inflate your noise. This is why NMAD is the right call, and it's the
jumping-off point for the per-pixel uncertainty layer in O3.*

**(d) First whiff of the attribution signal (Fig. 5) — evidence O1 works.**

![Fig 5](finesst_figures/fig4_attribution.png)
***Figure 5.*** *Each stream's "hustle" (gross rate) vs. how much melt water ran through it. In the
lidar period the link is strong and positive (**r = +0.89** — busier streams move more dirt, makes
sense). In the satellite period it's noisier (r = +0.43; fewer gauge records after 2014 and a
larger satellite noise floor). That's the point of O1: raw flow gets you the first-order story but
leaves real scatter, so I'll bring in **melt energy** (PDD / sunlight / thaw) to nail the "why."*

**Bottom line on feasibility:** the scary question for any FINESST proposal — *can this person
actually run the whole pipeline?* — is already answered. The new science (O1–O3) sits on top of a
foundation I've test-driven.

---

## 5. Why I'm the right person (track record)

I already run an end-to-end pipeline called **WellSight** that uses the *exact same machinery* —
U-Net segmentation on terrain layers, ICP alignment, DoD change detection — on a completely
different landscape: spotting channels, roads, and old well-pad scars in the Appalachian Plateau
from elevation alone. So I've already proven this approach travels across sensors and biomes
(that's literally O2's risk, pre-retired), and that I can drive the full toolchain. The Antarctic
preliminary work in §4 is me pointing that same toolchain at this project's target.

---

## 6. Data — what I need and whether I have it

Everything the project needs is **free/public**, and I've already downloaded the whole stack
(scripted, so it regenerates from source). Translation: data availability won't blow up the
schedule. The only gated thing is Barlow's training labels (handled in §7).

| Category | Where it's from | Got it? |
|---|---|---|
| **A. Terrain** — MDV lidar 2001 + 2014; REMA 2021-23 | free/public | ✅ in hand |
| Per-period terrain layers (slope/aspect/curvature/flow/intensity) | scripted from terrain | ✅ shown on Taylor pilot |
| **B. Labels** — LTER stream centerlines (for QC) | EDI `knb-lter-mcm.6007` | ✅ in hand |
| Barlow's hand-drawn training tiles | author-gated | ⚠️ **the one catch** (see §7) |
| **C. Drivers** — LTER weather, 21 gauges, glacier melt, soil/thaw | EDI | ✅ in hand |
| Weather reanalysis — ERA5, AMPS | CDS; GDEX | ✅ in hand |
| **D. Cross-valley** — all four valleys, lidar + REMA | OpenTopography/PGC | ✅ DEMs in hand; per-valley layers to build |
| **E. Validation** — high-res imagery; published rates | PGC (restricted); papers | optional / cross-check |

---

## 7. Plan, timeline, risks, and data sharing

**My role & growth.** I'm the lead and main author; my advisor mentors and is PI on record. Along
the way I'll present at AGU and a SCAR/ISAES Antarctic venue, push the O1 attribution result out as
its own paper, and take coursework in Bayesian/hierarchical modeling and remote-sensing uncertainty.

**Timeline (3 years).**

| Year | What ships |
|---|---|
| **Yr 1** | Build the driver time series per stream; first O1 attribution model on Taylor Valley (extends Fig. 5); prototype the per-pixel uncertainty (O3). **Deliverable:** attribution paper drafted. |
| **Yr 2** | Fix the lidar↔REMA domain shift and generalize the detector to all four valleys (O2); run attribution basin-wide; AGU talk. **Deliverable:** O2 paper. |
| **Yr 3** | Predict where acceleration migrates next; full three-period acceleration attribution; release the uncertainty product (O3). **Deliverable:** synthesis/prediction paper + public datasets. |

**Risks & how I dodge them.** **(1)** *Barlow's training labels are gated* → I'll ask her group;
if that stalls, the LTER centerlines already work as a stand-in (Figs. 2–3 were built on them), and
WellSight proves I can build labels from scratch. **(2)** *REMA coverage after 2014 is patchy* →
prioritize Taylor Valley (it has all three periods) for the acceleration work; treat other valleys
as two-period. **(3)** *Gauge records have gaps* → that's a big reason O1 leans on melt *energy*
from reanalysis, not just raw gauge flow.

**Data sharing.** All inputs are free/public and cited. My outputs — change maps, per-stream rate
tables, uncertainty layers, stream-boundary polygons — go out open-access (DOIs via Zenodo/EDI)
with the code. Heavy regenerable rasters stay out of version control; scripts, figures, and tables
are tracked. Everything carries explicit coordinate-system, method, and uncertainty metadata, in
line with NASA's open-science push.

---

## References

[1] Barlow, M. C. (2026). *A Comprehensive Spatial Analysis of Stream Boundary and Geomorphological
Change Detection: McMurdo Dry Valleys, Antarctica.* PhD Dissertation, Univ. of Houston (chair:
C. L. Glennie). 240 pp.

[2] Barlow, M. C., Zhu, X., & Glennie, C. L. (2022). Stream Boundary Detection of a Hyper-Arid,
Polar Region Using a U-Net Architecture: Taylor Valley, Antarctica. *Remote Sensing* 14(1):234.
doi:10.3390/rs14010234. *(Dissertation Ch. 4 — the proof of concept.)*

[3] Höhle, J., & Höhle, M. (2009). Accuracy assessment of DEMs by means of robust statistical
methods. *ISPRS J. Photogramm. Remote Sens.* 64(4):398–406. *(Where NMAD comes from.)*

[4] Howat, I. M., et al. (2019). The Reference Elevation Model of Antarctica (REMA). *The
Cryosphere* 13:665–674.

[5] Ronneberger, O., Fischer, P., & Brox, T. (2015). U-Net: Convolutional Networks for Biomedical
Image Segmentation. *MICCAI* 234–241.

[6] McMurdo Dry Valleys LTER datasets (stream discharge, weather, glacier mass balance, soil),
Environmental Data Initiative, `knb-lter-mcm.*`.

[7] Hersbach, H., et al. (2020). The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.*
146:1999–2049.

---

*Plain-language version of `finesst_proposal.md` — same science, same real numbers, friendlier
voice. The §4 results are preliminary feasibility work by the FI, not funded-project deliverables.
Figures from `barlow/build/_finesst_figures.py`. Not a submitted proposal.*

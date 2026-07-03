# Barlow 2026 — Dissertation Summary

*Barlow, M. C. (2026). "A Comprehensive Spatial Analysis of Stream Boundary and
Geomorphological Change Detection: McMurdo Dry Valleys, Antarctica." PhD dissertation,
Dept. of Civil and Environmental Engineering, University of Houston (chair: Dr. Craig
L. Glennie). 240 pages.*

## The whole thing in one paragraph

The McMurdo Dry Valleys (MDVs) are an ice-free polar desert in Antarctica, long
considered the most stable landscape on Earth. Each summer, glacier melt briefly feeds
*ephemeral streams* — temporary rivers that flow for a few weeks, move sediment, and
vanish. Barlow trained a neural network to outline those stream channels using only the
shape of the ground (no water is visible most of the year), proved that free satellite
elevation data is accurate enough to detect the small changes involved, and then
subtracted elevation maps from 2001, 2014, and 2021–23 to measure two decades of
landscape change across four valleys. The result is the first valley-wide, automated
climate-change monitor for the region — and the finding that the "most stable place on
Earth" is measurably changing, and in places speeding up.

## Why it matters

The MDV system is *energy-limited*: there is plenty of ice but barely enough heat to
melt it. A small warming shift therefore produces an outsized, measurable response —
which makes these streams one of the most sensitive climate indicators on the continent.
Before this work, streams were studied one at a time with ground surveys: slow, not
scalable to the 100+ streams in the region, and blind to the regional picture.

## The three elevation snapshots

| Epoch | Source | Resolution | Role |
|---|---|---|---|
| 2001 | NASA ATM airborne lidar | 2 m | Oldest baseline |
| 2014 | NCALM airborne lidar | 1 m | Accuracy benchmark |
| 2021–23 | REMA satellite (stereo photos) | 2 m | Free, keeps updating — the future of the record |

## What each chapter establishes

**Chapter 4 — Detection proof of concept (Taylor Valley).**
A U-Net (an image-segmentation neural network) learns to outline stream channels from
terrain rasters alone — elevation, slope, lidar intensity, and flow accumulation.
Training data: 217 hand-labeled 300 × 300 m tiles, about 1% of the valley. Surprise
result: single input features beat combinations — elevation alone and slope alone each
reach F1 ≈ 0.94 (F1 balances "found everything" against "didn't cry wolf"), while
stacked combinations score lower. Once trained, the model maps the entire valley in
about 15 minutes. Published as Barlow, Zhu & Glennie 2022, *Remote Sensing*.

**Chapter 5 — Is the satellite ruler trustworthy?**
Lidar flights are rare, one-off events; REMA satellite elevation is free and recurring,
but noisier. After aligning REMA to lidar with point-to-plane ICP (sliding one 3-D
surface over the other until they fit), the leftover errors on stable ground turn out to
be *Laplacian* — sharply peaked with heavy outlier tails — rather than the bell curve
statisticians usually assume. So she measures noise with NMAD, an outlier-proof version
of the standard deviation. Verdict: REMA is accurate to the sub-meter level and good
enough for stream-corridor change detection, provided steep slopes and problem aspects
are masked and NMAD-based uncertainty is used.

**Chapter 6 — Scale up.**
The detector is retrained to work across all four valley systems (Taylor, Wright,
Victoria/Barwick, Denton Hills) and all three epochs, with aspect and curvature added as
inputs. Across valleys and sensors, elevation, slope, and aspect are the three most
informative features. Deliverable: the first multi-valley, multi-epoch stream-boundary
*polygon* dataset for the MDVs (previous best was centerlines only).

**Chapter 7 — Two decades of change.**
Inside the detected channel outlines, newer DEM minus older DEM gives a DEM of
Difference: positive = sediment deposited, negative = eroded. Only changes larger than
the level of detection (LOD95 = 1.96 × NMAD — the smallest change distinguishable from
noise at 95% confidence) are counted. Detectable change: roughly 15–92 cm between the
lidar epochs, 37–104 cm when satellite data is involved. Volumes become per-stream,
per-year rates, normalized by channel area so big and small streams compare fairly.

**Chapter 8 — Synthesis, limitations, future work.**

## Headline findings

- **Denton Hills is the erosion hotspot** — the strongest per-area erosion in the MDVs.
  Its Ward Stream alone moved ~78,700 m³ of sediment per year, almost all of it erosion.
- **Taylor Valley has a split personality**: inland reaches erode; coastal reaches
  deposit, as streams lose energy spreading out near the lakes and coast.
- **Wright Valley** is broadly balanced to mildly depositional; **Victoria/Barwick**
  mostly depositional.
- **Acceleration is real but localized.** For Taylor Valley streams with all three
  epochs, the rate of change itself can be computed over time — and some streams are
  clearly speeding up. This is the early-warning "canary" signal the climate community
  has been looking for.

## Contributions, in her own framing

1. First terrain-only (no water signal needed) neural-network stream-boundary detector —
   it works on channels that are dry 11 months a year.
2. First multi-valley, multi-epoch stream-polygon dataset for the MDVs.
3. Validation of REMA satellite DEMs for fine-scale change detection, including the
   Laplacian error model and NMAD-based uncertainty framework.
4. First valley-wide quantification of fluvial geomorphic change in the MDVs across two
   decades, with per-stream rates and acceleration estimates.

## Limitations she states honestly

Detection struggles where banks blend into bedrock; REMA coverage after 2014 is uneven,
so the three-epoch acceleration analysis is possible only where coverage overlaps (mainly
Taylor Valley); training labels are hand-drawn, so the model inherits the labeler's
judgment; small unknown streams may be missed entirely.

## Future work she proposes (and where the FINESST proposal picks up)

Keep the monitor running as new REMA epochs arrive; correlate the measured change with
climate drivers — temperature, solar radiation, energy balance — to predict where rapid
change happens next; and generalize the detector beyond the MDVs (other polar regions,
arid ephemeral channels, planetary terrain). The first two are exactly the attribution
and generalization objectives of the FINESST expansion (`finesst_proposal.md`).

# AGU 2026 abstract — WellSight

Drafted 2026-07-23. 1,942 characters / 281 words (AGU limit 2,000 characters).

---

Pennsylvania carries a 150-year legacy of oil and gas extraction. Hundreds of thousands of abandoned wells remain across the state, and many are absent from official records. These orphaned wells leak methane and brine into forests and streams. Locating them across steep, canopy-covered terrain by field survey is slow and expensive. We present a LiDAR-based framework to detect the surface expressions of orphaned wells in western Pennsylvania. Airborne LiDAR resolves the ground beneath dense deciduous canopy, exposing features that aerial imagery cannot. We process QL1 and QL2 point clouds into bare-earth terrain models at 0.5 to 1 m resolution. From each model we derive a stack of terrain channels, including local relief models, topographic openness, slope residuals, and Red Relief Image Maps. These channels enhance the shallow, linear, and circular signatures that mark well sites. Orphaned wells leave three recurring signs: graded pads, remnant access roads, and casing depressions. We train a U-Net to trace access roads from the terrain stack. A topology-preserving clDice loss keeps the traced network connected across canopy gaps that pixel-wise losses fragment. We validate detections against the Pennsylvania DEP well inventory, reporting confidence, method, and distance to the nearest known well. Known coordinates tune the terrain thresholds and quantify false positives before we extend the search to undocumented sites. We also test whether directional metrics, such as the slope local length of autocorrelation and Hessian ridge filters, separate engineered linear features from natural breaks in slope. Early passes reproduce mapped road networks with high spatial fidelity and flag candidate wells missing from state records. This work defines a reproducible, ground-truth-validated pipeline for orphaned-well discovery. The same terrain-signature approach transfers to other legacy basins, including the Permian.

---

## Before submission — one claim needs the author's sign-off

> "Early passes reproduce mapped road networks with high spatial fidelity and
> **flag candidate wells missing from state records**."

The first half is supported: the deployed road trace on 613590 covers ~231 km and
recovers ~86% of the public TIGER road network within 20 m
(`roads_studio/exports/faithful_613590_deployed_t030.gpkg`).

The second half is **not yet demonstrated**. No validated list of candidate wells
absent from the DEP inventory has been produced. Either produce that list before
submitting, or soften the clause to describe intent rather than result.

## Claims and their backing

| claim | status |
|---|---|
| QL1 + QL2 point clouds, 0.5–1 m bare earth | done (9t, 613590, McKean) |
| LRM / openness / slope-residual / RRIM channel stack | done — [[linear_feature_channels]] |
| U-Net road tracing with clDice topology loss | done — `road_sweep_202607`, Shit et al. 2021 |
| SLLAC + Hessian ridge filters tested | built and visually QC'd — [[linear_feature_channels]] |
| validation vs PA DEP inventory | partially — 540 known wells in 9t used for QC |
| candidate wells missing from records | **not yet** — see above |
| transfer to the Permian | grids built, pad U-Net inference tested |

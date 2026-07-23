# Linear-feature channels for road/trail detection (2026-07-23)

## Goal
Add terrain channels that specifically enhance elongated anthropogenic earthworks
(roads, skid trails, well-access benches), driven by a literature review and a
bench-detection diagnosis from the user's Claude agent. Motivation: the road U-Net
plateaued and the LRM/slope channels are weak on treads.

## Inputs / provenance
- Base stack: `data/derivatives/tiles/613590_05/` (0.5 m, EPSG:6346), **rebuilt
  2026-07-23** with tile `616590` added, fixing the SE-corner data hole
  (DEM nodata 5.56% → 0.00%). Source: USGS_LPC_PA_WesternPA_2019_D20 tiles (QL2).
- Road reference for overlays: `cldice/road_prob_613590_1m.tif`.
- Method sources: see `literature/CITATIONS.md` (Frangi 1998, Sato 1998, Steger 1998,
  Sofia 2014 SLLAC, Chiba 2008, Savitzky-Golay 1964, Wood 1996, Soille 2004, Ferraz
  2016, Batra 2019).

## What was built
Script: `notebooks/wellsight_v2/build/_build_extra_channels.py` (reads an existing
tile dir, writes `<stem>_<sfx>.tif`). Channels:

| channel | method | source |
|---|---|---|
| `slope_residual_{12,24}m` | slope − focal-mean(slope) | Ferraz 2016 |
| `diff_openness` | openness_pos − openness_neg | Chiba 2008 |
| `rough_aniso`, `rough_orient` | structure-tensor coherence + orientation | — |
| `profile_curv`, `curv_doublet` | WBT curvature + cut/fill doublet | Wood 1996 |
| `sllac_len`, `sllac_aniso` | slope local autocorrelation length (4-dir approx) | Sofia 2014 |
| `frangi_lrm`, `frangi_slresid` | multiscale Frangi vesselness | Frangi 1998 |
| `ridge_sato`, `ridge_orient` | Sato tubeness + Hessian orientation field | Sato/Steger 1998 |
| `savgol_resid_37px`, `savgol_resid_msmax` | 2D SavGol quadratic residual (detrends slope+curvature) | Savitzky-Golay 1964, Wood 1996 |
| `tophat_white`, `tophat_black` | white/black top-hat of the SavGol residual (fill lip / cut) | Soille 2004 |

Params: res 0.5 m; SavGol window 6× tread (37 px) primary, 4/6/8× multiscale;
top-hat disk SE r≈0.7× tread; Frangi/Sato sigmas 1–4; SLLAC 4 dirs, max-lag 10 m.

## Results (visual QC on a 500 m road crop)
- **SavGol quadratic residual is the clear winner.** At a matched 18.5 m window, the
  plain mean residual is swamped by hillslope curvature (large convex/concave blobs);
  the quadratic residual removes them and roads become the dominant coherent feature.
  The `mean − quad` difference isolates exactly the smooth `(σ²/2)∇²z` curvature field.
  Fig: `data/derivatives/tiles/613590_05/_savgol_vs_lrm_quicklook_613590_05.png`.
- **`frangi_lrm`** and **`rough_aniso`** also clearly light up on roads (high SNR).
- **`ridge_sato`** strong but shows a cross-hatch artifact (scan-pattern / grid weave)
  at small scale — raise min sigma.
- **`tophat_black`** (cut) traces roads cleanly; `tophat_white` noisier.
- Weak here: `sllac_len` (noisy 4-dir approx), `curv_doublet` (sparse by design).
- All channels 0% NaN on the rebuilt DEM; 14 corner-edge outlier pixels (0.0000%),
  cosmetic only. Overview: `data/derivatives/tiles/613590_05/_extra_channels_quicklook_613590_05.png`.

## Interpretation
The LRM unsharp mask (`DEM − focal_mean`) is curvature-contaminated and that is the
real reason it underperforms on treads — not slope. Replacing/augmenting it with a
quadratic (SavGol) residual is the highest-value channel change. The genuinely new
lever beyond enhancers is `ridge_orient` (orientation field) for gap-linking
(Ferraz 2016, Batra 2019). Not yet shown: whether any channel recovers roads the
model *misses* (the recall question) — next step.

## Reproduce
```
# rebuild base (fills SE hole)
python notebooks/wellsight_v2/build/_build_derivatives.py \
  --tiles <19 D20 tiles incl 616590> --bbox 613500,4590000,618000,4594500 \
  --suffix 613590_05 --res 0.5 --crs EPSG:6346 --overwrite --dem-method delaunay
# all extra channels
python notebooks/wellsight_v2/build/_build_extra_channels.py \
  --dir data/derivatives/tiles/613590_05 --sfx 613590_05 --res 0.5
# just the SavGol + top-hat additions
python notebooks/wellsight_v2/build/_build_extra_channels.py \
  --dir data/derivatives/tiles/613590_05 --sfx 613590_05 --res 0.5 --only savgol,tophat
```

## Deferred
Robust IRLS fit, slope-normal frame (matters for >30° Appalachian slopes), 1D
transect detector, feeding winners into the road U-Net, Sato artifact fix.
See `BACKLOG.md` → "Linear-feature channel refinements".

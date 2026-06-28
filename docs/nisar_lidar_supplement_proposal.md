# Proposal: NISAR L-band SAR as a Supplement to LiDAR (WellSight)

**Date:** 2026-06-27
**Author:** WellSight analysis agent
**Status:** proposal — grounded in a hands-on reconnaissance of real granules over the 9t core
**Region of reference:** 9t core, NW Pennsylvania (41.50 N, −79.54 W; EPSG:6346)

---

## 1. Executive summary

NISAR (NASA-ISRO SAR, L-band, launched 2025) gives us something LiDAR never will: a
**repeating (12-day), all-weather, day/night** look at the same ground, with a signal
that penetrates canopy and responds to **soil moisture, surface roughness, vegetation
structure, and (where coherent) millimetre-scale ground motion.**

It does **not** compete with LiDAR for *detection*. NISAR's usable products over our area
are **10 m (backscatter)** and **80 m (InSAR)** — 10–80× coarser than our 1 m / 0.5 m
LiDAR derivatives. A road is sub-pixel; a pit is invisible; a well pad (~50–100 m) is only
5–10 pixels. So the value is as **context, covariates, and a time axis**, feeding the
existing LiDAR detectors and the FINESST "geomorphic change vs. drivers" line of work —
**not** as a new standalone detector.

I downloaded and inspected two real NISAR granules over 9t before writing this. The
findings below are measured, not assumed.

---

## 2. What I actually verified (reconnaissance, 2 granules over 9t)

| Product | Resolution | State over 9t | Verdict |
|---|---|---|---|
| **GCOV** (geocoded polarimetric backscatter, HH+HV, RTC gamma-0) | **10 m**, EPSG:32617 | 100% valid; HH mean −8.2 dB, HV −16.3 dB, HH−HV 8.1 dB — physically sound forest signature with bright infrastructure spikes (+7 dB) | **Usable now** |
| **GUNW** (geocoded unwrapped interferogram + coherence) | **80 m** | Valid-pixel coherence **mean 0.16, median 0.13, 9% > 0.3, 1.5% > 0.5** → too low to unwrap reliably *in this pair* | **Inconclusive — this beta pair decorrelated; not yet a fair test** |

Clipped GeoTIFFs (QGIS-ready, UTM 17N) written to `data/external/nisar/9t/clip_9t/`:
`gcov_HH_db`, `gcov_HV_db`, `gcov_HHminusHV_db`, `gunw_coherence`, `gunw_los_disp_mm`.

**The InSAR result needs care — do not over-read it.** Backscatter and interferometric
coherence are *different* properties: L-band's vegetation strength (canopy penetration,
volume scattering) is in **backscatter**, which our GCOV recon confirmed works well.
**Coherence** measures phase stability between two passes, and the one pair we checked
(2026-01-08 → 2026-01-20) came back at 0.16. But that pair is **not a clean test**:

- It is **BETA pre-calibration** data — NISAR's interferometric processing is explicitly
  not validated yet; beta coherence/phase is known to be unreliable.
- It is a **mid-winter pair** in NW PA: snow cover + freeze/thaw + wet-snow change between
  passes is a *strong* L-band decorrelator (often worse than summer canopy).
- Geometry is **not** the culprit — the perpendicular baseline is only **−34.9 m**
  (negligible geometric decorrelation), so this is temporal/volume + processing, not orbit.

So the correct conclusion is **"InSAR over forested PA is unproven, not impossible."**
L-band is the *best-case* wavelength for forest InSAR, and a validated, snow-free,
short-baseline pair (or a longer multi-pass time series) may well reach usable coherence.
It is also likely **easier over the Permian desert** (sparse vegetation). Verdict: retest
before relying on — or writing off — InSAR for either region.

---

## 3. Why supplement LiDAR with NISAR at all?

LiDAR is a **one-time 3-D snapshot**: exquisite geometry, zero time dimension, flown once
(2019 for WPA D20). Its blind spots are exactly NISAR's strengths:

| LiDAR limitation | NISAR contribution |
|---|---|
| Single epoch — can't see change since 2019 | 12-day repeat → new clearings, activity, disturbance over time |
| Geometry only — no material/moisture info | Backscatter responds to soil moisture, roughness, dielectric (disturbed/compacted pad soils) |
| Canopy blocks optical context | L-band penetrates canopy; HV cross-pol senses volume/structure beneath |
| No driver data for change modelling | Soil-moisture (SME2) + backscatter time series = physical/climate covariates (FINESST) |

---

## 4. Proposed use cases (ranked by evidence + payoff)

### 4.1 GCOV backscatter as a LiDAR covariate (PA) — **recommended first**
Resample the 10 m HH, HV, and HH−HV layers onto the LiDAR grid and add them as extra
channels alongside the terrain derivatives (lrm, tpi, openness, slope). Rationale: a
cleared/compacted well pad has a different dielectric and roughness signature than
surrounding forest; HV drops over bare/cleared ground vs. forest volume scattering. This
is a low-risk add — it slots into the existing multi-channel U-Net input with no new
architecture. Expect modest help on **pads/clearings**, little on roads/pits (too small).

### 4.2 Temporal change detection to *task* LiDAR (PA) — **high payoff**
Stack the GCOV time series (12 granules over 9t, Oct 2025 → Jan 2026; growing). A
backscatter step-change flags **new disturbance** (clearing, re-entry, equipment) since
the 2019 LiDAR. Use it as a **landscape-scale trigger**: NISAR says "something changed in
this 100 m cell," then the high-res LiDAR/optical workflow zooms in. NISAR becomes the
wide-area tripwire; LiDAR the magnifier.

### 4.3 InSAR subsidence — **unproven over PA, test both regions**
The one beta winter pair over 9t decorrelated (coherence 0.16), but that is not a fair
test (beta processing + snow; baseline was fine at −35 m). Before any verdict: (a) retest
PA with a **validated, snow-free, leaf-off** pair and/or a multi-pass coherence stack, and
(b) test a **Permian** GUNW pair, where sparse desert vegetation should hold coherence
better. If coherence clears ~0.4 in either, GUNW time-series subsidence becomes viable —
directly relevant to **plugged/orphaned wellbore integrity and sinkhole risk**. Cheap to
check; don't write it off on one beta winter scene.

### 4.4 FINESST driver layers (both regions) — **strategic**
For the Barlow/MDV "couple geomorphic change to physical & climate drivers" thread, NISAR
**SME2 soil moisture** + backscatter are exactly the physical-driver covariates needed to
pair with LiDAR-derived geomorphology and DEM-of-difference change. This is the cleanest
fit to the dissertation framing.

---

## 5. Reality checks & logistics

- **Resolution:** GCOV 10 m, GUNW 80 m vs. LiDAR 1 m/0.5 m. NISAR = context/covariate/time,
  never a fine detector. Frame this explicitly so results aren't over-claimed.
- **Data volume:** ~6.6 GB per GCOV granule, ~2.5 GB per GUNW — **full ~250 km frames**;
  the 9t AOI is ~0.1% of a frame. Always **subset on ingest** (we already clip to the 9t
  window → ~tens of MB). Pulling whole frames is wasteful and will exhaust disk (we hit
  this).
- **Auth:** free Earthdata Login via `~/_netrc`; fetch via `_fetch_nisar_9t.py`.
- **Maturity:** everything over 9t today is **BETA / pre-calibration** — fine for
  feasibility, *not* for quantitative claims. **Validated CONUS products begin ~July 2026**;
  re-pull then for any real analysis.
- **CRS:** NISAR is WGS84 UTM (EPSG:32617); LiDAR is NAD83(2011) UTM (6346). ~1–1.5 m
  datum offset — negligible at 10 m, but reproject on fusion.

---

## 6. Recommended pilot (small, decisive)

1. **Coherence test, Permian:** pull one Permian GUNW granule, measure coherence. If
   > 0.4, InSAR subsidence is a real Permian product; if not, drop InSAR entirely. *(1 day)*
2. **GCOV covariate test, 9t:** resample HH/HV/HH−HV to the 9t LiDAR grid, add as channels
   to the pad/plat U-Net, retrain, compare pad recall/precision vs. the LiDAR-only baseline.
   *(2–3 days)*
3. **Change tripwire, 9t:** build the 12-date GCOV stack, compute per-pixel temporal
   std/step, overlay on the LiDAR hillshade, and check whether known recent disturbances
   light up. *(2 days)*
4. Decide go/no-go on each thread from measured deltas, then re-pull **validated** data in
   July 2026 for anything that earns its place.

---

## 7. Bottom line

NISAR will not find a single new pit or road — wrong resolution. But as a **repeating,
moisture/structure-sensitive, canopy-penetrating covariate and change-trigger**, it
plausibly improves **pad/disturbance** detection and adds the **time axis and driver
layers** our single-epoch LiDAR fundamentally lacks. The InSAR-subsidence idea is **not
yet proven** over forested PA — one beta *winter* pair decorrelated (coherence 0.16), but
that is confounded by beta processing and snow, not bad geometry, so it warrants a retest
(validated, snow-free pair) rather than dismissal; it is likely easier over the Permian.
Start with the GCOV covariate + change-tripwire pilots on 9t and coherence tests (PA
snow-free + Permian); spend real effort only after the validated July-2026 release.

*Reconnaissance basis:* `NISAR_L2_GCOV_BETA_V1` granule `...010_162_A_023...20260120` and
`NISAR_L2_GUNW_BETA_V1` granule `...009_162_A_023_010...20260108`, both clipped to the 9t
bbox; see `data/external/nisar/9t/clip_9t/` and `_fetch_nisar_9t.py`.

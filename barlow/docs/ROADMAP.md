# Barlow / FINESST — Programming & Generation Roadmap

*Written 2026-07-06. Ordered by logical dependency: each phase consumes the previous
phase's outputs. Within a phase, tasks are ordered by what-blocks-what. "Generation" =
documents/figures/data products; "Programming" = code. Existing scripts live in
`barlow/build/`; new scripts follow the same `_snake_case.py` convention and log to
`docs/analysis_log.md` per the documentation-maintenance rule.*

**Standing rules that bind everything below:** proposal documents stay plan-only (no
preliminary results/figures); Cami's data is never committed/pushed; every ≥100 MB
output gets a same-change `.gitignore` rule; heavy products live on
`E:\barlow_data_DO_NOT_DELETE\`; user-authored files are forked (`_vN`) before editing.

---

## Phase 0 — FINESST submission (deadline-driven: 14 July 2026)

Nothing here is programming; all of it gates the fellowship. Ordered by lead time.

| # | Task | Owner | Blocks |
|---|---|---|---|
| 0.1 | Confirm **NSPIRES shell** exists (advisor creates; FI registered + affiliated) | user + advisor | everything |
| 0.2 | Get **university internal routing deadline** from grants office (likely ~5 business days before 7/14) | user | 0.5–0.8 |
| 0.3 | Decide **award duration** (graduation date vs 3-yr default) → propagate to timeline tables + RRS + budget years | user, then Claude | 0.5, 0.6 |
| 0.4 | Advisor session: **Mentoring Plan** review/sign-off (draft exists: `finesst_mentoring_plan.md`) | user + advisor | package |
| 0.5 | Fill RRS `[brackets]` (enrollment, graduation, coursework) — `finesst_readiness_statement.md` | user | package |
| 0.6 | **Budget**: institutional rates into `finesst_ancillary_docs.md` §C skeleton; grants office finalizes | user + grants office | package |
| 0.7 | **Biosketches + Current & Pending** (NASA form templates, FI + PI) | user + advisor | package |
| 0.8 | Assemble submission PDFs from the chosen variant; verify against the **final F.5 text** (page caps, anonymization, required-docs list); ToC; 150-word acknowledgements w/ AI disclosure (draft in ancillary §B) | Claude + user | submission |
| 0.9 | Decide submission variant (formal vs user's v2 lineage) and reconcile any divergence between them ONCE, before assembly | user | 0.8 |

**Parked (user directive):** propagating "tiles acquired" through the repo variants /
manifest / OSDMP — needs confirmation of what was actually received and where it lives.
Do NOT touch until unparked; then it is a one-pass audit (§4 tables, risk lists, OSDMP
§1/§5, manifest, reference doc §2/§7/§9).

## Phase 1 — Data completion (fetch what is wired, stage what was given)

**1.1 Run the expanded LTER fetch.** `python barlow/build/_fetch_barlow_data.py --lter`
now pulls the four new sub-registries wired 2026-07-03 but never executed:
`lter_met_network` (19 met stations, 7002–7030), `lter_melt_model` (8005–8012
energy-balance model I/O), `lter_groundice` (501 DVDP-11 + 5100–5103 SLIME),
`lter_lakelevel` (68 levels / 67 ice thickness / 3104 stage).
*Acceptance:* file counts per sub-dir logged; manifest 🎁/⛔ rows flipped to ✅ with
sizes; analysis_log entry.

**1.2 Stage Cami's training tiles** (when unparked): inventory → `E:\...\labels\`,
CRS/format check, tile count vs the Ch. 6 claim (1,274 at 616 locations), never
committed. *Acceptance:* manifest row with counts + a `_tiles_inventory.py` report.

**1.3 Manual acquisitions (no API):** NZ soil-climate/CALM stations (Bull Pass, Marble
Point, Victoria Valley) via USDA-NRCS/Landcare request; LINZ Antarctica shapefiles +
gazetteer (Cami's `MDV_Resources.docx` links). *Acceptance:* staged on E:, manifest rows.

**1.4 Geology staging (parked conversation, cheap when wanted):** reproject Cami's
OutcropGeology svl_* + Dikes_Sills gdb (EPSG:4326) to 3294; hunt a *surficial* geology /
drift map source (Bockheim soils; GNS/USGS surficial mapping) — the substrate layer that
actually matters for erodibility.

**1.5 Optional driver add-on (decide before Yr-1 modeling):** Landsat/ASTER LST over the
valleys for spatially distributed surface temperature (station+reanalysis coverage is
defensible without it; wire only if O1 residuals demand it).

## Phase 2 — Driver engineering (the O1 substrate)

New script: **`_build_driver_series.py`** — one tidy table per stream × season:
`stream, season, PDD, insolation_sum, mean_discharge, gauged_days, thaw_depth_max,
glacier_mass_balance, lake_level_delta, microclimate_zone`.

- 2.1 **PDD engine:** daily met (station network from 1.1) → positive-degree-day sums
  per melt season; ERA5 t2m fallback where stations gap; AMPS cross-check on a sample
  season. *Acceptance:* PDD series per gauged stream's nearest station, plotted sanity
  check vs known warm years (e.g., 2001-02 flood year spike).
- 2.2 **Insolation:** met-station shortwave where present; ERA5 ssrd elsewhere;
  optionally terrain-corrected via DEM aspect (ties to the aspect-as-driver idea).
- 2.3 **Discharge summaries:** reuse `_finesst_figures._mean_discharge` logic, promoted
  out of the figures script into a shared module (it is load-bearing now); carry
  `gauged_days` as a data-quality column (the 48–362 audit becomes a standing QC).
- 2.4 **Thaw depth / active layer:** soil-T profiles (4020–4024 + SLIME + NZ when in
  hand) → annual max thaw-depth estimate per station; nearest-station or zone-level
  assignment per stream.
- 2.5 **Lake level:** package 68/3104 → per-basin seasonal level deltas (integrated-melt
  proxy AND the standing-water screen's independent check).
- 2.6 **Zone/substrate joins:** microclimate zone per stream/patch (Cami's gdb);
  geology class when 1.4 lands.
*Acceptance for the phase:* one CSV on E: + a QC notebook/markdown with per-driver
coverage tables; iteration doc `docs/iterations/barlow_driver_series.md`.

## Phase 3 — Whole-landscape change (the rescoped O2, prototype order)

- 3.1 **Valley-floor mask:** `_build_valley_floor_mask.py` — slope threshold + elevation
  band + NCALM/NASA footprint intersection (boundaries from `MDV_Shapefiles.gdb`);
  excludes glaciers (USGS 1970 + LTER glacier outlines) and lakes (level data + flat-
  surface detection generalized from `water_mask()`).
- 3.2 **Whole-surface DoD:** extend `_change_detection.py` with `--mask valleyfloor`
  (currently channel-only per-stream logic); emit significant-change patch polygons
  (connected components over |dz| > threshold) with per-patch stats (area, mean dz,
  slope, aspect, distance-to-channel, distance-to-lake, zone).
- 3.3 **Patch classifier v0 (rules):** decision rules on the 3.2 attributes → classes
  {channel, thermokarst-candidate, slope, fan/delta, lake-margin, unclassified}. Rules
  first, ML later only if rules underperform — matches fix-in-design preference.
- 3.4 **Per-class rates:** per-class erosion/deposition/specific rates per epoch pair —
  the O2 deliverable table; per-class water screening (lake-margin class absorbs level
  signal by construction).
- 3.5 **Per-class attribution hook:** feed 3.4 into the Phase-2 driver table → the H2
  fingerprint test (channels~melt/discharge vs thermokarst~thaw depth).
*Acceptance:* pilot on the Fryxell window first (bootstrap rule), QGIS review package of
classified patches, iteration doc + LEADERBOARD-style class-count table. Every raster
≥100 MB gitignored in the same change.

## Phase 4 — Calibrated uncertainty (O3; gates trust in Phase 3)

- 4.1 **Conditioned error model:** `_error_model.py` — stable-terrain dz binned by
  (slope × aspect × sensor-pair) → per-bin NMAD; fit smooth surface (spline or GAM-ish);
  emit per-pixel LOD95 raster per epoch pair.
- 4.2 **Calibration check:** on held-out stable terrain, exceedance rate of the 95%
  threshold must be 5% ± tolerance per bin — the "no more, no less" test from the
  proposal, automated.
- 4.3 **Re-gate Phase 3** with per-pixel thresholds (replace global LOD95); report how
  patch counts/areas change — that delta is itself a result.
*Acceptance:* calibration table (bin, n, exceedance%), iteration doc; per-pixel LOD
raster on E: (gitignored).

## Phase 5 — Attribution modeling (O1 proper)

- 5.1 **Hierarchical regression:** rate ~ drivers with stream-level grouping (and
  geology/zone fixed effects when available); leave-one-stream-out CV harness.
- 5.2 **Random forest twin:** same design matrix; agreement check vs 5.1.
- 5.3 **H1 head-to-head:** energy-based vs discharge-only model comparison (out-of-
  sample error + information criteria); honest small-n reporting.
- 5.4 **Acceleration regression** (3-epoch Taylor streams): Δrate ~ Δdrivers.
- 5.5 **H2 fingerprints:** per-class driver models from 3.5; report per-class winners.
*Acceptance:* `docs/iterations/barlow_attribution_v1.md` with full model cards, CV
tables, and a pre-registered-style analysis plan written BEFORE fitting (guards the
small-n credibility).

## Phase 6 — Generation (documents/figures that follow the science)

- 6.1 Figures regenerated from Phases 3–5 outputs (internal only until publication;
  plan-only rule keeps them out of proposal variants).
- 6.2 Manifest/README/analysis_log/BACKLOG kept current per pass (standing rule).
- 6.3 Post-award or post-result: manuscript skeleton for the O1 attribution paper
  (target: journal TBD with advisor) — earliest artifact worth drafting once 5.3 lands.
- 6.4 Reference doc (`finesst_reference.md`) updated whenever numbers/objectives move.

## Dependency spine (one line)

0 (submission) is independent of 1–6. Then: 1.1 → 2.x → 5.x; 3.1→3.2→3.3→3.4→3.5;
4.1→4.2 gates 3.x's trustworthiness (4 can start in parallel with 3 using global LOD,
then re-gate); 5.5 needs both 2.x and 3.4. Fryxell-window pilot before any full-valley
run, always (bootstrap rule).

# WellSight Control Panel — UI Plan (extensive)

**Date:** 2026-07-20 · **Decisions locked:** Streamlit (localhost browser app) ·
no inline maps (outputs viewed in QGIS) · full scope including GPU training with
a job queue. **Status: PLAN — nothing built yet.**

The goal: one app where every process in this repo is runnable by picking
options — radio buttons for methodology, checkboxes for channels, dropdowns for
blocks and shapefiles, sliders for parameters — so nothing requires asking for
a script run. Selecting options builds the exact command line; Run executes it
through a managed job system with live logs, progress, and provenance.

This plan is deliberately exhaustive: it encodes the non-obvious lessons this
project has already paid for (stale derivatives, locked GeoPackages, silent
90-minute logs, val/test leakage, byte-identical-deploy forensics, orphaned
overnight runs).

---

## 1. Architecture

```
ui/
  app.py            # streamlit entry: page router + startup audit
  registry.py       # THE core: declarative catalog of every runnable task
  jobs.py           # JobManager: spawn/queue/cancel/re-attach subprocesses
  pipelines.py      # canned multi-step chains (DAG-ish, sequential + gates)
  deps.py           # product dependency graph + staleness checker
  widgets.py        # shared widget builders (channel picker, block picker, ...)
  paths.py          # single source of truth for repo paths (wraps _common.py)
  presets/          # named saved form-states (JSON)
  runs/<job_id>/    # cmd.json, output.log, status.json, env.json
  jobs.jsonl        # append-only job ledger (survives refresh/restart)
  settings.json
pages/              # 1_Roads.py, 2_Pits.py, 3_Pads.py, 4_DataBuilder.py,
                    # 5_Analysis.py, 6_Pipelines.py, 7_Jobs.py, 8_Reports.py,
                    # 9_Models.py, 10_Settings.py
```

**Execution model.** Every task runs as a subprocess: `python -u <script>
<args>`, stdout+stderr teed to `ui/runs/<job_id>/output.log`. The UI never
imports the heavy scripts — it shells out exactly as we do by hand, so a UI
crash never kills a training run, and every job is reproducible from its saved
`cmd.json`. Each job also snapshots `env.json`: git commit hash, dirty-file
list, python/torch/CUDA versions, input file mtimes+sizes.

**Job queue.** One worker thread drains a FIFO queue. Jobs declare `gpu`;
GPU jobs are strictly serialized (8 GB 1070 Ti), CPU jobs (exports,
aggregations, figure builds) can run alongside (cap configurable, default 2).
Queue supports: reorder, priority bump, "run after current", pause/resume,
per-job cancel (psutil kills the whole process tree — Windows-safe), and an
optional "start at HH:MM" delay (overnight scheduling).

**Crash / restart recovery (non-obvious, essential).** On startup the
JobManager reconciles `jobs.jsonl` against live PIDs:
- PID alive → **re-attach**: resume tailing its log, progress bar picks up.
  A Streamlit restart must never lose sight of a 6-hour training.
- PID dead but status "running" → mark **orphaned**, show last log lines,
  offer re-queue. (Trainers checkpoint `best.pt` every improving epoch, so a
  killed training is safe — the best model so far survives. The UI says so.)

**Progress parsing.** Tail each log for known patterns → `st.progress` + ETA:
- `ep (\d+)/(\d+)` → epoch bar; per-epoch seconds → ETA
- `Inference grid: .* = (\d+) patches` → inference phase
- `(\d+)/(\d+)$` → builder counters
- `Traceback|CUDA out of memory|rc=[1-9]` → FAILED with last 30 lines
  surfaced; OOM specifically suggests "retry with batch/2" one-click.
**Stall detection:** no log growth for N min (task-type-specific) → flag
STALLED (amber), notify.

**Task registry (the heart).** Each entry declares script, GPU flag, widgets
→ CLI arg mapping, `requires` (input files), `outputs` (declared products),
`docs` (link to its iteration doc), and default values sourced from one
`defaults.yaml` so "champion settings" live in exactly one place:

```python
TASKS["roads.sweep"] = Task(
  script="notebooks/wellsight_v2/s3_train/_road_sweep_202607.py",
  gpu=True,
  inputs=[Radio("variant", [...]), Int("epochs"), Flag("eval_only")],
  requires=[F1, L1, CORR_LABELS],
  outputs=lambda a: [SWEEP/a.variant/"road_prob.tif"],
  docs="docs/handoff/ROAD_SWEEP_HANDOFF.md",
)
```
Pages auto-generate their forms from the registry — adding a new script to the
UI is ~10 lines. Startup validates each entry: script exists, `--help` parses
(drift detection when a CLI changes under the UI).

---

## 2. Cross-cutting systems (the non-obvious functionality)

### 2.1 Environment health check (startup + Settings page)
Runs at launch, results as Dashboard banners:
- `torch.cuda.is_available()` + GPU name/VRAM; GDAL/rasterio/geopandas import;
  PDAL exe on path; whitebox present.
- Disk free on C: with red banner under 50 GB (we have run at 26 GB free).
- Git status: current branch, uncommitted changes; **dirty-script warning** —
  if the script a form is about to run has uncommitted edits, the form shows
  an amber "running uncommitted code" chip (provenance honesty).
- jobs.jsonl reconciliation report (re-attached / orphaned).

### 2.2 Product dependency graph + staleness detection
`deps.py` declares the DAG we keep tripping over:

```
annotations shp/gpkg → label rasters → trained models → prob rasters
                                            ↓                ↓
                              review packages → corrections  extraction gpkg
                                                     ↓            ↓
                                                fine-tunes    validation vs wells
```
Every node = file(s) + builder task. The checker compares mtimes along edges
and surfaces **stale chains** as actionable banners: "annotations edited
2026-07-21 but labels_road_9t_1m built 2026-07-18 → re-rasterize?" (one click
queues the builder). This directly addresses recurring real bugs: the 58
null-geometry pads misdiagnosis, the stale 613590 vector network after raster
deploy, plat.shp-vs-gpkg drift.

### 2.3 Deploy & rollback manager (per block)
A small state file per block records which model produced each *live* raster
(name + best.pt hash + date). The Roads/Pits/Pads tabs show "deployed:
corrected (2026-07-20)" and offer:
- **Deploy** (confirm dialog): auto-backup current as `*_prev_<model>.tif`,
  copy new, update state, and flag downstream products (extraction gpkg) stale.
- **Rollback** to any recorded previous.
- **Verify**: byte-hash the live raster against the claimed model output
  (the check we did manually today) — green check or red mismatch.

### 2.4 Honesty guards (methodology-audit lessons, enforced by UI)
- Tuning controls (thresholds, cleaning params) run against **val** by
  default; the "score on test" button is separate, logged, and shows a
  **test-peek counter** per artifact ("test evaluated 3× this month") to keep
  test discipline visible.
- Split viewer: map-free table of block/cell → split assignments for 9t and
  correction cells; erosion buffers shown; edits require typed confirmation
  and invalidate (mark stale) every downstream metric.
- Seed field on every training form + a **"repeat ×3 seeds"** button that
  queues replicates and reports mean±sd — the audit's run-to-run noise answer.
- Metrics tables always display n (test counts) beside rates.

### 2.5 File-lock and Windows realities
- Before any task that overwrites a gpkg/tif, try an exclusive open; if locked
  (QGIS has it), show "close it in QGIS first" with the file name — no
  half-written outputs. Retry button. (We hit exactly this today.)
- Long-path and spaces handled by always quoting; all subprocess CWD = repo
  root; UTF-8 forced (`PYTHONIOENCODING=utf-8`) — the cp1252 `≥` crash class.
- **Keep-awake**: while a GPU job runs, call SetThreadExecutionState so the
  desktop never sleeps mid-training; release after.
- Windows toast + optional sound on job done/failed/stalled (plyer).

### 2.6 Model registry / family tree (Models page)
Auto-scan all `best.pt` under known roots → table: name, task, trained date,
epochs, val score, channels, resolution, **init lineage** (recall → corrected
→ cldice…) rendered as an indented tree, disk size, and which blocks have its
inference outputs. Actions per model: infer on block(s), evaluate, set as
fine-tune parent in a training form, delete (guarded). Checkpoint metadata
comes free — trainers already save channels/patch/init in the ckpt dict.

### 2.7 Comparison lab
Pick model A vs model B (or raster A vs B):
- difference raster (A−B) written next to outputs for QGIS,
- side-by-side metrics table (from their test_metrics.json),
- the before/after two-panel PNG generator (generalizes
  `_compare_corrected_613590.py` — prob over hillshade, corrections overlaid),
- per-line P(road) scatter (before vs after on held-out added/reject lines).

### 2.8 Reports & compliance page (CLAUDE.md reporting rule, automated)
One click after a detection/validation run generates the structured summary
the project charter requires: candidate count, validation rate vs known wells,
false-positive characterization, parameters used, nearest-known-well distance
distribution, confidence labeling ("candidate"/"probable" only — never
"confirmed"), CRS statement, and reproduce commands. Written to
`docs/reports/<date>_<task>.md` for human curation; the UI never edits the
curated analysis log itself — instead every job appends to
`docs/analysis_log_runs.csv` (timestamp, task, params, job id, git hash) as
the machine-side ledger. LEADERBOARD stays human-curated; eval jobs offer a
copy-ready markdown row snippet.

### 2.9 Annotation health check (Data Builder)
On demand per layer: feature count, **null/empty geometries** (the 58-pad
lesson), invalid geometries (with make_valid preview count), CRS (must be
6346 — offer reproject copy, never in-place), bbox vs expected block, dupes.
Runs automatically before any label rasterization; blocks the run on nulls
with an explain panel instead of silently dropping features.

### 2.10 CRS + geometry gates on all user-supplied paths
Any free-text shapefile/gpkg input is opened read-only, CRS-checked (must
match EPSG:6346 or offer a reprojected copy under `data/derivatives/ui_inputs/`),
geometry-type-checked against what the task expects (lines for roads,
polygons for pads), and size-sanity-checked. Protected paths
(`output_wells.csv`, Glennie/Cami files, `*_ORIGINAL.gpkg` review baselines)
are on a deny-list for any writable slot.

### 2.11 Presets, smoke tests, and estimates
- **Presets**: save/load named form states; ship with "champion defaults"
  per task (sourced from defaults.yaml, so UI and scripts can't drift).
- **Smoke test toggle** on every training form: 1 epoch + tiny sample —
  exactly the pattern that caught today's bugs before burning GPU hours. The
  toggle also routes outputs to a `_smoke/` dir so real dirs stay clean.
- **ETA everywhere**: per-task runtime priors learned from job history
  (median of last 5 runs at same params class) → queue shows projected
  finish times; grid-sweep composer shows total cost before you commit.
- Ground-footprint calculator on patch/resolution controls (256 px @ 0.5 m
  = 128 m — displayed inline, since this trips everyone).

### 2.12 QGIS handoff (files-only, but frictionless)
Every output row: copy-path button, "open containing folder", and a generated
**.qlr layer file** wherever we have a style (the gpkgs already embed styles;
for rasters we ship qml presets: road_prob viridis-over-0.3, argmax
categorical). Optional "append to wellsight.qgz group" is explicitly out of
scope (we won't touch the user's project file).

### 2.13 Batch fan-out
Any inference/extraction form accepts multi-select blocks → expands to one
queued job per block with a compact status grid (block × task → chip). Used
for "run corrected roads on every data_3x3 block."

### 2.14 Escape hatches
- "Show command" on every form (copyable exact CLI) — also the trust anchor.
- Free-text extra-args field (power user), recorded in cmd.json like
  everything else.
- "Open a terminal here" button (repo root) for the 1% the UI doesn't cover.

---

## 3. Global layout

Sidebar (always visible): GPU widget (util %, VRAM, current GPU job) ·
queue widget (running + N queued) · global block picker (9t · 613590 ·
data_3x3 auto-globbed · mkf · permian_01-04) · disk-free · notifications
toggle.

Pages: **Dashboard · Roads · Pits · Pads · Data Builder · Analysis ·
Pipelines · Jobs · Reports · Models · Settings**.

---

## 4. Pages, control by control

### 4.1 Dashboard
- Champion cards per task (road/pit/pad) with headline metric, deployed-where,
  and quick actions (infer, evaluate).
- Startup-audit banners (env, disk, git-dirty, stale chains, orphaned jobs).
- Recent runs (last 10) with status chips; live sweep panel while a sweep is
  in flight (per-variant done/pending + current leaderboard, read-only).

### 4.2 Roads tab
Expanders in workflow order, each with requires-check, Show-command, Run/Queue:

**A. Inference** — model radio (deployed · recall · corrected · each sweep
variant; grayed until its best.pt exists), block multiselect, advanced
patch/overlap, output naming preview; optional "deploy as live" checkbox
(routes through Deploy manager §2.3).

**B. Vector extraction** (`_road_optimize.py`) — prob-source radio (live
deployed vs any model output), cleaning-stage checkboxes (enhance /
threshold / skeleton / prune / bridge), threshold: radio "frozen tuned
config" (default) vs custom slider (val-scored, per §2.4), GT scoring shown
when the block has truth (9t), else network-km + segment stats.

**C. Training** — recipe radio (fine-tune corrected · recall-style scratch ·
sweep variant · custom). Custom exposes: α sliders (bg/road/drainage), γ, lr
(log), epochs, wd, seed, batch, init-parent picker (from Models page),
corrections checkboxes (include 613590; per-class added/reject/kept +
kept-cap), channel checkboxes (7 bands; needs the small `--channels-mask`
trainer patch — phase 3), smoke-test toggle, repeat-×3-seeds button.

**D. Active-learning loop** — the 5-step workflow with live state chips
(§ package built → human-edited (mtime diff vs ORIGINAL detected) →
corrections built → fine-tuned → compared/deployed). Each step queues its
script; step 2 shows the QGIS instructions inline (from README_EDIT.md).

**E. Sweep panel** — variant checkboxes + queue-selected, per-variant status
from test_metrics.json, aggregate button, leaderboard + fig links, "promote
winner" action (= deploy + leaderboard-row snippet + report stub).

### 4.3 Pits tab
- **Inference**: model radio (pit_unet_v2 · pit_07_maskrcnn · pit_08_yolo ·
  multitask), block, score-threshold slider labeled with the caveat that
  0.3/0.05 were never tuned + link to the threshold-sweep task (val-select,
  freeze, test-once — a first-class task here).
- **Post-processing** (`_pit_optimize.py`): frozen-best radio vs custom
  sliders (min/max area, depth, circularity), val-scored.
- **Training**: same pattern as Roads C (0.5 m stack fixed).
- **Review package** builder + the same active-learning chips as Roads D.
- **Eval**: instance metrics (greedy 1:1 P/R/F1@IoU) on the 65-pit split,
  n displayed, JSON + leaderboard-row snippet.

### 4.4 Pads tab
Mirror of Pits (plat_unet · pad_05_maskrcnn · pad_06_yolo · multitask), plus
**Morphology bins** (`_pad_morphology_bins.py`): k radio (2/3/4/auto),
region scope (9t / joint McKean), outputs (styled gpkg, montage, profile)
listed with QGIS handoff buttons.

### 4.5 Data Builder tab
- **Derivative stacks** (`_build_derivatives.py`): block or new-bbox entry,
  resolution radio, product checkboxes (DEM/slope/LRM set/TPI set/openness/
  CHM/hillshades/RRIM), disk-cost estimate, ≥100 MB gitignore note + audit
  button (runs the find/check-ignore loop from CLAUDE.md).
- **Labels & annotations**: layer dropdowns from `data/derivatives/annotations/`
  + free path (gated by §2.9/2.10), per-product re-rasterize buttons,
  annotation health check panel, orientation-labels builder.
- **RRIM / contours / fetch** with their pickers.
- **Staleness view**: the §2.2 DAG for the selected block as an indented
  checklist with rebuild buttons.

### 4.6 Analysis tab
- **Known-well validation**: detections picker (any model output gpkg) ×
  wells picker (venango_wells_all · provenance layers · VPASEC · custom),
  radius slider (25 m default), status-class checkboxes (DEP Orphan List,
  Abandoned…, from WELL_STATU), provenance-class filter (newly-documented
  bounty-era proxy etc.), null-model baseline toggle (random-point matching
  rate — the audit's missing control), outputs per-well CSV + summary +
  report stub.
- **Well age morphology** / **provenance flags** / **photo layers** re-run
  forms with their parameters.
- **Leaderboards**: LEADERBOARD.md + sweep leaderboard rendered read-only.

### 4.7 Pipelines page
Canned chains with per-step gates (each step waits, checks rc + expected
outputs, halts-or-continues per policy):
- **Road refresh** (per block): infer → extract → validate vs wells →
  comparison figures → report stub.
- **Active-learning round**: build review package → [human gate: "I've
  edited in QGIS" confirm] → corrections → fine-tune → eval → compare →
  optional deploy.
- **New-block onboarding**: fetch → derivatives → labels (if annotations) →
  infer roads+pits+pads → extract → validate → report.
- **Full sweep**: N variant trainings → aggregate → promote-winner gate.
Each pipeline is a first-class queued object: one progress bar over steps,
expandable to per-step jobs; resumable from a failed step.

### 4.8 Jobs page
Table (id, task, params summary, status, started, elapsed, ETA, GPU?, git
hash) with log viewer (auto-refresh tail + parsed progress + **live loss
curve** chart read from the trainer's train_log.csv), cancel / re-run
(reloads cmd.json into its originating form) / open-run-folder. Queue
controls: reorder, pause, schedule-at. History filterable; failures keep
their last-30-lines snapshot even after logs rotate.

### 4.9 Reports page
List of generated report stubs (§2.8) with edit-in-VSCode buttons, the
machine ledger (analysis_log_runs.csv) as a table, and the test-peek counters.

### 4.10 Models page
The registry/family tree of §2.6.

### 4.11 Settings
Paths (python exe, PDAL, repo root), poll intervals, CPU-job cap, default
block, notification prefs, keep-awake toggle, theme. Stored settings.json.

---

## 5. Day-one registry wiring

| Task id | Script | GPU |
|---|---|---|
| roads.infer | thin new CLI (load any best.pt → predict block; ~40 lines, the sweep script nearly has it) | yes |
| roads.extract | `_road_optimize.py` | no |
| roads.train.* | existing trainers / `_road_sweep_202607.py` | yes |
| roads.review / corrections / compare | `_build_road_review_package.py` / `_build_road_corrections_613590.py` / `_compare_corrected_613590.py` | no |
| roads.sweep.aggregate | `_road_sweep_aggregate.py` | no |
| pits.* | `_pit_unet_v2.py`, `_pit_maskrcnn.py`, `_pit_yolo.py`, `_pit_optimize.py`, review builder | mixed |
| pads.* | plat trainers, `_pad_morphology_bins.py` | mixed |
| build.* | `_build_derivatives.py`, `_build_label_grids.py`, `_make_rrim.py`, contours, fetchers, `_build_orient_labels.py` | no |
| analysis.* | `_compare_known_wells.py`, `_well_age_morphology.py`, `_well_provenance_flags.py`, `_photo_source_locations.py` | no |

Small code additions outside `ui/` (everything else runs as-is):
1. `roads.infer` thin CLI (~40 lines).
2. Optional `--channels-mask` on trainers (phase 3).
3. Optional graceful-stop sentinel check in `train_loop` ("stop after this
   epoch") — nice-to-have; kill is already safe since best.pt persists.

---

## 6. Build phases

- **Phase 1 — core (1 session):** skeleton, registry, JobManager (spawn/queue/
  cancel/re-attach/toasts), Jobs page with log viewer + progress, Roads A/B/E,
  Dashboard with env audit. → You can run inference/extraction/sweeps yourself.
- **Phase 2 (1 session):** Roads C/D, Pits + Pads tabs, Analysis tab, Deploy/
  rollback manager, comparison lab, presets + smoke toggles.
- **Phase 3 (1 session):** Data Builder + DAG staleness, Pipelines, Reports,
  Models family tree, channels-mask training, seed-replicates, ETA priors.
- **Phase 4 (polish):** schedule-at, test-peek counters, .qlr generators,
  keep-awake, stall detection tuning.

Launch: `streamlit run ui/app.py`; ship `wellsight_ui.bat` double-click
launcher. Localhost only; no auth needed (single user, single machine).

## 7. Known limitations (stated up front)

- Streamlit reruns on every interaction — all job state lives in the
  JobManager singleton + jobs.jsonl, never widget state; the UI must be open
  to *watch* progress, but jobs run detached and survive UI restarts.
- No inline maps by decision — QGIS remains the viewer; the UI compensates
  with paths/folders/.qlr buttons.
- One GPU job at a time by design (8 GB card).
- The UI shells the same scripts we run by hand; registry entries must move
  when a script's CLI moves (startup drift-check catches this).
- Streamlit's file pickers can't browse arbitrary Windows paths; we use
  globbed dropdowns for known locations + validated free-text for the rest.

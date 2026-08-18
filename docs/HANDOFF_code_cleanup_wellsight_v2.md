# HANDOFF — code cleanup of `notebooks/wellsight_v2`

**Written:** 2026-08-12
**For:** a fresh conversation thread picking up the WellSight code-cleanup work
**Repo:** `C:\Users\colto\Documents\GitHub\lidar_project`
**Branch at handoff:** `pit-iter-06-dem-only`

---

## 0. Read this first — what the user actually wants

The user asked for the code to be **cleaned up and consolidated**. Not planned.
Not documented. **Edited.**

The previous thread spent hours on scaffolding — a stage refactor that was pure
file renames, four planning documents, and a test harness — and produced **zero
content changes** to `notebooks/wellsight_v2/s1_build`. The user caught this and
was rightly angry:

> "We're supposed to be working on cleaning out code, fixing things,
> `notebooks/wellsight_v2/s1_build` has NO CHANGES since earlier today? so wtf
> have you been doing?"

**Do not write another plan.** The plan exists (§1). Execute it, verify with the
golden harness, commit, and report deleted-line counts.

Other standing constraints from that thread:

- **Do not delete anything** at the file level. Consolidating a function into
  `core/` and deleting the now-dead duplicate *definitions* is what was asked
  for and is fine. Deleting or archiving whole scripts is not — the user
  reversed an earlier archiving pass with *"It still needs to exist. If it's
  part of generating the training data, we use it."*
- **File paths must be respected.** `sys.path.insert(0, ... parents[N])` appears
  167 times and the depth is load-bearing. QGIS binds 57 layers by relative path.
- When two files are genuinely redundant and it is not obvious which is real,
  rename the redundant one `_dupe` — never delete, never guess (CLAUDE.md rule).
- Report the **full path** of every file you create or modify.
- Commit + push after every major change (stage selectively, branch off default).

---

## 1. The work, in order

Ordering is from `docs/REFACTOR_REVIEW.md` §7 — safest and highest-reach first,
so each step de-risks the next. Steps 1 and 2 are provably no-op refactors, which
is exactly what you want as the first live test of the golden harness.

### Step 1 — `core/vector.py` ← `polygonize` (9 copies → 1)

`polygonize()` (probability raster → scored polygons) is **defined in 9 files,
referenced in 18**. Verified this session: all textual variants are
**behaviourally identical**. Differences are cosmetic only —

| Difference | Kind |
|---|---|
| `thr` vs `thresh` parameter name | cosmetic; every call site is **positional** |
| `from shapely.geometry import shape` inside vs outside the function | cosmetic |
| `return (X if rows else Y)` vs early-return | cosmetic |

The 8 same-signature definitions to remove:

```
s3_train/_pit_unet_cv5.py:134            def polygonize(prob, transform, crs, thr, min_area=MIN_AREA_M2)
s3_train/_pad_unet_cv5.py:129            def polygonize(prob, transform, crs, thr, min_area=MIN_AREA_M2)
s5_eval/_heldout_overlap_9t.py:66        def polygonize(prob, transform, crs, thresh, min_area=MIN_AREA_M2)
s5_eval/_heldout_rim_containment_9t.py:105
s5_eval/_pit_threshold_products_9t.py:67
s5_eval/_reeval_instance_precision_9t.py:146
s5_eval/_uncounted_well_recovery_9t.py:84
s5_eval/_threshold_common.py:56          def polygonize(prob, transform, crs, thresh, min_area)   # no default
```

**LEAVE ALONE:** `s4_infer/_pad_unet_infer_grid.py:70` —
`polygonize(argmax, prob1, profile, out_gpkg)` is a genuinely different function
that happens to share the name. Do not touch it.

**`min_area` is NOT a shared constant.** It is per-target and each caller must
keep passing its own:

| Value | Files |
|---|---|
| `4.0` (pit) | `_pit_unet_cv5`, `_build_undecided_pit_candidates_9t`, `_heldout_overlap_9t`, `_heldout_rim_containment_9t`, `_map_cv5_unmatched_pit_thr0p50_9t`, `_pit_threshold_products_9t`, `_reeval_instance_precision_9t`, `_uncounted_well_recovery_9t` |
| `100.0` (pad) | `_pad_unet_cv5`, `_pad_threshold_products_9t` |
| `200.0` (ICP patches) | `s7_analysis/_icp_change_classify_9t.py` |

So `core/vector.py`'s `polygonize` should have **no default** for `min_area` —
make it required and let each module keep its own `MIN_AREA_M2` constant. A
shared default is how the pad threshold silently becomes the pit threshold.

Expected: ~140 lines deleted, 18 call sites reached, **zero output change.**

### Step 2 — `core/folds.py` ← `assign_folds`

**The complication flagged at the end of the last thread is resolved.** The
function-body hashes differed (`2566674c527d` vs `e48c0299735f`), which looked
like drift. It is not. Diffed both bodies this session — they are identical line
for line; the only difference is one word in the docstring
(`balanced on pit count` vs `balanced on pad count`). It is a blind merge after
all.

The shared implementation (`s3_train/_pit_unet_cv5.py:117`,
`s3_train/_pad_unet_cv5.py:115`):

```python
def assign_folds(blocks_n: pd.DataFrame, k: int, seed: int) -> dict[int, int]:
    """Greedy-deficit assignment of blocks to k folds, balanced on annotation count."""
    shuffled = blocks_n.sample(frac=1, random_state=seed).values
    total = int(shuffled[:, 1].sum())
    quota = [total / k] * k
    got = [0] * k
    out = {}
    for bid, n in shuffled:
        f = int(np.argmax([quota[i] - got[i] for i in range(k)]))
        out[int(bid)] = f
        got[f] += int(n)
    return out
```

`CV_SEED = 20260727`. Fold assignment must not move — the deployed CV5
checkpoints were fold-assigned with it.

### Step 3 — break the eval → train coupling

**Six evaluation scripts import from training scripts.** This is the most
important structural defect in the codebase.

```
s5_eval/_build_undecided_pit_candidates_9t.py:87  from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_cv5_centroid_precision_pit_pad_9t.py:64  from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_map_cv5_unmatched_pit_thr0p50_9t.py:52   from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_match_rules_pit_pad_9t.py:58             from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_pit_cv5_tau_scale.py:30  from _pit_unet_cv5 import (ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR, SCORE_BUF_M, ...)
s5_eval/_pad_cv5_tau_scale.py:30  from _pad_unet_cv5 import (ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR, SCORE_BUF_M, ...)
```

Steps 1+2 fix the first four for free — repoint them at `core/vector.py` and
`core/folds.py`.

The last two import **configuration constants** from a trainer. Move
`ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR, SCORE_BUF_M` into
`config/targets.toml` (they already live alongside `config/paths.toml`, which
`_common.py` reads).

Three consequences of the coupling, all fixed by this step:

1. Eval cannot run without loading torch (importing the trainer imports `_dl`).
   This is why `--help` smoke checks took minutes.
2. Changing a **training** constant silently moves an **eval** number —
   `SCORE_BUF_M` lives in the trainer and is read by the tau-scale scripts.
3. It blocks the CV5 twin merge (Step 5). Six scripts import those module names
   directly.

### Step 4 — wire in `_manifest_guard.py` (already written, not yet wired)

`notebooks/wellsight_v2/s2_labels/_manifest_guard.py` exists and is complete but
**is not imported anywhere.** It guards a live footgun that already fired once
this session:

Running `_build_pit_dataset.py` regenerated `pit_blocks_9t.gpkg` against **655**
currently-drawn pits instead of the **527** the deployed `pit_unet_cv5`
checkpoints were trained and fold-assigned against. Every `s5_eval` CV5 consumer
recomputes folds from that manifest, so this silently scores existing checkpoints
against a split they were never trained on. Caught only by diffing the E: mirror.

Wire `check_or_refuse()` into both label builders, each of which currently takes
**0 CLI args** and always writes to the canonical `DERIV_9T` paths:

- `s2_labels/_build_pit_dataset.py` (152 lines) → guards `pit_dataset_manifest.csv`
- `s2_labels/_build_pad_road_dataset.py` (189 lines) → guards
  `pad_dataset_manifest.csv` (written line 129) and `road_dataset_manifest.csv`
  (line 157)

Add a `--force` flag to each. Then golden-record both — that takes Phase 0 from
11/13 to **13/13**.

### Step 5 — merge the CV5 twins

Only after Step 3. `_pit_unet_cv5.py` (407 lines) and `_pad_unet_cv5.py`
(391 lines) are 72% identical, and the divergence is mostly docstring prose:

| Function | pit | pad | note |
|---|---:|---:|---|
| `assign_folds` | 12 | 12 | identical → `core/folds.py` (Step 2) |
| `polygonize` | 16 | 16 | identical → `core/vector.py` (Step 1) |
| `match_scores` | 31 | 31 | identical |
| `containment` / `locate_rate` | 14 | 12 | |
| `main` | 255 | 248 | differs in constants + one match rule |

Real differences to parameterise: patch 128 m / 30 m jitter / 3 classes (pit) vs
384 px / 40 m jitter / 2 classes (pad); `MIN_AREA_M2` 4.0 vs 100.0; one
target-specific match rule. Target: `train_unet_cv5.py --target {pit,pad}`.

### Step 6 — the NULL-`pit_inside_id` correctness bug (three scripts still carry it)

This is a **real defect**, not a refactor. `dissolve(by="pit_inside_id")` silently drops
**138 rims** whose `pit_inside_id` is NULL (a rim with no paired floor). The tell is a
candidate that overlaps a rim 100% while reporting `near_pit_m` of 126–137 m.

Fix: key on `pit_inside_id` where present, `f"o{pit_full_id}"` otherwise.

- **Already fixed** (use as the control that must NOT change):
  `s5_eval/_build_undecided_pit_candidates_9t.py`
- **Still broken:** `s5_eval/_match_rules_pit_pad_9t.py`,
  `s5_eval/_cv5_centroid_precision_pit_pad_9t.py`,
  `s5_eval/_map_cv5_unmatched_pit_thr0p50_9t.py`

Related and also required: pit matching must consider **both** `pit_full` and
`pit_inside` — key on the per-`pit_inside_id` union of the two layers. The user caught
this explicitly: *".... are you not checking this against pit_full and
pit_inside?"*

**These three scripts will legitimately change their golden output.** That is the
point. Re-record the baselines afterward and note the numbers that moved in
`docs/analysis_log.md`. Do not lump this step in with Steps 1–2, whose whole
value is being provably no-op.

---

## 2. How to verify — this is not optional

`tools/golden.py` records a script's outputs by **filesystem snapshot diff**
(snapshot → run → snapshot → hash whatever changed), because static "what does
this output" inference failed twice on this codebase.

```bash
C:/Python313/python.exe tools/golden.py verify <name>
```

**Must run under `C:\Python313\python.exe`.** The `.venv` interpreter lacks
geopandas and pyogrio, and golden.py needs both to content-hash GeoPackages. It
degrades to raw-byte hashing with a warning, which false-alarms on every run.

11 baselines exist in `docs/golden/`:

```
prep_annotations          heldout_overlap            match_rules_pit_pad
rebuild_road_labels       heldout_rim_containment    cv5_centroid_precision
score_road_613590         reeval_instance_precision  build_undecided_pit_candidates
pit_tau_scale             pad_tau_scale
```

Two harness gotchas are already fixed — do not "rediscover" them:

1. **GeoPackages are never byte-stable.** GDAL writes a `last_change` timestamp
   into `gpkg_contents` on every save. `.gpkg` is hashed by content (per layer:
   columns, dtypes, per-row values + geometry WKB).
2. **QGIS `layer_styles.update_time` changes by design.** That table is skipped.

After Steps 1–3, **all 11 must PASS.** If any fails, the refactor changed
behaviour — stop and find out why. That is the entire reason the harness exists.

---

## 3. What already exists — don't rebuild it

`docs/REFACTOR_PLAN.md` says to create `core/models.py`. **It already exists
under another name.** Two-thirds of the "shared core" is already there:

| File | Contents | Importers |
|---|---|---:|
| `notebooks/wellsight_v2/_dl.py` (379 LOC) | `UNet`, `FocalCE`, `CenteredPatchSampler`, `train_loop`, `run_epoch`, `predict_full_tile`, `load_stats`, `normalize`, `random_d4` | **14** |
| `notebooks/wellsight_v2/_common.py` | `run_pdal`, `read_tif`, `write_tif`, `make_profile`, `path_for`, and `ROOT/DERIV/DERIV_9T/DST_CRS/PDAL_EXE/PATHS/CONFIG` from `config/paths.toml` | **67** |

These are `core/models.py` and `core/io.py`. Renaming them is optional and low
value; if you do, leave a shim re-export so all 81 importers keep working.

**The real diagnosis:** the code quality is good — docstrings explain *why*, and
several carry explicit leakage warnings. The shared layer was extracted early and
well, then **stopped growing**. Everything written afterwards was copied instead
of added to it. The defect is duplication and coupling, not craft.

---

## 4. Landmines

- **`_prep_road_1m.py` overwrites the trained-on feature stack.** Running it
  clobbers `features_pit_9t_1m.tif` / `feature_stats_1m.json` with values ~2%
  off what the models trained on (slope mean 8.3177 → 8.5156). Already restored
  from the E: mirror and the rebuild target was renamed to
  `tiles/9t_1m_rebuilt20260812/` so the script fails fast. Do not undo that.
- **`_build_pit_dataset.py` / `_build_pad_road_dataset.py` have no dry-run and
  no output redirect.** Do not run them until Step 4 lands.
- **Backups:** `E:\Colton\_BACKUPS\lidar_project_MIRROR` is the only backup.
  **There is no F: drive** (it was mounted 2026-08-05/06, gone since). Robocopy
  flags: `/E /XO /XJ /FFT /R:2 /W:5 /MT:8`. `/MIR` is forbidden.
- **`613590_review_r2` scoring is circular** — it is a prior model's own vetted
  output; all 12 models score 0.96–1.00. Only `613590_added_r2` (48.87 km) is
  informative.
- `s1_build/_fetch_nisar_9t.py` and `s1_build/_fetch_permian_grids.py` are not
  lidar pipeline and should move out of `s1_build`.

---

## 5. Open questions, unresolved

- `pad.shp` has **1,053** features but `pad_dataset_manifest.csv` has **650**.
  No explanation found.
- `plat_02`/`road_02` and `plat_03`/`road_03` hold **byte-identical checkpoints**
  under different names. Candidates for the `_dupe` rename rule — but confirm
  which is referenced before touching anything.

---

## 6. Definition of done

- [ ] `polygonize` defined once in `core/vector.py`; 8 duplicates deleted;
      `_pad_unet_infer_grid.py`'s different function untouched
- [ ] `assign_folds` defined once in `core/folds.py`
- [ ] Zero `from _pit_unet_cv5 import` / `from _pad_unet_cv5 import` lines in
      `s5_eval/`
- [ ] Eval scripts import without loading torch
- [ ] All 11 golden baselines PASS after Steps 1–3
- [ ] `_manifest_guard.py` wired into both label builders with `--force`;
      golden at 13/13
- [ ] NULL-`pit_inside_id` fix in the 3 remaining eval scripts; baselines re-recorded
      and the moved numbers written up
- [ ] `docs/analysis_log.md` entry (newest at top) and
      `docs/iterations/BACKLOG.md` updated
- [ ] Committed and pushed on a branch off `main`

**Report progress in deleted lines and passing golden checks, not in documents
written.**

---

## 7. Reference docs (context only — do not add to them)

| Path | What it is |
|---|---|
| `docs/REFACTOR_REVIEW.md` | The most accurate document. Written after reading the code; corrects the two below. Revised ordering is in §7. |
| `docs/REFACTOR_STEPS.md` | Step-level detail. Note its Phase 3 has an unlisted blocker (the eval→train coupling). |
| `docs/REFACTOR_PLAN.md` | Original plan. Wrong that `core/models.py` needs creating. |
| `docs/golden/NON_DETERMINISTIC.md` | Phase 0 findings: the 11 verified, the 2 deferred and why, both harness bugs. |
| `docs/RUNBOOK.md`, `docs/script_map.md` | Script inventory. |

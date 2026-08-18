# Code review — reassessing the refactor plan after reading the code

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

**Written:** 2026-08-12
**Amends:** `docs/REFACTOR_PLAN.md`, `docs/REFACTOR_STEPS.md`

The plan was built from measurements — similarity percentages, script counts,
docstring lines. This is what changed after reading the code.

---

## 1. The shared core already exists. The plan said it did not.

`REFACTOR_PLAN.md` §2 proposes creating `core/models.py`. It is already there,
under another name:

| Existing | Contents | Importers |
|---|---|---:|
| `_dl.py` (379 LOC) | `UNet`, `FocalCE`, `CenteredPatchSampler`, `train_loop`, `run_epoch`, `predict_full_tile`, `load_stats`, `normalize`, `random_d4` | **14** |
| `_common.py` | `run_pdal`, `read_tif`, `write_tif`, `make_profile`, `path_for`, path/CRS config | **67** |

Between them these are `core/models.py` and `core/io.py`. **Phase 2.3 is a
rename, not a creation**, and should be reduced accordingly.

The real story is not "there is no shared layer". It is that **the shared layer
stopped growing.** `_common` and `_dl` were extracted early and well; everything
written afterwards was copied instead of added to them.

---

## 2. The worst duplication is invisible to pairwise similarity

`polygonize()` — probability raster to scored polygons — is **defined in 9 files
and referenced in 18.**

It never appeared in the 12-pair similarity table because it is a 17-line
function scattered widely, not two large similar files. My analysis method could
not see it.

Five textual variants exist. I expected drift and found none:

| Difference | Kind |
|---|---|
| `thr` vs `thresh` parameter name | cosmetic |
| `from shapely.geometry import shape` moved inside the function | cosmetic |
| `return (X if rows else Y)` vs early-return | cosmetic |

**All nine are behaviourally identical.** That makes this the safest extraction
available: provably no behaviour change, removes 8 copies, reaches 18 call
sites. It should be the *first* thing extracted, not an afterthought.

---

## 3. A layering inversion the plan did not account for

**Six evaluation scripts import from training scripts.**

```
s5_eval/_build_undecided_pit_candidates_9t.py : from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_cv5_centroid_precision_pit_pad_9t.py : from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_map_cv5_unmatched_pit_thr0p50_9t.py  : from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_match_rules_pit_pad_9t.py            : from _pit_unet_cv5 import assign_folds, polygonize
s5_eval/_pit_cv5_tau_scale.py                 : from _pit_unet_cv5 import ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR, SCORE_BUF_M
s5_eval/_pad_cv5_tau_scale.py                 : from _pad_unet_cv5 import ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR, SCORE_BUF_M
```

The last two import **configuration constants** from the trainer. The trainer is
doing three jobs: training, hosting a helper library, and acting as the eval
config module.

Three consequences:

1. **Eval cannot run without torch loading**, because importing the trainer
   imports `_dl`, which imports torch. That is why the `--help` smoke checks
   earlier took minutes.
2. **Changing a training constant silently moves an eval result.** `SCORE_BUF_M`
   lives in the trainer and is read by the tau-scale scripts.
3. **`REFACTOR_STEPS.md` Phase 3 breaks six scripts.** It proposes merging
   `_pit_unet_cv5` and `_pad_unet_cv5` into `train.py --target {pit,pad}`. Six
   scripts import those module names directly. The step does not mention it.

This is the most important structural defect in the codebase and it was not in
the plan at all.

---

## 4. The CV5 twins are more mergeable than 72% suggested

Normalising target names in the diff shows the divergence is **mostly docstring
prose**. Structurally:

| Function | pit | pad |
|---|---:|---:|
| `assign_folds` | 11 | 11 |
| `polygonize` | 16 | 16 |
| `match_scores` | 31 | 31 |
| `containment` / `locate_rate` | 14 | 12 |
| `main` | 255 | 248 |

~72 lines of identical helpers plus a `main` differing in constants (patch
128 m / 30 m jitter / 3 classes vs 384 px / 40 m jitter / 2 classes) and one
target-specific match rule.

Once the helpers move to `core/`, the two mains are close enough that
`--target` is a clean merge rather than a forced one.

---

## 5. Code quality is not the problem

Worth stating plainly, because "143 scripts" invites the wrong conclusion.

The code is good. Docstrings explain *why*, not just what —
`_match_rules_pit_pad_9t.py` opens by explaining which defect it fixes and in
what order so each effect is separately visible. `_road_threshold_products_9t.py`
carries an explicit LEAKAGE WARNING about 40 m chunking putting 39.8% of
held-out chunks on a parent road that also has training chunks. `_dl.py` is a
properly factored module.

The defect is architectural, not craft: the shared layer stopped growing, and
target/area variation was expressed by copying files instead of by parameters.

---

## 6. What the plan gets wrong, precisely

| Plan says | Reality | Fix |
|---|---|---|
| Phase 2.3 creates `core/models.py` | `_dl.py` already is it, 14 importers | Downgrade to a rename plus MaskRCNN/YOLO wrappers |
| Phase 2 extracts matching, metrics, models, labels | Omits `polygonize` (9 copies) and `assign_folds` (the eval→train coupling) | Add both, first |
| Phase 3 merges the CV5 twins | Six eval scripts import them by module name | Break the coupling in Phase 2 or Phase 3 fails |
| "The core does not exist" | Two thirds of it does | Say so; the job is smaller than advertised |

---

## 7. Revised Phase 2 ordering

Safest and highest-reach first, so each step de-risks the next.

**2.0 — `core/vector.py` ← `polygonize`**
Nine identical copies to one. 18 call sites. Provably no behaviour change, so
golden verification should be clean on the first run. If it is not, the
harness itself is wrong and that is worth knowing before anything risky.

**2.1 — `core/folds.py` ← `assign_folds`**
Removes four `from _pit_unet_cv5 import …` lines in `s5_eval`. Eval stops
importing a trainer, and stops loading torch to compute a fold assignment.

**2.2 — eval constants out of the trainers**
`ANN_GPKG`, `BLOCKS`, `CRS`, `FEATURES`, `OUTDIR`, `SCORE_BUF_M` move to
`config/targets.toml` + `config/areas.toml`. Kills the last two eval→train
imports. **After this the trainers can be merged safely.**

**2.3 — `core/matching.py` ← `match_scores`, `containment`, `locate_rate`**
Carries the corrected `pit_inside_id` / `pit_full_id` keying. Three consumers will
legitimately change; `_build_undecided_pit_candidates_9t.py` already has the fix
and is the control that must not.

**2.4 — `core/metrics.py`**, **2.5 — `_dl.py` → `core/models.py`** (shim
re-export), **2.6 — `core/labels.py`**.

Phase 3 then proceeds as written, unblocked.

---

## 8. Verdict on the plan

The phases and the golden-harness discipline are right and should stand. Three
amendments:

1. **Phase 2 is smaller than stated** — two thirds of the core exists.
2. **Phase 2 is missing its two most valuable steps** — `polygonize` and the
   eval→train decoupling.
3. **Phase 3 has an unlisted blocker** that Phase 2 must clear first.

Phase 0 and Phase 1 are unaffected and remain the right place to start.

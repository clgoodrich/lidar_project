# Phase 0 findings — golden harness

**Result: 11 of 13 planned Tier-1 scripts recorded and verified clean.
2 deliberately deferred, not because they are non-deterministic, but because
running them mutates pipeline-critical state.**

---

## The 11 verified deterministic

All PASS on a second consecutive run, byte-for-byte (content-for-content on
`.gpkg`), after two harness fixes described below:

```
prep_annotations
rebuild_road_labels
heldout_overlap
heldout_rim_containment
reeval_instance_precision
match_rules_pit_pad
cv5_centroid_precision
build_undecided_pit_candidates
pit_tau_scale
pad_tau_scale
score_road_613590
```

## Two deferred: `_build_pit_dataset.py`, `_build_pad_road_dataset.py`

> **RESOLVED for the pit builder, 2026-09-04.** The guard argued for below now
> exists. `notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py` calls
> `_manifest_guard.check_or_refuse()` once, before anything writes, and exits 1
> with a `REFUSING TO OVERWRITE` banner when the annotation count disagrees with
> the manifest on disk. `--force` is required to proceed and prints the warning;
> `--dry-run` reports and writes nothing; `--out-dir` makes a scratch run
> possible at all. Verified live the same day: the guard refused a 527 -> 712
> rebuild, then `--force` performed it deliberately as Phase 4 step 2.
>
> `_build_pad_road_dataset.py` is **still unguarded** and still has no argparse
> at all -- it ignores `--help` and runs the full build. Same footgun, separate
> change. Tracked in `docs/iterations/BACKLOG.md`.


**Not run for golden recording.** Both regenerate `pit_blocks_9t.gpkg` /
`pit_dataset_manifest.csv` and `pad_dataset_manifest.csv` from whatever is
currently in `pit_inside.shp` / `pad.shp` — no dry-run mode, no output
redirect, they always write to the canonical `DERIV_9T` paths.

**This was not a hypothetical risk.** Running `_build_pit_dataset.py` once,
live, during this session, regenerated `pit_blocks_9t.gpkg` against **655**
currently-drawn pits instead of the **527** the deployed `pit_unet_cv5`
checkpoints were actually trained and fold-assigned against. Caught by
comparing against the `E:\Colton\_BACKUPS\lidar_project_MIRROR` copy;
restored immediately, verified byte-identical to the mirror afterward.

**Consequence if this goes unnoticed:** any eval script that recomputes fold
assignment from the manifest (all of `s5_eval`'s CV5 consumers do, via
`assign_folds(nper, K, CV_SEED)`) would silently score the existing
checkpoints against a held-out split those models were never trained
against — some "held-out" blocks might actually have been in that fold's
training set.

**This is now the strongest available argument for `REFACTOR_STEPS.md`
Phase 2 Step 2.1** (extracting `assign_folds` into `core/folds.py`) **and for
adding a guard to the label builders** — e.g., refuse to overwrite
`pit_blocks_9t.gpkg` when the annotation count differs from the manifest's
recorded count without an explicit `--force`. That guard does not exist yet
and this is a live footgun in the current 9t pipeline, not just a 613590
problem: **every time `pit_inside.shp` or `pad.shp` grows, the next run of
these two scripts silently reassigns folds with no warning.**

Golden-recording these two safely requires either the `--force` guard above,
or golden-recording their **inputs** (shapefile row counts + hashes) rather
than running them live — the same Tier-2 treatment `REFACTOR_STEPS.md`
already prescribes for the CUDA trainers. Do this before Phase 1 touches
either script.

---

## Two harness bugs found and fixed, not script bugs

### 1. GeoPackage files are not byte-stable, ever

Confirmed empirically: running `_prep_annotations.py` twice in a row with
zero code or data changes produced two `.gpkg` files with different SHA-256
sums. Per-layer content comparison (row count, attributes, geometry WKB) showed
**all 7 layers byte-for-byte identical** across the two runs. GDAL/OGR's
GeoPackage driver writes a `last_change` timestamp into the `gpkg_contents`
metadata table on every save — required by the spec, unrelated to payload.

5 of the first 11 scripts tripped this on the first verify pass. Fixed:
`tools/golden.py` now hashes `.gpkg` files by content (columns, dtypes, and
each row's attributes + geometry WKB, per layer) instead of raw bytes.

### 2. QGIS `layer_styles` tables are supposed to change

Second, related false positive on `_heldout_rim_containment_9t.py`. This
project's `_style_heldout_gpkg.py` convention writes a QGIS `layer_styles`
system table with an `update_time` column that changes by design on every
save — it is styling metadata, not pipeline output. All 5 real data layers
were confirmed identical; only `layer_styles.update_time` differed. Fixed:
`tools/golden.py` skips the `layer_styles` table when hashing.

Both fixes are documented in `tools/golden.py`'s module docstring, since any
future extension of the golden harness to more scripts will hit the same two
issues again.

---

## What this means for Phase 1+

The golden harness works and 11 of the highest-value eval/label scripts have
a trustworthy baseline. The two deferred scripts are the two that most need
Phase 2's `assign_folds` extraction and a write-guard — not because they are
broken, but because they are the exact shape of footgun this whole
reorganization has been fighting all session.

## 2026-08-12 — the 11 Phase 0 baselines are STALE (inputs changed, not code)

All five golden records covering annotation-reading scripts fail verify today:
`prep_annotations`, `heldout_overlap`, `heldout_rim_containment`,
`score_road_613590`, `reeval_instance_precision`.

**This is not a code regression.** The same failures reproduce against the
pre-conversion code, verified by stashing the change and re-running. The cause is
that `data/derivatives/annotations/annotations_proj.gpkg` has uncommitted
modifications made before the 2026-08-12 session, so every downstream product
legitimately differs from what was recorded on 2026-08-11.

Re-recording is the correct maintenance action, but it freezes whatever
annotation state is on disk at that moment. That belongs to whoever made the
edits, not to a refactor pass. Left stale deliberately.

**How the path-literal conversion was proven instead.** A fresh baseline was
recorded from the ORIGINAL code, the conversion was restored, and verify was run
against that baseline:

| record | result |
|---|---|
| `conversion_equivalence_rim_containment_9t.json` | 5 unchanged, 0 mismatched — PASS |
| `conversion_equivalence_road_score_613590.json`  | 3 unchanged, 0 mismatched — PASS |

Byte-identical output across the conversion. Those two records stay as the
evidence; they are A/B artifacts, not pipeline baselines.

## 2026-08-12 — a golden record tracks output PATHS, so a move invalidates it

After Phase 4D, `conversion_equivalence_rim_containment_9t` failed with
**0 MISMATCHED, 5 MISSING, 0 new/extra**. Read that shape carefully before
treating it as a regression: nothing produced different content. The five
outputs moved from `data/derivatives/eval_9t_rim_containment/` to
`data/05_results/9t/pit/rim_containment/`, which is the reorganization working.

The distinction is worth stating because the two failure modes look alike in a
summary line and mean opposite things:

| shape | meaning |
|---|---|
| `n MISMATCHED` | same path, different bytes. **A real behaviour change.** |
| `n MISSING, n new/extra` | same bytes, different path. A move. |
| `n MISSING, 0 new/extra` | the run wrote to a path outside the watched set, or wrote nothing |

Re-recorded at the new location after confirming the shape.

# Refactor work order — the actual steps

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

**Written:** 2026-08-12
**Companion to:** `docs/REFACTOR_PLAN.md` (the why). This is the how.
**Branch:** `refactor-package`, cut from `repo-reorg`.

Every step states what it touches, how to verify it, and how to undo it. No step
proceeds if its verification fails.

---

## Correction to the plan document

`REFACTOR_PLAN.md` §1.4 claims Phase 1 unlocks "187.6 km of road, 403 pads and
152 pits". **Only the roads are in 613590.** Measured inside the 613590 bbox
(613500,4590000 → 618000,4594500):

| Annotation | In 613590 |
|---|---:|
| roads | **1,490 features, 187.6 km** |
| drainage | **986 features** |
| pit floors | 96 |
| pit rims | **0** |
| pads | **0** |
| not_roads | **0** |

So 613590 buys **road and drainage training only**. Pits would be floor-only
with no rims to match against and no hard negatives; pads gain nothing. The 403
pads and remaining pits that sit outside 9t are somewhere else — `label_grids/`
or McKean — and locating them is a separate task.

This is still the highest-value target: roads are the weakest model, and the
faint-road class it fails on is exactly what 613590 holds.

**Phase 1 is therefore scoped to roads + drainage on 613590 at 1 m.**

---

## Preconditions

```
git checkout repo-reorg && git pull
git checkout -b refactor-package
python tools/verify_paths.py            # must PASS
robocopy … E:\Colton\_BACKUPS\lidar_project_MIRROR   # tools/backup_to_E.bat
python tools/verify_backup.py --target "E:/Colton/_BACKUPS/lidar_project_MIRROR"
```

Do not start until the backup verifies PASS.

---

# PHASE 0 — the golden harness

> **EXECUTED 2026-08-12. 11 of 13 planned scripts recorded and verified
> clean. Full findings in `docs/golden/NON_DETERMINISTIC.md`.**
>
> The 2 deferred (`_build_pit_dataset.py`, `_build_plat_road_dataset.py`) were
> not a judgment call — running `_build_pit_dataset.py` live during this pass
> regenerated `pit_blocks_9t.gpkg` against 655 currently-drawn pits instead of
> the 527 the deployed CV5 checkpoints were trained and fold-assigned against.
> Caught against the E: mirror, restored, re-verified identical. **This is a
> live footgun in the current 9t pipeline**, not a 613590-only problem: every
> time annotation grows, the next run of either script silently reassigns
> folds with no warning. It is the strongest evidence yet for Phase 2 Step 2.1
> (extract `assign_folds`) and motivates a `--force` write-guard that does not
> exist yet — add it before Phase 1 touches either script.
>
> Also found and fixed: `.gpkg` files are not byte-stable between runs even
> with zero data change (GDAL embeds a `last_change` timestamp), and this
> project's QGIS auto-styling convention adds a second, similar false
> positive via `layer_styles.update_time`. `tools/golden.py` now hashes
> `.gpkg` output by content instead of raw bytes and skips `layer_styles`.
> Both were real harness bugs, not script bugs — 5 of the first 11 scripts
> tripped the first one, 1 tripped the second.

Nothing in the pipeline changes. Exit criterion: every Tier-1 script proves
itself deterministic across two consecutive runs.

## Step 0.1 — `tools/golden.py`

**Design.** Do not try to infer a script's outputs statically — that failed
twice already (`map_scripts.py`, `check_archived_still_used.py`), because these
scripts build output paths inside `main()` from CLI arguments. Observe the
filesystem instead.

```
python tools/golden.py record <name> -- <command…>
python tools/golden.py verify <name> -- <command…>
```

`record`:
1. Walk `data/derivatives/`, `docs/`, `qgis/`; capture `(path, size, mtime_ns)`.
2. Run the command.
3. Walk again. Any path that is new, or whose size/mtime changed, is an **output**.
4. SHA-256 each output. Write `docs/golden/<name>.json`:
   `{command, timestamp, outputs: {relpath: {sha256, bytes}}, ignored: [...]}`.

`verify`: repeat, compare hashes, exit non-zero on any difference.

**Ignore list** (changes on every run by construction, proves nothing):
`*.log`, `*.aux.xml`, `_tmp_*`, `docs/golden/*`, `backup_to_*_last_run.log`,
anything under `__pycache__`.

**Rollback:** delete the file. It writes nothing outside `docs/golden/`.

## Step 0.2 — pick the Tier-1 set

Deterministic and fast enough to run twice. Candidates, all of `s5_eval` except
the plot-only ones, plus the label builders:

```
s2_labels/_prep_annotations.py
s2_labels/_build_pit_dataset.py
s2_labels/_build_plat_road_dataset.py
s2_labels/_rebuild_labels_road_9t_1m.py
s5_eval/_match_rules_pit_pad_9t.py
s5_eval/_cv5_centroid_precision_pit_pad_9t.py
s5_eval/_build_undecided_pit_candidates_9t.py
s5_eval/_pit_cv5_tau_scale.py
s5_eval/_pad_cv5_tau_scale.py
s5_eval/_score_road_pred_vs_roads_shp_613590.py
s5_eval/_heldout_overlap_9t.py
s5_eval/_heldout_rim_containment_9t.py
s5_eval/_reeval_instance_precision_9t.py
```

**Verification:** `record` each, then `verify` each **without changing
anything**. A script that fails its own verify is non-deterministic — record it
in `docs/golden/NON_DETERMINISTIC.md` with the differing files and exclude it.
Expect the map/figure producers to land here (matplotlib embeds timestamps).

## Step 0.3 — Tier 2, the trainers

Weights are not bit-reproducible on CUDA. Do not pretend otherwise. Instead
hash the **inputs**:

```
python tools/golden.py record train-inputs-9t-pit -- \
    python -c "import hashlib,sys;[print(p, hashlib.sha256(open(p,'rb').read()).hexdigest()) for p in sys.argv[1:]]" \
    data/derivatives/tiles/9t/features_pit_9t_05.tif \
    data/derivatives/tiles/9t/labels_pit_9t_05.tif \
    data/derivatives/tiles/9t/pit_dataset_manifest.csv \
    data/derivatives/tiles/9t/pit_blocks_9t.gpkg
```

If those four hashes are unchanged after a refactor, training sees identical
data and any weight difference is CUDA nondeterminism, not the refactor.

## Step 0.4 — Tier 3, inference against a frozen checkpoint

```
python tools/golden.py record infer-613590-road -- \
    python notebooks/wellsight_v2/s4_infer/_road_infer.py \
      --checkpoint data/derivatives/tiles/9t/road_unet_1m_recall_relabeled20260806/best.pt \
      --features data/derivatives/tiles/data_3x3/westernpa_d20/613590/features_613590_1m.tif \
      --stats data/derivatives/tiles/9t/feature_stats_1m.json \
      --outdir data/derivatives/_golden_infer_check
```

Probability rasters must hash identical. Delete `_golden_infer_check` after.

## Step 0.5 — commit

`docs/golden/*.json`, `tools/golden.py`, `docs/golden/NON_DETERMINISTIC.md`.

**Phase 0 exit:** every Tier-1 script either verifies clean twice, or is listed
as non-deterministic with the reason.

---

# PHASE 1 — config, and 613590 road/drainage training

## Step 1.1 — `config/areas.toml`

Values below are measured, not invented.

```toml
[9t]
crs        = "EPSG:6346"
bbox       = [619500, 4593000, 624000, 4597500]
tiles      = "data/source_laz/westernpa/*17TPF6[12][0-9]*.laz"
dir        = "data/derivatives/tiles/9t"
ref_05     = "dem_9t_05.tif"
ref_1m     = "features_pit_9t_1m.tif"
block_m    = 375                  # 12 x 12 = 144 blocks, matches pit_blocks_9t.gpkg
resolutions = [0.5, 1.0]

[613590]
crs        = "EPSG:6346"
bbox       = [613500, 4590000, 618000, 4594500]
tiles      = "data/source_laz/westernpa/*17TPF6[01][0-9]*.laz"
dir        = "data/derivatives/tiles/data_3x3/westernpa_d20/613590"
ref_1m     = "features_613590_1m.tif"
block_m    = 375                  # same 4500 m extent -> same 12 x 12 grid
resolutions = [1.0]
targets    = ["road", "drainage"] # NO pads and NO pit rims exist here
```

## Step 1.2 — `config/targets.toml`

```toml
[road]
layers      = ["roads"]
negatives   = ["not_roads"]
third_class = "drainage"
classes     = 3            # 0 bg / 1 road / 2 drainage
buffer_m    = 1.5
chunk_m     = 40.0
match       = "length-coverage"
tol_m       = 5.0
cover_frac  = 0.5

[pit]
layers      = ["pit_inside"]      # the model draws FLOORS
match_layer = "union"             # scored against rim OR floor, per 2026-08-12
classes     = 3                   # 0 bg / 1 floor / 2 wall
min_area_m2 = 4.0
score_buf_m = 40.0
match       = "centroid-bidirectional"

[pad]
layers      = ["plat"]
classes     = 2
min_area_m2 = 100.0
score_buf_m = 80.0
match       = "centroid-bidirectional"

[split]
fracs = { train = 0.70, val = 0.15, test = 0.15 }
seed  = 42
```

**Verification:** `python -c "import tomllib;tomllib.load(open('config/areas.toml','rb'))"`
for both.

## Step 1.3 — extend `_common.py`

Add `area(name) -> dict` and `target(name) -> dict`, resolving relative paths
against `ROOT`. **Add only. Change nothing.** `ROOT`, `DERIV`, `DERIV_9T`,
`DST_CRS`, `PDAL_EXE`, `PATHS`, `path_for` keep their current values.

**Verification:**
```
python -c "
import sys;sys.path.insert(0,'notebooks/wellsight_v2')
from _common import ROOT,DERIV,DERIV_9T,DST_CRS,area,target
assert str(ROOT).endswith('lidar_project')
assert DERIV_9T == DERIV/'tiles'/'9t'
assert DST_CRS=='EPSG:6346'
assert area('613590')['bbox'][0]==613500
assert target('road')['buffer_m']==1.5
print('OK')"
python tools/golden.py verify <every Tier-1 script>     # must all still pass
```

## Step 1.4 — extract the block-grid builder

**The grid builder is not a separate script today.** `_build_pit_dataset.py`
generates the 12×12 375 m grid inline and writes `pit_blocks_9t.gpkg`
(columns `block_id, ix, iy, n_pits, split`; splits 77 train / 22 val / 16 test /
29 unused).

Create `s2_labels/_build_block_grid.py`:

```
python …/_build_block_grid.py --area 613590 --target road [--block-m 375] [--seed 42]
```

Lift the grid generation and the stratified split assignment verbatim from
`_build_pit_dataset.py`. `n_pits` becomes a generic `n_objects` column, with
`n_pits` retained as an alias so nothing downstream breaks.

**Verification — the important one:**
```
python …/_build_block_grid.py --area 9t --target pit --out /tmp/check_blocks.gpkg
# must be byte-identical in block_id, ix, iy, n_objects and split to
# data/derivatives/tiles/9t/pit_blocks_9t.gpkg
```
If the split assignment differs by even one block, the CV5 fold assignment
changes and every pit/pad number on the leaderboard moves. **Stop if it differs.**

## Step 1.5 — parameterise `_rebuild_labels_road_9t_1m.py`

Smallest of the three, so it goes first. Today:

```python
GRID   = D / "features_pit_9t_1m.tif"
OUT    = D / "labels_road_9t_1m.tif"
BACKUP = D / "labels_road_9t_1m_pre2026-08-06.tif"
```

Becomes `--area {9t,613590}`, resolving `GRID`/`OUT` from `areas.toml`, and
renamed `s2_labels/_build_road_labels.py` (it is no longer 9t-specific).
Keep buffers in `targets.toml`.

**Verification:**
```
python …/_build_road_labels.py --area 9t
# labels_road_9t_1m.tif must hash identical to its golden record.
# Expect 614,003 road px and 179,895 drainage px.
```

## Step 1.6 — generate 613590 road labels

```
python …/_build_block_grid.py   --area 613590 --target road
python …/_build_road_labels.py  --area 613590
```

Produces `labels_road_613590_1m.tif` and `road_blocks_613590.gpkg`.

**Verification — human, in QGIS, before anything trains on it:**
- load `hillshade_613590_1m.tif`, the new label raster, and `roads.shp`
- road pixels must sit on the drawn lines
- drainage must not be painted as road
- the block grid must cover the tile with no gaps
- confirm the road-pixel count is plausible: 187.6 km × 3 m ≈ 560,000 px

**Do not proceed to training until this is eyeballed.**

## Step 1.7 — parameterise `_build_plat_road_dataset.py`

Currently writes plat labels, road labels, road chunks, road manifest and the
classifier samples in one pass — five products, three targets. Split by
`--target`:

```
python …/_build_plat_road_dataset.py --area 9t --target road
python …/_build_plat_road_dataset.py --area 9t --target pad
```

`--target road` on 613590 produces `road_dataset_manifest_613590.csv` and
`road_chunks_613590.gpkg`.

**Verification:** `--area 9t --target road` and `--target pad` together must
reproduce the current outputs byte-for-byte. Expect 15,292 road chunks,
3,315 / 983 / 672 in-tile.

**Known trap:** this script also rewrites `plat_dataset_manifest.csv`, which is
still at 650 rows while `plat.shp` has 1,053. Running it regenerates the
manifest at 995+ and **changes the pad CV5 fold assignment**. Snapshot
`plat_dataset_manifest.csv` first and restore it, exactly as on 2026-08-06,
until the pad manifest question is settled separately.

## Step 1.8 — parameterise `_build_pit_dataset.py`

Same treatment. 613590 is not a valid `--area` for pits (0 rims), so the script
must **refuse** with a clear message rather than silently build a floor-only
dataset.

**Verification:** `--area 9t` reproduces `pit_dataset_manifest.csv` and
`pit_blocks_9t.gpkg` byte-identical. `--area 613590` exits non-zero with
"target `pit` requires layer `pit_outside`, which has 0 features in this area".

## Step 1.9 — train a road model on 9t + 613590

```
python …/s3_train/_road_unet_1m_recall.py --epochs 40 --areas 9t,613590 \
       --tag 9t_plus_613590
```

Requires `_road_unet_1m_recall.py` to accept `--areas` and concatenate datasets
— the pattern already exists in `_road_unet_1m_corrected.py`, which builds a
`ConcatDataset(9t, 613590)`. Reuse it rather than writing it again.

**Model selection stays on 9t val road IoU**, so the number remains comparable
to every previous road model.

## Step 1.10 — score it honestly

```
python …/s5_eval/_score_road_pred_vs_roads_shp_613590.py \
    --prob …/road_unet_1m_recall_9t_plus_613590/road_prob_613590_1m.tif \
    --label 9t_plus_613590
```

**This score is now circular** — the model trained on 613590. Record it, do not
quote it. The honest test becomes a **different** held-out block. Candidates
with existing derivative stacks: `618594`, `622594`, `609594`. Pick one, and
draw enough road on it to score against.

That is the real cost of consuming 613590 as training data: it stops being a
test set. Say so in `LEADERBOARD.md` when the row is added.

## Step 1.11 — documentation

- `docs/analysis_log.md` — new entry at top
- `docs/iterations/LEADERBOARD.md` — new road row, flagged as train-on-613590
- `docs/RUNBOOK.md` — Track B gains `--area`
- `config/*.toml` — comments naming the source of each value

## Step 1.12 — commit and re-verify

```
python tools/verify_paths.py
python tools/golden.py verify <all Tier-1>
git commit && git push origin refactor-package
```

**Phase 1 exit:** every Tier-1 golden still passes, 9t outputs unchanged, and a
road model trained on both areas exists with an honest caveat recorded.

---

# PHASE 2 — extract the shared core

> **AMENDED 2026-08-12 after reading the code — see `REFACTOR_REVIEW.md`.**
> Two thirds of the core already exists: `_dl.py` (379 LOC, 14 importers) is
> `core/models.py`, and `_common.py` (67 importers) is `core/io.py`. The order
> below is revised, and two steps that were missing entirely are now first.
>
> **Step 2.0 — `core/vector.py` <- `polygonize`.** Defined in **9 files**,
> referenced in **18**. Five textual variants, all behaviourally identical
> (parameter name, a moved import, early-return style). Provably safe, biggest
> reach, so it goes first and doubles as a test of the golden harness.
>
> **Step 2.1 — `core/folds.py` <- `assign_folds`.** Four `s5_eval` scripts
> currently do `from _pit_unet_cv5 import assign_folds, polygonize`. Eval imports
> a TRAINER, which drags in torch to compute a fold assignment.
>
> **Step 2.2 — eval constants out of the trainers.** `_pit_cv5_tau_scale.py` and
> `_pad_cv5_tau_scale.py` import `ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR,
> SCORE_BUF_M` from the trainer, so the trainer is also the eval config module
> and a training constant silently moves an eval result. Move them to
> `config/*.toml`.
>
> **This is a hard prerequisite for Phase 3.** Phase 3 merges `_pit_unet_cv5`
> and `_pad_unet_cv5` into `train.py --target`; **six scripts import those module
> names directly** and would break. The original Phase 3 did not mention it.
>
> Steps 2.3-2.6 below then follow: matching, metrics, models (a rename), labels.

## Step 2.3 — `core/matching.py`

The single highest-value extraction. Centroid containment, bidirectional
matching, greedy 1:1, log-space size filtering currently exist in four separate
copies, and the NULL-`pit_id` defect lived in three of them at once.

Consumers to repoint: `_match_rules_pit_pad_9t.py`,
`_cv5_centroid_precision_pit_pad_9t.py`, `_map_cv5_unmatched_pit_thr0p50_9t.py`,
`_build_undecided_pit_candidates_9t.py`.

The extracted module must implement the **corrected** behaviour: key on
`pit_id` where present and `pit_id_outer` otherwise, so no rim is dropped.

**Verification:** golden-verify all four consumers. Three of them will
**legitimately change** — they currently use the buggy `dissolve(by="pit_id")`.
So: record a *new* golden for those three, and document the delta in
`analysis_log.md` as a metric correction, with old and new numbers side by side.
`_build_undecided_pit_candidates_9t.py` already has the fix and **must not
change** — it is the control.

## Step 2.4 — `core/metrics.py`

P/R/F1 and the Wiedemann completeness/correctness/quality triple.
Consumers: the three `*_threshold_products_9t.py`, `_score_road_pred_*`,
`_road_optimize.py`. Pure functions, no I/O. Golden must be unchanged.

## Step 2.5 — `core/models.py` (a RENAME: `_dl.py` already is this)

Move `_dl.py`'s `UNet`, `FocalCE`, `train_loop`, `predict_full_tile`,
`CenteredPatchSampler` in as-is, then add MaskRCNN and YOLO behind the same
interface. `_dl.py` becomes a shim re-exporting from `core.models` so the
existing 20-odd importers keep working during migration.

**Verification:** Tier-2 input hashes unchanged; one short training run
(2 epochs) before and after must produce the same loss at epoch 1 with a fixed
seed on CPU.

## Step 2.6 — `core/labels.py`

Rasterisation, chunking, block-grid generation, split assignment — from
`_build_pit_dataset.py`, `_build_plat_road_dataset.py`, `_build_block_grid.py`.
Golden must be unchanged.

---

# PHASE 3 — collapse the twins

Only where measured similarity exceeds 50%. Each merge: build the merged script,
golden-verify **both** original invocations against it, then archive the
originals through `tools/apply_moves.py` (never delete).

| New | Replaces | Similarity |
|---|---|---:|
| `train.py --target {pit,pad} --arch unet --cv 5` | `_pit_unet_cv5`, `_pad_unet_cv5` | 72% |
| `eval_tau.py --target {pit,pad}` | `_pit_cv5_tau_scale`, `_pad_cv5_tau_scale` | 77% |
| `train.py --arch yolo` | `_pit_yolo`, `_pad_yolo` | 67% |
| `train.py --arch maskrcnn` | `_pit_maskrcnn`, `_pad_maskrcnn` | 52% |
| `infer.py --arch {yolo,maskrcnn}` | the four matching infer scripts | 37–59% |
| `corrections_diff.py --target {pit,road}` | `_pit_corrections_diff`, `_road_corrections_diff` | 60% |

12 scripts → 5.

---

# PHASE 4 — package and CLI

## Step 4.1 — `pyproject.toml`, `pip install -e .`
## Step 4.2 — `wellsight/cli.py` dispatching build / label / train / infer / eval / review
## Step 4.3 — delete the 167 `sys.path.insert(parents[N])` calls; imports become `from wellsight.core import matching`
## Step 4.4 — update `ui/registry.py`, `roads_studio/`, every `Reproduce:` docstring, `RUNBOOK.md`

**Blocking:** this changes how every script is invoked. Do it at a quiet point.

---

## Verification summary — run after every step

```
python tools/verify_paths.py                       # leaks, QGIS, path constants
python tools/golden.py verify <affected scripts>   # numeric output unchanged
python -m py_compile $(git ls-files '*.py')        # nothing broken
```

## Rollback

Every file move goes through `tools/apply_moves.py`, logged to `docs/MOVES.csv`:

```
python tools/apply_moves.py --undo --phase <phase>
```

Code edits are reverted with `git checkout`. The branch is never merged until
Phase 1 exits clean.

---

## What is out of scope

`s7_analysis/` (12 one-off science scripts), the threshold-products trio
(14–16% similar — blobs and lines are different problems), the optimisers (24%),
the review-package builders (22–27%), and `notebooks/wellsight/` (51 v1 scripts,
frozen). Reasons in `REFACTOR_PLAN.md` §5.

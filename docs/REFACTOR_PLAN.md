# WellSight refactor plan — from 92 scripts to a parameterised package

**Written:** 2026-08-12
**Status:** proposal. Nothing started.
**Governing constraint:** every number in `docs/iterations/LEADERBOARD.md` was
produced by a specific script. A refactor that changes behaviour invalidates
them silently. Nothing moves without a proven-identical output.

---

## 1. The problem, measured

### 1.1 Nothing is area-agnostic

| | Count |
|---|---:|
| Scripts taking an area argument with no hardcoded area | **0 of 92** |
| Scripts taking an argument *and* hardcoding an area | 14 |
| **Scripts with no area argument at all** | **78** |

`_build_derivatives.py` is the closest thing to generic — it takes
`--tiles --bbox --suffix --res` — and even it hardcodes the merge output to
`source_laz/westernpa/` on line 162 regardless of region.

### 1.2 The same operation is written once per target

| Pair | Identical | LOC each |
|---|---:|---:|
| `_pit_cv5_tau_scale` / `_pad_cv5_tau_scale` | **77%** | 88 |
| `_pit_unet_cv5` / `_pad_unet_cv5` | **72%** | 383 |
| `_pit_yolo` / `_pad_yolo` | 67% | 61 |
| `_pit_corrections_diff` / `_road_corrections_diff` | 60% | 82 |
| `_pit_yolo_infer` / `_pad_yolo_infer` | 59% | 52 |
| `_pit_maskrcnn` / `_pad_maskrcnn` | 52% | 118 |

~742 duplicated lines across twelve pairs.

### 1.3 The real cost is drift, not line count

`_pit_threshold_products_9t.py` and `_pad_threshold_products_9t.py` began as
copies and are now **16% similar**. A fix to one does not reach the other.

That is not hypothetical. The NULL-`pit_id` defect — where
`dissolve(by="pit_id")` silently discarded 138 annotated rims — existed
simultaneously in `_match_rules_pit_pad_9t.py`,
`_cv5_centroid_precision_pit_pad_9t.py` and
`_map_cv5_unmatched_pit_thr0p50_9t.py`, because each carries its own copy of the
matching logic. Every published pit precision and recall figure was computed
against 138 missing rims.

### 1.4 The concrete consequence

613590 has **187.6 km of road, 403 pads and 152 pits** drawn and invisible to
training. Not a data problem — a hardcoding problem:

| Script | `9t` references | CLI arguments |
|---|---:|---:|
| `_build_pit_dataset.py` | 11 | **0** |
| `_build_plat_road_dataset.py` | 12 | **0** |
| `_rebuild_labels_road_9t_1m.py` | 11 | **0** |

There is no way to point them at another tile.

---

## 2. Target architecture

```
wellsight/
├── config/
│   ├── areas.toml     # per area: tiles glob, bbox, res, block grid, splits
│   └── targets.toml   # per target: annotation layers, classes, buffers,
│                      #             thresholds, match rule, min area
├── core/              # pure functions. no globals, no CLI, no I/O assumptions
│   ├── terrain.py     # openness, lrm, tpi, slope, roughness
│   ├── labels.py      # annotation -> label raster + manifest + block splits
│   ├── models.py      # UNet / MaskRCNN / YOLO behind one interface
│   ├── matching.py    # centroid, IoU, greedy 1:1 -- ONE implementation
│   ├── metrics.py     # P/R/F1; completeness/correctness/quality
│   └── vector.py      # skeletonize, prune, merge, chunk
└── cli.py             # wellsight <verb> --area X --target Y
```

```
wellsight build  --area 613590
wellsight label  --area 613590 --target road
wellsight train  --area 9t     --target pit  --arch unet --cv 5
wellsight infer  --area 613590 --model road_unet_1m_recall_relabeled20260806
wellsight eval   --area 613590 --target road
wellsight review --area 613590 --target road
```

A new tile becomes a row in `areas.toml`. A new target becomes a row in
`targets.toml`. Neither requires a new file.

### 2.1 The two config schemas

```toml
# areas.toml
[9t]
tiles   = "data/source_laz/westernpa/*17TPF6[12][0-9]*.laz"
bbox    = [619500, 4593000, 624000, 4597500]
res     = [0.5, 1.0]
blocks  = "data/derivatives/tiles/9t/pit_blocks_9t.gpkg"
crs     = "EPSG:6346"

[613590]
tiles   = "data/source_laz/westernpa/*17TPF6[01][0-9]*.laz"
bbox    = [613500, 4590000, 618000, 4594500]
res     = [1.0]
blocks  = ""            # <- does not exist yet; Phase 1 builds it
```

```toml
# targets.toml
[pit]
layers      = ["pit_inside", "pit_outside"]
predicts    = "pit_inside"      # the model draws floors
matches_on  = "union"           # scored against rim OR floor
classes     = 3                 # bg / floor / wall
min_area_m2 = 4.0
match       = "centroid-bidirectional"

[road]
layers      = ["roads", "not_roads", "drainage"]
classes     = 3                 # bg / road / drainage
buffer_m    = 1.5
chunk_m     = 40.0
match       = "length-coverage"
tol_m       = 5.0
```

---

## 3. The non-negotiable: golden outputs

No extraction happens without proof the output is unchanged.

**`tools/golden.py`** — two modes:

```
python tools/golden.py --record <script>    # run it, hash every artifact it writes
python tools/golden.py --verify <script>    # re-run, compare against the record
```

Hashes land in `docs/golden/<script>.json`. Any difference stops the refactor.

### 3.1 Three tiers, because not everything is bit-reproducible

| Tier | Scripts | What is verified |
|---|---|---|
| **1 — deterministic** | eval, label builders, matching, vectorising | Full byte-level hash of every output. ~30 scripts. |
| **2 — training** | the U-Net / MaskRCNN / YOLO trainers | Weights are **not** bit-reproducible on CUDA. Verify the *inputs*: feature stack hash, label raster hash, manifest hash, fold assignment. If the data going in is identical, the refactor did not change training. |
| **3 — inference** | `_predict_on_tile`, `_road_infer` | Run against a **frozen checkpoint**; probability rasters must hash identical. |

This is the same discipline that caught the feature-stack overwrite on
2026-08-12: hash before, hash after, compare.

---

## 4. Phases

Each phase is independently revertible via `docs/MOVES.csv` and
`tools/apply_moves.py --undo`, and each ends with the three existing gates
(`tools/verify_paths.py`) plus golden verification.

### Phase 0 — the harness (1 session)

| Deliverable | Purpose |
|---|---|
| `tools/golden.py` | record / verify, three tiers |
| `docs/golden/*.json` | baseline for the ~30 Tier-1 scripts |
| Branch `refactor-package` | isolation |

**Nothing changes.** Exit criterion: `--verify` passes on every Tier-1 script
against a freshly recorded baseline, twice in a row (proves the scripts are
themselves deterministic — any that are not get flagged and excluded).

### Phase 1 — config, and unlock 613590 (1–2 sessions)

The highest-value phase. No code is restructured; constants become config.

1. `config/areas.toml`, `config/targets.toml` with `9t` and `613590` populated.
2. `_common.py` gains `area(name)` and `target(name)` accessors alongside the
   existing exports. All 67 importers unaffected.
3. **New:** `s2_labels/_build_block_grid.py --area X` — generates the block grid
   and train/val/test split for any area. This is the genuinely missing piece;
   613590 has a feature stack and annotation but no grid.
4. Parameterise the three blockers: `_build_pit_dataset.py`,
   `_build_plat_road_dataset.py`, `_rebuild_labels_road_9t_1m.py` →
   `--area {9t,613590}`, defaulting to `9t`.

**Verification:** run each with `--area 9t`, golden-verify byte-identical to the
pre-change baseline. Then run `--area 613590` and inspect the new labels in QGIS
before training on them.

**What this buys:** 187.6 km of road, 403 pads and 152 pits become trainable.
The road model's weakest class — faint roads — is exactly what 613590 holds.

### Phase 2 — extract the shared core (2–3 sessions)

In this order, highest bug-risk first:

1. **`core/matching.py`** — centroid containment, bidirectional, greedy 1:1,
   size filtering. Currently duplicated across four eval scripts and the site of
   the NULL-`pit_id` defect. One implementation, one place to fix.
2. **`core/metrics.py`** — P/R/F1 and the Wiedemann completeness/correctness/
   quality triple.
3. **`core/models.py`** — the U-Net/loss/train-loop currently in `_dl.py`, plus
   the MaskRCNN and YOLO wrappers, behind one interface.
4. **`core/labels.py`** — rasterisation, chunking, block splits.

Each extraction: move the function, leave the old script importing it, golden-
verify, commit. The scripts keep working; they just stop carrying their own copy.

### Phase 3 — collapse the twins (1–2 sessions)

Only where measured similarity exceeds 50%:

| Merge into | From |
|---|---|
| `train.py --target {pit,pad} --arch unet --cv 5` | `_pit_unet_cv5`, `_pad_unet_cv5` (72%) |
| `eval_tau.py --target {pit,pad}` | `_pit_cv5_tau_scale`, `_pad_cv5_tau_scale` (77%) |
| `train.py --arch yolo` | `_pit_yolo`, `_pad_yolo` (67%) |
| `train.py --arch maskrcnn` | `_pit_maskrcnn`, `_pad_maskrcnn` (52%) |
| `infer.py --arch {yolo,maskrcnn}` | the four matching infer scripts |
| `corrections_diff.py --target {pit,road}` | `_pit_corrections_diff`, `_road_corrections_diff` (60%) |

~12 scripts become ~5.

### Phase 4 — the CLI (1 session)

`wellsight/cli.py` dispatching to the ops. Thin; all logic already lives in
`core/`. `pyproject.toml` so `pip install -e .` puts `wellsight` on PATH and the
`sys.path.insert(parents[N])` pattern disappears entirely.

---

## 5. What deliberately does NOT change

Merging these would be worse than the duplication:

| Kept separate | Similarity | Why |
|---|---:|---|
| `_pit_/_pad_/_road_threshold_products_9t` | 14–16% | Pits are blobs scored by containment; roads are lines scored by length coverage. Genuinely different problems. |
| `_pit_optimize` / `_road_optimize` | 24% | Different post-processing algorithms entirely. |
| The three review-package builders | 22–27% | Different QGIS layer structures per target. |
| `s7_analysis/` (12 scripts) | — | One-off science. Consolidating exploratory work removes its value. |
| `notebooks/wellsight/` (51 v1 scripts) | — | Frozen. Not touched by this plan. |

---

## 6. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| A refactor silently moves a published number | **Critical** | Golden harness, Phase 0, before anything else |
| Training is not bit-reproducible, so "unchanged" cannot be proven | High | Tier 2 verifies inputs, not weights. Stated explicitly, not papered over. |
| A Tier-1 script turns out to be non-deterministic | Medium | Phase 0 runs each twice; non-deterministic ones are excluded and listed |
| Refactor collides with in-flight analysis | Medium | Branch `refactor-package`, merge at a quiet point |
| Scope creep into `s7_analysis` | Medium | Explicitly out of scope, §5 |
| 613590 labels are wrong and training on them is worse than not | Medium | Phase 1 stops at label generation; inspect in QGIS before training |

---

## 7. Effort

| Phase | Sessions | Reversible | Blocking |
|---|---|---|---|
| 0 — harness | 1 | n/a | no |
| 1 — config + 613590 | 1–2 | yes | no |
| 2 — extract core | 2–3 | yes | no |
| 3 — collapse twins | 1–2 | yes | no |
| 4 — CLI + package | 1 | yes | **yes** — import style changes |

**Phases 0–1 are the ones worth doing regardless.** They cost two or three
sessions, change no behaviour, and turn existing annotation into training data.
Phases 2–4 are cleanup; valuable, but they buy maintainability rather than
results.

Stopping after Phase 1 is a legitimate outcome.

---

## 8. Open decisions

1. **Package name and import style.** `wellsight` as an installed package
   (`pip install -e .`) removes 167 `sys.path.insert` calls but changes how every
   script is invoked. Do it in Phase 4, or leave the scripts standalone?
2. **Do the retired architectures come along?** Mask R-CNN and YOLO lost the
   bake-off but `LEADERBOARD.md` cites their numbers. Refactor them into
   `--arch`, or freeze them where they are?
3. **Phase 1 only, or the whole thing?**

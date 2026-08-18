# WellSight Repository Reorganization Plan

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

**Written:** 2026-08-12
**Status:** decisions taken, Phase 0 in progress. Nothing moved yet.
**Governing constraint:** file paths are respected. Nothing is deleted.

---

## Decisions taken 2026-08-12

| # | Decision | Effect |
|---|---|---|
| 1 | **Phases 0–3 now.** Phase 4 deferred, not cancelled. | The `data/derivatives/tiles/...` skeleton stays put, so the 57 QGIS layer paths and ~60 `.gitignore` rules keep working untouched. Risk drops sharply. |
| 2 | **Archive the Permian / Ramachandran thread.** | 8.3 GB, 87,538 files leave the working tree. Repository file count drops by ~86%. |
| 3 | **Archive Barlow.** Proposal is submitted. | 1.5 GB out of the root; release the ~50 GB `barlow_data/` reservation in `.gitignore`. |
| 4 | **E: is the only backup, and it is labelled as one.** | See §8, rewritten. |

### F: no longer exists

F: was mounted on 2026-08-05 and 2026-08-06, when two backups were written to
`F:\lidar_project`. As of 2026-08-12 the drive is **not present** — only C, D, E and
G are mounted. That copy is on a disconnected or removed disk and cannot be relied on.

Every reference to F: in this plan is superseded by §8. `backup_to_F.bat` is not
created. Phase 6 is replaced by §8.

---

## 0. Executive summary

The repository is 122 GB across 101,000 files. It is not disorganized by accident.
It grew one experiment at a time, and each experiment wrote where it was convenient.

Three things make it hard to use today:

1. **457 files sit loose in two directories that should hold only subdirectories.**
   282 files (7.5 GB) directly in `data/derivatives/`, and 175 files (8.6 GB)
   directly in `data/derivatives/tiles/9t/`.
2. **Three parallel copies of the codebase exist.** Only one is live.
3. **There is no separation between immutable input, regenerable output, and
   result.** All three sit at the same level under `data/derivatives/`.

The good news is that the code is far less path-coupled than the file tree suggests.
**Exactly two Python files hardcode an absolute path**, out of 92 live scripts:

* `notebooks/wellsight_v2/_common.py:38` — `ROOT = C:\Users\colto\Documents\GitHub\lidar_project`. This is the intended anchor.
* `notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py:79` — `OLD_DIR = F:\lidar_project\consolidated\lidar_all`. **This one is already broken.** F: is no longer mounted, so that script cannot run today.

Everything else derives from `_common`. That is what makes a restructure safe.

(An earlier draft of this document claimed zero hardcoded paths outside `_common.py`.
That claim came from a grep for `C:\Users` and missed the `F:` literal. Gate C found
it. The tooling caught an error the survey did not, which is the argument for the
tooling.)

The bad news is that two non-Python systems are heavily path-coupled and will break
silently rather than loudly:

* `qgis/wellsight.qgz` binds **57 of its 59 layers** by relative path into
  `data/derivatives/`.
* `.gitignore` carries roughly **60 path-anchored rules**. If a directory moves and
  its rule does not, a 100 MB raster enters git history on the next commit.

This plan therefore builds tooling before it moves anything.

---

## 1. What is actually there

### 1.1 Size and shape

| Directory | Size | Files | Note |
|---|---:|---:|---|
| `data/derivatives/` | 96.3 GB | 12,032 | the working tree |
| `data/source_laz/` | 18.1 GB | 306 | raw lidar, immutable |
| `data/external/` | 7.6 GB | 87,599 | **86% of all files in the repo** |
| `label_grids/` | 5.1 GB | 211 | annotation grids, 8 areas |
| `barlow/` | 1.5 GB | 911 | FINESST proposal, not lidar analysis |
| `docs/` | 330 MB | 124 | |
| `literature/` | 64 MB | 17 | |
| `notebooks/` | 42 MB | 289 | three code trees, see 1.3 |
| `models/`, `roads_studio/`, `ui/`, `tests/`, `archive/`, `qgis/` | < 40 MB each | | |
| `barlow_data/` | 0 | **0** | empty, but `.gitignore` reserves ~50 GB for it |

`data/external/ramachandran_2024/` alone holds **87,535 files** (5.2 GB). It is 86%
of the repository's file count. Every backup run walks it. Every `find` walks it.

### 1.2 The loose-file problem

`data/derivatives/` should contain directories. It contains 282 loose files:

| Type | Count | Note |
|---|---:|---|
| `.tif` | 182 | belong in `tiles/<area>/` |
| `.png` | 62 | quicklooks and figures |
| `.gpkg` | 16 | some are live, some are dead |
| `.gpkg-wal` / `.gpkg-shm` | 6 | QGIS transaction sidecars, should never persist |
| other | 16 | logs, txt, one `.pt`, one `.csv` |

The 182 loose `.tif` files carry study-area suffixes, and every one of those areas
**already has a proper home** under `data/derivatives/tiles/`:

| Suffix | Count | Correct home |
|---|---:|---|
| `_9t_1m` | 34 | `tiles/9t/` |
| `_mk5_1m` | 30 | `tiles/mk5_1m/` (does not exist yet) |
| `_mck_e1423n2238_05` | 29 | `tiles/mckean/e1423n2238_05/` |
| `_616593_1m` | 19 | `tiles/data_3x3/westernpa_d20/616593/` |
| `_610605_1m` | 19 | same pattern |
| `_610594_1m` | 19 | same pattern |
| `_607594_1m` | 19 | same pattern |

`tiles/9t/` has the same problem one level down: 175 loose files, 8.6 GB. **These
are not equivalent.** Many `tiles/9t/` loose files are live pipeline inputs
(`features_pit_9t_1m.tif`, `labels_road_9t_1m.tif`, `pit_blocks_9t.gpkg`, the
manifests). They must not be moved blindly.

### 1.3 Three code trees

| Tree | `.py` files | Live? | Evidence |
|---|---:|---|---|
| `notebooks/wellsight_v2/` | 92 | **yes** | 154 in-repo references |
| `notebooks/wellsight/` | 88 | **no** | zero references from live code; 34 files byte-identical to their v2 twin |
| `archive/wellsight/` | 73 | no | already archived; zero filename overlap with `notebooks/wellsight/` |

`notebooks/wellsight/` is a complete v1 snapshot that was never archived. It is
referenced only from prose in `docs/` and from `archive/`.

### 1.4 Naming inconsistencies

The same concept is spelled several ways:

* `mkf_1m` and `mkf_road_1m` are different things with near-identical names.
* `mckean_sw_05` and `mckean_sw_1m` split by resolution; `613590_05` and
  `data_3x3/westernpa_d20/613590` split the same tile by **parent directory**
  instead. One tile lives in two places under two rules.
* `eval_9t_centroid_matching`, `eval_9t_heldout_overlap`, `eval_9t_instance_precision`,
  `eval_9t_pad_thresholds`, `eval_9t_pit_thresholds`, `eval_9t_rim_containment`,
  `eval_9t_road_thresholds`, `eval_9t_uncounted_wells`, `eval_613590_roads` are nine
  siblings of one category, flat at the top of `data/derivatives/`.

### 1.5 Duplicated large files

Seven confirmed duplicate pairs over 50 MB, roughly 600 MB:

| File | Copies | Each |
|---|---:|---:|
| `twi_9t_1m.tif` | 2 | 77 MB |
| `best.pt` (plat_03 / road_03) | 2 | 93 MB |
| `best.pt` (plat_02 / road_02) | 2 | 93 MB |
| `best.pt` (pad_06_yolo, dir + `run/weights/`) | 2 | 90 MB |
| `best.pt` (pit_08_yolo, dir + `run/weights/`) | 2 | 90 MB |
| `road_prob_613590_1m.tif` | 2 | 64 MB |
| `drainage_prob_613590_1m.tif` | 2 | 65 MB |

The `plat_02`/`road_02` and `plat_03`/`road_03` pairs are the interesting ones. Two
differently-named model directories hold byte-identical checkpoints. Either one
model was copied into both, or the training script wrote to the wrong place. This
needs a decision from you, not a guess from me.

### 1.6 Top-level clutter

`bad roads.png`, `original roads.png`, `roads_prob.png`, `distorted_river.jpg`,
`stream_bottom.jpg`, `scratchpad_tiles_613590.txt`, `downloadlist 2006-2008 laz.txt`,
`yolo26n.pt`, and three `backup_to_*_last_run.log` files sit in the repository root.

---

## 2. The path-coupling inventory

This is the section that governs everything else. Six mechanisms bind paths.

| # | Mechanism | Instances | Breaks when | Detectable? |
|---|---|---:|---|---|
| 1 | `qgis/wellsight.qgz` relative `<datasource>` | 57 of 59 layers | any data file moves | only by opening QGIS |
| 2 | `.gitignore` path-anchored rules | ~60 | any data directory moves | **silent — file enters git** |
| 3 | `sys.path.insert(parents[N])` | 93 uses | a **script** changes depth | import error, loud |
| 4 | `_common.py` constants | 67 of 92 scripts import | `DERIV` / `DERIV_9T` target moves | one file, loud |
| 5 | Per-script literal subpaths | 25 scripts self-roll `ROOT` | their specific directory moves | loud |
| 6 | `E:` and `F:` robocopy mirrors | 2 targets | the tree changes shape | silent duplication |

Three consequences follow directly.

**Scripts must not change depth.** `parents[3]` from
`notebooks/wellsight_v2/eval/x.py` resolves to the repository root. Move that script
one level and it silently resolves to the wrong directory, or crashes. 27 scripts use
`parents[3]`, 63 use `parents[1]`, 3 use `parents[2]`. **Recommendation: do not
reorganize `notebooks/` at all in this pass, beyond retiring the dead trees.** The
benefit is small and the blast radius is the whole pipeline.

**`.gitignore` is the highest-risk item, because it fails silently.** The CLAUDE.md
Large-file rule exists because this has bitten before. Every phase below ends with
the leak audit, and no phase is complete until it prints nothing.

**QGIS is the highest-effort item, but it is scriptable.** A `.qgz` is a ZIP holding
one `.qgs` XML file. Datasources can be rewritten programmatically and the archive
repacked. A tool for this is Phase 0 work.

One incidental finding: one QGIS layer points at `../../../bold_roads.shp`, which
resolves to `C:\Users\colto\Documents\bold_roads.shp` — outside the repository. The
real file is `data/derivatives/annotations/bold_roads.shp`. That layer is already
broken and should be repointed during the rewrite.

---

## 3. What is obsolete

The instruction was explicit. Obsolete means **superseded**, not **untouched for a
while**. I split the candidates three ways, and only the first group is obsolete.

### 3.1 Obsolete — superseded, with documentary evidence

| Item | Size | Evidence |
|---|---:|---|
| `notebooks/wellsight/` | 12 MB | superseded by `wellsight_v2`; zero live references; 34 files byte-identical to their v2 twin |
| `data/derivatives/tiles/road_multiblock/` | 241 MB | `LEADERBOARD.md`: "**Rejected.** … Diluting the dense 9t core hurt." |
| `road_unet_1m/best.pt.2class.BAK` | 93 MB | superseded 2026-06-08 by the 3-class in-model fix |
| `road_unet_1m/best.pt.3class_nochunk.BAK` | 93 MB | superseded by the chunked 3-class model |
| `road_unet/best.pt.BAK` | 93 MB | 0.5 m two-class lineage, retired |
| `annotations_proj.gpkg.BAK` | 0.4 MB | pre-`pad_id` schema |
| `annotations_proj.gpkg.preDrainage.BAK` | 2.6 MB | pre-drainage-layer schema |
| `road_dataset_manifest.csv.BAK` | small | superseded by the 2026-08-06 rebuild |
| stale `roads_<key>_1m.gpkg` / `road_clean_*` | varies | `BACKLOG.md`: "are obsolete and can be deleted" |
| ICP change-detection Part-2 outputs | varies | `BACKLOG.md`: "[STALE 2026-07-31] Part 2 outputs derive from the superseded DoD" |
| pit/pad IoU-strictness eval outputs | ~50 MB | `BACKLOG.md`: "[METRIC] IoU is retired for pits and pads" |
| `tiles/9t/diagnostics/twi_9t_1m.tif` | 77 MB | exact duplicate of `tiles/9t/twi_9t_1m.tif` |
| `*.gpkg-wal`, `*.gpkg-shm` in `data/derivatives/` | 6 files | QGIS transaction sidecars, never valid to keep |

**Deliberate backups that look obsolete but are not.** These were created on purpose
during a documented change and are the only record of the prior state. They belong in
the archive, labelled, not discarded:
`labels_road_9t_1m_pre2026-08-06.tif`, `_backup_pit_ann426_2026-06-10/` (1.5 GB),
`_snapshot_plat_artifacts_2026-08-06/`, `annotations/_backup_2026-06-10/`,
`annotations/_backup_roads_2026-08-05/`, the `*_ORIGINAL.gpkg` review packages.

### 3.2 Superseded but still cited — archive in place, keep reachable

`data/derivatives/tiles/9t/iterations/` is 12.6 GB across 9,055 files: `01_tta_miou`
through `06_dem_only`, `plat_01`–`plat_04`, `road_01`–`road_04`, `pit_07_maskrcnn`,
`pit_08_yolo`, `pad_05_maskrcnn`, `pad_06_yolo`, and three road post-filter variants.

Every one is superseded by `pit_unet_cv5` / `pad_unet_cv5` / `road_unet_1m_*`. But
`LEADERBOARD.md` cites their numbers, and the current git branch is literally named
`pit-iter-06-dem-only`. **Do not move these.** Add a `README.md` inside `iterations/`
that states they are superseded and points to the current model. Cost: one file.
Benefit: the next reader stops wondering.

### 3.3 Parked by decision — archived, not deleted

These are quiet because a human decided to stop, not because something replaced them.
That is a research decision, and it was taken on 2026-08-12.

| Thread | Size | Files | Decision |
|---|---:|---:|---|
| Permian / Ramachandran (`data/external/ramachandran_2024`, `label_grids/permian_*`) | 8.3 GB | 87,538 | **Archive.** Removes ~86% of the repository's file count. |
| Barlow FINESST (`barlow/`, `barlow_data/`) | 1.5 GB | 911 | **Archive.** Proposal submitted. Release the `barlow_data/` `.gitignore` reservation. |
| McKean (`mckean_sw_05`, `mckean_sw_1m`, `mkf_1m`, `mkf_road_1m`) | 4.9 GB | 92 | **Leave in place** for now. "McKean set aside per advisor 2026-07", but `mkf_road_1m` fed the `cldice_mkf` sweep variant that is still on the leaderboard. Not asked, not assumed. |

Archiving here means **moved into `data/99_archive/` with a manifest row**. Nothing is
deleted, and both are recoverable with `tools/undo_moves.py`.

Two notes on the Permian archive:

* `data/external/ramachandran_2024/` is 87,535 of the 87,538 files. Almost all are
  NAIP image chips. Moving them is a rename on the same volume, so it is fast.
* `label_grids/permian_01/pad_unet_xfer/` already has its own `.gitignore` rule. That
  rule must be re-anchored to the archive path in the same change, or the leak audit
  will start reporting.

---

## 4. Design principles for the target structure

1. **Separate by role in the pipeline, not by date.** Source, truth, derived, model,
   result. A reader should be able to tell what a directory is for from its name.
2. **Immutable input never shares a parent with regenerable output.** This one
   distinction drives backup policy, `.gitignore` policy, and disaster recovery.
3. **One canonical home per artifact class.** No artifact class appears at two depths.
4. **Study area is a first-class, consistently-spelled dimension.**
5. **Regenerability is metadata, not folklore.** Every derived directory carries a
   `_PROVENANCE.json` naming the script and inputs that rebuild it.
6. **Scripts do not move.** Depth coupling (`parents[N]`) makes the risk-to-benefit
   ratio indefensible in this pass.

---

## 5. Target structure

```
lidar_project/
├── config/
│   └── paths.toml                 # NEW single source of truth (see §6.3)
├── data/
│   ├── 01_source/                 # immutable; pipeline never writes here
│   │   ├── lidar/                 #   was data/source_laz/
│   │   └── reference/             #   was data/external/ (DEP, TIGER, land cover)
│   ├── 02_truth/                  # hand annotation only
│   │   └── annotations/           #   was data/derivatives/annotations/
│   ├── 03_derived/                # regenerable rasters, by area then resolution
│   │   ├── 9t/{05,1m}/
│   │   ├── westernpa_d20/<block>/
│   │   ├── mckean/<tile>/
│   │   └── _loose_intake/         #   staging for the 282 + 175 loose files
│   ├── 04_models/                 # checkpoints, train logs, per-model prob rasters
│   │   ├── pit/  pad/  road/  drainage/  multitask/
│   ├── 05_results/                # eval outputs and candidate layers
│   │   ├── eval_9t/               #   the nine flat eval_* dirs, nested
│   │   └── eval_613590/
│   ├── 06_experiments/            # was data/derivatives/experiments/
│   └── 99_archive/                # superseded; never deleted
│       ├── code/                  #   notebooks/wellsight/, archive/wellsight/
│       ├── data/                  #   road_multiblock, *.BAK, retired-metric evals
│       └── ARCHIVE_MANIFEST.csv   #   what, when, why, what replaced it
├── notebooks/wellsight_v2/        # UNCHANGED — depth is load-bearing
├── docs/  literature/  qgis/  ui/  roads_studio/  tests/  models/
└── tools/                         # backup .bat, launchers, path utilities
```

Two deliberate departures from a textbook layout:

* **`notebooks/wellsight_v2/` keeps its name and depth.** A textbook layout would call
  it `src/`. The rename costs 93 `parents[N]` edits and buys a nicer noun.
* **`data/99_archive/` sits inside `data/`, not at the repository root.** The existing
  root `archive/` already holds code. Data archives belong next to data, and the
  existing `.gitignore` archive rules already anticipate this shape.

---

## 6. Phased execution

Every phase is independently revertible. Every phase ends with the same three gates.

**Gate A — git leak audit.** Must print nothing:
```bash
find . -type f -size +100M -not -path './.git/*' | while read f; do \
  [ -z "$(git check-ignore "$f")" ] && echo "LEAKING: $f"; done
```
**Gate B — QGIS resolves.** `tools/verify_qgis_paths.py` opens `wellsight.qgz` and
confirms every `<datasource>` resolves to a file that exists.
**Gate C — scripts import.** `tools/verify_script_paths.py` compiles every `.py` under
`notebooks/wellsight_v2/`, `ui/`, `roads_studio/`, resolves its module-level `Path`
constants, and reports any that no longer exist.

### Phase 0 — Build the safety net (nothing moves)

| Deliverable | Purpose |
|---|---|
| `tools/build_reference_index.py` | Scan every `.py`, `.md`, `.bat`, `.qgz`, `.json` for path literals. Emit `docs/reference_index.csv`: `path, referenced_by, reference_count`. **A file with zero references is a move candidate. A file with references is not.** |
| `tools/verify_qgis_paths.py` | Gate B. |
| `tools/verify_script_paths.py` | Gate C. |
| `tools/rewrite_qgis_paths.py` | Unzip `.qgz`, apply a `MOVES.csv` mapping to every `<datasource>`, repack. Writes `wellsight_<date>.qgz.bak` first. |
| `tools/apply_moves.py` / `tools/undo_moves.py` | Execute and reverse a `MOVES.csv` ledger of `old_path, new_path, phase, reason`. |
| Full snapshot to `E:\Colton\lidar_project_prereorg_2026-08-12\` | E: has 4.1 TB free. This is the rollback of last resort. |

**Do this on a branch.** `git checkout -b repo-reorg`.

### Phase 1 — Zero-risk cleanup

* Move root clutter to `docs/figures/scratch/` and `tools/`.
* Delete nothing. Move the six `.gpkg-wal` / `.gpkg-shm` sidecars to
  `data/99_archive/data/` (they are transient, but the instruction is absolute).
* Remove the two empty directories `data/derivatives/inference/` and `barlow_data/`,
  or leave them with a `.gitkeep` and a one-line README. **Ask first** — `barlow_data/`
  has a 50 GB `.gitignore` reservation, which implies intent to refill it.
* Add `README.md` to `tiles/9t/iterations/` marking it superseded (§3.2).
* Fix `backup_to_E.bat`: it targets `E:\lidar_project`, which does not exist. The real
  target is `E:\Colton\lidar_project`. Its junction comment is also stale — the
  junctions are gone, which is what broke `_prep_road_1m.py` on 2026-08-06.
* Add `tools/backup_to_F.bat` to match.

### Phase 2 — Consolidate the loose derivative rasters

The 282 files in `data/derivatives/`. For each, consult `reference_index.csv`:

* **Zero references** → move to `data/03_derived/<area>/<res>/`, record in `MOVES.csv`.
* **Referenced** → leave, and log why in the plan appendix.

Then the 175 files in `tiles/9t/`. **This set is dangerous** and gets a stricter rule:
move only files with zero references *and* a same-named replacement elsewhere. Live
inputs (`features_pit_9t_1m.tif`, `labels_road_9t_1m.tif`, `pit_blocks_9t.gpkg`,
`*_dataset_manifest.csv`, `road_chunks_9t.gpkg`) stay.

Run `rewrite_qgis_paths.py` against `MOVES.csv`. Run all three gates.

### Phase 3 — Introduce the config layer

Create `config/paths.toml`:

```toml
root = "C:/Users/colto/Documents/GitHub/lidar_project"   # override with WELLSIGHT_ROOT
source   = "data/01_source"
truth    = "data/02_truth"
derived  = "data/03_derived"
models   = "data/04_models"
results  = "data/05_results"
archive  = "data/99_archive"
```

Rewrite `_common.py` to read it, with an environment-variable override and a fallback
to `Path(__file__).resolve().parents[2]` so the repository stops being pinned to one
username. Keep `DERIV` and `DERIV_9T` exported as aliases so **all 67 importing
scripts keep working unchanged.**

After this phase, a future move is one edit in one file instead of sixty.

### Phase 4 — The role-based restructure

This is the only phase that touches the big directories. Order matters, because each
step's gate protects the next.

1. `data/derivatives/annotations/` → `data/02_truth/annotations/`
2. The nine flat `eval_*` directories → `data/05_results/`
3. `data/derivatives/experiments/` → `data/06_experiments/`
4. Model directories under `tiles/9t/` (`pit_unet_cv5`, `pad_unet_cv5`,
   `road_unet_1m*`, `drainage_unet_1m`, `pad_unet`, `multitask_unet`,
   `road_sweep_202607`, `road_classifier`) → `data/04_models/<target>/`
5. `data/derivatives/tiles/` → `data/03_derived/`, normalising the naming
   inconsistencies from §1.4
6. `data/source_laz/` → `data/01_source/lidar/`
7. `data/external/` → `data/01_source/reference/`

**Regenerate `.gitignore` from a template rather than editing it by hand.** Sixty
hand-edits under time pressure is how a 100 MB raster gets committed. A generator
that reads `paths.toml` and emits the rules is a two-hour job that removes the entire
class of error.

### Phase 5 — Archive the obsolete

Move every §3.1 item into `data/99_archive/` with an `ARCHIVE_MANIFEST.csv` row:
`original_path, archived_path, date, reason, superseded_by, evidence_doc`.

Nothing is deleted. The manifest is the point — an archive without a manifest is just
a different kind of mess.

### Phase 6 — Re-sync the backups

See §8. This phase needs your decision before it can be specified.

---

## 7. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| 100 MB file enters git after a move | **High** — history is permanent | Generated `.gitignore`; Gate A after every phase |
| QGIS project silently loses 57 layers | High | `rewrite_qgis_paths.py`; `.qgz.bak`; Gate B |
| A script breaks weeks later, not now | Medium | `reference_index.csv` built first; Gate C |
| Backups double to 244 GB | Medium — F: has only 151 GB free | §8 decision |
| A "zero-reference" file was actually used by hand in QGIS | Medium | Nothing is deleted; `undo_moves.py` |
| Reorg collides with in-flight analysis | Medium | Run on a branch; merge at a quiet point |
| `parents[N]` breakage | High if scripts move | Scripts do not move |

---

## 8. Backup policy (decided)

**E: is the only backup target. F: does not exist.**

The current location, `E:\Colton\lidar_project`, is badly named. It sits beside
`E:\Colton\ai_music`, `E:\Colton\hammond`, `E:\Colton\Writing` and other *working*
project folders, so nothing about it says "backup". Someone opening it — including a
future you, or QGIS via a stale recent-files entry — cannot tell it is a copy. Worse,
editing a file there does nothing, because the next `/XO` run overwrites it from C:.

### Target layout

```
E:\Colton\_BACKUPS\
├── README_THIS_IS_A_BACKUP.txt        # plain-language, read first
└── lidar_project_MIRROR\              # live incremental mirror of C:\...\lidar_project
    └── _BACKUP_MANIFEST.txt           # source, tool, flags, last run, file count, bytes
```

and, taken once before anything moves:

```
E:\Colton\_BACKUPS\lidar_project_SNAPSHOT_prereorg_2026-08-12\
```

E: has 4,154 GB free. A 122 GB snapshot plus a 122 GB mirror is 244 GB, about 6% of
the free space. Both fit with room to spare, so nothing has to be deleted or mirrored
destructively.

### Rules

1. **`_MIRROR` is written only by the backup script.** Never edit it. Never open a
   layer from it in QGIS.
2. **`_SNAPSHOT_*` directories are frozen.** Never written again after creation.
3. **`robocopy /XO` only. Never `/MIR`.** `/MIR` deletes, and the standing instruction
   is that nothing is deleted.
4. Every backup run appends to `_BACKUP_MANIFEST.txt`: timestamp, files copied, bytes,
   exit code.

### Implementation

* Rename `E:\Colton\lidar_project` → `E:\Colton\_BACKUPS\lidar_project_MIRROR`. This is
  a metadata operation on the same volume, so it is instant and copies nothing. The
  next `/XO` run then sees the content as current and copies only real changes.
* Write `README_THIS_IS_A_BACKUP.txt` and `_BACKUP_MANIFEST.txt`.
* Replace `backup_to_E.bat`, which currently targets `E:\lidar_project` — a path that
  has never existed. Its junction comment is also stale; those junctions are gone, and
  their absence is what broke `_prep_road_1m.py` on 2026-08-06.
* New launcher lives at `tools/backup_to_E.bat`.

---

## 9. Effort and sequencing

| Phase | Effort | Reversible | Blocking |
|---|---|---|---|
| 0 — safety net | 1 session | n/a | no |
| 1 — zero-risk cleanup | 1 hour | trivially | no |
| 2 — loose files | 1 session | via ledger | no |
| 3 — config layer | 2 hours | trivially | no |
| 4 — restructure | 1–2 sessions | via ledger | **yes** — pause analysis |
| 5 — archive | 1 hour | via ledger | no |
| 6 — backups | background | n/a | no |

Phases 0–3 deliver most of the ease-of-access benefit at a fraction of the risk.
**Phase 4 is the only one that genuinely requires a quiet period.** It is entirely
reasonable to stop after Phase 3 and decide later.

---

## 10. Still open

Answered 2026-08-12: scope (Phases 0–3), Permian (archive), Barlow (archive), backups
(E: only, labelled). See the Decisions table at the top.

Two small questions remain, neither blocking:

1. **`plat_02`/`road_02` and `plat_03`/`road_03` hold byte-identical 93 MB
   checkpoints.** Either one model was copied into both directories, or a training
   script wrote to the wrong one. Which name is correct? Until answered, both stay and
   both are flagged in `docs/reference_index.csv`.
2. **`barlow_data/` is empty.** With Barlow archived, its ~50 GB `.gitignore`
   reservation is released. If the dataset is ever re-fetched, it should land under the
   archive, not the repository root.

And two defects the Phase 0 gates found, both worth fixing in Phase 1:

3. **One QGIS layer points outside the repository.** Its datasource is
   `../../../bold_roads.shp` → `C:\Users\colto\Documents\bold_roads.shp`. That file
   **does exist**, so the layer loads and nothing looks wrong. It is byte-identical
   (3,380 bytes) to `data/derivatives/annotations/bold_roads.shp`. So the project
   depends on a stray copy that is outside git, outside the E: backup, and outside
   every audit. Repoint the layer to the in-repo copy.

4. **`_icp_change_9t_rebuild.py` hardcodes `F:\lidar_project\consolidated\lidar_all`.**
   F: is gone, so the script is dead. It needs either a `--old-dir` argument or a
   `paths.toml` entry. Note the source data it wants lived on F: under
   `consolidated\`, which has no equivalent on C: or E: — that data may be lost.

### Phase 0 baseline, recorded 2026-08-12

| Gate | Checked | Failing |
|---|---:|---:|
| A — git leak >100 MB | all 101,516 files | **0** |
| B — QGIS datasources | 58 | **0** |
| C — script path constants | 291 resolved (33 unresolvable) | 10 |

Of Gate C's 10, four are genuinely dead (`tiles/9t_1m`, `F:\...\lidar_all`,
`mosaic_3x3`, `external/nisar`) and six are output paths created on first write.
Baseline stored in `docs/verify_paths_baseline.json`; later runs report only *new*
breakage.

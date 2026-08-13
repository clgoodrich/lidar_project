# Project structure

Reorganized **2026-06-09**, then **2026-08-12** (Phases 0–3, then Phase 4A–4E:
the role-based layout). The previous 2026-05-15 reorg is superseded by this
document. See `CLAUDE.md` for the agent operating
instructions (unchanged location at repo root).

## Where paths come from — read this before adding a file

`config/paths.toml` is the single source of truth. It carries the **full
role-based vocabulary** (`source`, `truth`, `derived`, `models`, `results`,
`experiments`, `archive`, …). Names and values are both live — 4D moved the
tree and the config followed.

```python
from _common import path_for
path_for("truth") / "roads.shp"        # correct
ROOT / "data" / "derivatives" / "annotations" / "roads.shp"   # Gate E failure
```

Adding a directory means adding a key here, not spelling it in a script.
`tools/verify_no_path_literals.py` (Gate E) enforces it. 226 sites existed on
2026-08-12; 206 were converted by `tools/convert_path_literals.py` and the
remaining 20 are frozen in `docs/_ledgers/path_literals_baseline.json`. New ones
fail the gate.

Full plan: `docs/REORGANIZATION_PLAN_phase4_role_based.md`.

```
lidar_project/
├── CLAUDE.md  README.md  STRUCTURE.md  pytest.ini
├── config/paths.toml       SINGLE SOURCE OF TRUTH for every directory below
│
├── data/                   AREA-MAJOR. one directory per study area.
│   ├── 9t/                 the primary area, and where every model is trained
│   │   ├── derived/{05,1m,1m_rebuilt20260812}/   dem, slope, lrm, rrim, features
│   │   ├── models/         pit/ pad/ plat/ road/ drainage/ multitask/
│   │   │                   classifiers/ _retired/   (see models/README.md)
│   │   ├── results/        pit/{thresholds,centroid_matching,rim_containment}/
│   │   │                   pad/ road/ wells/ heldout_overlap/ instance_precision/
│   │   └── experiments/    diagnostics/ exag3x/
│   ├── 613590/             derived/{05,1m,inference_05}/  results/road/
│   ├── 607594|610594|610605|616593/derived/1m/
│   ├── westernpa_d20/<block>/derived/1m/    northcentral_b19/<block>/derived/1m/
│   ├── mckean/{mk5,mkf,sw,e1423n2238}/derived/{05,1m,road_1m}/
│   ├── oilcreek/derived/22tile/
│   ├── grids/westernpa_0{1..4}/derived/1m/   annotation grids
│   │
│   ├── _source/            IMMUTABLE. lidar/ (raw LAZ) + reference/ (DEP, TIGER,
│   │                       land cover, NLCD). The pipeline never writes here.
│   ├── _results/           results that span areas: candidates/ validation/
│   ├── _experiments/       threads not tied to one area
│   ├── _pretrained/        seed weights (yolov8s-seg, yolo26n)
│   ├── _logs/              cross-area build logs
│   └── _archive/           parked + superseded, ARCHIVE_MANIFEST.csv
│
├── qgis/                   THE FRONT DOOR
│   ├── wellsight.qgz       61 layers, all resolving
│   ├── annotations/        HAND-DRAWN GROUND TRUTH. roads, plat, pit_inside,
│   │                       drainage, waterways, annotations_proj.gpkg
│   │                       grids/    per-grid pit annotation
│   │                       _history/ dated snapshots
│   └── grids/              per-grid QGIS projects
│
├── notebooks/wellsight_v2/ UNCHANGED — parents[N] depth is load-bearing
├── docs/  literature/  tools/  tests/  ui/  roads_studio/  archive/  personal/
```

## Why area-major

Two organisations were possible. Role-major puts the artifact class first
(`derived/9t`, `models/pit`, `results/9t`); area-major puts the study area first
(`9t/derived`, `9t/models`, `9t/results`).

Area-major was chosen because the question asked most often here is "show me
everything about 9t", not "show me every derivative in the project". The
role-major arrangement answered the second question well and made the first one
a four-directory hunt — which is the same complaint that started this
reorganisation, just rotated.

Role survives as the second level, which is what keeps the `.gitignore` to one
rule per role (`data/**/derived/**`) instead of one per directory.

Ground truth is the exception: it lives in `qgis/annotations/`, not under an
area, because `roads.shp` spans Oil Creek to McKean and does not belong to any
single tile — and because that is the folder it is drawn from every day.


## Path conventions (IMPORTANT — keep code paths anchored)

Live scripts live in `notebooks/wellsight_v2/` and resolve paths through
`_common.py`, which reads `config/paths.toml`.

| Name | Meaning |
|------|---------|
| `path_for("<key>")` | **use this** — any directory, by role |
| `ROOT` | repo root |
| `DERIV` | legacy alias, `data/derivatives` (the shrinking remainder) |
| `DERIV_9T` | legacy alias, now `data/03_derived/9t/05` |
| `DST_CRS` | `EPSG:6346` (NAD83(2011) / UTM 17N, canonical) |

`DERIV` and `DERIV_9T` are kept so the 67 scripts that import them keep working.
New code should use `path_for`.

Per-area stacks build under `path_for("derived")/<area>/<res>/`.

```bash
cd C:/Users/colto/Documents/GitHub/lidar_project
python notebooks/wellsight_v2/s1_build/_build_derivatives.py --suffix 9t
```

## Tile / region keys

| Key  | Description                          | EPSG (raster) | Source LAZ project              |
|------|--------------------------------------|---------------|---------------------------------|
| 9t   | 4.5×4.5 km, Venango County PA        | 6346          | PA_WesternPA_2019_D20 (UTM 17N) |
| mk5  | 5×5 km subset of mkf                 | 6346          | PA_Northcentral_2019_B19 (Albers)|
| mkf  | 10×10 km, McKean County PA           | 6346          | PA_Northcentral_2019_B19 (Albers)|
| pilot_A | TX/NM/Permian LAZ bridge           | 26913/14      | USGS Permian subsets            |

## File size / `.gitignore` policy

Any output that may exceed **100 MB** must be covered by a `.gitignore` rule in
the same change. Since Phase 4D that mostly falls out of the role:

| Tree | Default | Why |
|---|---|---|
| `data/03_derived/**` | **ignored**, small records negated back in | regenerable by definition |
| `data/04_models/**` | `*.pt`, `*.tif`, `dataset/`, `run/` ignored | weights and rasters rebuild from the trainer |
| `data/02_truth/**` | **tracked**, no rule | irreplaceable; only `_history/` rasters are ignored |
| `data/05_results/**` | **tracked**, no rule | small, and it is the deliverable |
| `data/99_archive/**` | ignored, manifest force-added | bulk |

Audit after every change that writes large outputs (must print nothing):

```bash
find . -type f -size +100M -not -path "./.git/*" -not -path "./.venv/*" |   while read f; do git check-ignore -q "$f" || echo "NOT IGNORED: $f"; done
```

## Gates

| Gate | Checks | Tool |
|---|---|---|
| A | no >100 MB file unignored | `tools/verify_paths.py` |
| B | every QGIS datasource resolves | same |
| C | every script path constant resolves | same |
| D | outputs byte-identical after a change | `tools/golden.py` |
| E | no directory literals in live code | `tools/verify_no_path_literals.py` |

Every reorganization phase ends with all five. Moves go through
`tools/apply_moves.py` (ledger at `docs/MOVES.csv`, reversible with `--undo`),
and `--root` replays the same ledger onto the E: mirror so it stays a mirror.

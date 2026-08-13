# Project structure

Reorganized **2026-06-09** (full data-tree restructure + root cleanup), then
**2026-08-12** (Phases 0–3, then Phase 4A/4B). The previous 2026-05-15 reorg is
superseded by this document. See `CLAUDE.md` for the agent operating
instructions (unchanged location at repo root).

## Where paths come from — read this before adding a file

`config/paths.toml` is the single source of truth. It carries the **full
role-based vocabulary** (`source`, `truth`, `derived`, `models`, `results`,
`experiments`, `archive`, …) as of Phase 4A. The names are final; the values
still point at the current tree because Phase 4D has not run.

```python
from _common import path_for
path_for("truth") / "roads.shp"        # correct
ROOT / "data" / "derivatives" / "annotations" / "roads.shp"   # Gate E failure
```

Adding a directory means adding a key here, not spelling it in a script.
`tools/verify_no_path_literals.py` enforces it against a 226-site baseline in
`docs/_ledgers/path_literals_baseline.json`. Those 226 are the pre-existing
sites, frozen; new ones fail the gate.

The eventual Phase 4D values are recorded as comments at the bottom of
`paths.toml`, so the move is a value change rather than an archaeology exercise.
Full plan: `docs/REORGANIZATION_PLAN_phase4_role_based.md`.

```
lidar_project/
├── CLAUDE.md  README.md  STRUCTURE.md  pytest.ini
├── config/paths.toml           SINGLE SOURCE OF TRUTH for every directory below
│
├── data/
│   ├── 02_truth/               HAND-DRAWN. irreplaceable. tracked by default.
│   │   ├── annotations/        roads, plat, pit_inside/outside, drainage, ...
│   │   ├── grids/              per-grid pit annotation gpkgs (was label_grids/)
│   │   └── _history/           dated snapshots; rasters inside them are ignored
│   ├── 03_derived/             REGENERABLE BY DEFINITION. one blanket .gitignore.
│   │   ├── 9t/{05,1m_rebuilt20260812}/
│   │   ├── 613590/{05,inference_05}/
│   │   ├── 607594|610594|610605|616593/1m/
│   │   ├── westernpa_d20/<block>/1m/    northcentral_b19/<block>/1m/
│   │   ├── mckean/{mk5,mkf,sw,e1423n2238}/{05,1m,road_1m}/
│   │   ├── oilcreek/22tile/    grids/<grid>/1m/   _logs/
│   ├── 04_models/              A MODEL IS A BUNDLE. see 04_models/README.md
│   │   ├── pit|pad|plat|road|drainage|multitask|classifiers/<run>/
│   │   ├── pretrained/         _retired/  (9,055 files, cited by LEADERBOARD)
│   ├── 05_results/             WHAT THE PROJECT PRODUCES
│   │   ├── 9t/<target>/<question>/     613590/road/thresholds/
│   │   ├── candidates/         validation/
│   ├── 06_experiments/         one thread per directory
│   ├── 99_archive/             parked/ + superseded/ + ARCHIVE_MANIFEST.csv
│   ├── derivatives/            SHRINKING REMAINDER — 110 loose files, see below
│   ├── source_laz/             raw LAZ (-> 01_source/lidar, not yet moved)
│   └── external/               third-party downloads (-> 01_source/reference)
│
├── notebooks/wellsight_v2/     UNCHANGED — parents[N] depth is load-bearing
├── qgis/                       wellsight.qgz + grids/<grid>.qgz
├── docs/  literature/  tools/  tests/  ui/  roads_studio/  archive/  personal/
```

## Still to move

`data/derivatives/` holds 110 loose files, `data/source_laz/` and
`data/external/` still sit outside `01_source/`. Those are the remainder of
Phase 4D and are tracked in `docs/REORGANIZATION_PLAN_phase4_role_based.md`.
The loose files are the hard ones — many are referenced by exact filename and
several are the canonical 1 m 9t stack, which cannot be consolidated until the
`_prep_road_1m.py` stats regression is resolved.


## Path conventions (IMPORTANT — keep code paths anchored)

All active scripts anchor to absolute constants in `notebooks/wellsight/_common.py`:

| Constant   | Value                                            |
|------------|--------------------------------------------------|
| `ROOT`     | repo root                                         |
| `DERIV`    | `ROOT/data/derivatives`                           |
| `DERIV_9T` | `ROOT/data/derivatives/tiles/9t`                  |
| `DST_CRS`  | `EPSG:6346` (NAD83(2011) / UTM 17N, canonical)    |

Per-area stacks are built under `DERIV/"tiles"/<key>` (the `--suffix` / region
key becomes the leaf). Source LAZ lives in `ROOT/data/source_laz/{westernpa,mckean}`.

```bash
cd C:/Users/colto/Documents/GitHub/lidar_project
python notebooks/wellsight/build/_build_derivatives.py --suffix 9t ...   # -> tiles/9t/
python notebooks/wellsight/build/_build_data_3x3_derivatives.py          # -> tiles/data_3x3/
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
the same change. A blanket `data/derivatives/**/*.tif(.aux.xml)` covers all
derivative rasters at any depth; `archive/derivatives/**/*.{tif,gpkg,las,...}`
covers archived heavy data. Audit (output must be empty):

```bash
find . -type f -size +100M -not -path "./.git/*" -not -path "./.venv/*" | \
  while read f; do git check-ignore -q "$f" || echo "NOT IGNORED: $f"; done
```

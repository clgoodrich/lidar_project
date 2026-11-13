# NISAR radar work: start here

This folder holds all of the NISAR work in one place. It also holds the Sentinel-1 cross-check made in November 2026.
Everything here was moved from other folders on 2026-11-13. Nothing was deleted.

## The question

Does adding NISAR L-band radar to the lidar detector find more well pits and pads?
The bar was set in advance. A gain of +0.05 in score over the lidar-only detector.

## The answer so far

No design reached the bar. The one test with room to fail was the held-out pit test on area 613590.
Lidar alone scored 0.881 and lidar plus radar scored 0.865. The gain was -0.017, with a 95% interval of -0.055 to +0.020.
That rules out +0.05 for those 36 pits. It does not prove the radar can never help.
The Sentinel-1 C-band cross-check agrees. Pits show no coherence, motion or steady-bright-target signal.

## Read these first

1. `nisar/docs/NISAR_FINDINGS.md`. The findings and the numbers.
2. `nisar/docs/NISAR_METHODS.md`. How every number was made.
3. `nisar/writeup/nisar_project_status_brief.md`. One page on where things stand.
4. `nisar/reviews/nisar_adversarial_20261109/REPORT.md`. An independent adversarial review, and what was fixed.

## What is in the folder

| Folder | What it holds |
|---|---|
| `code/` | Every NISAR script. `_nisar_area.py` sets the paths. `s1_build/` fetches and geocodes the data. `s5_eval/` runs the tests. `s6_review/` and `s7_analysis/` make review and cross-section products. `nisar_reflectors/` is a framework that was never run. |
| `results/<area>/` | Every output. CSV, JSON, figures and GeoPackages. Areas are `9t`, `613590`, `warren` and `mkf` (McKean). |
| `derived/<area>/` | The large rasters and the date indexes. Git-ignored and rebuilt by the scripts. About 11 GB. |
| `docs/` | The findings, the methods and one write-up per experiment in `docs/iterations/`. |
| `writeup/` | The checkpoint slide decks, their figures and the plain-language explainers. |
| `reviews/` | The independent audits and the slide-revision notes. |
| `qgis/` | A QGIS project draping the radar on the lidar. |
| `sentinel1/` | The Sentinel-1 C-band cross-check. `code/`, `results/<area>/`, `docs/` and `source/` (raw downloads, git-ignored, about 5 GB). |

## How the scripts work

- Every script is named for what it does. Output names carry the area tag, for example `_9t` or `_613590`.
- Scripts take `--area 613590`, `--area warren` or `--area mkf`. The default is 9t.
- `--slc` switches to the stack re-placed on lidar heights. This is the stack used for the corrected results.
- Run from the repository root. For example `python nisar/code/s5_eval/_nisar_pol_season_canopy_9t.py --slc`.
- Each script's opening comment says what it reads and what it writes. `docs/iterations/` has the reproduce command for each experiment.
- Checked 2026-11-13. Three scripts were rerun after the move and reproduced their saved outputs exactly. The fourth, `_nisar_steel_9t.py`, wrote different date counts, because its saved results predate the 2026-10-26 bad-date fix. The saved files were kept and the script needs a deliberate rerun.

## What lives outside this folder

The scripts read these shared inputs from the rest of the repository.

- The lidar derivatives under `data/<area>/derived/1m/`. Elevation, canopy height and hillshade.
- The annotations in `qgis/annotations/`. Pits, pads and roads.
- The well records in `data/_source/reference/dep_wells/`.
- The shared helper `notebooks/wellsight_v2/_common.py`. `_nisar_area.py` adds it to the path.

## Old paths

One older document still names the previous locations. It is `docs/analysis_log.md`.
That log is an append-only record, so its paths were left as written.
Every move is listed in `docs/MOVES.csv` under the phase `nisar_folder`. Use the old path column to find the new one.
The full list of 134 moves is also in `docs/_ledgers/nisar_folder_moves.csv`.

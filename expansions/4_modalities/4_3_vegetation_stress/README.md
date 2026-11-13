# 4.3. Vegetation stress

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05 at the user's request to stop deferring).
**Plan.** [docs/plan_mod_vegetation_stress.md](docs/plan_mod_vegetation_stress.md)
**Framework.** [docs/fw_4_3_vegetation_stress.md](docs/fw_4_3_vegetation_stress.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_3.md](docs/decisions_4_3.md)
**Shared rules.** [fw_00_common.md](../../_shared/fw_00_common.md) and [protocol_gates_and_metrics.md](../../../docs/plans/protocol_gates_and_metrics.md). The protocol wins on any conflict.

## Folders

| Folder | Holds | In git |
|---|---|---|
| `docs/` | plan, framework, decisions log | yes |
| `src/` | scripts for this expansion | yes |
| `data/raw/` | inputs as received. Never edited | no |
| `data/interim/` | intermediate products | no |
| `data/processed/` | model-ready inputs | no |
| `models/` | weights and checkpoints | no |
| `results/figures/` | small figures | yes |
| `results/tables/` | small tables and JSON | yes |

Products for a new study area go to `data/<area>/` as everywhere else, not here.
Scripts resolve paths with `path_for("expansions")` (key in `config/paths.toml`). Add the import path with
`sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "notebooks/wellsight_v2"))`.
Anything at or above 100 MB goes under an ignored folder. Every run gets an entry in `docs/analysis_log.md`.

## Build status (2026-11-06)

Defaults applied 2026-11-06 (user said "take defaults"). visible_lookback_days is 365. V3 useful gain is 0.03 recall at K. max_undefined is 0 for V3 and V4. The September scene stays shoulder. V3 and V4 on all labels are the two primaries. Their stage verdicts are now `verdict_unadjusted`. The gate is Holm over both, run by `src/_vegstress_primary_holm_9t.py`. V0 on the held data still refuses, now only because the code lists are placeholders. Tests 12 passed.


Review fixes applied on 2026-11-06 (findings 4.3-01, 4.3-02, 4.3-03, P2-01, SH-01, the latest-run order and the weak chain test). Tests pass with `python -m pytest -q expansions/4_modalities/4_3_vegetation_stress/src/test_4_3.py -p no:cacheprovider` (12 passed). Paths and assumed schemas live in `src/config_4_3.json`. Generic helpers come from `../4_2_thermal/src/_thermal_shared_io.py`. Each script writes a run folder `results/<YYYYMMDD>_<short>_<hash7>/` with `_CONFIG.json`, `_RUN.md` and `_PROVENANCE.json`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_vegstress_shared_io.py` | library (indices, L2A radiometry, native grids, Hanley and McNeil SE) | yes | nothing |
| `src/_vegstress_label_audit_9t.py` | V0 label gate | partly | `--hm-only` runs now. Records (request R1), real DEP code lists (`labels.codes_status` must be `dep_verified`) and `labels.visible_lookback_days` are missing. It refuses without them |
| `src/_vegstress_observability_9t.py` | V1 observability | yes | Leaf-off scenes. The held stacks give one usable leaf-on and one usable shoulder scene |
| `src/_vegstress_match_controls_9t.py` | matched controls and the unmatched population layer | no | Non-well disturbance layer `data/raw/nonpad_disturbance_9t.gpkg`. The frozen P2 audit set (or `--allow-no-audit`, labelled exploratory) |
| `src/_vegstress_extract_sites_9t.py` | V2 index extraction and stress anomaly | no | L2A radiometry for the held stacks. They carry no offset tags, so V2 refuses until `radiometry` is declared per scene. Then matched controls, red-edge and blue bands |
| `src/_vegstress_added_value_9t.py` | V3 Question A at K = 40 per km2 | no | V2 on the population layer and the 3.0 block folds `data/raw/transfer_blocks.csv` |
| `src/_vegstress_leak_test_9t.py` | V4 Question B | no | A V0 gate verdict of success. It refuses to run otherwise |
| `src/test_4_3.py` | tests | yes | nothing |

What changed on 2026-11-06.
- V2 converts DN to reflectance with the L2A quantification and BOA offset from the stack tags or a declared scene radiometry. It refuses otherwise. It refuses negative reflectance over valid land, which is how a doubled offset shows.
- V2 works on native grids. A 5 m stack must be a block copy of native pixels. NDVI and EVI are read at 10 m, NDMI and NDRE at 20 m.
- SCL keeps classes 4 and 5 only. Water, snow, cloud, cirrus and shadow are masked. A stack without SCL refuses unless `extract.allow_unmasked`, and is then labelled unmasked.
- V3 runs on the unmatched population layer by default. On the matched layer it returns `not_identifiable`.
- V0 counts records only inside the dates the scenes can see. It refuses placeholder code lists.
- The audit set is read through `ek.require_audit`. Bootstrap intervals count undefined draws.
- The held stack dates come from the script that wrote them (`nisar/code/s5_eval/_nisar_vs_optical_9t.py`). They are 2026-06-03, 2026-09-07 and 2025-10-27, not the mid-month placeholders.

Runs. All numbers are from the JSON files named.
- `results/20261105_vegstress_labels_7f82a84/vegstress_label_counts_9t.json`. Hanley and McNeil check. At AUC 0.70 with 40 per class the SE is 0.058 and the lower bound is 0.585, above 0.5. Fourteen per class is the smallest equal n that clears 0.5 under simple random sampling. Lease clustering widens this. Unchanged.
- `results/20261106_vegstress_observe_4bb908c/vegstress_observability_9t.json` reruns V1 with SCL classes 4 and 5. The numbers match the 2026-11-05 run because the held SCL holds no water or snow pixels. At 10 m the median pad holds 7 interior pixels and 3 open interior pixels, so the gate is inconclusive. At 20 m and 30 m the median is 0, a failure. The median pad edge band is 61% under canopy over 2 m. The September stack has 37% valid SCL pixels. No leaf-off scene is held.
- `results/20261105_vegstress_sites_30295c9/vegstress_by_site_9t.csv` is superseded. It read DN at 5 m with no offset check. A rerun of V2 now refuses for want of radiometry, so no new table exists.

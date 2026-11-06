# 7.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Candidates are scored with `sc.load_policy("pit_floor")` from the 7.3 scorer 2 (F02). The cutoff moves from 0.10 to 0.35 and matching is block-local. Out-of-fold files are read with `strict=True`. No 7.1 scored output existed, so nothing was rescored. Made by the review-fix agent.
- 2026-11-06. Review fix 7.1-01. The audit file is read through `ek.require_audit`. A missing file stops the run unless `--allow-no-audit`. Such outputs are labelled "no audit exclusion, exploratory". Made by the review-fix agent.
- 2026-11-06. Audit and buffer rows leave train and inner validation. Only the sealed audit rows leave the held-out lists. Buffer blocks may still be scored out of fold. Made by the review-fix agent, change freely.
- 2026-11-06. A fine-tune run refuses label subsets built against a different audit hash. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix 7.1-02. `--audit-once` scores only `audit_*` files from `--predict-audit`. It needs a frozen audit, a primary arm, a set G and one named fold model. The lock file is written before any score. Made by the review-fix agent.
- 2026-11-06. Review fix 7.2-01 in 7.1. G comes from the config or the preregistration. It is never derived from the runs it judges and never floored. An unset G gives an inconclusive decision. This replaces the 2026-11-05 floor decision below. Made by the review-fix agent.
- 2026-11-06. Training windows are redrawn every epoch from the child seed (seed, index, epoch). Validation windows stay fixed so epochs compare on the same windows. Made by the review-fix agent, change freely.
- 2026-11-06. The label subsets JSON was rebuilt with `--allow-no-audit`. Its content did not change. It now says it has no audit exclusion. Made by the review-fix agent.

## Needs user decision

- G, the useful gain for the primary test. Set it in `config_7_1.json` or the preregistration JSON before any pretrained arm is scored. Until then the primary decision is inconclusive.
- `finetune.audit_model_fold`. Which fold model scores the sealed audit blocks in `--audit-once`. The audit lies outside every fold, so any fold model can score it.
- The primary arm (already open since 2026-11-05).


- 2026-11-05. Masked reconstruction targets lrm_25 and lrm_5. The stack has no raw DEM and lrm_25 is the DEM minus its 25 m smooth. Made by the build agent, change freely.
- 2026-11-05. Contrast views are slope, roughness_11 and tpi_05 against lrm_25, lrm_5 and both openness channels. The stack has no hillshade or curvature. Made by the build agent, change freely.
- 2026-11-05. The U-Net output conv is the projection head. Fine-tuning replaces it with a new 3-class head. Made by the build agent, change freely.
- 2026-11-05. Window-level negatives come from batches that take half their chips from one window, with no two chips overlapping. Made by the build agent, change freely.
- 2026-11-05. Blocks with no pits form their own stratum and are cut at the same fraction as pit-bearing blocks. Made by the build agent, change freely.
- 2026-11-05. Corpus chips are an index into the window stacks, not copies. Made by the build agent, change freely.
- 2026-11-05. Run outputs go to this expansion's results/ and models/ folders, not data/9t/results/ssl/. The build was scoped to the expansion folder. Made by the build agent, change freely.
- 2026-11-05. A derived G below 0 is floored at 0 and the raw value is kept. A negative margin would let an arm win while doing worse. Made by the build agent, change freely.
- 2026-11-05. Candidate extraction and matching use the 7.3 scorer until the 3.0 scorer is frozen. Made by the build agent, change freely.
- 2026-11-05. The provisional split takes a seeded 15% of training blocks as inner validation. It never feeds the primary claim. Made by the build agent, change freely.
- 2026-11-05. Fine-tuning reads the full 9t stack into memory (about 2.6 GB with labels). Made by the build agent, change freely.

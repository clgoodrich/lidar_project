# Framework 7.1. Self-supervised pretraining and label efficiency

**Tier A (full depth, 2026-11-05).** The user withdrew the deferral. The plan assumes the unlabelled corpus and the compute in section 5 exist. Each assumption is tagged VERIFY.
**Evidence level.** (a). It measures recall of drawn terrain features. It says nothing about wells.
**Depends on.** P1 (isolated trainer, saved splits). P2 (audit guard). 3.0 scorer for recall at K. 6.3 adjudicated labels for the validity control.
**Blocks.** Nothing. 7.3 may use the pretrained checkpoint as a benchmark baseline.

## 1. Problem and objective
Labels are scarce and costly. A network may learn terrain structure from unlabelled lidar derivatives and then need fewer labels. Two earlier lessons shape the design. A 45.9 M parameter Mask R-CNN overfit 74 pits and 51 pads (memory note, `docs/iterations/LEADERBOARD.md`). The review point is that label validity, not label count, is the bottleneck.

**Question.** At a fixed number of annotated blocks, does a pretrained encoder give higher recall at K = 40 per km² than a randomly initialised one, and how many validated labels is that gain worth?

**Hypotheses.**
- H1. Pretrained fine-tuning beats random init at 25% of labels by at least the useful gain G (section 7).
- H2. The gain shrinks as the label fraction rises.
- H3. Adding validated labels to a random-init model buys at least as much as pretraining does. This is the control that guards against reading a label-count story as the whole story.

Three different comparisons exist and each is reported on its own (protocol section 12).
- C1. Fixed annotation budget. Primary.
- C2. Fixed total compute. The random-init arm receives the pretraining GPU-hours as extra fine-tune epochs. Secondary.
- C3. Cost counted. Pretraining GPU-hours amortised over the areas that reuse the checkpoint. Reported as a table, no gate.

## 2. Scope
In. Masked-DEM reconstruction, cross-channel contrast, and both together. Fine-tuning pit and pad on 9t at label fractions. A validated-label control. A runtime benchmark.
Out. Road models. Transfer claims to other states (that is 3.0 and 3.1). Large backbones beyond the optional arm in section 6 S6.

## 3. Definitions and estimand
- **Unit.** The 375 m block on 9t. Resampling is over blocks.
- **Label fraction f.** The share of pit-bearing training blocks in a fold whose labels the fine-tune may use. Blocks are drawn nested (the 5% set sits inside the 10% set) by a seeded permutation, stratified by feature-count tercile so no subset is empty of pits.
- **Arm.** A0 random init. A1 masked reconstruction. A2 cross-channel contrast. A3 both. A4 random init plus validated labels. A5 optional, the existing `unetpp_r34_imagenet` encoder as an external-pretraining reference.
- **Matched seeds.** Seed s fixes the label subset, the fine-tune sampler and the fold split in every arm. Pretraining seed s fixes the pretrained weights. Child seed is master + 1000 fold + arm.
- **Estimand (primary).** Recall of annotated pit floors at K = 40 per km² of scored eligible area, pooled over out-of-fold blocks, at f = 25%, difference A1 or A2 or A3 minus A0, averaged over 3 or more matched seeds on the same resampled blocks. Matching rule and tie rule are those of `fw_00_common.md` section 4. The primary arm is named in the preregistration before any fine-tune runs. The other two are exploratory.
- **Label-efficiency ratio (secondary).** Labels needed by A0 to reach a target recall divided by labels needed by the pretrained arm, from interpolated curves. Target is 90% of A0 recall at f = 100%.
- **Validated label.** A feature confirmed by two reviewers blind to each other and to model score, as in 6.3. Share U (undecided) is excluded and counted.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Derivative builders (7 channels) | `notebooks/wellsight_v2/s1_build/_build_derivatives.py`, `_build_extra_channels.py` | held |
| Pit and pad manifests | `data/9t/derived/05/pit_dataset_manifest.csv`, `pad_dataset_manifest.csv` | held |
| Saved splits, buffer | `data/9t/results/splits/cv_splits_future_9t_v1.json`, `buffer_derivation_9t.json` | from P1 |
| Isolated trainers | `notebooks/wellsight_v2/s3_train/_pad_unet_iso_cv5.py` (held), `_pit_unet_iso_cv5.py` (from P1) | held, proposed |
| Network and sampler | `notebooks/wellsight_v2/_dl.py` (`UNet`, `CenteredPatchSampler`) | held |
| Audit files and guard | `data/9t/results/splits/audit_blocks_9t_v1.csv`, `notebooks/wellsight_v2/_audit_guard.py` | from P2 |
| Lidar window list | `data/_source/reference/lidar_catalogue/lidar_win_download_summary_us.csv`, `lidar_win_download_list_us.csv` | held |
| Validated labels | `data/9t/results/confusers/` pooled blind labels | from 6.3, proposed |
| Reference numbers | `docs/iterations/LEADERBOARD.md` (plain U-Net 7.8 M params, noise sd about 0.02 IoU) | held |

## 5. Assumed data
| # | Assumption | Tag | How to verify |
|---|---|---|---|
| 1 | The unlabelled corpus is derivative stacks built from the listed windows (52 rows in the catalogue). Use windows with Appalachian-like relief first, then the rest. Held tile files exist for PA windows | VERIFY | `wc -l` the summary CSV. Sum real tile sizes and compute union coverage from tile geometry. Catalogue totals are discovery estimates |
| 2 | At least 300 km² of corpus ground has ground-classified returns at 0.5 m derivative resolution | VERIFY | Measure ground-return density per window with PDAL CLI via `run_pipeline`. Drop windows below the 9t density |
| 3 | The corpus excludes all of 9t, all of Warren, and every audit block and buffer | VERIFY | `_audit_guard.py` run over the corpus window footprints |
| 4 | Survey density and vintage differ across windows (QL1 about 9 ppsm, QL2 about 4.8 ppsm) | VERIFY | Record points per m² per window. Stratify the sampler by density bin |
| 5 | GPU for pretraining is the held GTX 1070 Ti 8 GB. A 24 GB card is optional and only for arm A5 variants | VERIFY | `nvidia-smi`. S0 benchmark |
| 6 | Validated labels for A4 exist, at least 40 pit-bearing blocks worth | VERIFY | Count adjudicated rows from 6.3. If fewer, A4 uses the largest available step and says so |
| 7 | Reviewer time for the validity control is about 40 hours | VERIFY | Pilot throughput from 6.3 (2 hours per 20 candidates per reviewer, to confirm) |
| 8 | Disk for the corpus stack is 300 GB or less on F: | VERIFY | Estimate after S1 from 3 real windows. Add `.gitignore` rule in the same change |

If assumption 1 or 2 fails, the corpus shrinks. The design still runs, and the claim narrows to the corpus actually built.

## 6. Prerequisites and decisions
P1 done. P2 guard in place. User decisions that block the preregistration only. The useful gain G (default derivation in section 7). Primary arm. Whether arm A5 is run.

## 7. Procedure
**S0. Runtime benchmark (first, before any corpus build).**
- Script `notebooks/wellsight_v2/s3_train/_ssl_runtime_bench_9t.py` (proposed). Time one full epoch by wall clock, never the dry-run estimator, which under-reported by 1.8 times (`BACKLOG.md`). Test batch sizes 8, 16, 32 and patch sizes 128 and 256 px. Record peak memory, data-loader share of time, and whether mixed precision helps. The 1070 Ti has no tensor cores, so expect little gain.
- Output `data/9t/results/ssl/ssl_runtime_bench_9t.json` and `docs/iterations/pretrain_runtime.md`. Extrapolate GPU hours only from these.

**S1. Corpus builder.**
- Script `notebooks/wellsight_v2/s1_build/_build_ssl_corpus_us.py` (proposed). For each admitted window, build the 7-channel stack with the exact 9t builders. Write 256 px chips at stride 192 to `data/_ssl/corpus/<window>/` with a chip index CSV (window, x, y, density bin).
- Normalisation statistics come from the corpus only, saved as `ssl_norm_stats.npz`. Fine-tuning refits its own fold-local statistics (P1 S3).
- Checks. CRS asserted per chip. No chip intersects an audit block plus buffer. No chip is mostly nodata (over 20% dropped, count logged).

**S2. Pretraining objectives.** Same 7.8 M U-Net as the supervised arms, so architecture is identical.
- Masked reconstruction (A1). Mask 50% of 16 px patches in all channels. The network reconstructs the detrended elevation channel and the local relief channel in masked patches. Loss is L1 on masked pixels only. Detrending removes the 25 m local plane so the task is texture and shape, not absolute height.
- Cross-channel contrast (A2). Two views of one chip. View one holds hillshade, slope and curvature. View two holds local relief, openness and the remaining channels. A 1x1 projection head gives per-pixel embeddings. InfoNCE with the same location as positive and other locations in the batch and the same-window chips as negatives (temperature 0.1). Window-level negatives keep the net from learning only survey identity.
- Combined (A3). Sum of the two losses with equal weights, fixed before running.
- Three pretraining seeds each. Checkpoints saved under `data/_ssl/models/<arm>_seed<s>/` with SHA-256 in provenance.

**S3. Fine-tune.**
- Script `notebooks/wellsight_v2/s3_train/_pit_ssl_finetune_9t.py` (proposed), a thin layer on `_pit_unet_iso_cv5.py`. Load the encoder and decoder, keep the segmentation head new. Same loss, epochs (40), sampler, augmentation and rejection rule in every arm. Epoch count is not tuned per arm.
- Loop. 4 arms (A0 to A3) x 5 folds x 5 fractions (5, 10, 25, 50, 100%) x 3 seeds. That is 114 full-run equivalents of 40 epochs (sum of fractions 1.9 x 5 folds x 4 arms x 3 seeds). Hours follow from S0.
- Best epoch and cutoff on inner validation blocks only. The held-out fold is scored once.
- Outputs under `data/9t/results/ssl/<run_id>/` with `oof_candidates_<arm>_f<fraction>_s<seed>.csv`.

**S4. Validated-label control (A4).**
- Reviewers label additional candidates by 6.3 rules until n_extra validated labels exist beyond the f = 25% set. Two levels, equal to the labels in the 25% to 50% step and in the 25% to 100% step. Random init, same seeds.
- The comparison is recall per added validated label versus recall gain from pretraining at f = 25%. Reviewer minutes are logged so the cost is in hours, not only counts.
- Also report label noise. A random 10% of the training labels are re-checked by a second reviewer. Recall of the model against the re-checked set is reported with the original set.

**S5. Scoring and curves.** Script `notebooks/wellsight_v2/s5_eval/_ssl_curve_score_9t.py` (proposed). Calls the 3.0 scorer for every candidate file. Writes `ssl_recall_curves_9t.csv` (arm, fraction, seed, fold, matched, truth, area) and the figure `ssl_label_efficiency_9t.png`.

**S6. Optional arm A5.** Reference encoder from `unetpp_r34_imagenet`. Same fine-tune loop. It tests whether in-domain pretraining beats generic pretraining. Not part of the primary gate.

**S7. Final check on the audit set.** Only the pre-named best arm and A0, at f = 100% and f = 25%, are scored once on the comparative audit blocks (P2 S1). Absolute claims need the absolute audit area.

## 8. Statistical analysis plan
- **Primary.** Difference in pooled recall at K, pretrained minus A0, f = 25%. Same resampled blocks for both arms (paired block bootstrap, B = 2000). Average over matched seeds inside each resample. Report the 95% interval.
- **Margin.** Useful gain G. Default derivation is the recall A0 itself gains from f = 25% to 50%. Pretraining must be worth at least a doubling of labels. G is read from the A0 curve and frozen before any pretrained arm is scored. The user may replace it with a reviewer-hour value. G never comes from fold or seed spread.
- **Decision.** Superiority. Success if lower bound above G. Failure if upper bound below G. Otherwise inconclusive.
- **Curves.** Fit recall = a minus b n^-c per arm, bootstrap blocks, report labels-to-target and the ratio. The fit is descriptive. It is not a gate.
- **Secondary.** Each f separately (exploratory). A4 minus A1 at matched extra labels. C2 equal-compute difference. Calibration (Brier, log loss, ECE) per arm. Fold-by-fold spread reported, never used as a margin.
- **Seeds.** Seeds are nuisance replicates, not the sample. Report the seed spread beside the interval. Fewer than 3 seeds per arm voids the primary claim.
- **Multiplicity.** One primary. Everything else is exploratory.

## 9. Quality control and leakage checks
1. Corpus chips and the fine-tune windows never touch an audit block or buffer (guard run and logged).
2. Corpus exclusion of 9t is asserted by footprint test. If 9t training chips are added (transductive arm), the run is labelled transductive and not used in the primary.
3. Fold-local normalisation differs across folds and differs from the corpus statistics.
4. Label subsets nest across fractions. Same subset across arms for a given seed. Assert by hash.
5. A second run with the same config gives identical outputs (fine-tune determinism with fixed loader generator).
6. Pretraining collapse check. Embedding variance across the batch above a floor, and the reconstruction loss below the mean-fill baseline.
7. Survey-identity probe. A linear probe predicts window id from frozen embeddings. High accuracy warns that the encoder learned the sensor, not terrain. Reported, not a gate.
8. Row counts asserted at every join. No NaN block ids. No duplicate candidates.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Primary lower bound above G | Adopt the pretrained encoder for 9t pit and pad. Score the audit set once |
| Failure | Primary upper bound below G | Keep random init. Say whether the objective failed or the mechanism cannot help at this corpus size |
| Inconclusive | Interval spans G | Report. Add seeds first, then fractions. Do not move G |
| Control reading | A4 gain per label above the pretraining gain | Spend reviewer time on validated labels, not on pretraining. Record in BACKLOG |

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s3_train\_ssl_runtime_bench_9t.py`, `_pit_ssl_pretrain_us.py`, `_pit_ssl_finetune_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\_build_ssl_corpus_us.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_ssl_curve_score_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\ssl\` (benchmark JSON, curves CSV, figure)
- `C:\Users\colto\Documents\GitHub\lidar_project\data\_ssl\` (corpus chips and checkpoints, gitignored)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\pretrain_runtime.md`, `ssl_label_efficiency_9t.md`
- Preregistration `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\prereg_ssl_label_efficiency.md`

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Encoder learns survey vintage, not terrain | Window-level negatives, density-stratified sampling, identity probe |
| Mask task too easy on smooth terrain | Detrend target, harder mask ratio, report reconstruction versus mean-fill |
| Few pits at f = 5% | Stratified nested subsets. Report empty-subset counts. Drop the fraction if over 20% of subsets lack pits |
| Gain is within noise (sd about 0.02 IoU) | Seeds, paired blocks, report as inconclusive |
| Epoch time under-reported | S0 uses wall clock on a full epoch |
| Pretraining leaks held-out ground | Corpus excludes 9t and audit areas. Guard test |
| Gain comes from longer total training | C2 arm and equal-epoch rule |

## 13. Resources
Setup 12 hours (S0 to S1). Reviewer time about 40 hours for S4. GPU hours unknown until S0. Disk about 300 GB on F: (VERIFY). Heavy outputs need `.gitignore` rules and the 100 MB audit in the same change.

## 14. Handoff and open questions
- Confirm the primary arm and G.
- Confirm corpus window list and density floor.
- Confirm reviewer names for S4.
- Record the interpreter and seeds in every run.

## 15. Documentation updates
`pretrain_runtime.md`, `ssl_label_efficiency_9t.md`, `LEADERBOARD.md` (one row per arm and fraction), `analysis_log.md`, `BACKLOG.md`, `literature/CITATIONS.md` (masked autoencoder and contrastive sources, same change), master plan.

## Review revision (2026-11-05)
Deferral withdrawn by the user. Framework written to full depth on assumed data. Nothing here has been run.
Source. `docs/plans/protocol_gates_and_metrics.md` section 12.

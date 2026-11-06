# Preregistration draft. Transfer warren (arm 1)

**Generated** 2026-11-06 by `_xfer_prereg_draft_wfm.py`. DRAFT. Not committed. Not valid for scoring.

## Blockers
- buffer is provisional (P1 derived buffer missing)
- projected width exceeds 2 x Delta (0.03) in every S2 design cell. Add blocks or revisit Delta
- reference tables are provisional (historical CV5 pit). Scores stay descriptive until the P1 isolated baseline
- pit: P1 isolated checkpoints missing
- pad: P1 isolated checkpoints missing
- flight dates not recorded (USGS metadata, manifest D1)
- reviewers and adjudicator not named

## Primary estimand
Recall of annotated pit floors at K = 40 candidates per km2 of eligible test area, target minus the 9t reference. Complete blind blocks, including empty ones. Block bootstrap, B = 2000, independent per area. Non-inferiority against minus Delta. Delta = 0.03.

## Fixed choices
- K primary 40 per km2. K = 30 sensitivity only.
- Scoring policy ek.policy_for(pit) 5ca1e98. IoU 0.3, greedy one-to-one in score order. Blobs under 4.0 m2 dropped. Score = mean probability. Dedupe truth_matched.
- Proposal cutoff 0.35 (ek.policy_for, the sweep's cutoff). Declare it, the IoU, the dedupe, K and the checkpoint in the json prereg block.
- Model policy ensemble_mean_5_folds.
- Program PA_WesternPA_2019_D20. Native density primary. Thinning is a separate sensitivity arm.
- Roles seed 20261105. Buffer 192.0 m. Adaptation dropped True.
- Eligibility. cover >= 0.999, void <= 0.8, density rule 9t_p5 (1.905815111111111 per m2). Low-density blocks are a reported stratum.

## Hashes
| file | sha256 (16) |
|---|---|
| roles `C:\Users\colto\Documents\GitHub\lidar_project\expansions\3_geography\3_1_warren_forest_mckean\results\tables\warren\xfer_blocks_roles_warren.gpkg` | 056db840000689a8 |
| reference `C:\Users\colto\Documents\GitHub\lidar_project\expansions\3_geography\3_3_low_relief_slope\results\20261105_slope_recall_5886eff\slope_recall_blocks_9t.csv` | 25903f698b593855 |
| config `C:\Users\colto\Documents\GitHub\lidar_project\expansions\3_geography\3_1_warren_forest_mckean\src\config_3_1.json` | 2e116b32f60982e2 |

| task | fold | source | checkpoint | sha256 (16) |
|---|---|---|---|---|
| pit | 0 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pit\unet_cv5\fold0\best.pt` | 1143a4f37c38acdc |
| pit | 1 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pit\unet_cv5\fold1\best.pt` | 3fbd51e391c397ee |
| pit | 2 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pit\unet_cv5\fold2\best.pt` | 59fbe9d673e3679d |
| pit | 3 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pit\unet_cv5\fold3\best.pt` | f145f4ced8eccbdd |
| pit | 4 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pit\unet_cv5\fold4\best.pt` | 9f14ac2119275685 |
| pad | 0 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pad\unet_cv5\fold0\best.pt` | ab493182f93a8054 |
| pad | 1 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pad\unet_cv5\fold1\best.pt` | 081cc3646ae58019 |
| pad | 2 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pad\unet_cv5\fold2\best.pt` | a38fb22ae6a47ff4 |
| pad | 3 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pad\unet_cv5\fold3\best.pt` | a8eacda78407a363 |
| pad | 4 | CV5 original sampler (PROVISIONAL) | `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\models\pad\unet_cv5\fold4\best.pt` | 1b659eaee529ecc4 |

## Annotation protocol
Two reviewers per test block, layers pit_inside, pit_full and pad, no model output, no well points, no scores. Third look adjudicates. A seeded 20% of test blocks is re-annotated independently. Exposure logged per block.

## Gates
Readiness. Projected width at most 2Delta. Success. Holm-adjusted one-sided bootstrap share under 0.025. Failure. Upper bound below minus Delta. Otherwise inconclusive. One scoring run.
- Multiplicity. Holm over the declared primaries ['warren', 'mckean', 'forest']. Secondaries are reported, never gated. No undefined bootstrap draw is tolerated (max_undefined 0).

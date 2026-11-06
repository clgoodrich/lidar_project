# Upstream inventory for context stacking (9t)

Draft of `docs/iterations/context_upstream_inventory.md`. Written by `expansions/5_tasks/5_1_context_features/src/_context_upstream_inventory_9t.py`.
Reference scheme is `pit_cv5`.
Every number below comes from the CSV beside this file.

| model | role | n_checkpoints | per_fold | n_blocks | folds | vs_ref_share_same_fold | vs_ref_same_partition | status |
|---|---|---|---|---|---|---|---|---|
| pit_cv5 | pit | 5 | True | 115.000 | 5.000 | 1.000 | True | must retrain (not isolated) |
| pit_cv5_smrf | pit | 5 | True | 115.000 | 5.000 | 1.000 | True | must retrain (not isolated) |
| pad_cv5 | pad | 5 | True | 129.000 | 5.000 | 0.309 | False | must retrain (scheme, not isolated) |
| pad_cv5_iso | pad | 5 | True | 129.000 | 5.000 | 0.309 | False | must retrain (scheme) |
| road_unet_1m_recall | road | 1 | False |  |  |  |  | must retrain (scheme, not isolated) |
| road_unet_1m_recall_relabeled | road | 1 | False |  |  |  |  | must retrain (scheme, not isolated) |
| road_unet_1m | road | 1 | False |  |  |  |  | must retrain (scheme, not isolated) |
| road_unet_05 | road | 1 | False |  |  |  |  | must retrain (scheme, not isolated) |

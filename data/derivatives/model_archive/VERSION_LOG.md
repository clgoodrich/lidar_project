# Model Version Archive

All candidate GPKGs + metrics from every XGBoost/ensemble run, preserved here so no version gets lost.

## Model Versions (chronological)

### v1 — RF baseline (90 pits, output3 only, 0.5m)
- `pit_candidates_rf.gpkg` — Random Forest, OOB, 45 features
- PR-AUC: 0.436

### v2 — XGBoost (90 pits, output3, 0.5m)
- `pit_candidates_xgb.gpkg` — GroupKFold OOF, 45 features
- PR-AUC: 0.478

### v3 — XGB + 2008 temporal + pad/road priors (90 pits)
- `pit_candidates_xgb_plus.gpkg` — 73 features
- PR-AUC: 0.678

### v4 — XGB + morphology + multi-template (90 pits)
- `pit_candidates_xgb_plus2.gpkg` — 88 features
- PR-AUC: 0.716

### v5 — XGB+LGBM ensemble + isotonic calibration (90 pits)
- `pit_candidates_ensemble.gpkg` — best single-tile model
- PR-AUC: 0.722

### v6 — Template-only candidates
- `pit_candidates_template.gpkg` — NCC candidates before any ML

### v7 — Cross-tile to output2 (no priors)
- `pit_candidates_output2.gpkg` — blind application to adjacent tile

### v8 — Sep area (2019, no priors)
- `pit_candidates_sep.gpkg`
- `pit_candidates_sep_filtered.gpkg` (NLCD-filtered attempt)

### v9 — Sep area (2008 only)
- `pit_candidates_sep_2008.gpkg`

### v10 — McKean 3x3 (trained on output3)
- `pit_candidates_mckean.gpkg`

### v11 — 675 pits retrain (9-tile + McKean, no land cover)
- `pit_candidates_675_9tile.gpkg`
- `pit_candidates_675_mckean.gpkg`
- PR-AUC: 0.372

### v12 — 675 pits + land cover features
- `pit_candidates_675lc_9tile.gpkg`
- `pit_candidates_675lc_mckean.gpkg`
- PR-AUC: 0.382

### v13 — Single tile blind runs (607594, 610605)
- `pit_candidates_607594.gpkg`
- `pit_candidates_610605.gpkg`

### v14 — High-density orphan tiles + McKean 5x5 (DEP overlay)
- `pit_candidates_616593.gpkg` — 204 DEP orphan wells in area
- `pit_candidates_610594.gpkg` — 163 DEP orphan wells in area
- `pit_candidates_mk5.gpkg` — McKean expanded, 655 DEP wells
- `pit_candidates_616593_enriched.gpkg` — with diagnostic columns

## Notes
- Use `proba` column for calibrated probability (best for training tile)
- Use `proba_raw` column for cross-tile applications (calibration too aggressive across tiles)
- Enriched GPKGs include: lrm5_depth, slope_deg, chm_m, tpi15, neighbors_10m, neighbors_25m

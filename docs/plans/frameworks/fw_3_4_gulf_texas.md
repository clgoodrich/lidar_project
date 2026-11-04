# Framework 3.4. Gulf Coast and Texas

**Tier B.** Deferred.
**Evidence level.** (a) and (b). RRC records are administrative evidence, not level (d).
**Depends on.** 3.0, a ground-density measurement.

## 1. Problem and objective
Wetland, vegetation and ground-return conditions differ. Lidar may have poor ground coverage under dense or flooded cover. Texas has a documented orphan well layer (RRC layer 2) whose locations carry a reliability field. Only about 35% of RRC orphans sat within 100 m of an optical pad detection in earlier Permian work, which does not apply to East Texas.

**Objective.** Measure ground-return density and void fraction first. Then run an unchanged zero-shot baseline, with a separate adaptation arm.

## 2. Scope
In. Density and void audit, zero-shot baseline, strata, a separate adaptation experiment.
Out. Claims about East Texas without East Texas data (the 51-county list holds Caddo LA, Pecos TX and Ouachita AR).

## 3. Definitions
Void fraction at 0.5 m per block. Wetland stratum from NLCD. Adaptation arm uses relief-normalised channels and is reported as a different experiment.

## 4. Inputs
Windows listed: Louisiana Caddo (`LA_Sabine_River_Lidar_2018_D18`, 36 tiles, 7.69 GB, big tiles), Texas Pecos (`TX_WestTexas_2018_D19`, 24 tiles, 2.35 GB), Arkansas Ouachita. RRC layer 2 (D13). Databases from USGS 2022 for LA, TX, AR.

## 5. Prerequisites and decisions
Choose an East Texas county from RRC or TNRIS data. Margin Δ.

## 6. Procedure
1. Measure ground density and void fraction on one tile per window (PDAL CLI). Write `data/<area>/results/transfer/ground_density_by_block.csv`.
2. Stratify blocks by wetland and by void fraction.
3. Zero-shot baseline with the unchanged pipeline (3.0).
4. Adaptation arm (relief-normalised channels, own preregistration).
5. An exclusion arm for wetland blocks is a different target population and is reported separately.
6. Fetch RRC layer 2 and the reliability fields (D13) and plan association (5.6) with reliability stratification.

## 7. Statistical analysis plan
As 3.1 per arm, with stratum tables.

## 8. Quality control
Unchanged baseline in every table. No mixing of arms.

## 9. Gates
As 3.1.

## 10. Deliverables
Density table, scores, doc `transfer_gulf_9t_model.md`.

## 11. Failure modes
Low ground density. Flooded cover. Large tile sizes.

## 12. Resources
Similar to 3.1.

## 13. Handoff
East Texas county choice.

## 14. Documentation updates
Doc, master plan.

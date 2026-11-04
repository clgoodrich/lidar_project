# Framework 3.5. Oklahoma and Kansas

**Tier B.** Deferred.
**Evidence level.** (a) per modality.
**Depends on.** 3.0, 3.1.

## 1. Problem and objective
Large orphan inventories sit in open terrain with active infrastructure. Whether lidar, optical and fusion differ there is unknown.

**Objective.** A three-arm comparison on identical sites and splits, with matched labelling and tuning effort.

## 2. Scope
In. Lidar, optical and fusion arms on the same sites.
Out. Claims beyond these counties.

## 3. Definitions
Arms. Lidar only, optical only, fusion. Same spatial splits and label budget. Missingness table for each modality. Active infrastructure confounding flagged.

## 4. Inputs
Windows listed: OK Okmulgee (`OK_Statewide_D22`, 19 tiles, 1.21 GB), Washington, Nowata (FEMA QL2, 19, 0.51), Rogers; KS Montgomery (`KS_Statewide_2018_A18`, 4 tiles, 2.39 GB, big tiles), Labette, Neosho; MO Jackson, Cass. Databases downloaded: OK RBDMS and orphan list, KS paged export. Optical imagery to be found (NAIP and state orthos).

## 5. Prerequisites and decisions
Optical labels and annotation effort. Matched effort is not measurable as written. Measure minutes per block.

## 6. Procedure
1. Coverage intersection and temporal eligibility table (lidar dates, imagery dates, well dates).
2. Choose sites present in all modalities.
3. Annotate once on a common footprint, blind to model output.
4. Train arms with matched tuning effort (same number of hyperparameter trials, same budget).
5. Score with 3.0 on the same blocks. Paired differences between arms.
6. Missingness and active-infrastructure analysis.

## 7. Statistical analysis plan
Paired block bootstrap for arm differences. Superiority of fusion over lidar by the smallest useful gain.

## 8. Quality control
Same footprint and splits across arms. Hash everything.

## 9. Gates
As 3.1 for each arm. Fusion gate is superiority.

## 10. Deliverables
Docs and results folders per state.

## 11. Failure modes
Modality missingness. Tuning imbalance. Infrastructure confusion.

## 12. Resources
Large (new labels and training).

## 13. Handoff
Needs optical source choice.

## 14. Documentation updates
Doc, master plan.

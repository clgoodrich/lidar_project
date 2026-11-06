# Datasheet terrain_v1

Status. PROVISIONAL. Not for release.
Evidence level (a) throughout. Labels are drawn terrain features. They are not wells.
Audit exclusion. none. Provisional historical roles, no P2 audit set. Exploratory, not for release.
Scoring policy fw00_s4_20261105 (scoring_policy.json).

## Motivation
No public benchmark exists for lidar detection of terrain features linked to old oil and gas sites.
The release lets others compare methods on the same tiles and the same scorer. Funding is VERIFY.

## Composition
| role | task | n_blocks | area_km2 | n_features | per_km2 | share_blocks_empty |
|---|---|---|---|---|---|---|
| devtest | pit_floor | 21 | 2.9531 | 101.0 | 34.201 | 0.0 |
| devtest | pit_full | 21 | 2.9531 | 101.0 | 34.201 | 0.0 |
| devtest | pad | 21 | 2.9531 | 111.0 | 37.587 | 0.0 |
| train | pit_floor | 94 | 13.2188 | 402.0 | 30.411 | 0.0 |
| train | pit_full | 94 | 13.2188 | 405.0 | 30.638 | 0.0 |
| train | pad | 94 | 13.2188 | 473.0 | 35.783 | 0.0532 |
| unassigned | (no labels) | 29 | 4.078125 |  |  |  |

## Collection
Tiles 4. CRS EPSG:6346. Resolution 0.5 m.
Bands lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11, dem. Vertical datum NAVD88.
Lidar project and flight dates are VERIFY. A publication date is not a flight date.

## Label provenance
One annotator drew polygons in QGIS from derivative views. The labels are one person's reading of terrain.
The annotator did not see DEP well points while drawing (user, 2026-11-04). Other context seen is unrecorded.

## Exclusions
Features with no block (off tile) per task {'pit_floor': 209, 'pit_full': 217, 'pad': 411}.
Features touching a hidden block, dropped from public files, per task {'pit_floor': 0, 'pit_full': 0, 'pad': 0}.
Near-duplicate features across splits within 5 m 0.

## Spatial buffers
Roles {'train': 94, 'devtest': 21}. Buffer blocks ship tiles and no labels.

## Uncertainty
Uncertainty not measured. Second-reviewer labels from 6.3 are absent (C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\confusers\second_reviewer_labels_9t.gpkg).

## Uses
Intended. Compare terrain-feature detectors on pit and pad features in forested Appalachian lidar.
Out of scope. Locating wells, regulatory or legal decisions, counting wells, safety decisions, other states.

## Distribution and licences
Lidar VERIFY. PA 2019 D20 3DEP. Read USGS and PASDA terms. Labels VERIFY. CC BY 4.0 proposed. Annotator consent in writing. Well context VERIFY. No well coordinates or distances released unless the licence permits.
Host and DOI are VERIFY. Versioning follows the manifest. A change makes a new version.

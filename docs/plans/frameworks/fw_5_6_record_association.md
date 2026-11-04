# Framework 5.6. Record association

**Tier A.** The first attempt is withdrawn. Repair the input, then rerun.
**Evidence level.** A proposed association between records and terrain features. Not a corrected coordinate.
**Depends on.** P1 (splits), 3.0 scorer, DEP answers (R1) for validation.
**Blocks.** 5.4 (r term), A6 recall gap.

## 1. Problem and objective
Agency records have coordinates of unknown accuracy. A detected feature near a record might be that well. Linking them could save field time.

**The first run was wrong.** The loader dropped every row with `dup_on_pit = 1`. All 481 matched pit detections carry that flag, so only the 204 unmatched leftovers were used. The pad file was the unmatched leftover set. The one-to-one proposals were not global (197 rows, 153 unique detections). The pit footprint was reused for pads (115 against 129 blocks). The result (orphan records not above chance) is withdrawn.

**Objective.** A correct, preregistered association analysis with a defensible null, a positive control and a statistic that tells a crew how often a proposed link is right. Validation only with independent coordinates.

**Hypotheses.** H1. DEP records of a given status sit closer to detected features than a shifted-record null. The effect is expressed as the predictive value 1 minus null over observed.

## 2. Scope
In. 9t full detector output and full annotations. Seven other state databases held (NY, KY, OK, IL, WV, OH, KS) for later use.
Out. Coordinate correction without independent points.

## 3. Definitions
- **Full detector output.** All candidates at the frozen cutoff 0.50 from the out-of-fold raster, matched and unmatched, with one deployment-compatible deduplication rule (a second blob inside an already-matched feature is dropped, the same way the deployed pipeline would).
- **Novel candidates.** The unmatched subset only, analysed separately and labelled.
- **Annotated features.** Hand-drawn floors and pads (an agreement analysis with drawings, not a detector test).
- **Footprints.** Pits use the 115 pit-bearing blocks. Pads use the 129 pad blocks. Or a declared intersection. Same rule for observed and null.
- **Statuses.** Orphan or abandoned (DEP Orphan List, DEP Abandoned List), plugged, active.
- **Primary radius.** Pits 50 m. Pads inside the polygon. Others are sensitivity.
- **Positive control.** Active wells at pad level.
- **Predictive value.** PV = 1 minus null mean over observed. Interval from the null distribution.
- **Independent coordinates.** GNSS positions or NETL surveyed sites. None held yet.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Candidate layers | `data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg` layers `matched`, `undecided`, `missed_pit` | held |
| Pad candidates (unmatched only) | `pad_candidates_filtered_heldout_9t.shp` | held, wrong input |
| Full pad output | rebuild from the out-of-fold pad raster with the matching code `_match_rules_pit_pad_9t.py` | to build |
| Builder of candidates | `notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py` (defines `dup_on_pit`) | held |
| Annotated features | `qgis/annotations/annotations_proj.gpkg` | held |
| DEP wells | `data/_source/reference/dep_wells/venango_wells_all.gpkg` | held |
| Old association script | `notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py` | held, withdrawn input |
| Other states | `data/_source/reference/wells_*` | downloaded |
| GNSS and coordinate provenance | R1 (DEP), R2 (NETL) | requested |

## 5. Prerequisites and decisions
- Annotators did not see DEP points (user, 2026-11-04). Annotation context (roads, pads, imagery) is still unrecorded. Keep the caveat.
- Preregister the primary radius, the null and the field-use minimum predictive value.
- DEP coordinate provenance changes the cohort analysis (A6) but not the 9t association.

## 6. Procedure
**S0. Input contract.**
- Script `notebooks/wellsight_v2/s5_eval/_build_full_detector_output_9t.py` (new). Build the full set of candidates for pits (matched + undecided + dup-flag rows resolved by the deployment dedupe rule) and for pads (matched + unmatched) from the out-of-fold rasters and truth. Write `data/9t/results/records/detector_output_pit_full_9t.gpkg` and `detector_output_pad_full_9t.gpkg`. Add a table of row counts per source layer. Assert pit matched + undecided counts equal the expected 481 + 207 before dedupe, and report the dedupe counts after.

**S1. Corrected association script.**
- Script `notebooks/wellsight_v2/s5_eval/_record_assoc_9t_v2.py` (new, do not edit the withdrawn one). Changes.
  1. Reads the full outputs from S0.
  2. Footprints per modality.
  3. Observed rates per status and radius.
  4. Null. Translate the whole record set as one by a vector of length 200 to 500 m in a random direction, 300 shifts, seed in the preregistration. Keep eligible records fixed. Reject and redraw shifts that move more than 10% of records outside the footprint, and report each shift's retained count. State what the null conditions on (spatial gradients in oil development and road density are only partly preserved).
  5. Global one-to-one assignment (Hungarian) across all statuses, or publish per-status outputs labelled "competing proposals".
  6. PV and intervals.
- Output run folder `data/9t/results/records/<run_id>/` with `rates.csv`, `proposals.csv`, `summary.json`, figure (observed blue, null grey with 95% band and a second marker shape).

**S2. Three analyses.**
- (a) Full detector output versus records (the headline).
- (b) Novel candidates only versus records.
- (c) Annotated features versus records (agreement with drawings, not detector performance).
- Label each with its evidence level. Mark all as exploratory since the earlier run existed.

**S3. Positive control and power.**
- Report whether the active-pad control exceeds the null. If it does not, the test is uninformative and the target-group result cannot be interpreted.
- Power. Report the minimum detectable PV given the number of records and the null width.

**S4. Cohort stratification.**
- Split orphan or abandoned records into those on the 2022 orphan list and newly documented ones (permit key `121-<n>` against the 2022 CSV). Cohort-specific nulls. Stratify by DEP coordinate source once R1 answers. Never compare raw match rates between cohorts.

**S5. Other states (later, only if wanted).**
- Same scripts on the seven state databases with harmonised statuses. Each state is a separate case study. Coordinate methods differ.

**S6. Independent validation (blocked until coordinates arrive).**
- With GNSS or NETL points. For each proposed association compute the position error before (record to GNSS) and after (candidate centroid to GNSS). Report paired change, wrong matches and abstentions. Proximity excess alone never passes coordinate correction.

## 7. Statistical analysis plan
- Primary. Excess over the shifted null at the preregistered radius and PV, per status, with null-based 95% interval.
- Positive control. Active at pad level, lower bound of excess above 0.
- Secondary. Sensitivity over radii (10, 25, 50, 75, 100 m pits; inside, 25, 50 m pads).
- Validation (when data exist). Paired position-error difference with block bootstrap over records, non-inferiority and superiority.
- Multiplicity. One primary per status. Everything else is sensitivity.

## 8. Quality control
- Row counts at every join (expected 481 matched and 207 undecided pit rows).
- Dedupe rule written down and applied identically to observed and shifted data.
- Check that proposals have at most one record per detection (global assignment).
- Plot ten proposals over hillshade.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Positive control passes and target group PV lower bound above the field-use minimum | Association is informative | Offer proposals to a crew for a field test |
| Positive control passes and target upper bound below the minimum | Records do not mark features at these radii | Stop automatic snapping on 9t. Say so. Do not stop all association work |
| Positive control fails | Uninformative | Fix power or the null |
| Validation | Position error improves with interval above 0 on independent points | Consider a coordinate-correction pilot |

## 10. Deliverables
- Scripts `_build_full_detector_output_9t.py`, `_record_assoc_9t_v2.py` in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\records\` run folder
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\record_assoc_9t_v2.md` (and a note that v1 is withdrawn, already bannered)

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Dedupe rule changes the answer | Report both rules as a sensitivity |
| Few records per status | Power report. Merge only with a stated reason |
| Null drops many records | Redraw rule and retained counts |
| Circularity through annotation context | State the caveat. Do analysis (a) first |
| Records already near roads | Add distance to road as a stratifier in a sensitivity |

## 12. Resources
S0 to S3 about 12 to 16 hours. No GPU. Validation depends on R1 and R2.

## 13. Handoff and open questions
- Whether annotators saw roads or imagery. Whether DEP will give coordinate provenance.

## 14. Documentation updates
`record_assoc_9t_v2.md`, `analysis_log.md`, master plan, 5.4 and A6 plans (point to the new result).

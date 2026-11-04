# Framework 4.5. Multitemporal lidar at plugged wells

**Tier A.** Blocked until flight dates are known.
**Evidence level.** (a) terrain change at pad scale. Not evidence of plugging quality.
**Depends on.** Flight dates (D1), restoration records (R7), existing change-detection results.
**Blocks.** Nothing.

## 1. Problem and objective
Two lidar surveys cover 9t, 2006 to 2008 (statewide) and 2019 (D20). Plugging or site restoration may leave a change in terrain. The existing change work found that pad "changed" flags occur at about the placebo rate (19 of 404 flagged against about 15.3 expected). It has not shown well-related change. Plugged between 2006 and 2019 does not mean plugged between the flights.

**Question.** Do pads at wells plugged between the two flights show more terrain change than comparable eligible pads without that intervention?

**Hypothesis.** H1. The flag rate (or mean change) at plug-eligible pads exceeds that at matched eligible pads with no plugging between the flights.

## 2. Scope
In. Flight-date bounds, eligibility, matched controls, signal recovery test, comparison.
Out. Claims about plugging integrity. Surface restoration without dated earthwork.

## 3. Definitions
- **Flight window.** Acquisition date range per tile from project metadata. File creation dates are not flight dates.
- **Eligible plugged well.** DEP plug date strictly after the end of the 2006 to 2008 flight window for its tile and strictly before the start of the 2019 flight for its tile.
- **Eligible control pad.** A pad with a well that was not plugged between the flights and that had the same baseline condition (active at 2006, still active or abandoned at 2019 with no plug), matched on slope, pad area and baseline disturbance.
- **Pad-complex unit.** Analyse at pad or complex level, because several wells share a pad.
- **Detectable floor.** Mean change that the processing chain can recover on slopes under 15 degrees (reported 0.16 to 0.22 m).

## 4. Inputs
| Input | Path | State |
|---|---|---|
| 2006 to 2008 lidar | `s1_build/_fetch_lidar_2006_9t.py`, `data/9t/derived/` | held |
| 2019 D20 lidar | held | held |
| Change pipeline | `s7_analysis/_icp_change_9t.py`, `_change_rebuild_v2_9t.py`, `_change_features_9t.py`, `_change_seams_9t.py` | held |
| Saved v2 summary | `data/9t/results/change/change_features_summary_v2_9t.json` | held |
| DEP plug dates | `venango_wells_all.gpkg` field `DATE_PLUGG` | held |
| Flight dates | USGS project metadata | D1 to fetch |
| Restoration records | DEP | R7 requested |

## 5. Prerequisites and decisions
Flight dates in hand. Eligible n known. Minimum n for a test set in the preregistration (power).

## 6. Procedure
**S0. Flight-date bounds.**
- Fetch project metadata for `PA_STATEWIDE_N_2006_2008` and `PA_WesternPA_2019_D20` (D1). Record collection start and end per project, and per tile if given. Output `docs/iterations/lidar_acquisition_dates.md` and `data/9t/results/change/flight_windows_9t.csv`.

**S1. Eligibility.**
- Script `notebooks/wellsight_v2/s7_analysis/_plug_eligibility_9t.py` (new). Apply the eligibility rule to every DEP well in 9t. Output `data/9t/results/change/plug_eligible_wells_9t.csv` with counts of eligible, ambiguous and excluded wells. Write the counts. If eligible n is below the preregistered minimum, stop and report.

**S2. Matched controls.**
- Script `s7_analysis/_change_controls_matched_9t.py` (new). Use pads with a known well that is eligible-by-condition but not plugged between the flights. Match one to three per treated pad on slope, pad area, baseline roughness and distance to road (nearest neighbour with caliper). Write `data/9t/results/change/change_controls_matched_9t.gpkg`. The old controls (terrain excluding mapped pads, pits and roads) are not used for the primary test.

**S3. Signal recovery test.**
- Script `s7_analysis/_change_recovery_9t.py` (new). Inject synthetic changes of known size (0.1, 0.2, 0.3, 0.5 m mean) over footprints of 100, 400 and 1,000 m² into the 2006 surface in sample pads and controls, run the full chain (registration, differencing, high-pass, thresholding), and measure the flag rate. Output `data/9t/results/change/change_recovery_9t.csv`. The 3,368 m² patch threshold belongs to one spatial-null procedure and is not a physical floor.

**S4. Comparison.**
- Compute for each eligible plugged pad the change statistic (flag and mean change inside the pad polygon). Same for controls. Include seam position as a covariate (`_change_seams_9t.py`).

**S5. Report.**
- Estimate flag-rate difference and mean-change difference with block-bootstrap (cluster by pad complex). Report with the recovery curve and the eligible n. No detectable change is distinct from no restoration or no plugging.

## 7. Statistical analysis plan
- Primary. Flag rate at eligible pads minus flag rate at matched eligible controls, cluster bootstrap by pad complex.
- Secondary. Mean change difference. Dose-response against years since plugging.
- Placebo. Apply the same test to pairs of non-plugged pads to estimate false-alarm rate.
- Exploratory. Sensitivity of eligibility rule (include ambiguous dates).

## 8. Quality control
- Pad polygons registered between years (ICP result).
- Seam proximity flagged.
- A visual review of 10 flagged pads over hillshade for both years.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Flight dates bounded and eligible n at or above the minimum | Run S2 to S5 |
| Success | Lower bound above 0 and n meets the minimum | Report change associated with plugging |
| Failure | Upper bound below the smallest change worth detecting | Report no detectable change at the floor |
| Inconclusive | Otherwise, including n below minimum | Report and say why |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\lidar_acquisition_dates.md`, `plugging_change_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\change\` (flight windows, eligibility, controls, recovery, comparison)

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Eligible subset tiny | Say so, stay exploratory |
| Controls differ in disturbance opportunity | Matched design, sensitivity |
| Plugging leaves no surface earthwork | Request restoration records (R7). Report limit |
| Seams produce false flags | Seam covariate and exclusion band |

## 12. Resources
Dates 3 hours. Eligibility and controls 10 hours. Recovery 12 hours with compute. No GPU.

## 13. Handoff and open questions
- Minimum eligible n. Restoration records.

## 14. Documentation updates
`plugging_change_9t.md`, `outside_review_response_20261103.md` follow-ups, `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
Success and failure use one threshold δ_rate in rate units. The 0.16 to 0.22 m height floor is a separate measurement spec. Show recovery of a specified physical change through the full chain first.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

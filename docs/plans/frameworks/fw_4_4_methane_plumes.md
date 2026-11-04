# Framework 4.4. Methane plumes (detection-limit check, then close or proceed)

**Tier B.**
**Evidence level.** Regional association at best. Cannot attribute emissions to a candidate well.
**Depends on.** D4 (product guide, small).

## 1. Problem and objective
Satellites report methane plumes. It is unknown whether any plume can be tied to a candidate or documented well in Pennsylvania.

**Objective.** One quantitative check. Compare the mean emission of an abandoned Pennsylvania well with the satellite detection limit. Close for Pennsylvania if the gap is orders of magnitude. Keep deferred elsewhere.

## 2. Scope
In. Detection limit note, observation opportunity audit if the note does not close it.
Out. Plume attribution to individual wells.

## 3. Definitions
- **Mean emission.** Kang et al. (2014) measured 19 abandoned Pennsylvania wells (42 measurements), mean about 0.27 kg per day per well, with 3 of 19 high emitters (checked at the Princeton record, paper not read).
- **Detection limit.** The emission rate with 90% detection probability for a given instrument and wind speed.

## 4. Inputs
| Input | State |
|---|---|
| Carbon Mapper product guide (Tanager detection specification). A review states 90 to 180 kg per hour at 3 m/s wind, not yet checked | D4 to fetch |
| Kang et al. 2014 PDF | D3 to fetch |
| Other catalogues (public plume lists) | search |

## 5. Prerequisites and decisions
None.

## 6. Procedure
1. **Read the sources.** Fetch the product guide and the Kang paper. Extract the detection limit and the distribution of well emissions (not only the mean, since 3 of 19 were high emitters).
2. **Detection-limit note** `docs/iterations/methane_detection_limit_note.md`. Units in kg per hour. Compute the ratio of detection limit to mean emission and to the high-emitter range. Write the conclusion.
3. **Close or continue.** If the ratio is orders of magnitude for the mean and for the high emitters, close 4.4 for Pennsylvania. Otherwise, continue below.
4. **Observation opportunity audit** (only if continued). Script `s5_eval/_plume_catalogue_overlay.py` (new). Intersect plume footprints with well points and active facility layers. Record observation counts per area, retrieval quality, repeated observations of the same source, and selection toward known emitters.
5. **Source localisation.** A plume footprint is not a source-location uncertainty region. Use catalogue uncertainty fields if present.

## 7. Statistical analysis plan
None if closed. If continued, association with observation counts as an offset, and repeated observations modelled at source level.

## 8. Quality control
Units checked. Sources cited with versions.

## 9. Gates
Closed for Pennsylvania when the note shows the mean and high-emitter emissions sit well below the detection limit. Else continue.

## 10. Deliverables
`C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\methane_detection_limit_note.md`, citations.

## 11. Failure modes
A super-emitter well breaks the closure. Check the high-emitter range explicitly.

## 12. Resources
4 hours.

## 13. Handoff
Read both sources fully before closing.

## 14. Documentation updates
Note, `literature/CITATIONS.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
The Tanager threshold is checked (90 to 180 kg/h at 90% detection, stated conditions). The closure covers routine screening of ordinary small wells only. It does not bound rare large emitters.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

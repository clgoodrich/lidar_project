# Framework 4.1. Magnetometry pilot

**Tier A.**
**Evidence level.** (c) steel anomaly. Not a well identification.
**Depends on.** R3 (instrument), site access, 6.5.
**Blocks.** 7.5 field design.

## 1. Problem and objective
Lidar sees the surface. Steel casing sits below it. A magnetometer can detect buried steel and give independent coordinates. NETL states that magnetics detect ferromagnetic material (casing remnants and other oil-field metal alike) and cannot see wooden or removed casing (confirmed at its page). A review cites Hammack et al. (2023) for missed 1860 to 1880 wells in forested Pennsylvania (reported, not yet read). So a null is uninformative exactly where undocumented wells are most likely.

**Objective.** A practical pilot at 3 to 5 sites that measures (a) whether an anomaly is detectable and (b) how far it sits from the borehole and from the lidar centroid, with era strata and confusers. It tests practicality, not population sensitivity.

## 2. Scope
In. Ground magnetometer pilot, processing, reporting, protocol for later UAV.
Out. Population sensitivity (7.5). UAV or helicopter surveys (a separate sub-study).

## 3. Definitions
- **Era strata.** (1) Documented steel-era well (DEP record with a post-1930 date). (2) Early-era well (independently dated, for example on a historic map). (2b) Unknown-date well (1800 sentinel), its own stratum. (3) Pit with no record. (4) Metal confuser (culvert, fence, buried pipe, vehicle). (5) Blank control.
- **Anomaly.** A residual field feature above 3 times the local noise standard deviation after removing the regional field and diurnal drift, with a dipole or monopole shape consistent with a vertical steel casing.
- **Localisation error.** Distance from anomaly peak to the surveyed borehole or wellhead, where one is visible.

## 4. Inputs
| Input | State |
|---|---|
| Magnetometer, base station, GNSS | R3 (not arranged) |
| Site list | `data/<area>/results/magnetometry/pilot_sites.csv` (new) |
| DEP wells with dates and statuses | held |
| Lidar candidates and features | held |
| Historic marks | 4.6 (future) |
| Landowner permission | partner |

## 5. Prerequisites and decisions
Instrument access. Safety training. Permission. A decision on sites (see S0).

## 6. Procedure
**S0. Site selection.**
- Choose 3 to 5 sites covering at least three strata. Prefer sites with a visible wellhead or a record for strata 1 and 2 so localisation error can be measured. One metal confuser and one blank control. Document why each was chosen (selection is not random, so this is not an estimate of sensitivity).

**S1. Protocol.**
- `docs/iterations/magnetometry_pilot_protocol.md`. Instrument model and sensor type (fluxgate or cesium), sensor height, line spacing (nominal 1 m for a 20 m by 20 m grid, wider for the approach), walking speed and sampling rate, base station placement and time sync, GNSS method and datum (RTK if available), weather and time-of-day constraints, removal of personal metal, field sheet.

**S2. Field data and sheet.**
- `docs/iterations/magnetometry_field_sheet.md`. Record site, date, operator, instrument settings, GNSS accuracy, hazards, photographs, wellhead coordinates, observed surface evidence.

**S3. Processing.**
- Script `notebooks/wellsight_v2/s5_eval/_mag_process.py` (new). Read raw files (format depends on instrument). Steps. Despike, correct diurnal drift using the base station, remove the regional field with a low-order polynomial fit, grid to 0.25 m by kriging or minimum curvature, compute total field residual, vertical gradient or analytic signal. Output `data/<area>/results/magnetometry/mag_residual_<site>.tif`, `mag_anomalies_<site>.csv` (peak amplitude, position, signal to noise, width).
- Check. Noise standard deviation per site recorded. Calibration against a known steel object at each site (a test object placed at a known position).

**S4. Reporting.**
- Table per site. Stratum, anomaly present or absent, amplitude, localisation error to wellhead and to lidar centroid, evidence of casing. Report each site as a single case. Do not pool across strata.

**S5. Feed forward.**
- Update 7.5 design with realised noise, achievable search radius per hour, and which strata need non-magnetic evidence.

## 7. Statistical analysis plan
- Descriptive. Per-site outcomes. Localisation error summary with range (n too small for an interval).
- No hypothesis tests at 3 to 5 sites. State that this tests practicality.

## 8. Quality control
- Base station coverage for every survey. Instrument zeroed. Duplicate line check (repeat one line per site, compare).
- GNSS accuracy logged for every wellhead.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Pilot passes | Reliable measurement under tested conditions (noise below target, repeat lines agree, confuser identified as confuser) | Proceed to 7.5 with magnetics as one evidence type |
| Pilot fails | Noise too high, access impractical, or confusers indistinguishable | Record and drop magnetics from 7.5 or change instrument |
| Not a gate | Population sensitivity | Needs 7.5 |

## 10. Deliverables
- Protocol and field sheet docs.
- `C:\Users\colto\Documents\GitHub\lidar_project\data\<area>\results\magnetometry\`
- Script `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_mag_process.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\magnetometry_pilot_results.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| No instrument | Stay on paper. Alternative is a metal detector survey with lower sensitivity |
| Wooden casing | Add non-magnetic evidence (cellar walls, cable-tool debris, historic position) |
| Casing cut and plugged | Expect weak anomalies. Record depth of cut if known |
| Interference | Test object and noise logging |
| Wells with gas | Methane screening first (6.5) |

## 12. Resources
Protocol 8 hours. Field about 1 to 2 days per site with two people. Processing 10 hours. Instrument loan or partner.

## 13. Handoff and open questions
- Read Hammack et al. (2023). Choose instrument.

## 14. Documentation updates
Protocol, results doc, `literature/CITATIONS.md` (Hammack, NETL page), `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
Unknown dates (1800 sentinel) are their own stratum, not early era. Magnetometry detects ferromagnetic material of any kind, so pilot with known targets, metal confusers and blanks. Record identity status apart from the outcome.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

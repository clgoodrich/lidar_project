# Framework 4.4. Methane plumes (detection-limit arithmetic gate, then a close or a large-leaker arm)

**Tier A (rewritten 2026-11-05 at the user's request to stop deferring).** Stage M0 is arithmetic and reading. Nothing here has been run.
**Evidence level.** None of (a) to (d). A plume is regional association with a source area. It cannot attribute emission to a candidate well and it is not evidence level (d).
**Depends on.** D3 (Kang et al. 2014) and D4 (Carbon Mapper product guide) to be read. Well points from the DEP export.
**Blocks.** Any satellite-based prioritisation of wells.
**Pre-specified outcome.** The framework may end at M0 with a CLOSE for Pennsylvania small-well attribution. That is allowed and is likely given the figures below. The framework then becomes the large-leaker arm, in Pennsylvania and in other basins.

## 1. Problem and objective
Satellites report methane plumes above a detection limit. An open abandoned well leaks small amounts. Whether any satellite plume can be tied to a Pennsylvania abandoned or candidate well is a question of physics before it is a question of statistics.

**Question 0 (detection limit).** Is the emission rate of an ordinary abandoned Pennsylvania well, or of its measured high-emitter tail, inside the detection capability of any available satellite, under the best plausible wind and surface conditions?
**Question 1 (large leakers).** Where emitters above the limit exist (blowouts, super-emitters, aggregated sites, other basins), do catalogued plumes fall at documented or candidate wells more often than expected given observation opportunity?
**Question 2 (source localisation).** When a plume is near a well, is the well the plausible source, given the plume's source-location uncertainty and the active facilities nearby?

## 2. Scope
In. The detection-limit arithmetic. A catalogue overlay for large emitters over Pennsylvania and any chosen other basin. A repeated-observation model at source level.
Out. Attributing any plume to one candidate well from a satellite alone. Routine satellite screening of small wells. Quantifying emission of a well.

## 3. Definitions
- **Detection limit (DL).** Emission rate in kg per hour with 90% detection probability for an instrument under stated wind, solar zenith, albedo and ground sample distance.
- **Ratio R.** DL divided by the emission rate of interest. R above 1 means the source sits below the limit.
- **Mean well emission.** From Kang et al. (2014), 19 abandoned Pennsylvania wells, 42 measurements, mean about 0.27 kg per day per well, 3 of 19 high emitters. 0.27 kg per day is about 0.011 kg per hour. Figures taken from the review `docs/plans/adversarial_review_claude.md` B13 and `docs/plans/protocol_gates_and_metrics.md` section 9. VERIFY against the paper.
- **Review's DL.** Carbon Mapper lists a Tanager 90% detection probability of 90 to 180 kg per hour at 3 m/s wind, 35 degree solar zenith, 25% albedo and 30 m ground sample distance. Taken from the review, checked at carbonmapper.org on 2026-11-04 per the protocol. VERIFY against the product guide.
- **Aggregation count N.** DL divided by mean well emission. The number of mean wells that would have to sit in one footprint to reach the limit.
- **Source.** A persistent emission point, the unit for repeated observations. Plumes are observations of a source.
- **Observation opportunity.** Count of usable acquisitions over an area, with quality flags.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Kang et al. 2014 PDF | `literature/papers/` (name per filename rule) | D3 to fetch |
| Carbon Mapper product guide | `literature/papers/` | D4 to fetch |
| DEP well points | DEP export and `venango_wells_all` (through `path_for`) | held |
| Candidate well points | `data/9t/results/wells/` outputs (confirm names) | held |
| Active facility layers | DEP or state facility layers | proposed |
| Plume catalogue and observation records | `data/OTHER_DATA/derived/methane/` | proposed, assumed to exist |
| Gate and overlay outputs | `data/9t/results/methane/` | proposed |

## 5. Assumed data
Assumed to exist. Each item is tagged VERIFY with its check.

| Assumed item | Detail assumed | VERIFY by |
|---|---|---|
| Carbon Mapper plume list (L2B) | Per plume point or polygon, centroid, emission rate in kg per hour and uncertainty, instrument, date and time, sector label, quality flag, wind source. Open licence (CC BY style assumed) | Download the list. Check the field names and the licence text |
| Carbon Mapper gridded maps (L3) | Concentration enhancement rasters per overpass at 30 m (Tanager) | Product guide |
| Observation records | For each overpass, footprint, date, whether a plume search was done and the quality flag. Needed for observation opportunity | Ask whether non-detections and coverage footprints are published. If not, opportunity cannot be computed and Question 1 reduces to a descriptive map |
| Tanager (Carbon Mapper) | 30 m ground sample, DL per section 3, launch 2024, public data policy for the plume list | Product guide and data policy |
| EMIT (NASA, on the ISS) | About 60 m, plumes listed on a public portal, DL assumed in the hundreds of kg per hour | Read the EMIT guide. Fill the number from the source |
| GHGSat and similar | 25 m class, commercial. DL assumed near 100 to 200 kg per hour | Vendor specification and licence. Likely paid |
| Aircraft imaging spectrometer campaigns | DL assumed lower than satellite by an order of magnitude, coverage only where flown | Campaign reports for Appalachia. Confirm flight lines |
| Wind | Reanalysis winds at overpass, 10 m and averaged | Data source and uncertainty. The DL depends on wind |
| Kang et al. measured rates | Per well rates, not only the mean | Read tables and supplement |
| Large-emitter ground truth elsewhere | Documented blowouts or high-flow orphan wells in another basin, with a rate | Search state agency records. Not assumed for Pennsylvania |

## 6. Prerequisites and decisions
- User decision. The best-case factor on the DL (wind and albedo). Proposed default 10 times lower than the review's figure.
- User decision. The ratio at which closure is called. Proposed default R at least 100 at the best case.
- User decision. Which other basins, if the framework continues there.
- Read D3 and D4 fully before any ratio is final.

## 7. Procedure
**M0. Detection-limit arithmetic gate (no spatial data).**
- Script `notebooks/wellsight_v2/s5_eval/_methane_gate_limit_pa.py` (proposed) writes the table from numbers entered in a JSON file with their source page.
- Step 1. Convert all rates to kg per hour. Mean well 0.27 kg per day gives 0.01125 kg per hour. DL low 90 and DL high 180.
- Step 2. Ratio at the review's DL. R_mean is 90 divided by 0.01125, which is 8,000, and 180 divided by 0.01125, which is 16,000. Those figures are about four orders of magnitude. They are arithmetic from the review's inputs and must be recomputed from the sources.
- Step 3. Best-case ratio. Divide the DL by the best-case factor. With a factor of 10, R_mean is still 800.
- Step 4. High-emitter range. From Kang, the largest measured rate and the rates of the 3 of 19 high emitters. R_high is the best-case DL over the largest measured rate. If the largest measured rate is above the best-case DL, the closure fails for that tail.
- Step 5. Aggregation. N equals DL over mean emission. At the review's DL, N is about 8,000 to 16,000 mean wells in one footprint. Compare with the number of documented wells in one 30 m pixel (at most a handful on a lease).
- Step 6. Tail. Fit a lognormal and a heavy-tail alternative to Kang's per-well rates. Expected number of Pennsylvania wells at or above the best-case DL equals fitted tail probability times the DEP well count. Report both fits and the interval. A small sample of 19 wells makes the tail uncertain, so report the bound and not a point.
- Outputs `data/9t/results/methane/methane_gate_limit_pa.json` and `methane_gate_limit_pa.csv`, figure `methane_gate_ratio_bars_pa.png`.
- Note `docs/iterations/methane_detection_limit_pa.md`.

**M1. Decision.** Apply the gate in section 10. If CLOSE, write the closure note, stop Pennsylvania small-well work, and record that large-leaker work in section 7 M2 is the only live branch.

**M2. Catalogue overlay for large emitters (Pennsylvania rare tail and other basins).**
- Script `s5_eval/_methane_plume_overlay_pa.py` (proposed). Intersect plume points with well points, facility layers and pad polygons. Use each plume's source-location uncertainty field and never the plume footprint as the uncertainty region.
- Output `data/OTHER_DATA/results/methane/methane_overlay_by_source.csv` (proposed path, confirm with `path_for`).
- Observation opportunity table `methane_opportunity_by_cell.csv`. Usable overpass count per 5 km cell and quality flag.

**M3. Source-level model.**
- Script `s5_eval/_methane_source_model_pa.py` (proposed). Plumes grouped into persistent sources. Count of sources near wells versus near facilities, with observation opportunity as an offset and selection toward known emitters stated.
- Attribution rule. A source is attributed to a well only if no active facility lies within its uncertainty radius and a repeat observation agrees. Otherwise the output reads "plume near well" and nothing more.

**M4. Other basins.**
- Repeat M0 with the basin's measured well rates. Repeat M2 and M3 with that basin's well and facility data. The unit of inference is the source and the basin is the cluster.

## 8. Statistical analysis plan
- M0 has no inference beyond the tail interval and the ratio at best case. It is arithmetic with a stated uncertainty.
- M3 primary. Rate ratio of plume sources near wells versus matched control locations, Poisson or negative binomial with log observation count as offset, source as the unit, basin or cell as cluster. Interval by cluster bootstrap.
- Repeated observations of one source are one source. Repeated overpasses and extra plumes are not independent.
- Facility confounding. Report with and without cells holding an active facility.
- Selection toward known emitters. Report the share of plumes whose source was already known before detection, if the catalogue records it.
- A plume near a candidate well is labelled "plume near candidate" with its distance and uncertainty, never as the cause.

## 9. Quality control and leakage checks
1. Units checked in every table (kg per hour, kg per day, tonnes per hour).
2. Each source figure cites file, page and version. Typed numbers are not allowed.
3. Every join has expected and observed counts. Catalogue queries paginate and compare the retrieved total with the reported total. Empty, failed and incomplete results are separated.
4. CRS asserted (plume catalogue geographic, wells UTM). Distances computed in a metric CRS.
5. No candidate well is used to define a control.
6. Dates and times kept in UTC and converted for wind.
7. Second run gives identical output.
8. Every number in a document comes from a saved file.

## 10. Gates
Margin source. The factor 100 is a headroom for wind, albedo and retrieval variance. It is a decision margin on a ratio and not a variance quantity.

| Stage | Success (proceed to attribution for small wells) | Failure (CLOSE for Pennsylvania small wells) | Inconclusive | Action |
|---|---|---|---|---|
| M0 mean | R_mean at best case at or below 1 | R_mean at best case at least 100 | Between 1 and 100 | Failure is a pre-specified CLOSE |
| M0 tail | Expected wells at or above best-case DL at least 1 with lower bound above 0 | Expected count upper bound below 1 and largest measured rate below best-case DL | Otherwise | Inconclusive keeps M2 for the tail only |
| M0 aggregation | N at most the number of wells in a footprint | N at least 100 times the wells in a footprint | Between | |
| M2, M3 | Source-level rate ratio lower bound above the useful ratio | Upper bound below it | Otherwise | Only if M0 left a live branch |

The expected outcome from the review's figures is CLOSE for Pennsylvania small wells. Closing is not manufactured. It follows if the sources confirm the review's numbers. It does not bound rare large emitters, and it does not apply to other basins or other instruments.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\methane_detection_limit_pa.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_methane_gate_limit_pa.py`, `_methane_plume_overlay_pa.py`, `_methane_source_model_pa.py` (all proposed)
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\methane\methane_gate_limit_pa.json`, `methane_gate_limit_pa.csv`, `methane_gate_ratio_bars_pa.png`
- `C:\Users\colto\Documents\GitHub\lidar_project\literature\CITATIONS.md` entries and PDFs in `C:\Users\colto\Documents\GitHub\lidar_project\literature\papers\`

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| A super-emitter well breaks the closure | Step 4 and step 6 test the tail explicitly |
| DL figure was misread or from other conditions | Read the guide. Record the wind, zenith, albedo and GSD behind each number |
| 19 wells under-represent the population | Report the bound. Seek further measurements (EPA, state or academic datasets) as an assumed addition |
| Plume near a facility is not from the well | Attribution rule in M3 |
| No non-detection records | Opportunity unavailable. Report descriptive map only |
| Selection toward known emitters | State it. Do not read as base rate |
| Closure read as a general claim | Wording limited to the stated instrument and conditions |

## 13. Resources
M0 about 6 hours including reading. M1 under 2 hours. M2 and M3 about 20 hours if a live branch remains. M4 about 20 hours per basin. No GPU. Catalogue under 1 GB.

## 14. Handoff and open questions
- Fetch D3 and D4 and read them fully before any ratio is final.
- Fill the DL for each assumed sensor from its guide.
- Decide the best-case factor, the closure ratio and the other basins.
- Confirm whether observation records and non-detections are published.

## 15. Documentation updates
`docs/iterations/methane_detection_limit_pa.md`, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, `literature/CITATIONS.md`, `docs/plans/EXPANSION_MASTER_PLAN.md`.

## Rewrite note (2026-11-05)
Replaces the Tier B text. Figures are taken from `docs/plans/adversarial_review_claude.md` B13 and `docs/plans/protocol_gates_and_metrics.md` section 9 and are marked VERIFY.

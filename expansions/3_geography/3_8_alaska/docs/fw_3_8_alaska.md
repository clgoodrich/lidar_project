# Framework 3.8. Alaska (permafrost displacement at legacy wells)

**Tier A (full design, data assumed).** Written 2026-11-05 after the user ended deferral. Nothing here has been run, fetched or measured. Every assumed input is tagged VERIFY in section 5.
**Evidence level.** None of (a) to (d). This study does not detect wells and does not test whether any location is a well. It estimates surface displacement at known legacy well sites against matched controls. Displacement is not well integrity.
**Depends on.** Nothing in the detector line. It reuses no model. Reads the NISAR notes only for tooling background (section 3).
**Blocks.** Nothing. A result here does not change any detector decision.

## 1. Problem and objective
Legacy wells in the Arctic sit in permafrost. Thawing ground can settle or heave around a pad. A monitoring programme would want to know whether well sites move differently from comparable ground.

**This is a different question from detection and it uses a different method.** The detector reads lidar terrain with a U-Net. This study reads a stack of radar phase images. The repository has no prior success with this method. The only radar work held here is NISAR over the Pennsylvania site 9t. It found no pit-scale signal and its pad scores were later shown to be confounded by location (`docs/iterations/nisar_gslc_interferogram_pits_9t.md`, `nisar_methodology_audit_20261026.md`). None of that work measures displacement at wells, and none of it was on tundra. Treat this as a new, unproven project.

**Estimand E1 (measurement, not a hypothesis).** The smallest displacement rate the chosen radar stack can resolve at a pad-sized target, given noise, reference stability and seasonal confounding.
**Estimand E2 (primary).** The difference, in millimetres per year of line-of-sight displacement, between legacy well sites and matched control sites with no wells, over a stated multi-year window, relative to a stable reference.
**Estimand E3 (exploratory).** The same difference for the seasonal thaw-season amplitude.

**Hypotheses.** Decided by a two-sided rule around one threshold δ (section 10). The study can report that well sites move more than controls, that they do not by more than δ, or that it cannot tell.

**What this study can show.** Whether a radar stack can see millimetre to centimetre displacement at pad scale in this setting at all. Whether well sites differ from matched ground by more than δ. How large the confounding from seasonal thaw and hydrology is.
**What it cannot show.** Well integrity, leakage, casing condition or plugging state. That displacement comes from the well and not from the gravel pad, the road or the permafrost. Vertical motion, because radar measures motion along the line of sight. Anything at the well head itself (about 1 m) because the pixel is tens of metres.

## 2. Scope
In. Known legacy well sites with listed coordinates. Matched control sites. Multi-year stacks from one or more radar missions. A stability-checked reference. An injection-recovery test of the whole chain.
Out. Well detection from elevation or radar. Training any network. Wells with no coordinates. Claims about gas, oil or water leakage.

## 3. Definitions
- **Line-of-sight (LOS) displacement.** Motion along the radar-to-ground direction. Positive toward the satellite by the repository convention, to be fixed in the prereg.
- **Site.** One well pad or well cluster within 300 m. The site is the unit and the effective sample. Dates, pixels and wells are not independent.
- **Control site.** A location with no known well within 2 km, matched to a well site on land-cover class, ice-richness class, slope class, wetness, and distance to the nearest gravel road or pad. Same ecoregion and same radar frame.
- **Reference.** A set of coherent ground pixels whose motion is subtracted. A reference must pass the stability test in S4.
- **Noise floor.** The standard deviation of reference-corrected displacement at control sites, per interval.
- **Seasonal amplitude.** Peak-to-trough LOS change within a thaw season.
- **Long-term rate.** Slope of end-of-season to end-of-season displacement across years, which removes the seasonal cycle by design.
- **Injection-recovery.** Adding a known synthetic displacement to the phase at selected control pixels and recovering it through the whole chain.
- Tooling background. `notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py` fetches NISAR complex windows and `s5_eval/_nisar_gslc_interferogram_pits_9t.py` forms interferograms from consecutive dates. The 9t docs report median HH coherence 0.50 outside winter and no displacement difference between pits and decoys (about 7.5 mm phase noise per pit per 12-day pair). These numbers are for Pennsylvania forest and carry no weight here.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| USGS 2022 orphan list, 12 Alaska rows | `data/_source/reference/wells_us_orphan_2022/US_orphaned_wells.csv` | held |
| USGS 2026 orphan list, 44 Alaska rows (35 with blank status and type) | `data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv` | held |
| NISAR fetch and interferogram scripts (Pennsylvania) | `notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py`, `s5_eval/_nisar_gslc_interferogram_pits_9t.py` | held, reusable as a pattern only |
| Alaska wells, SAR stacks, elevation, controls | `data/_source/reference/wells_ak/`, `data/ak1/derived/` | proposed |

The US catalogue under `data/_source/reference/lidar_catalogue/` is United States 3DEP lidar listing and holds no Alaska radar or IfSAR rows.

## 5. Assumed data
Every row is an assumption with a VERIFY test.
| Item | Assumed to exist | Format, resolution, CRS | Fields | Licence and access | VERIFY (how) |
|---|---|---|---|---|---|
| Legacy well list | A federal list of legacy wells on the North Slope and National Petroleum Reserve in Alaska, plus the state commission well database | CSV or shapefile, NAD83 | Well name, API, status, drill dates, coordinates, coordinate source, pad type | Public. Terms unchecked | Obtain both. Count wells, pads and clusters within 300 m. Compare with the 12 and 44 rows held. Record coordinate method and plug status |
| Radar, C-band | Sentinel-1 IW SLC or processed interferograms over the slope, 6 to 12 day repeat | SLC or HyP3-style products at about 40 to 80 m posting | Acquisition date, track, polarisation | Open, ASF archive | Query the archive for each site. Count acquisitions per thaw season and year. Note gaps |
| Radar, L-band | NISAR L2 GUNW or GSLC over the slope on a 12-day repeat, beta and science phases | HDF5, 5 m GSLC, about 80 m GUNW | Date, track, polarisation, coherence layers | Open after release, terms unchecked | Check coverage over Alaska and the first date. The repository holds only Pennsylvania windows |
| Radar, L-band (option) | ALOS-2 PALSAR-2 archive | CEOS or GeoTIFF | Date, mode | Research proposal or commercial | Ask. Treat as optional |
| Elevation | Statewide IfSAR DTM at about 5 m, or lidar where it exists | GeoTIFF, EPSG:3338 or UTM 6 and 7 | Elevation, orthoimage | Public | Check vintage and the date of the underlying survey. Check void areas on wet tundra |
| Permafrost and ice context | Permafrost probability and ground-ice maps | Raster 30 m to 1 km | Class or probability | Public | Check vintage and scale. Used only for matching |
| Land cover | National land cover for Alaska | Raster 30 m | Class | Public | Check class list |
| Active-layer ground truth | Active-layer monitoring sites and borehole temperatures | Tables | Thaw depth, date, subsidence where measured | Public | Count sites within 50 km of any radar frame and list the years observed |
| Weather and snow | Reanalysis air temperature, precipitation, snow cover | Gridded | Daily | Public | Check coverage. Used as covariates and to flag wet or snowy dates |
| Tools | Open radar time-series software (interferogram formation and small-baseline inversion) | Python | Not applicable | Open source | Run a toy example on any open stack and record versions in `requirements_lock.txt` |
| Reviewer | A permafrost or InSAR scientist | Not data | Review of S3 to S5 | Volunteer | Confirm one before S5. Without one, the result is internal only |

Literature to read and cite before acting on it (cite-only until a copy is held). L-band interferometry for active-layer thickness and seasonal subsidence on the North Slope, and the remotely sensed active-layer thickness product. Authors and years are recalled, not verified. Add them to `literature/CITATIONS.md` in the same change that uses them.

## 6. Prerequisites and decisions
User decisions before preregistration.
- **D-AK1.** δ in mm per year, with its source. The displacement a monitoring programme would act on. No default is supplied.
- **D-AK2.** Which radar missions to include.
- **D-AK3.** Reviewer. The study is not run without one.
- **D-AK4.** Study window and number of thaw seasons.
Prerequisite. S0 (metadata check) and S1 (observability gate) must pass before S2.

## 7. Procedure
**S0. Metadata and tools check.** Verify the rows in section 5. Count wells, sites and controls. Write `docs/iterations/alaska_data_verification.md`. Stop at any failure.
- Script `notebooks/wellsight_v2/s1_build/_ak_wells_inventory.py` (proposed). Output `data/ak1/derived/ak_wells_sites_ak1.gpkg`, `ak_controls_ak1.gpkg`.

**S1. Observability gate (protocol section 9).** Measure before any statistics.
- Fraction of the radar pixel a pad fills, at each mission posting.
- Usable acquisitions per site, per thaw season, per year.
- Spatial support after multilooking, and registration error against IfSAR.
- Plausible signal against variability. Compare δ with the expected noise floor from the literature once read.
- Script `s5_eval/_ak_observability_ak1.py` (proposed). Output `data/ak1/results/ak_observability_ak1.csv`. Decision go, no-go or defer, written in the verification doc.

**S2. Stack formation.** Pull the radar data for one frame over a set of sites. Form interferograms with short temporal baselines. Invert to a time series with small-baseline or distributed-scatterer methods. Correct for atmosphere with reanalysis and, for L-band, for ionospheric phase (strong at high latitude).
- Scripts `s1_build/_ak_fetch_stack_ak1.py`, `s1_build/_ak_insar_series_ak1.py` (proposed). Outputs under `data/ak1/derived/ak_stack_ak1/`.
- Pilot first. Process 3 to 5 sites and 3 to 5 controls only and review every interferogram by eye before scaling.
- Closure-phase check on triplets. Large closure phase signals soil-moisture bias and the interval is flagged.

**S3. Reference stability.** Choose several candidate references by coherence and low variance. Compare pairs of references. A reference passes if the difference of two independent references stays inside the noise floor over the whole window.
- Script `s5_eval/_ak_reference_test_ak1.py` (proposed). Output `data/ak1/results/ak_reference_stability_ak1.csv`.

**S4. Injection-recovery (acceptance test).** Add known LOS displacement (ramps and seasonal cycles of several amplitudes, 10 pixel footprint) to control pixels in the raw phase. Run the full chain. Report the recovered fraction and bias per amplitude and per coherence band.
- Script `s5_eval/_ak_injection_recovery_ak1.py` (proposed). Output `data/ak1/results/ak_injection_recovery_ak1.csv`. A pipeline that cannot recover 2 times δ fails readiness.

**S5. Matching and estimation.** Match controls (section 3). Compute per-site long-term rate and seasonal amplitude. Estimate E2 and E3.
- Scripts `s5_eval/_ak_site_matching_ak1.py`, `_ak_rate_difference_ak1.py` (proposed). Outputs `data/ak1/results/ak_rate_difference_ak1.csv` and `ak_rate_difference_ak1.json`.

**S6. Location-only baseline and placebo.** Predict well versus control from coordinates and matching covariates alone. Run placebo sets by choosing control sites as pseudo-wells (S6 uses the same matched design). The NISAR audit showed a coordinate-only classifier can beat a radar feature set, so this check is required.
- Script `s5_eval/_ak_placebo_ak1.py` (proposed). Output `data/ak1/results/ak_placebo_ak1.csv`.

**S7. Optional ground check.** Compare series with active-layer thaw depth and subsidence at monitoring sites. A sanity check of the seasonal signal, not a validation of well results.

## 8. Statistical analysis plan
- **Primary (E2).** Matched-pair difference in long-term LOS rate, well site minus its matched control set mean, one number per site. Median difference with a site-level bootstrap, B = 2000, and a permutation interval (swap labels within matching strata). Equivalence and difference both judged against δ.
- **Spatial dependence.** Use an empirical variogram of control-site rates to set the minimum separation between sites. Treat sites within that range as one cluster.
- **Projected width.** Before S5, resample n well-site-sized sets from control sites only, B = 2000, and take the median interval width. If it exceeds 2 δ, the design has no power at the available n and the study is reported as underpowered. With 12 to 44 listed Alaska rows and unknown clustering, this may fail.
- **Secondary.** Seasonal amplitude difference (E3). Effects of coherence, pad type, plug status, gravel thickness, distance to road (exploratory, labelled).
- **Baselines.** Location-only and covariate-only predictors against the displacement feature (S6).
- **Calibration of noise.** Report the noise floor from S3 and S4 with every result.
- **Multiplicity.** One primary estimand. All else exploratory.
- **Effective sample.** Sites. Not pixels, dates, wells or interferograms.

## 9. Quality control and leakage checks
1. Row counts at every join. CRS asserted for every layer and every stack. Orbit, track and frame logged.
2. Sign convention and reference location written in every output.
3. Controls chosen before any displacement value is read. The matching file is hashed and committed.
4. No site selected or dropped after viewing its series. Drops come from coherence rules fixed in the prereg and are counted.
5. Dates with snow, flood or wet snowmelt flagged from weather data and reported both ways.
6. Atmosphere and ionosphere corrections logged with versions.
7. Interferogram samples reviewed by eye, with unwrapping errors counted.
8. Hash match for inputs and a same-config rerun gives the same numbers.
9. Placebo and injection results saved before well results are unmasked.
10. Figures use blue `#1F5FA8` for well sites and orange `#D97706` for controls with a second encoding by marker shape.

## 10. Gates
Margin source. δ is the displacement rate a monitoring programme would act on (D-AK1). It is never taken from noise or variance.
| Outcome | Rule | Action |
|---|---|---|
| Readiness (S1, S3, S4) | Pad fills a usable share of a pixel, enough acquisitions, reference passes, injection recovers 2 times δ | Run S5 |
| No-go | Any readiness item fails | Report as not observable with this stack. Do not run S5 |
| Decisive, difference | Lower bound of the absolute median difference above δ | Well sites move more than matched ground. Not an integrity claim |
| Decisive, equivalence | Interval inside minus δ to plus δ | No difference larger than δ detected at this noise floor |
| Inconclusive | Otherwise, or projected width above 2 δ | Report. Add sites or seasons |
| Placebo | Placebo interval excludes zero | The design is biased. Stop and fix |
| Location-only baseline | Matches the displacement feature | No site-specific signal beyond location |

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\alaska_data_verification.md`, `alaska_displacement_prereg_ak1.md`, `alaska_displacement_ak1.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\_ak_wells_inventory.py`, `_ak_fetch_stack_ak1.py`, `_ak_insar_series_ak1.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_ak_observability_ak1.py`, `_ak_reference_test_ak1.py`, `_ak_injection_recovery_ak1.py`, `_ak_site_matching_ak1.py`, `_ak_rate_difference_ak1.py`, `_ak_placebo_ak1.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\ak1\results\` and `data\ak1\derived\ak_stack_ak1\`
- Heavy stacks get a `.gitignore` rule in the same change.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Decorrelation on wet tundra and in summer | Coherence mask. Report retained share. Prefer L-band |
| Seasonal thaw and frost heave | End-of-season comparison and seasonal term. Report both |
| Snowmelt flooding and hydrology | Weather flags and wetness matching |
| Pad is gravel on ice-rich ground, so the pad and the well cannot be separated | State plainly. The estimate is for the site, not the well |
| Reference moves | S3 test and several references |
| Ionosphere at L-band | Split-spectrum or reanalysis correction, report residual |
| Too few sites | Projected width. Report underpowered |
| Coordinates off by tens of metres | Use the pad footprint from IfSAR orthoimage. Report offsets |
| Unwrapping errors | Short baselines, review, count |
| Misreading motion as integrity | Wording rule in every output |

## 13. Resources
Reconnaissance about 80 hours (the earlier estimate). Full study about 200 to 300 hours of person time (unmeasured, uncertain). Radar processing is the cost driver. HyP3-style products keep disk to tens of GB. Raw SLC stacks over many years can reach about 1 to 2 TB and need F: or an external drive (measure one frame first). GPU is not required. Calendar dependency. NISAR science data availability and the reviewer.

## 14. Handoff and open questions
- D-AK1 to D-AK4.
- Whether the federal list gives site coordinates good to a pad width.
- Which radar mission covers the sites with enough acquisitions.
- Whether n is large enough (section 8 projected width).
- Stop and report on a failed readiness gate. A no-go is a valid result.

## 15. Documentation updates
The three iteration docs, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, master plan, `literature/CITATIONS.md` (radar methods and permafrost sources), `requirements_lock.txt` if new packages enter.

## Review revision 2 (third review, 2026-11-04) and 2026-11-05 expansion
Motion is not well integrity. This framework states line-of-sight displacement as its own estimand, requires a reference-stability test, an injection-recovery test, matched controls and a location-only baseline, and keeps the study off the (a) to (d) scale.
Source. `docs/plans/protocol_gates_and_metrics.md` sections 9 and 16, `docs/iterations/nisar_methodology_audit_20261026.md`.

# Framework 4.7. Drone lidar density ladder

**Tier A.** A request now, analysis when data arrive.
**Evidence level.** (a). Level (d) only for sites with independent confirmation.
**Depends on.** R2 (NETL request), 3.0 scorer, P1.
**Blocks.** Nothing.

## 1. Problem and objective
NETL reports that 63 potential well sites on two hillsides at Oil Creek were located using lidar. They are potential sites found with lidar, not confirmed wells. The page does not say any drone data are released. It is unknown how detection depends on point density.

**Objective.** Measure recall at K against point density on the same sites by thinning one native drone acquisition. State that the curve is conditional on lidar-visible sites.

**Hypotheses.** None for a pass or fail. The output is a curve and the density at which recall drops below a stated share of its native value.

## 2. Scope
In. Request, provenance check, thinning ladder, model run, curve, comparison with airborne.
Out. Claims about representative sensitivity or about a different platform's geometry.

## 3. Definitions
- **Native density.** Ground returns per m² in the drone point cloud.
- **Thinning ladder.** Random thinning to 100%, 50%, 25%, 10%, 5% and 2% of native, repeated 5 times per rung with seeds.
- **Rung density.** Measured ground returns per m² after thinning, per site.
- **Anchor.** The 9t airborne ground density (2.70 points per m² measured).

## 4. Inputs
| Input | State |
|---|---|
| Drone point clouds (LAS or LAZ), acquisition metadata | R2 request, not made |
| Site list, selection history and any field confirmation | R2 |
| Coordinates and their method | R2 |
| 9t airborne for comparison | held |
| Frozen models | P1 |

## 5. Prerequisites and decisions
NETL reply and data-use terms. Disk on F: (size unknown). Choice of model (isolated pit model).

## 6. Procedure
**S0. Request.**
- Send the NETL message from `docs/iterations/outreach_requests_drafts.md` (user). Ask for point clouds, sensor, flight height, date, pulse density, ground density, canopy condition, site selection history, coordinates and method, field confirmation notes and release terms. Log in `docs/iterations/outreach_log.md`.

**S1. Provenance.**
- On receipt, document `docs/iterations/drone_lidar_provenance.md`. Dataset identity, platform, coverage polygon, CRS, datum, number of sites, how sites were chosen, whether any were confirmed. If sites were chosen by lidar visibility, label every result "conditional on visibility".

**S2. Ingest and measure.**
- Script `notebooks/wellsight_v2/s1_build/_drone_ingest.py` (new). Read with PDAL CLI via `run_pipeline`. Compute ground density map, canopy, void fraction. Store under `data/oil_creek/derived/drone_native/` on F: with a `.gitignore` rule.

**S3. Thinning ladder.**
- Script `s1_build/_thin_drone_lidar.py` (new). Thin ground and non-ground returns by random sampling at the rung rates, 5 seeds per rung. Do not thin by grid, which changes spacing. Output thinned clouds to F: (large). Record measured density per rung.

**S4. Derivatives and inference.**
- Build the 9t feature stack from each thinned cloud at 0.5 m with the 9t builders. Run the frozen model. Use the same grid and normalisation as 9t. Output probability rasters and void fraction per rung.

**S5. Score.**
- For each rung and seed compute recall at K = 40 per km² on the site footprint with `_transfer_score.py`, against drawn features or confirmed wells where available. Curve versus measured ground density. Anchor line at 2.70 points per m².

**S6. Airborne comparison (separate).**
- Compare native drone at the 9t density rung with 9t-like airborne performance. Describe, do not attribute, because platform, season and processing differ.

## 7. Statistical analysis plan
- Curve of recall versus density with a bootstrap interval over sites (cluster by hillside) and a band across seeds.
- Report the density where recall falls to 90% and 75% of native.
- Say every curve is conditional on lidar-visible sites.

## 8. Quality control
- Thinning is random per point class, with the seed in the output.
- Measured density per rung printed.
- Check that thinned clouds still match the original positions (no re-projection).

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Data and provenance in hand | Run S2 to S5 |
| Not a pass-fail gate | A curve | Describe |
| Close | NETL declines | Close 4.7 |

## 10. Deliverables
- Scripts in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\` as named
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\drone_lidar_provenance.md`, `drone_density_ladder.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\oil_creek\results\drone\` curves

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Data not released | Close the item. Use a public sUAS alternative if found |
| Selection by visibility | Label as conditional |
| Different platform geometry | Do not attribute differences |
| Very large files | F: only, thin on the fly |

## 12. Resources
About 10 hours once data arrive. Disk unknown (possibly tens of GB). GPU minutes per rung.

## 13. Handoff and open questions
- Reply from NETL. Data size.

## 14. Documentation updates
Provenance doc, density doc, `literature/CITATIONS.md`, `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
Report a paired response curve over retained ground density. No universal threshold and no cross-platform equivalence claim.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

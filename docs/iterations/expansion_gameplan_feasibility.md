# Expansion gameplan and feasibility

**Date:** 2026-11-04
**Status:** Plan. Written to be handed off. The assistant account that wrote it ends within days, so every task below names its inputs, steps, outputs and acceptance test.
**Companion:** `docs/iterations/expansion_options_methods.md` holds the method behind each item. This file says whether each item can be done, by whom, in what order, and how to stop.

## Revisions after the second outside review (2026-11-04)
These override the matching text below.
- **A9 moves first.** A7 depends on the pre-registration template.
- **A2 repaired and rerun.** Eligibility is the scored footprint including zero-detection blocks, identical for observed and shifted records, whole-set translation. Primary radius fixed before looking (pits 50 m, pads inside). Other radii are sensitivity only. Result unchanged (see `record_assoc_pits_9t.md`).
- **Audit set is not untouched by default.** Before A1 calls any block untouched, list every model, threshold and negative-mining step that used it. Exclude audit blocks from later training, calibration, mining and selection, including models that supply context features. The strongest final test is a new area.
- **A1 review package.** The existing builder is a QGIS correction package with default "keep". The blinded multi-class contact sheet is new work. Budget 2 hours per 20 candidates per reviewer, not 2 hours for 150 with two reviewers.
- **A3.** Add sham edits, realistic terrain backgrounds, derivatives recomputed from the edited DEM, and all-pit sampling beside the detected-only subset. Drop the half-score rule. Report paired changes in score and rank.
- **A4.** Prerequisite is an inventory of upstream checkpoints and splits. Missing road OOF models mean training, not just raster generation. Every upstream model must respect the outer fold exclusion.
- **A5 is blocked.** No flight dates are established. Plugged between 2006 and 2019 does not put plugging between the flights. Bound acquisition dates first, drop ambiguous wells, and treat the rest as exploratory. Plugging may leave no surface change.
- **A6.** The 1,316 count is Venango. Check overlap with inference coverage before power. Match groups on location, status and acquisition eligibility. Separate new discoveries from reclassifications.
- **A7.** Pre-register before viewing outputs. Keep adaptation and final test areas separate. Hash checkpoints and inputs, not only the commit.
- **A8.** Report usable here, unusable here or inconclusive. One frame is not a verdict. Test several dates and known positives, with independent check points.
- **B3.** Platt scaling is monotonic. Report calibration separately. It cannot change top-K recall.
- **B7.** Replace the density surface with a sensitivity and identifiability analysis until well-level precision and detection probability are supported.
- **Training reproducibility is a dependency.** Both CV scripts (`_pit_unet_cv5.py`, `_pad_unet_cv5.py`) rebuild splits at run time. Save explicit split manifests and check spatial separation before any retraining.
- **Gates.** Recall gap. Use a confidence interval for the difference and a prespecified non-inferiority margin, since overlapping intervals are not a test. Historical labels. Judge by independent interpretability and positional accuracy, since a low lidar score may be model failure. Confusers. Require confuser reduction and acceptable recall loss, since one failed run does not retire the idea. Field sample. Forty sites cannot give plus or minus 15 points in each of five score bins, so size the primary estimate first, then weight, cluster and allow for inaccessible sites.
- **Schedule.** A0 to A9 total about 49 hours, over six eight-hour days before debugging. The three-day calendar is optimistic. Independent items (historical coverage checks, instrument planning) need not wait for label review.
- **Resources.** Do not plan a county at 20 GB. Estimate from real tile sizes with decompressed clouds, derivative stacks and checkpoints. Pin the interpreter and dependencies instead of relying on plain `python`.
- **Item notes.** 3.3 needs sham edits and real low-slope pits. 3.4 keeps an unchanged zero-shot baseline. 4.7 needs the provenance of the 63 sites and native against thinned comparisons. 5.2 treats historical absence as censored. 5.3 keeps existence, hazard and exposure separate. 7.2 needs a random audit sample that is not tuned on. 7.5 sizes the primary estimate and uses independent searches to estimate recall.


## 0. How to use this file

1. Read section 1 for what the machine and the data can do.
2. Read section 3 for the verdict on every item.
3. Work section 5 in order. Each task is written so a person or another assistant can run it cold.
4. Use section 7 as the handoff checklist.

Hours are my estimates. Costs are not estimated because I have no quotes. Where a cost matters I say "get quotes".

## 1. What the machine and data can do (measured 2026-11-04)

| Resource | Finding | Consequence |
|---|---|---|
| GPU | NVIDIA GeForce GTX 1070 Ti, 8 GB. PyTorch 2.7.1 with CUDA 11.8 sees it. | U-Net training and inference on 256 px patches at small batch is fine. Large pretraining is not. |
| Disk | C: has 145 GB free. F: has about 3.2 TB free. | A county of lidar (about 20 GB of tiles) fits on C:. Bulk data goes on F:. E: is the only backup, per the repo notes. |
| Python | Project packages (geopandas, rasterio, torch) work with plain `python`. They fail with `python -I`. | Run scripts with `python script.py`. |
| Public lidar | The USGS TNM Access API answers from this machine. | Tiles for any US area can be listed and fetched by script. |
| Historic topo | The TNM API lists 31 Historical Topographic sheets over tile 9t, as GeoTIFF. Oil City and Titusville 1:62,500 sheets run 1922 to 1943. The 1:24,000 sheets are 1963 and 1967. | Pre-1956 coverage exists but at coarse scale. |
| Topo probe | One sheet (Oil City 1922, 1:62,500) was downloaded and cropped to 9t. See 4.6 below. | No well symbols were visible in the part of the crop that holds map. One sheet only. |
| Wells | `data/_source/reference/dep_wells/venango_wells_all.gpkg`. 20,108 Venango wells. 1,068 inside 9t. | Enough for tile-scale tests. |
| Detections | Out-of-fold pit detections and pad candidates on 9t. 204 pit detections after dropping second pieces. | Enough for association and context tests on 9t. |
| Second tile | 613590 has a saved pit transfer test, 153 floors. | Pit transfer has a first answer. |
| Warren lidar | Seven D20 tiles at `data/_source/lidar/warren_sheffield/`. | Warren work can start without a download. |
| Models | Pit and pad U-Net cross-validation checkpoints under `data/9t/models/`. | Inference on new tiles works without retraining. |

## 2. Feasibility scale

| Class | Meaning |
|---|---|
| F1 | Runs now on local data and the local GPU. No outside input. |
| F2 | Needs public data downloaded first. No outside input after that. |
| F3 | Needs a person to label or review. |
| F4 | Needs an outside party, permission, hardware or funding. |
| F5 | Not worth doing now. |

Value is the decision value for the project. High means it settles a question reviewers asked. Low means it is nice to have.

## 3. Feasibility matrix

| ID | Item | Class | Blocker | Hours | Value | Verdict |
|---|---|---|---|---:|---|---|
| 3.0 | Transfer protocol and prereg template | F1 | None | 6 | High | Do now |
| 3.1 | Warren and Forest, same survey | F2, F3 | Pad labels drawn blind to the model | 25 | High | Do now |
| 3.2 | OH, WV, NY, KY | F2, F3 | Find and convert each agency list | 25 each | Medium | After 3.1 |
| 3.3 | Illinois and Michigan basins | F2, F3 | Agency list. Context test needs nothing | 6 for the context test, 30 for an area | Medium | Context test now, area later |
| 3.4 | Gulf Coast, East Texas | F2, F3 | Ground density may be too thin | 30 | Medium | Later |
| 3.5 | Oklahoma and Kansas | F2, F3 | Agency list, optical arm | 35 | Medium | Later |
| 3.6 | California | F2, F3 | Status labels, urban masks | 40 | Low to medium | Later |
| 3.7 | Alberta, BC, Ontario | F2, F4 | Lidar licence, record format | 40 | Medium | Later. Ontario first |
| 3.8 | Alaska permafrost | F4, F5 | Data type, new method, sample size | 80 | Low now | Defer |
| 4.1 | Magnetometry | F4 | Hardware, access, partner | 10 for the pilot plan, 100 or more for a campaign | Highest | Start outreach now |
| 4.2 | Thermal infrared | F2 for satellite, F4 for drone | Pad is about one pixel | 12 satellite | Low | Quick test only |
| 4.3 | Vegetation stress | F2 | No leak labels. Pads are a few pixels | 15 | Low to medium | Pad screen only |
| 4.4 | Methane plumes | F2 | New data pipeline. Detection limits | 30 | Low to medium | Permian only, later |
| 4.5 | Multitemporal lidar plug-date test | F1 | Small sample | 5 | Medium | Do now |
| 4.6 | Historic topo and aerials | F2, F3 | Topo probe was negative. Aerials untested | 20 | High if aerials work | Probe aerials first |
| 4.7 | Drone lidar | F4 | Data request to NETL | 3 to ask, 10 to analyse | High | Send the request now |
| 4.8 | Leaf-off optical | F2 | Coverage check | 6 | Low | Only if cheap |
| 4.9 | More radar | F5 | No reason | 0 | None | Drop |
| 5.1 | Context features | F1 | Needs out-of-fold roads and pads | 8 | Medium | Do now |
| 5.2 | Era classification | F5 now | No labels | 15 | Low | Defer |
| 5.3 | Risk ranking | F2 | Public layers to gather | 20 | Medium later | After 5.4 |
| 5.4 | Undocumented-well density | F1 for the recall-gap test, F4 for precision | Well-level precision needs outside evidence | 15 for the gap test, 40 for the model | High | Gap test now |
| 5.5 | Polygon area and cost | F1 | Cost source | 8 | Low to medium | Later |
| 5.6 | Record association | F1, F4 for validation | Independent coordinates | 3 more for the next run | Medium | Next run now |
| 6.1 | CO₂ and geothermal framing | F1 for the document, F4 for a project | Partner | 10 | Funding value | After 5.4 |
| 6.2 | Coal mine features | F2, F3 | Inventory and labels | 40 | Medium | Later |
| 6.3 | Negative classes | F1, F3 | Reviewer time | 15 plus review | High | Do now |
| 6.4 | Hydrogen framing | F5 now | Same as 6.1 | 4 | Low | Defer |
| 6.5 | Field methane | F4 | Instrument | 2 to plan | Medium | Bundle with 7.5 |
| 6.6 | WiSAR and viewshed | F1 | Not a well question | 6 | None for wells | Separate |
| 7.1 | Self-supervised pretraining | F2 | 8 GB GPU limits scale | 40 | Medium | Small prototype only, later |
| 7.2 | Active learning | F3 | Needs independent labels first | 20 | Medium | After 6.3 and 4.1 |
| 7.3 | Public benchmark | F1, F3 | Label quality audit | 25 | Medium | After the audit set exists |
| 7.4 | Agency tooling | F1, F4 | First user | 40 | Medium | After 3.1 |
| 7.5 | Field campaign | F4 | People, funding, permits | Months | Highest | Plan now, run when funded |

## 4. Notes behind the verdicts

**Why the local machine is enough for most of it.** Inference and U-Net work fit an 8 GB card at small batch. The expensive step is labelling and field access, not compute.

**Why 4.1 is rated highest and F4.** It is the only item that gives evidence of steel that does not come from lidar. It needs a magnetometer, a person to run it, and landowner or state-land permission. Everything else can be done at a desk.

**4.6 probe result.** The Oil City 1922 sheet (1:62,500, NAD27 polyconic, 5.3 m per pixel) is saved at `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\historic_topo_probe\oil_city_1922_62500.tif` (8.7 MB). The 9t crop is `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\historic_topo_probe\crop_9t_oil_city_1922.png`. The sheet's north neatline runs through the tile, so the northern part of 9t lies on another sheet. No oil well or derrick symbols were visible in the mapped part at 3 times zoom. That is one sheet and one look. It lowers my expectation for topo sheets as a label source. Aerials from the 1930s to 1950s and oil-field maps from the state geological survey are the better candidates to test. Sheets are NAD27, so a datum transform is needed before any overlay.

**Why 5.4 is split.** The recall-gap test (recall on wells newly documented since 2022 against older wells) needs only detections and the DEP snapshots. The full density model needs well-level precision, and that needs outside evidence.

**Why 7.1 is small.** An 8 GB card with no tensor-core speedup on this generation limits pretraining to a small encoder and a few dozen tiles. It can show whether pretraining helps at all. It cannot be a headline result.

## 5. Gameplan

### Phase A. Days 0 to 3. Things that need the assistant's coding help or have long lead times

Run these first. Order is by value per hour. Do not start a task before its predecessor's output exists.

**A0. Send the lead-time requests (user, 1 hour).** These cost nothing to send and take weeks to answer.
- Ask NETL for the Oil City drone lidar point clouds and the 63 well coordinates (item 4.7).
- Ask one university geophysics group or a state survey whether a magnetometer can be borrowed, and what a pilot of 5 sites would need (item 4.1). Get quotes if a rental is the only route.
- Ask the DEP contacts in `docs/articles/well_reporting_outreach_contacts_pa_2026-08.md` whether any wells have GNSS-surveyed coordinates and whether a joint visit is possible (items 5.6, 7.5).
- Ask the professor whether McKean is still set aside, and where the thermal work is.

**A1. Freeze an audit set and build the confuser review package (6.3, 6 hours plus 2 hours review).**
- Inputs. `data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg` (layer `undecided`, 207 candidates, empty `status` field). The pad equivalents are `pad_candidates_unmatched_heldout_9t.shp`. The review builder is `notebooks/wellsight_v2/s6_review/_build_pit_review_package.py`.
- Steps.
  1. Choose audit blocks. Hold out about 20% of scored blocks by a seeded draw. Write their ids to `data/9t/results/confusers/confuser_audit_blocks_9t.csv`. Nothing mined or trained on them.
  2. From the other blocks, list the top 150 unmatched pit and pad detections by score.
  3. Build contact sheets (hillshade, slope, 2019 DEM crop, NLCD class) with the existing builder.
  4. Write the codebook `docs/iterations/confuser_codebook.md`. Classes are charcoal hearth, mill dam or race, quarry or borrow pit, cellar hole, farm or beaver pond, tree-throw ground, railroad or tram grade, other, uncertain, and "possible well".
  5. Two reviewers label independently. Compute Cohen's kappa. A third reviewer settles ties.
- Acceptance. Kappa is reported. The audit blocks are never used again until the final evaluation.
- Output paths. `data/9t/results/confusers/`, `docs/iterations/confuser_codebook.md`, `docs/iterations/confuser_negatives_9t.md`.

**A2. Association on the full annotated features (5.6, 3 hours).**
- Extend `notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py`. Read the annotation shapefiles under `qgis/annotations/`. Add a null that shifts records inside their own 500 m block so feature clustering is kept.
- Acceptance. Same tables as `docs/iterations/record_assoc_pits_9t.md`, with a second null. State whether orphan and abandoned records now exceed chance.
- Why now. It is quick and it decides whether record association is worth more time.

**A3. Context-reliance test (3.3 step 1, 6 hours).**
- Inputs. The pit CV checkpoints under `data/9t/models/pit/unet_cv5` and the 9t DEM derivative tiles.
- Steps.
  1. Take 60 annotated pits that the model detects out of fold.
  2. Paste each pit crop with a 5 m rim into a flat synthetic surface (a plane plus noise at the measured 9t ground noise). Score it.
  3. Keep the real pit and replace the terrain around it (beyond 15 m) with shuffled terrain from other blocks. Score it.
  4. Report the score change for each arm with block-bootstrap intervals.
- Acceptance. A table of score retention. If the isolated pit keeps under half its score, the model relies on slope context and the Illinois and Michigan expectation is lower.
- Output. `notebooks/wellsight_v2/s5_eval/_context_reliance_pits_9t.py`, `docs/iterations/context_reliance_pits_9t.md`.

**A4. Context features, second stage (5.1, 8 hours).**
- Steps. Build out-of-fold road and pad rasters (the backlog names this). Build candidate features. Fit logistic and gradient boosting with block cross-validation. Run the shuffled-context control.
- Acceptance. Gain in AP over the first-stage score with a block-bootstrap interval, and the gain must beat the shuffled control.
- Output. `notebooks/wellsight_v2/s5_eval/_context_stage2_9t.py`, `docs/iterations/context_stage2_9t.md`.
- Risk. If out-of-fold road and pad rasters are not available, building them is a separate half-day. Say so in the doc and stop.

**A5. Plug-date test with the change surface (4.5, 5 hours).**
- Steps. Pull wells with a plug date between 2006 and 2019 from the DEP table. Use `notebooks/wellsight_v2/s7_analysis/_change_features_9t.py` with the v2 surface, slope-matched controls and the measured placebo. Report flag rate against the placebo.
- Acceptance. Flag rate, placebo rate and count. Expect a null.
- Output. A short section in `docs/iterations/icp_change_9t.md` and a CSV under `data/9t/results/change/`.

**A6. Bounty-era recall gap (5.4 step 5, 6 hours).**
- Steps. List the 1,316 wells added to the DEP orphan or abandoned statuses between the 2022 list and the April 2026 export. Take the part inside tiles we can score (9t, its neighbours, Warren). Compare recall with the frozen model against older documented wells, at a fixed K.
- Acceptance. Recall for both groups with block-bootstrap intervals. Only 6 are inside 9t and 71 within 2 km, so say plainly that it needs the neighbouring tiles.
- Output. `notebooks/wellsight_v2/s5_eval/_recall_gap_newly_documented.py`, `docs/iterations/recall_gap_newly_documented.md`.

**A7. Warren and Forest preparation (3.1, 8 hours).**
- Steps.
  1. Measure ground density and void fraction on the seven Warren tiles. Fill the shift table from 3.0.
  2. Write `docs/iterations/transfer_warren_prereg.md` from the 3.0 template, with the margin chosen before scoring.
  3. List the D20 tiles needed for the Warren and Forest wells and write the fetch script with the 429 back-off pattern used for the 2006 fetch.
  4. Run inference with the frozen models on the Warren tiles. Do not score yet.
- Acceptance. Prereg committed before any scoring. Density table complete.

**A8. Aerial imagery probe (4.6, 3 hours).**
- Steps. Check what historic aerial coverage exists for Venango (state or federal portals) and write down date, scale and access terms. Download one frame over a known dense field. Look for derricks, tanks and roads.
- Acceptance. A one-page answer in `docs/iterations/historic_imagery_probe_9t.md`. Yes or no on whether aerials are a label source.

**A9. Shared prereg template (3.0, 3 hours).** One file, `docs/iterations/transfer_prereg_template.md`, with the freeze checklist, the shift table, the metrics, the adaptation ladder and the decision rule blank. All later areas copy it.

Phase A total is about 50 hours of work. The assistant can code A1 to A9 in a few focused sessions. The user's own time is A0 and the review in A1.

### Phase B. Weeks 1 to 4. Evidence that needs reviewers or data pulls

| Task | Steps | Acceptance |
|---|---|---|
| B1. Score Warren | Score the frozen models on Warren against DEP orphan and abandoned wells. Draw pad labels blind to the model. | Recall at fixed K, feature precision from blind review weighted by stratum, calibration error before and after Platt. |
| B2. Retrain with confusers (6.3) | Retrain with adjudicated confusers on the same block split. Add the random-negatives control. | Confuser detections per km² at fixed recall, against the control, on the frozen audit blocks. |
| B3. Adaptation ladder on Warren | Zero-shot, recalibrate on 50 labels, fine-tune on N, pooled retrain. | Recall at fixed K against N. The N an agency needs. |
| B4. Next area, Ohio county | Pick one county with a documented list and measured ground density of at least 2 per m². Run 3.0. | Same table as Warren. |
| B5. Aerial labels, if A8 said yes | Georeference with ground control, hold out a third, digitise windows, test against DEP and lidar scores. | RMSE reported. Historic-only set scored against matched random points. |
| B6. Magnetometer pilot design | Write the site list (12 to 20 sites, four groups), the detection rule, the blind protocol and the safety plan. | A signed-off protocol document, ready for the first instrument. |
| B7. Density model v1 | Hierarchical model on 9t and Warren with the corrected equation. Uses the recall-gap result and the best available precision. | Density per 5 km cell with a 90% interval, labelled as feature-based until well precision exists. |
| B8. Prioritisation layers | Gather public stream, water well and building layers for the risk index. | Layers cached with provenance. |

### Phase C. Months 2 to 4. Wider area tests and products

- **C1.** Run 3.0 on one West Virginia or New York county, then Kentucky if time allows (3.2).
- **C2.** Illinois or Michigan county with the context-test result in hand (3.3).
- **C3.** Oklahoma or Kansas three-arm test, lidar against optical against fused (3.5).
- **C4.** Ontario hand-dug well test after checking lidar licence (3.7).
- **C5.** Active learning rounds on the audit-set design (7.2). One round per month.
- **C6.** Benchmark release prep (7.3). Datasheet, splits, baselines with intervals, licence check.
- **C7.** Agency tool v1 (7.4). Command line, quality stops, Platt refit step, pinned environment.
- **C8.** Small pretraining prototype (7.1). 30 to 50 tiles, small encoder, label-efficiency curve at 10, 25, 50 and 100% of labels.
- **C9.** Risk ranking v1 (5.3) and a CO₂ area-of-review mock inventory (6.1).
- **C10.** Satellite thermal and Sentinel-2 pad screens (4.2, 4.3) as quick tests with placebo controls.

### Phase D. Field and partner work

- **D1.** Magnetometer pilot on 3 to 5 known wells to measure signal and noise at ground and drone height (4.1 step 1).
- **D2.** Full campaign of 40 or more sites if the pilot detects casings (7.5). Sample size per estimate under simple sampling is about 43 sites for ±15 points. Clustering widens it.
- **D3.** NETL drone lidar analysis once data arrive (4.7).
- **D4.** GNSS points at a subset of sites to test record association (5.6).
- **D5.** Methane readings at every site (6.5).

### Phase E. Long horizon

Alaska permafrost (3.8), era classification (5.2) once pre-1956 labels exist, hydrogen framing (6.4), California status classification (3.6), Gulf Coast (3.4), coal features (6.2), Permian methane regional test (4.4).

## 6. Decision gates and kill rules

| Gate | Rule | If it fails |
|---|---|---|
| After A2 | Orphan records exceed chance on the full annotations. | Stop record association. Keep the null result as a finding. |
| After A3 | Isolated pit keeps at least half its score. | Lower expectations for flat terrain and say so in the proposal. |
| After A4 | Gain beats the shuffled-context control. | Drop context features. |
| After A6 | Newly documented wells have recall within the interval of older wells. | If lower, inflate any density estimate and say why. |
| After B1 | Warren recall at fixed K is within the prereg margin. | Run the adaptation ladder before any other area. |
| After B2 | Confuser detections fall against the random-negatives control. | Stop negative-class work. Keep the inventory as a side product. |
| After A8 and B5 | Historic-only points score above matched random. | Drop historic labels. |
| After D1 | Casing anomaly is detectable above noise at a usable height. | Use ground survey only, or drop magnetometry. |

## 7. Handoff checklist

Where state lives.
- Live to-do list. `docs/iterations/BACKLOG.md`.
- Running log, newest first. `docs/analysis_log.md`.
- Method. `docs/iterations/expansion_options_methods.md`.
- This plan. `docs/iterations/expansion_gameplan_feasibility.md`.
- Review answers. `docs/iterations/outside_review_response_20261103.md`.
- Project rules. `CLAUDE.md`. Key ones are the documentation rules, the full-path rule, the filename rule, the large-file rule and the colourblind rule.

For any next assistant or colleague.
1. Run scripts with `python`, not `python -I`.
2. Never overwrite `output_wells.csv` or the DEP export. Write new files.
3. Pre-register before scoring. Freeze the model and the audit set first.
4. Call results "candidate" or "steel-confirmed candidate". Nothing is a confirmed well without a record or a visible wellhead.
5. Update the iteration doc, the analysis log and the backlog in the same change.
6. Stage files selectively. About 160 unrelated modified files sit in the working tree.

A prompt that works for handing a task to another assistant.
"Read CLAUDE.md, docs/iterations/expansion_gameplan_feasibility.md and the section of docs/iterations/expansion_options_methods.md for item <ID>. Do task <A#>. Follow the project rules. Write the script, the iteration doc and an analysis_log entry. Report full paths of every new file. Do not commit unrelated files."

## 8. Risk register

| Risk | Effect | Mitigation |
|---|---|---|
| Account ends mid-task | Half-written scripts | Do tasks in A-order. Commit after each. Write the doc before the code. |
| Reviewer labels agree with the model | Inflated precision | Blind sheets. Population weights. Audit blocks. |
| Records are noisier than detections | Association fails | A2 gate. Use independent coordinates. |
| Magnetometer cannot see casings from a drone | Campaign shrinks | Pilot first. Ground survey as fallback. |
| Agency lidar is thinner than QL2 | Transfer fails for data reasons | Measure ground density first. Report by density. |
| GPU limits | Pretraining stays small | Frame it as a prototype. |
| Stale facts | Wrong proposal text | Section 9 of the methods file lists what to re-check. |
| Working tree is dirty | Wrong files committed | Selective staging. |

## 9. Calendar

| When | Work |
|---|---|
| Days 0 to 1 | A0 requests sent. A9 template. A2 association. A1 package built. |
| Days 1 to 2 | A3 context test. A5 plug-date test. A7 density table and prereg. |
| Days 2 to 3 | A4 context stage 2. A6 recall gap. A8 aerial probe. Final handoff commit. |
| Week 1 | Reviewers label A1 sheets. B6 pilot protocol. B8 layers. |
| Weeks 2 to 3 | B1 Warren scoring. B2 retrain. |
| Week 4 | B3 ladder. B4 Ohio county. B7 density v1. |
| Months 2 to 4 | Phase C in the order listed. |
| When funded | Phase D. |

## 10. Things only the user can do

- Send the requests in A0.
- Label or find two reviewers for A1.
- Decide whether McKean is back in scope.
- Say where the thermal work is.
- Find a magnetometer, a field partner and permission.
- Decide whether to share the repo with another assistant, and which.
- Get quotes for any hardware rental.

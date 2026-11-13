# NISAR work: where it stands

Compiled 2026-11-11 from the project record. It gathers every NISAR thread in one place. Nothing here is new analysis.

Sources. `nisar/docs/NISAR_FINDINGS.md`, `nisar/docs/NISAR_METHODS.md`, `nisar/writeup/README.md`, `nisar/docs/iterations/nisar_*.md`, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, `nisar/reviews/nisar_adversarial_20261109/REPORT.md` and `docs/plans/project_next_steps_outline.md`.

## 1. Bottom line

- Adding NISAR to the lidar detector never reached the +0.05 gate set in advance.
- The radar alone carries a weak signal. Most of it is location, not the pad.
- The one test with room to fail was the 613590 held-out pit test. Rich lidar 0.881, combined 0.865. Gain -0.017, 95% interval -0.055 to +0.020.
- That excludes +0.05 for those 36 pits. It does not prove the radar can never help.
- Two outside reviews agree. Do not add the current radar features to the detector. Stop open-ended feature exploration. Keep one conditional path open.

## 2. Data held

| Area | Product | Usable dates | Tracks | Use |
|---|---|---|---|---|
| 9t | GSLC as delivered | 35 of 37 | 26, 90, 162 | Early tests, wet/dry, calendar |
| 9t | SLC re-placed on lidar heights | 33 (8, 11, 14) | 26, 90, 162 | Corrected classifiers, seasonal test |
| 613590 | SLC re-placed on lidar heights | 25 | 26, 90, 162 (162 beta only) | Held-out pits |
| McKean (`mkf`) | GSLC as delivered | 34 | 26, 98, 162 | Early area extension only |
| Warren | GSLC as delivered | 47 | 26, 90, 162 | Bright targets against wells |

- Span 2025-10-28 to 2026-10-14. L-band, HH and HV, 5 m grid. 1.239 GHz and 40 MHz per local metadata.
- 11 beta dates (Oct 2025 to Jan 2026) and the rest provisional (Jun to Oct 2026). Season and processing level are tangled.
- Two track-26 dates are dropped (2026-07-22 empty, 2026-09-08 misplaced).
- No released scenes from 2026-01-20 to 2026-06-20. Raw L0B for the gap returned 403.
- Validated products started 2026-11-06 for new acquisitions. Reprocessing of older dates is scheduled for 2027.
- Only three leaf-off, snow-free dates exist (2025-11-21, 2025-12-18, 2026-01-08). Track 90 has none.
- Windows were cut with HTTP range reads (about 9 MB each from 22.6 GB files).

## 3. What was built

- **Placement fix.** NASA's product sat about 10 m off the lidar. The cause is the Copernicus DEM sitting above the lidar ground. We wrote our own geocoder (matches NASA to 0.02 pixel), swapped in lidar heights and solved per-date and per-track offsets. 46 of 48 blocks within 2.5 m on 9t, 31 of 48 on 613590. That is agreement with a lidar simulation, not an independent position check.
- **Feature stack.** 303 SAR bands per target (backscatter, texture, coherence, seasonal, sub-aperture, terrain gain).
- **Scoring design.** Matched decoys (canopy ±0.05, slope ±1°), gradient boosting, 5-fold spatial block CV (500 m blocks, 250 m buffer). Controls are lidar-only, rich lidar (26 bands), map x/y only and a placebo.
- **Speckle filters** (2026-11-08). Median, Frost, Gamma-MAP and Lee sigma at 5 × 5. Images in `nisar/derived/9t/nisar_speckle_filters/`.

## 4. The five ideas and how each came out

| Idea | Result |
|---|---|
| Steel is bright | No. Wells no more likely than random ground to hold a steady bright target (Warren 3.9% against 5.2%). Bright targets are real and repeat across tracks, but they are buildings, bridges and graded pads. |
| A pad is a scar | No. A 0.3 dB darkening vanished after the placement fix. |
| Pits change with season | Lead only. Within-season pit-minus-decoy contrasts of +0.25 dB HH (fall) and +0.19 dB HV (leaf-on). The between-season change tests were not significant. Speckle filtering shrinks the contrasts. |
| Old wells move | No. Pit coherence excess +0.0001. No well among 282 flagged for slope motion. |
| Wet pits are dark | No for radar. Wet and dry overlap fully (+1.58 against +1.74 dB). Lidar intensity ratio separated all 13 labelled pits. |

## 5. Scores that matter

| Test | NISAR alone | Rich lidar | Combined | Note |
|---|---|---|---|---|
| Pads, decoys anywhere | 0.64 | | | Place effect (rises with decoy distance) |
| Pads, local decoys | 0.48 | | | Chance |
| Pads against other clearings (60) | 0.80 | 0.99 | 0.99 | Ceiling-limited |
| Pits, held out on 613590 (36) | 0.658 | 0.881 | 0.865 | The one decisive test |
| U-Net fusion | | 0.999 | 0.995 | Ceiling-limited |
| Lidar-weak pads (159) | | 0.880 | +0.015 | Place-rewarding design, not credited |
| Radar against Sentinel-2 | 0.622 | | | Sentinel-2 alone 0.840 |

- Radar-alone scores move with the decoy set. Do not quote them as headlines.
- HV follows optical greenness (R² 0.52) far more than lidar canopy height (0.04). In closed forest raw HV is mostly terrain lighting.

## 6. Reviews and corrections

- Codex audit and two outside reviews (2026-10-26). Led to the corrected re-scoring.
- Outside review of NISAR and change detection (2026-11-03). `docs/iterations/outside_review_response_20261103.md`.
- Independent adversarial review (2026-11-09). `nisar/reviews/nisar_adversarial_20261109/REPORT.md`. Ten findings. Fixed the same day. Bad-date readers, wording of the seasonal result, date counts, held-out interval, dedupe fold caveat.
- Still unfixed from that review. The dedupe comparison did not hold folds fixed (F2). The wet/dry CSV generator is not in the repo. Registration is not independently confirmed (F6).

## 7. Current deliverable: CIVE 6359 checkpoint

- `nisar/writeup/nisar_checkpoint_slides_9t.pptx`. Original results deck (2026-11-06).
- `nisar/writeup/nisar_checkpoint_slides_methods_9t.pptx`. Methods-only deck. Has uncommitted edits from 2026-11-09.
- `nisar/writeup/nisar_checkpoint_slides_methods_9t - Copy.pptx` and `.pdf`. Untracked copies, 2026-11-09.
- `nisar/writeup/nisar_checkpoint_slides_outline_9t.pptx`. Outline deck with bracketed stand-in text (2026-11-10).
- `nisar/writeup/nisar_methods_slide3_explained.md` and `.pdf`. Plain-language explainer for slide 3.
- `nisar/writeup/ADVERSARIAL_REVIEW_PROMPT.md`. Untracked review prompt.

## 8. The planned test (methods deck, slide 3)

Question. Does lidar plus radar find more verified pads than lidar alone at the same inspection budget?

1. One input manifest for every date and layer.
2. Geocode on lidar heights. Offsets fit on reference targets.
3. A small fixed radar feature set.
4. Score the lidar detector's candidates with and without radar on fixed folds.
5. Recall at a fixed budget on a reserved area. Bar +0.05 recall.

The review suggests 10 candidates per km² as a provisional budget. The expansion plans use 40 per km². This needs one decision.

## 9. Open threads

**Blocked on labels**
- Pad held-out test on 613590. Mark `verdict` on the 161 candidates in `nisar/results/613590/nisar_pad_review_candidates_613590.gpkg` and add missed pads. Labels must be made without seeing radar.
- Pads that lidar cannot see. Outside every test so far.
- Independent wet/dry pit labels (field or date-matched optical, not lidar intensity).

**Blocked on data or partners**
- Independent registration check. Needs surveyed structures or corner reflectors.
- Validated reprocessing of older dates (2027). Needed to break the beta/provisional confound.
- Spring dates (Feb to May 2026). Not released.

**Cheap, low expected value**
- Score the three clean leaf-off dates. One has unknown snow depth.
- Freeze folds and redo the dedupe comparison (review F2).
- Pit decoys with footprint matching alone and incidence matching alone.

**Framework only**
- Compact reflectors. `nisar/docs/iterations/nisar_reflector_framework.md`. No backend run.

**Not pursued**
- S-band. Finer X-band archives (Capella, ICEYE, Umbra). Change detection through time.

## 10. Decisions waiting on you

- Inspection budget for the checkpoint test (10 or 40 per km²).
- Whether to label the 161 pad candidates on 613590 now. This is the gate for any pad transfer test.
- What to do with the uncommitted methods deck edits and the two `- Copy` files.

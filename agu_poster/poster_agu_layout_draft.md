# AGU poster layout draft — 44 in × 44 in, model predictions only

Drafted 2026-11-04. Scope is the three U-Net detectors (pits, pads, roads), their inputs, validation and results.
Out of scope: change detection, NISAR, ICP, SAR bright targets, instance-segmentation detectors.
Audience-facing title and headings must not say "WellSight" (internal working name).

## 1. Page grid (inches)

| Item | Value |
|---|---|
| Page | 44 × 44 |
| Outer margin | 1.5 all sides, usable area 41 × 41 |
| Title band | y 1.5 to 7.0 (5.5 tall) |
| Body | y 8.0 to 40.0 (32 tall) |
| Footer strip | y 40.5 to 42.5 (2 tall) |
| Columns | 3 × 13.0 wide, 1.0 gutter. Col 1 x 1.5–14.5, Col 2 x 15.5–28.5, Col 3 x 29.5–42.5 |
| Gutter between stacked boxes | 1.0 |

Reading order is Col 1 top to bottom, then the hero, then Col 2, then Col 3. Numbered badges (1 to 8) on each box force the order.

## 2. Block map

```
x:  1.5            14.5 15.5              28.5 29.5            42.5
y
1.5 +------------------------------------------------------------+
    |  TITLE  /  authors  /  affiliations  /  logos  (5.5 tall)  |
7.0 +------------------------------------------------------------+
8.0 +-------------+ +-------------------------------------------+
    | 1 PROBLEM   | | 4 HERO: held-out predictions               |
    | PA map +    | | one tile, hillshade base, three panels     |
    | the ask     | |  [pits]   [pads]   [roads]  + zoom insets  |
15.5+-------------+ |  prediction vs hand annotation  (27 x 14)  |
16.5+-------------+ |                                            |
    | 2 DATA      | |                                            |
    | 3DEP lidar  | |                                            |
    | 7 channels  | +-------------------------------------------+
    |             | 23.0+------------+ +------------+
27.0+-------------+     | 5 METHOD   | | 7 RESULTS  |
28.0+-------------+     | pipeline + | | PR curves  |
    | 3 LABELS &  |     | U-Net      | | + table    |
    | SIGNATURES  |     |            | |            |
    | pit/pad/road|31.0 +------------+ |            |
    | schematic   |32.0 +------------+ |            |
    |             |     | 6 VALIDATE | 33.0+--------+|
    |             |     | spatial    | 34.0+------------+
40.0+-------------+     | 5-fold CV  | | 8 TAKEAWAYS|
                  40.0 +------------+ | + NEXT     |
                                     40.0+------------+
40.5+------------------------------------------------------------+
    | footer: references | data sources | acknowledgments | QR     |
42.5+------------------------------------------------------------+
```

## 3. Box specs

| # | Box | x, y, w × h (in) | Contents | Figure to build or reuse |
|---|---|---|---|---|
| T | Title band | 1.5, 1.5, 41 × 5.5 | Title, authors, affiliations, logos | none |
| 1 | Problem | 1.5, 8.0, 13 × 7.5 | Three-sentence why (orphan wells leak methane and brine, 150 years of undocumented drilling, canopy hides them). The ask: find surface expressions from lidar alone | `docs/figures/Pennsylvania Map Abandoned.png` as the base. Check it against the colourblind rule |
| 2 | Data | 1.5, 16.5, 13 × 10.5 | USGS 3DEP QL1 and QL2, 0.5 and 1 m bare-earth models. Seven channels named and shown | Seven-panel strip of one pit: `lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11`. Build new from 9t derivatives. Do not show RRIM as an input (it is a visual product only) |
| 3 | Labels and signatures | 1.5, 28.0, 13 × 12.0 | Pit, pad, road as the three recurring signs. Annotation counts as a small table. Drainage as negatives for roads | Three-up schematic of pit profile, pad, road. Start from `docs/figures/pit_profile_diagram.png` |
| 4 | Hero | 15.5, 8.0, 27 × 14.0 | One held-out tile. Hillshade with model output and hand annotation. Zoom insets on a hit, a miss and a false positive | Build new, see section 5 |
| 5 | Method | 15.5, 23.0, 13 × 8.0 | Pipeline: point cloud, ground, DEM, channels, U-Net, threshold, candidates. One line on loss and chunked roads | Pipeline diagram redrawn from `docs/05_processing_pipeline.md` |
| 6 | Validation | 15.5, 32.0, 13 × 8.0 | Spatial-block five-fold CV, every feature scored by a model that never saw it. Thresholds picked on validation, test scored once. Centroid matching for pits and pads, length for roads | Fold map: 9t split into five spatial blocks, one colour per fold |
| 7 | Results | 29.5, 23.0, 13 × 10.0 | Headline table plus threshold-free PR curves for pits and pads | Table from section 4. PR curves from `data/9t/results/operating_point/pr_ap_froc_calibration_summary_cv5_pit_pitsmrf_pad_9t.json` |
| 8 | Takeaways and next | 29.5, 34.0, 13 × 6.0 | Three takeaways. One line on limits (one survey block, labels are our own interpretation). Active work: more blocks, field validation | none |
| F | Footer | 1.5, 40.5, 41 × 2.0 | Short reference list, 3DEP citation, funding, QR to the repo or abstract | QR code |

Optional swap-in for box 7 if space allows: the four-architecture comparison (`docs/iterations/LEADERBOARD.md`, 2026-09-19). Its honest message is that no rung clears noise on pits, so it is a "what did not matter" note, not a headline.

## 4. Numbers to put in box 7 (needs your call before they go on a poster)

Two sets exist and they do not match.

| Source | Pits | Pads | Metric |
|---|---|---|---|
| `agu_poster/agu_abstract_2026.md` v17 (2026-08-04) | 93% located, precision 0.72, trained on 471 | 94% located, precision 0.90 | centroid matching, ann503 era |
| `docs/iterations/LEADERBOARD.md` CV5 ann712 (2026-09-17) | R 0.861 / P 0.686 @IoU 0.3 (F1 rule), containment 0.914 | R 0.888 / P 0.597 @IoU 0.3, locate 0.923 | IoU 0.3, 712 pits, 995 pads |
| Threshold-free AP @IoU 0.3 (2026-09-23) | 0.818 [0.778–0.857] | 0.745 [0.703–0.789] | ranked AP, 95% block bootstrap |

Roads: 98% of 735 withheld segments recovered, 82% of extracted road is real, 3% of held-out drainage claimed as road (abstract v17, not re-checked against the current road model).

The abstract is older than the ann712 retrain. The poster should use one consistent set. My recommendation is the ann712 CV5 numbers with the threshold-free AP as the headline, because AP needs no cutoff and has a bootstrap interval. Per the quality rule I will re-verify each figure against its source file before it goes on the page.

## 5. Hero figure plan

- Tile: pick a 9t block that sits in one CV test fold, so every prediction shown is from a model that never saw it.
- Base: hillshade in grey.
- Layers: hand annotation as outlines, model output as filled translucent areas. Pits, pads and roads each get a distinct hue plus a distinct line style, so colour is never the only cue.
- Three zoom insets: a clean hit, a miss, a false positive. Label each directly.
- Scale bar, north arrow, CRS in the caption.

## 6. Type and colour

| Element | Size |
|---|---|
| Title | 130 pt |
| Authors | 60 pt |
| Box headings | 80 pt |
| Body | 44 pt minimum |
| Figure captions and axis labels | 32 pt minimum |
| Table text | 36 pt |

- Body line length about 13 in at 44 pt gives roughly 35 words per line cap. Keep each box under 90 words.
- Colour: reuse the validated classification palette (ground `#1F5FA8`, unassigned `#8E959B`, charcoal `#2B2F36`, single-hue green ramp for vegetation). For the three feature classes I will pick hues and run the dataviz validator with `--pairs all` before use. No red and green carrying different meanings.
- Voice: short declaratives, no prose colons or semicolons, terms defined at first use.
- Print: 44 × 44 at 150 dpi is 6,600 × 6,600 px. Figures at 200 dpi or vector.

## 7. Open decisions

1. Which number set goes on the page (section 4).
2. Title, author list, affiliations and logos.
3. Tool for the build: python-pptx at 44 × 44 (matches your existing decks), or Illustrator or Inkscape from exported PNG or SVG panels. My default is a single `.pptx` plus exported panels.
4. Whether roads get a full box or stay a third of the hero and a row in the table. Currently the latter.
5. Whether to show the 613590 out-of-domain road result as evidence of transfer. It is the only held-out-region test in the repo.

## 8. Next steps once the layout is approved

1. Build the hero tile and the seven-channel strip from existing derivatives.
2. Recompute and verify every number in box 7 against its source file.
3. Run the colourblind validator on the final palette.
4. Assemble `.pptx` at 44 × 44 and export a PDF proof at reduced size.
5. Log it in `docs/analysis_log.md` and add the poster build to `docs/iterations/BACKLOG.md`.

## 9. Source deck: `RemoteSensing_option2.pptx` (repo root, untracked), checked 2026-11-04

Three slides. Slide 2 also mentions NISAR, so do not copy that text. Images extracted for inspection only.

| Item | What it is | Poster use |
|---|---|---|
| Slide 2 `image2.png` (1618 × 768) | Optical aerial of the canopy | Box 1, "optical cannot see it" half of a pair |
| Slide 2 `image3.png` (1618 × 768) | RRIM of the same tile | Box 1, the other half of the pair |
| Slide 2 `image4.png` (1618 × 768) | Same RRIM with **hand annotation** (orange roads, blue pits). These are labels, not model output | Box 3 (labels). Not usable as the hero |
| Slide 3 `image6.png` (3000 × 1200) | Three-row pipeline flow, data to QA | Box 5 content, redrawn larger |
| Slide 3 text | 467/503 pits 92.8%, 593/650 pads 91.2%, 722/735 roads 98.2%, precision 0.633 and 0.587, second tile pit recall 0.911 | Box 7 numbers. They match the ann712 CV5 F2 rows in `LEADERBOARD.md`, so these supersede the abstract |

Gaps: no model-prediction overlay exists in the deck, so the hero must be built new. The pipeline text is about 9 pt at 13 in wide, far below the 32 pt floor.
Resolved 2026-11-05: both are right. The USGS project is `PA_WesternPA_2019_D20`, flown leaf-off November 2019 to March 2020 (`docs/03_las_inspection_report.md:106`). On the poster write "USGS 3DEP 2019 project, flown Nov 2019 to Mar 2020". The deck's 503 pit floors and the leaderboard's 502 scored rims differ by one. 467/503 = 0.928 matches the F2 recall.

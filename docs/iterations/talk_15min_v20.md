# 15-minute talk (v20)

Built 2026-11-25 from v19. Setup, methodology and results only.

## Goal
A talk that fits 15 minutes. The 45-minute v19 spent about 40 slides on data QA, the derivative tour, corn rows and annotation inventory. Those are cut.

## Inputs
`docs/presentation/v19_maps_and_plain_results/WellSight_Presentation v19.pptx` (read only, not edited).

## What stays (v19 slide number -> v20 slide number)
| Part | v19 -> v20 | Slide |
|---|---|---|
| Setup | 1 -> 1, 2 -> 2, 5 -> 3, 6 -> 4 | title, problem, why LiDAR, study area |
| Methodology | 8 -> 5, 33 -> 6, 45 -> 7, 55 -> 8, 58 -> 9 | pipeline, RRIM, own labels, block split, U-Net |
| Results | 61 -> 10, 62 -> 11, 66 -> 12, 69 -> 13 | scoring, pits, three detectors, unseen tile |
| Close | 73 -> 14, 74 -> 15, 78 -> 16 | limits, next steps, references |

## What is cut, and why
- v19 9-21 (data QA, clipped ground, vendor comparison): not setup, method or result.
- v19 22-32 (per-derivative tour): RRIM kept as the one representative.
- v19 39-44 (corn rows): data QA detail.
- v19 46-54, 56-57 (annotation inventory, preprocessing detail): block split kept for validity.
- v19 63-65, 67-68, 70-72 (pads, roads, drainage, architectures, 613590 maps): the side-by-side table and unseen-tile slides carry the numbers.
- v19 75-77, 79-84 (further research, appendix, backup).

## Known issues to check
- Slide 5 (pipeline overview) is a picture. It may still show data QA boxes. It cannot be edited in place.
- Speaker notes are the v19 notes, unchanged. Some are long (slide 8 has 2,650 characters). They were written for a 45-minute pace.
- Timing is about 55 seconds per slide. Not rehearsed.

## Reproduce
`python docs/presentation/v20_15min/_build_v20_15min_from_v19.py`

Output: `docs/presentation/v20_15min/WellSight_Presentation v20 15min.pptx` (8.9 MB, under the 100 MB limit, no `.gitignore` rule needed).

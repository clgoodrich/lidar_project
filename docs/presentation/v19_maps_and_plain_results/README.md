# v19 — more of the map, plainer results

Built 2026-09-23 from v18, after presenting v18. Two pieces of feedback drove it.

1. **Not enough of what the map itself shows.** Every map in v18 carried
   shapefile outlines. The audience never saw what the eye has to find unaided.
2. **The results were over-complex.** A single caption line carried recall,
   precision, a matching rule, a threshold rule and a flagged area.

v18 was not edited. It was copied, and the copy was changed.

## What is in this folder

```
docs/presentation/v19_maps_and_plain_results/
    _build_rrim_feature_closeups_9t.py   RRIM close-ups, nothing drawn on them
    _build_scoring_schematic.py          found / missed / extra diagram
    _build_v19_from_v18.py               the deck builder
    figures/                             every new image, plus _closeup_selection_9t.json
    WellSight_Presentation v19.pptx      the built deck (gitignored, ~113 MB)
```

Rebuild everything, in this order:

```
.venv/Scripts/python.exe docs/presentation/v19_maps_and_plain_results/_build_rrim_feature_closeups_9t.py
.venv/Scripts/python.exe docs/presentation/v19_maps_and_plain_results/_build_scoring_schematic.py
python docs/presentation/v19_maps_and_plain_results/_build_v19_from_v18.py
```

The deck builder uses the **system** Python, because python-pptx is installed
there and not in `.venv`. It reads `docs/presentation/WellSight_Presentation v18.pptx`.

## What changed in the deck

94 slides, against v18's 80. Nothing was deleted.

| v19 slides | what | source |
|---|---|---|
| 34–38 | **New map section.** Zoom from tile to pit, then a pit, a pad, a road, and one well site with all three. RRIM only. | new |
| 61 | **How we score a detector.** Found, matched, search area, defined once. | new |
| 62–64 | **Pits, pads, roads.** Same layout each: three numbers, one takeaway, one small "how it was measured" line. | new text, v18 figures |
| 65 | Drainage | v18 slide 58, unchanged |
| 66 | **The three detectors, side by side.** One table. | new |
| 67 | **Would a bigger network do better?** Native chart. | replaces v18 slide 56 |
| 68 | Where the two tiles are | v18 slide 62, unchanged |
| 69 | **On a tile it never saw.** Pits and roads on 613590. | replaces v18 slides 63–67 |
| 70–71 | Road network, and against TIGER | v18 slides 69–70, text rewritten |
| 72 | **What the numbers say.** | replaces v18 slide 72 |
| 73–80 | Limits, next steps, further research, references, appendix | v18 73–80, unchanged |
| 81 | Backup divider | new |
| 82–94 | Backup: the v18 results slides 56, 57, 59, 60, 61, 63–68, 71, 72 | v18, unchanged |

## How the map examples were chosen

By rule, not by eye. Details are in the builder docstring. The picked features
and their measurements are in `figures/_closeup_selection_9t.json`.

| image | rule |
|---|---|
| typical pit | jointly nearest the median depth and median rim area |
| deeper / shallower pit | depth nearest the 90th / 20th percentile |
| typical / larger / smaller pad | area nearest the 50th / 85th / 20th percentile, pads with no pit drawn |
| roads, 300 m view | window at the 75th percentile of road length, 15 x 15 grid |
| bold / faint road | median-length line of `bold_roads.shp` / `faint_roads.shp` |
| well site | pad with a pit and a road, area nearest the median of such pads |

The ranking depth is a simple ring-minus-floor measure (median 0.43 m). It runs
lower than the morphology slide's 0.54 m and is never quoted on a slide.

All three pads chosen from "no pit drawn" still show a pit-like ring. They are
likely undrawn pits. The speaker notes say so.

## Numbers

No new analysis. Every number is from the 2026-09-22 audit or re-derived from
the same source:

| claim | value | source |
|---|---|---|
| pits found / flagged | 467 of 503 / 738 | `data/9t/models/pit/unet_cv5/pit_cv5_per_fold_9t.csv`, F2 rows |
| pads found / flagged | 593 of 650 / 1,010 | `data/9t/models/pad/unet_cv5/pad_cv5_per_fold_9t.csv`, F2 rows |
| search area | 0.21% / 9.8% / 5.02% | `docs/iterations/LEADERBOARD.md`, threshold sweep |
| roads | 722 of 735; 42.56 of 43.07 km | `LEADERBOARD.md`; v18 slide 57 notes |
| 613590 | pits 139 of 153 (0.911); roads 0.759 / 0.828 | v18 slides 65–66 |
| architectures | 0.559 / 0.561 pit, 0.555 / 0.608 pad | `data/9t/results/arch_compare_1m/arch_compare_summary_9t_1m.csv` |

## A contradiction carried over from v18

v18 slide 66's map has **"146 found, recall 0.954"** baked into the image. The
slide text says **139 of 153 (0.911)**, the audited five-model average. v19's
main flow uses slide 63's map instead, which carries no numbers. Slide 66 is
still in the backup, unchanged, so the contradiction is still there. Resolve it
before that backup slide is shown.

## Colour

- Class schematic: `#1F5FA8` / `#D97706` / `#A31515`, the repo's validated
  lost/found set. All-pairs worst ΔE 21.1 deutan. Amber is 2.99:1 on `#F7F8F6`,
  relieved by direct labels.
- Architecture chart: `#4E8FE6` / `#1F5FA8`, an ordered light-to-dark pair.
  Every check passes, worst ΔE 16.3. Grey `#8E959B` was tried first and failed
  the chroma floor.
- No red–green pair anywhere.

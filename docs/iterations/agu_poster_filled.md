# AGU poster, filled in

Built 2026-11-25 on the 2026-11-09 layout.

## Goal
Replace draft text with final text, and give every figure a numbered caption in standard scientific form.

## Inputs
- Layout and builder: `agu_poster/_make_agu_poster.py`, template `agu_poster/AGU_poster.pptx`.
- Figures: `agu_poster/figures/` from `_make_poster_figures.py`, plus the new locator map from `_make_poster_locator.py`.
- Numbers: `data/9t/models/{pit,pad}/unet_cv5/*_cv5_per_fold_9t.csv` (F2 rows, pooled by held-out count) and `data/9t/results/operating_point/pr_ap_froc_calibration_summary_cv5_pit_pitsmrf_pad_9t.json`.

## What changed
- Title, author and affiliation filled in. Co-authors and funding are still open.
- Eight numbered figure captions and one table caption. Each states the scale, the data and the match rule.
- Table 1 headings now read Recall, Precision and IoU 0.5 recall. The earlier headings (Found, Correct, Tight fit) were plain-language stand-ins.
- Precision-recall figure now uses Precision and Recall axes and prints average precision on the curves.
- Pennsylvania map replaced by a cropped version with a redrawn 100 km scale bar and a north arrow. The old export had its scale bar and legend cut off by the crop.

## Revision 2026-11-25, style pass
- All poster text and all in-figure text set in Georgia. No bold, one text colour (charcoal) outside the header band.
- Figure 4 (map) rebuilt as a standard multi-panel figure. Panel (a) has easting and northing axes in EPSG:6346, a plain scale bar and a north arrow. Panels (b) to (d) are 50 m details with letters and 10 m scale bars. The legend is a framed box with line and fill symbols. The explanatory text that sat beside the insets moved into the caption.
- Processing chain redrawn as a plain flow chart, square boxes with thin outlines and no fills.
- The seven-layer thumbnail strip was removed. Its labels were too small to read at poster distance, and the layers are named in the text. Figures were renumbered 1 to 7.

## Numbers checked against source (2026-11-25)
| Sign | n | Recall (IoU 0.3) | Precision | IoU 0.5 recall | AP (IoU 0.3) |
|---|---|---|---|---|---|
| Pits | 503 | 467 = 92.8% | 0.633 | 82.3% | 0.818 [0.778, 0.857] |
| Pads | 650 | 593 = 91.2% | 0.587 | 77.4% | 0.745 [0.703, 0.789] |
| Roads | 735 segments | 98% | not object-scored | not applicable | not applicable |
Roads come from the v19 deck and LEADERBOARD. They were not recomputed here.

## Open before printing
1. Co-authors, and funding text in the footer.
2. QR code target.
3. Credit for the aerial photograph in Figure 2. It comes from `RemoteSensing_option2.pptx` and its source is not recorded.
4. The script's overflow estimate still warns on the right column. The PowerPoint render fits.

## Reproduce
```
python agu_poster/_make_poster_locator.py
python agu_poster/_make_poster_figures.py
python agu_poster/_make_agu_poster.py --mockup
```
Output: `agu_poster/agu_poster_filled_44in.pptx` (about 22 MB, under the 100 MB limit).

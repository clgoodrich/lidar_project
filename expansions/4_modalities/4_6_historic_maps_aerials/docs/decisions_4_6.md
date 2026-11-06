# 4.6 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-06. S5 compares marks only with DEP records spudded on or before the source date. A year-only source date compares by year. Records with no usable spud date (missing or the 1800 sentinel) are left out and enter a labelled sensitivity count (review 4.6-01). Made by the review-fix agent, change freely.
- 2026-11-06. A source with no date, or with more than one date, is refused by S5. Made by the review-fix agent, change freely.
- 2026-11-06. The agreement interval resamples units, one pair or one unpaired mark each, by percentile bootstrap. Clopper-Pearson on marks counted both members of a pair as independent. The pass rule is unchanged. The lower bound must exceed 0.70. Made by the review-fix agent, change freely.

- 2026-11-05. Cover share in S1 comes from the sheet neatline (--neatline), not from valid pixels. The scan collar counts as cover otherwise. The held 1922 sheet gives 1.00 without and 0.51 with an assumed Oil City 15 minute neatline. made by the build agent, change freely.
- 2026-11-05. Two-digitiser agreement passes when the Clopper-Pearson lower bound exceeds the level (0.70), not the point estimate. made by the build agent, change freely.
- 2026-11-05. Marks pair one to one across digitisers, greedy by distance within 25 m. Agreement is paired marks over all marks. made by the build agent, change freely.
- 2026-11-05. The shifted-set null moves each DEP record independently by 200 to 500 m and redraws until it stays inside the footprint. This keeps record density inside the field. made by the build agent, change freely.
- 2026-11-05. Without an oil field footprint, S5 uses the DEP record hull buffered 250 m and writes that into the result. made by the build agent, change freely.
- 2026-11-05. Association radius defaults to the source's measured check-point RMSE (review revision). made by the build agent, change freely.
- 2026-11-05. The aerial probe calls a date "legible candidate" at 8 or more pixels across 20 m. The final call stays human. made by the build agent, change freely.
- 2026-11-05. Docs that the framework places in docs/iterations/ are written to results/tables/ for the lead to copy. made by the build agent, change freely.

## Needs user decision
- Whether records with no usable spud date belong in the primary association or only in the sensitivity count.

# 4.8 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Minimum coverage `prereg.min_coverage` for the usable-share gate. User accepted the default 0.80 ("take defaults"). Change freely. Below it the gate is inconclusive, never success or failure.


- 2026-11-06. Review fix 4.8-01. Unavailable, blank and undated chips leave the usable-share denominator. They had been counted as not usable, so an all-undated PEMA source read `unusable here`. Coverage (judged chips over sampled chips) is now reported per source. With no judged chip the gate is inconclusive. This replaces the 2026-11-05 line that missing chips count against the share. Made by the review-fix agent, change freely.
- 2026-11-06. Registration nodes are true junctions only. A node needs three or more road arms. End-to-end joints of one road are dropped. Made by the review-fix agent, change freely.

## Needs user decision

None open after the 2026-11-06 defaults.

## Earlier decisions (2026-11-05)

- 2026-11-05. Framework rewritten to full depth (14 sections and an Assumed data table). made by the build agent, change freely.
- 2026-11-05. Two chip statuses added, undated and low visible ground, so no chip is forced into a wrong class. made by the build agent, change freely.
- 2026-11-05. Visible ground cutoff 0.15 and usable share gate 0.60 are defaults until the user confirms them before S1. made by the build agent, change freely.
- 2026-11-05. Visible ground is excess green under 0.05 with brightness 40 to 230, inside the footprint buffered 5 m. made by the build agent, change freely.
- 2026-11-05. Gate decision uses the Clopper-Pearson interval of usable share against 0.60. Missing chips count against the share and never as negatives. made by the build agent, change freely.
- 2026-11-05. The feature sample is proportional by layer (pit_inside, pad) with largest-remainder allocation. made by the build agent, change freely.
- 2026-11-05. Registration uses road intersections from the drawn roads layer, 10 per source, median offset 5 m or less. made by the build agent, change freely.
- 2026-11-05. NAIP stays in the table as a leaf-on control. All four dates on file are May to September. made by the build agent, change freely.

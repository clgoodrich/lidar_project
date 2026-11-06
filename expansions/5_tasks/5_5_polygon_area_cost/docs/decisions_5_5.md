# 5.5 decisions

Newest first. One line per decision, with the date and who made it.

## Needs user decision

- Pad polygons are the 0.50 product. The shared policy cutoff for pads is 0.525. Rebuilding the pad product at 0.525 is outside this folder. Decide whether 5.5 must move to 0.525.
- L_road counts annotated road length within 30 m of the pad edge (road_window_m). The road layer may include through roads that no restoration would pay for. Decide which roads count.
- The primary match rule is one-to-one with any positive overlap. Centroid containment is the other candidate. Confirm the rule before the survey run.

## Log

- 2026-11-06. Review 5.5-01. Pads are matched one to one by descending score with any positive overlap (overlap_any). The IoU 0.3 gate is now a sensitivity. The gate capped |r| at ln(1/0.3) = 1.204. On 9t matched pads go from 603 to 616 and the largest |r| from 1.18 to 2.89. Most of the 392 old unmatched pads (359) touch no model polygon, so they are misses. Made by the review-fix agent, change freely.
- 2026-11-06. Review 5.5-02. Each cost row needs a unit. Acre, ha, ft, km and mile are converted to m2 or m. Other units refuse. road_length_m is written per pad. The Monte Carlo refuses when the table has a road item and road length is missing. Made by the review-fix agent, change freely.
- 2026-11-06. The circular test with one constant scale inside the gate is replaced. New tests use scales outside the gate with a known ln(s) answer. Written paths are repo-relative. 5.5 has no cx column, so the cx collision does not apply here. Made by the review-fix agent.

- 2026-11-05. Pits are removed from both model and reference polygons (subtract_pits). Made by the build agent, change freely.
- 2026-11-05. Merged means one model polygon covers at least 20% of two or more pads. Split means two or more model polygons each put at least 20% of their area on one pad. Made by the build agent, change freely.
- 2026-11-05. Without a cost table delta_area falls back to ln 1.25. That is the area margin for a 25% cost tolerance when f is 1. Made by the build agent, change freely.
- 2026-11-05. The drawn-reference run is exploratory. It writes _drawn_ files so survey outputs are never overwritten. Made by the build agent, change freely.
- 2026-11-05. Cost terms are lognormal with the table's low and high as the 5th and 95th percentiles. Made by the build agent, change freely.
- 2026-11-05. The redraw sample is 30 pads, 10 per size tercile, spread over blocks first. Made by the build agent, change freely.

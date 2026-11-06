# 5.5 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Pits are removed from both model and reference polygons (subtract_pits). Made by the build agent, change freely.
- 2026-11-05. Merged means one model polygon covers at least 20% of two or more pads. Split means two or more model polygons each put at least 20% of their area on one pad. Made by the build agent, change freely.
- 2026-11-05. Without a cost table delta_area falls back to ln 1.25. That is the area margin for a 25% cost tolerance when f is 1. Made by the build agent, change freely.
- 2026-11-05. The drawn-reference run is exploratory. It writes _drawn_ files so survey outputs are never overwritten. Made by the build agent, change freely.
- 2026-11-05. Cost terms are lognormal with the table's low and high as the 5th and 95th percentiles. Made by the build agent, change freely.
- 2026-11-05. The redraw sample is 30 pads, 10 per size tercile, spread over blocks first. Made by the build agent, change freely.

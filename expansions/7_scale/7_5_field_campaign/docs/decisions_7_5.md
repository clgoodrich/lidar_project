# 7.5 decisions

Newest first. One line per decision, with the date and who made it.

## Needs user decision

- 2026-11-06. Target width 0.30 is out of reach at n = 182. The expected bound width there is 0.407. The design needs about 746 allocated sites at deff 1.5 and 20% inaccessible. Choose one. Fund about 746 sites, accept a wider target, or cut the inaccessible share. The target was not changed.
- 2026-11-06. No n can give plus or minus 0.10 on the share while 20% of sites are inaccessible. The gap alone is 0.20 wide. Decide whether plus or minus 0.10 stays a goal.
- 2026-11-06. Detector link radius for Arm C wells is 15 m, the protocol search radius. Confirm or replace it (config density_export.detector_link_m).
- 2026-11-06. Round-2 wells within 5 m of a round-1 well in the same cell count as one well. Confirm or replace it (config density_export.well_merge_m).
- 2026-11-06. A sampled stratum with a single cluster makes the arm result inconclusive. Decide whether to collapse such strata, and with which neighbour, before the draw.
- 2026-11-06. Arm B now draws from the 5.4 density site table inside the audit blocks or reserved area. 5.4 then applies a p from that subset to D for the whole footprint. Confirm that this transfer is acceptable.

## Log

- 2026-11-06. Review fixes F04, F05, F16, 7.5-01, 7.5-02 and the Arm B frame. Made by a review-fix agent, change freely.
- 2026-11-06. Interval method. Linearisation variance with clusters as PSUs nested in the sampling strata, then a Korn-Graubard interval. The Kish Clopper-Pearson columns stay as diagnostics only. The cluster bootstrap is gone. Made by a review-fix agent, change freely.
- 2026-11-06. A stratum with all pi = 1 was taken whole and adds no variance. A cluster that spans strata collapses the strata for the variance. Made by a review-fix agent, change freely.
- 2026-11-06. With zero design variance the effective n is the number of clusters. Copies inside a cluster add no precision. Made by a review-fix agent, change freely.
- 2026-11-06. Every found well gets its own row in a well table linked to its visit. Controls are found when a well row names the control permit in tied_record_id. The evidence-code rule of 2026-11-05 is replaced. Made by a review-fix agent, change freely.
- 2026-11-06. Control sensitivity counts control wells in searched cells, in numerator and denominator. Made by a review-fix agent, change freely.
- 2026-11-06. Arm C density counts every undocumented confirmed well, several per cell, in cells with or without a control. Made by a review-fix agent, change freely.
- 2026-11-06. Arm B is restricted to candidates inside the Arm A frame. Its frame is the 5.4 site table, whose hash goes into the key. Made by a review-fix agent, change freely.
- 2026-11-06. The P2 audit file is read with ek.require_audit. Only role audit forms the Arm A frame. Buffer blocks do not. Made by a review-fix agent, change freely.
- 2026-11-06. 5.4 exports go to data/processed/ of this expansion, where config_5_4.json already looks. Zero-well and inaccessible cells go to arm_c_search_areas.csv because the 5.4 schema has no row for them. Made by a review-fix agent, change freely.
- 2026-11-05. Era strata come from the nearest DEP record within 50 m. Before 1900 is early_dated, 1900 to 1929 transition_dated, 1930 on steel_dated. The 1800 sentinel is unknown_sentinel. A dated historic mark makes early_map. Made by the build agent, change freely.
- 2026-11-05. The cluster for inference is the DEP pad id of the nearest record within 50 m, else the feature itself. Made by the build agent, change freely.
- 2026-11-05. Arm C cells must lie fully inside the reserved area and outside 50 m of any arm A or B site. Made by the build agent, change freely.
- 2026-11-05. A seeded control counts as found when the cell record carries the evidence code agency_record_tied_on_site. A direct coordinator field is a later schema change. Made by the build agent, change freely.
- 2026-11-05. The reported interval is the wider of Clopper-Pearson on the Kish effective n and a cluster bootstrap. Made by the build agent, change freely.
- 2026-11-05. Field sheets drop arm, pi and weight and show only a search mode. Made by the build agent, change freely.
- 2026-11-05. A second draw is refused once the sample hash file exists, unless --force is given. Made by the build agent, change freely.
- 2026-11-05. Sample sizes use expkit.n_for_proportion, which rounds up. It gives 97 and 25 where the protocol text says 96 and 24. Made by the build agent, change freely.

# 5.4 decisions

Newest first. One line per decision, with the date and who made it.

## Needs user decision

- The footprint is all 144 blocks. The 29 zero-pit blocks have no out-of-fold pit prediction, so they add area but no candidates. K is then 810 and only 768 candidates exist. D is limited by supply, not by K. The fix is an out-of-fold prediction for those blocks, which needs a model choice.

## Log

- 2026-11-06. Defaults pass. 5.6 now cuts pits at 0.35. expected_pit_rows is 768. Rerun S0, S1, S2 and S5. D sites 656 [578, 739] to 733 [648, 782]. K 810 unchanged. Grid inconsistent cells 480 of 918. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix pass by the review-fix agent. Change freely.
- 2026-11-06. 5.4-02. The footprint is the complete grid, not the blocks with drawn pits. truth_bearing is kept as a sensitivity.
- 2026-11-06. 5.4-01. The D bootstrap reruns the top-K cut and the site merge on every resample. The old one summed per-block site counts after the cut. A resample that repeated dense blocks then held more than K sites. That is how it reached 678 with K = 647. Every draw now lies in 0 to K.
- 2026-11-06. Degenerate capture-recapture rows report se as NaN. Chapman variance is 0 there by construction.
- 2026-11-06. The Arm B frame check refuses a missing, blank or mixed frame_sha256. The 7.5 schema is unchanged.
- 2026-11-06. The 5.6 input is the new prediction-only output with 677 pit rows.

- 2026-11-05. Candidate blobs merge into one site within 15 m (single linkage). Made by the build agent, change freely.
- 2026-11-05. N_doc keeps every DEP status except Operator Reported Not Drilled and Proposed But Never Materialized. It merges records within 5 m. Made by the build agent, change freely.
- 2026-11-05. D uses the full 5.6 pit output ranked by score at K = 40 per km² of the 115-block footprint. K = 30 is a sensitivity. Made by the build agent, change freely.
- 2026-11-05. The grid is p 0.05 to 0.90, r 0.10 to 0.90, step 0.05, m in 1, 1.5 and 2. Cells with a total below N_doc are flagged inconsistent. Made by the build agent, change freely.
- 2026-11-05. Capture-recapture keeps well share p and link precision q as separate terms, because they cancel when set equal. Made by the build agent, change freely.
- 2026-11-05. Field bounds refuse to run if the Arm B frame hash differs from the site table hash. Made by the build agent, change freely.

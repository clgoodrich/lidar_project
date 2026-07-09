# Response to Glennie's comments — proposal v7 → v8

Each of the 9 margin comments, and exactly what changed. His comments are **kept in
v8** so each sits next to its revision. This is the anonymized S/T/M, so institution
names stay out (see #8).

| # | His comment (short) | What changed in v8 |
|---|---|---|
| 1 | Whole-valley extension not well supported; stick to stream channels | **Objective 2 narrowed** from "the whole valley floor" to the **stream corridor** (channel + near-channel: shift/avulsion, bank thaw, fans). Summary + Timeline + Assessment reworded to match. *(Biggest change — your/his sign-off.)* |
| 2 | What's the source of the driver data? | **(v9)** Objective 1 now names the sources precisely: drivers *"come from the McMurdo Dry Valleys LTER network (meteorology, stream gauges, glacier mass balance, and soil climate) [6], with ERA5 [7] and AMPS reanalysis filling gaps."* Also mirrored in the Approach para + Project Needs table. |
| 3 | Need stable areas to georeference REMA — can't assume all is moving | **(v9)** Objective 2 now states it at the comment's spot: *"bedrock and stable soils outside the corridor provide the fixed reference used to georeference the REMA satellite DEM to the airborne lidar, so change is measured against genuinely stable ground rather than an assumption that the whole surface is moving."* Reinforced in the O2 approach + the REMA-minus-LiDAR bias step. |
| 4 | Don't frame as fixing the dissertation's deficiencies — show new work | Section "Current Data Deficiencies" → **"The Open Question."** Rewrote it and Objective 3 to drop all "the dissertation's deficiency / this proposal completes it" framing. |
| 5 | Figure 2: add ICESat-2 / current NASA instruments; NCALM unmentioned | **(v9, image redrawn)** Figure 2 regenerated (`barlow/build/_fig_workflow.py`): added an **ICESat-2 control box** (NASA · ATL06/08, external elevation tie-point) feeding co-registration; co-register step now reads *"to airborne lidar + ICESat-2 control"*; **O2 box relabeled "valley floor" → "stream corridor."** NCALM already shown on the 2014-lidar input box. Caption already updated to match. |
| 6 | O1 step-by-step reads as a recipe, not research; make it hypothesis-driven | Objective 1 approach now **opens with the hypothesis** ("tests whether melt energy predicts channel change better than water volume") and frames the method as how it's tested. |
| 7 | Data table needs more NASA data | Added a row to Project Needs: **ICESat-2 elevation (external control) — NASA NSIDC DAAC.** |
| 8 | Mention free access to UH HPC | Computing paragraph now notes **free access to the host institution's HPC cluster.** ⚠️ Written as "host institution" — naming UH here would break dual-anonymous review. |
| 9 | Community Contact is really about dissemination (AGU) | Section "Community Contact" → **"Dissemination"**; rewritten around AGU/polar-meeting talks + open-access publications and archived products. |

## Still needs a human
- **#1** is a real scope decision — v8/v9 narrow to the corridor per his steer; confirm that's the intended call (vs. defending the whole-valley scope). This is the only one of the nine that is a judgment call rather than a mechanical fix.
- Length holds: S/T/M = 6 pages (references [1]–[9] spill to p7, which don't count).

## Where each fix lives
- The **stream-corridor figure** (Fig 2, `_fig_workflow.png`) is embedded in **v8, v9, and both `_tracked` docs** — the versions whose text already says "stream corridor."
- **v7** and the package copies (`finesst_final/A1_proposal_STM`, `finesst_submission/.../proposal_STM_v7`) keep the **original "valley floor" figure**, because their text still says valley floor. Figure and text stay consistent within each version. When Glennie accepts the v9 tracked changes, the accepted result (v9 text + new figure) replaces v7 as the package base.

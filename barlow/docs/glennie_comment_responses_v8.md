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

## Proofread + solicitation-compliance pass (2026-07-09)

A line-by-line proofread of v9 against the F.05 FINESST solicitation (corrected 4/15/26)
produced these fixes, applied to **v9 and v9_tracked** (as tracked changes, so Glennie
sees them; accept-all still equals v9):

- **Division/program named** (required element, §5.1.1.1): NASA Relevance now opens with
  *"…relevant to NASA's Earth Science Division — most directly the Cryospheric Sciences
  and Terrestrial Hydrology programs…"* Swap the program names if Glennie prefers others.
- **Figure 1 caption** no longer ends mid-sentence ("…measures; " → "…measures.").
- **NASA Relevance** editing artifact removed ("— reference for this as well [8]" →
  "[8]"), and the stray comma before "into a continuing" dropped.
- **Hypothesis fixes**: "sediment movement" → "channel change" (now matches the O1
  approach), and the falsification test now reads "if discharge alone predicts channel
  migration as well as or better than melt energy" (before, *any* discharge correlation
  failed the hypothesis).
- **Uncited references fixed**: [5] (U-Net) now cited at the Present Data bullet, [3]
  (NMAD robust stats) at the robust-statistics note.
- **Numbers reconciled**: "roughly 20 gauged streams" → "21" (matches the table).
- **Garbled sentence** repaired: "repeat acquisition and valley wide REMA" →
  "repeat-acquisition airborne lidar and valley-wide REMA".
- Consistency: "LiDAR" → "lidar" (5×), "high resolution" → "high-resolution" (2×),
  "Objective 3" heading gets its colon, ref [9] en-dash, comma before "or has been
  given" dropped.
- **DAPR metadata scrub** (§5.2 "document properties…properly anonymized"):
  `lastModifiedBy: Craig Glennie` blanked in v9, v9_tracked, and the package copies
  (`finesst_submission/.../proposal_STM_v7.docx`, `finesst_final/A1_proposal_STM.docx`
  — metadata only, content untouched). Package PDF author field is clean
  ("Microsoft account").

**Font density — RESOLVED (2026-07-09, same day).** v9 and v9_tracked converted from
11-pt Calibri (~16.5–17 chars/inch; captions ~20) to **12-pt Times New Roman** — the
solicitation's own compliance benchmark ("typical of 12-point Times New Roman").
Captions are now 12-pt italic TNR; tables stay 9-pt (the rule covers body text and
captions). The growth was absorbed without cutting any text: exact single line spacing
(was 1.08×), paragraph space-after 8 pt → 6 pt, both figures scaled to 85%. Result:
**v9 is now 6 pages total including references** (was 6 + refs spilling to p7); a
trailing blank page was removed. No content changed except one repair: the LiDAR→lidar
normalization had accidentally hit the verbatim title of ref [8] (Schenk et al.,
"…Antarctic LiDAR data") — restored in both docs.

⚠️ The same 15-cpi font rule applies to the **other proposal components** still in
11-pt Calibri: the OSDMP (user's edited copy — not touched), the Mentoring Plan, and
the Research Readiness Statement (1-page limit — converting may overflow it). These
need the same conversion before PDF assembly. The package copies
(`proposal_STM_v7` / `A1_proposal_STM`) also still carry the old font; they get
replaced wholesale when Glennie accepts v9.

## v10 — three ideas adopted from the PI's NSF 25-526 project description (2026-07-09)

Glennie shared his pending NSF proposal (same MDV program, written with Levy and
Fountain) "to help formulate the hypotheses and testing a little bit better." Rather
than reformulating the hypotheses (kept as-is), v10 adopts the three genuinely
strong *procedures* from it, as tracked insertions in **v10_tracked** (forked from
v9/v9_tracked; accept-all == v10 verified):

1. **Same-epoch zero-change validation** (O3 approach): difference a 2014 REMA DEM
   against the 2014 lidar DEM — same year, so true change is zero and every residual
   is sensor error. Calibrates the noise model with no stable-ground assumption.
2. **Insolation→discharge proxy for ungauged streams** (O1 approach + Assessment):
   regress measured discharge on source-glacier summer insolation over the gauged
   streams, apply to ungauged ones — extends the sample beyond 21 streams and fills
   the post-2015 gauge gap the Assessment previously conceded without mitigation.
3. **Operational stable-ground definition** (O2 approach): stable ground = areas the
   channel detector classifies as non-stream in every epoch — computed, not assumed.

No preliminary results or unpublished numbers were imported (FINESST plan-only,
DAPR-clean). Deliberately NOT adopted: MDV-wide expansion (the NSF award's lane),
Levy's substrate datasets (collaborator's workstream), and their H1 framing.
Pagination: S/T/M still ends on p6; references spill to p7 (excluded from the limit).

## Where each fix lives
- The **stream-corridor figure** (Fig 2, `_fig_workflow.png`) is embedded in **v8, v9, and both `_tracked` docs** — the versions whose text already says "stream corridor."
- **v7** and the package copies (`finesst_final/A1_proposal_STM`, `finesst_submission/.../proposal_STM_v7`) keep the **original "valley floor" figure**, because their text still says valley floor. Figure and text stay consistent within each version. When Glennie accepts the v9 tracked changes, the accepted result (v9 text + new figure) replaces v7 as the package base.

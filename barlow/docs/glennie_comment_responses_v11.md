# Response to Glennie's v11 comments — proposal_v11_cgedits → v11_working

**Date:** 2026-07-13
**Source:** `barlow/finesst_final_v2/proposal_v11_cgedits.docx` (11 comments dated
2026-07-13, no tracked line edits)
**Result:** `barlow/finesst_final_v2/finesst_proposal_v11_working.docx` (+ pdf),
promoted to `finesst_final/proposal_STM.docx` and
`finesst_submission/1_anonymized_technical/proposal_STM_v11.docx`.

| # | His comment (short) | What changed |
|---|---|---|
| 0 | Add why measuring this change is important / what it tells us about the Antarctic | Intro now adds: "How fast those channels change... Their pace of change is an early, direct measure of the ice-free Antarctic crossing a climate threshold [10]." |
| 2 | If we know the root cause, what can we do with it? | After the attribution statement: "Knowing the driver turns monitoring into forecasting, projecting channel response from climate scenarios here and in any polar region with repeat elevation data." |
| 3 | Preferred spelling is lowercase "lidar" (Deering & Stoker) | All 15 in-prose "LiDAR" → "lidar" in the proposal; cascaded to the OSDMP (2), research readiness statement (2), and current & pending (1). The Schenk et al. 2004 reference title keeps its published "LiDAR". This reverses the earlier all-caps pass at the FI's request; package now follows the community convention. |
| 4 | LTER / ERA5 / AMPS not spelled out | Now "McMurdo Dry Valleys Long Term Ecological Research (LTER) network [8]", "the European Centre for Medium-Range Weather Forecasts ERA5 reanalysis [9]", "the Antarctic Mesoscale Prediction System (AMPS)" at first use. |
| 5 | Elaborate on "tricky" | Replaced with the specific problem: "REMA... is built from optical stereo imagery. Its offset from lidar shifts with slope, aspect, and seasonal snow. The terrain-aware uncertainty model in objective 3 absorbs those offsets as part of the method." |
| 6 | Spell out ICP | "an optional iterative closest point (ICP) refinement" at first use. |
| 7 | What is LOD95? | Defined at first use: "the per-pixel level of detection at 95% confidence, LOD95, from objective 3". |
| 8 | mm/yr implies cm accuracy over 10 years — cm/yr at best | Conceded. The integrated channel-change rate unit is now cm/yr. No mm/yr claims remain. |
| 9 | "each type's rates" — what type? | "Run each **process** type's rates..." — antecedent is the process classification in the preceding sentence. |
| 10 | NMAD acronym | Defined at first use: "take the normalized median absolute deviation (NMAD) in each bin". |
| 11 | Reference the dissertation | Project Needs row now reads "The prior dissertation's hand-digitized training tiles [1]". |

## Page-budget pass

The additions (~7 lines) pushed the timeline table and DMOS onto page 7. Reclaimed
by condensations, none of which removed a comment answer:

- Intro history sentence shortened ("They were long treated as one of Earth's most
  stable landscapes.").
- Risks intro tightened; Gauge Records mitigation de-duplicated; Change Scale
  merged; "public data / proceed independently" sentence cut (duplicated the
  closer and the DMOS opener).
- NISAR answer tightened to two sentences; spheres enumeration compressed;
  hypothesis-falsification merged to one sentence; driver-history step merged.
- STV positioning sentence removed (voluntary relevance aside, not a comment
  answer; spheres + NISAR + ICESat-2 carry NASA relevance).
- Labels statement condensed; Computing cluster sentence shortened; Dissemination
  list compressed; DMOS folded to one sentence; two timeline cells shortened.

Result: body ends page 6 (DMOS last), References open page 7. All 11 fixes
verified present in the rendered PDF; "mm/yr" absent; lidar counts 15 lowercase +
1 published-title "LiDAR" (Schenk).

## Cascades

- OSDMP, research readiness statement, current & pending: lidar lowercased,
  re-promoted to `finesst_final/` and `finesst_submission/`, PDFs re-rendered.
- Biosketch untouched (FI-authored, do-not-modify; its "LiDAR" instances are the
  FI's own CV wording and can be adjusted at signing if desired).
- Facilities and mentoring plan contain no lidar mentions; unchanged this round.

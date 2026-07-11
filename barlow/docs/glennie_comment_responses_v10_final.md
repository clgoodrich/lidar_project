# Response to Glennie's newest comments — v10_tracked_cgedits → v10_working

**Date:** 2026-07-11
**Files:** `barlow/finesst_final_v2/finesst_proposal_v10_working.docx` (+ pdf),
`OSDMP_reworked.docx`, memo covers the 11 comments dated 2026-07-11 in
`finesst_proposal_v10_tracked_cgedits.docx`. The 9 comments dated 2026-07-08 were the
previous round (already addressed in v8/v9 — see `glennie_comment_responses_v8.md`) and
were stripped from the working copy without action.

Before comment work, the working copy was produced by a two-stage accept: all of the
FI's tracked changes (57 ins / 48 del), then all of Glennie's tracked line edits
(45 ins / 20 del + 5 formatting). Zero tracked changes remain; zero comments remain.

| # | His comment (short) | What changed |
|---|---|---|
| 13 | Renumber references — [9] appears 2nd, should be [2] | All in-text citations renumbered by order of first appearance; reference list reordered to match. Barlow/Zhu/Glennie 2022 was in the list but never cited — now cited at the U-Net method sentence ("A U-Net ML methodology [3], [4]…"), so every reference is cited. Final list is [1]–[12] in appearance order. |
| 63 | "honest"? Do you mean rigorous? | "honest uncertainty" → "rigorous uncertainty". |
| 149 | Inline formula is ugly — make it an equation | `1.96 x sqrt(NMAD1^2 + NMAD2^2)` is now a centered OMML display equation: LOD95,diff = 1.96 √(NMAD₁² + NMAD₂²). Inline LOD95 = 1.96 × NMAD kept with a proper ×. |
| 88 | Post-2014 REMA aside "seems out of place" | The aside sat between O2 and O3 in the objectives list; moved to after O3 (O1 → O2 → O3 → aside → Approach). Later condensed to one sentence in the page-budget pass. |
| 175 | Risks intro too blunt — soften | "Several things could go wrong and yield bad or incomplete results." → "The project is designed to keep risk low, and the main threats to the work have been mitigated as far as project design allows. A few could still affect the completeness of the results; each is described below with its mitigation." |
| 188 | Where is O1 in the timeline? | Stage 1 deliverable now reads "first attribution model (O1, Taylor Valley)" — all three objectives are now tagged in the schedule (O1/O2/O3 ↔ Stages 1/2/3). |
| 46 | Align relevance with NASA's new Earth Science *spheres* | Relevance paragraph now reads: "It spans three of the Division's research spheres: the Cryosphere (polar glaciers and their meltwater), the Hydrosphere (water moving through the stream network), and the Geosphere (surface-topography change)…" (replaces the old Cryospheric Sciences / Terrestrial Hydrology program names). |
| 60 | ICESat-2/NISAR "should be listed in your data source document" | ICESat-2 (ATLAS; ATL06/ATL08, NASA NSIDC DAAC) added to the OSDMP input table and it is already a Project Needs row. NISAR is deliberately *not* listed as an input — per the #89 resolution it is a possible future cross-check, not a data source used by the project. |
| 89 | Does NISAR reach the MDV? Future elevation source? | Answered in-text with a citation: "NISAR's left-looking, 12-day L-band coverage includes the Dry Valleys [7]; it maps surface deformation and coherence change rather than elevation, so it is a possible independent flag of melt-season bank disturbance, not an elevation source." Facts verified: NISAR looks left specifically to achieve complete Antarctica coverage (the tradeoff is a North-Pole gap); it is an InSAR deformation/coherence mission, not a DEM producer. New ref [7]: NISAR Mission Science Users' Handbook, 2nd ed. (2025), NASA JPL. |
| 104 | "More factors than melt energy or water volume… not enough confounding variables" (points to his NSF proposal) | O1 now frames candidate controls as **climate forcing** (temperature, insolation, discharge, mass balance, thaw — LTER/ERA5/AMPS) **× substrate susceptibility** (microclimate zone, mapped permafrost/ground-ice class, bed material — published MDV mapping, new refs [10] Fountain et al. 2014 *Geomorphology* 225:25–35 and [11] Bockheim et al. 2007 *PPP* 18:217–227). H1 is now conditioned: "after controlling for substrate, melt energy will predict channel change better than water volume alone; forcing should matter most where ground ice is present," and the falsification test adds "or if substrate class alone absorbs the explanatory power." Approach step 3 fits models "with substrate covariates, ranking variable importance across the full forcing-plus-substrate set"; step 4 tests "controlling for substrate class." H2 echo: "Bank thaw should track summer thaw and ground-ice class." This adopts the forcing-×-susceptibility framework from the PI's NSF 25-526 project description. |
| 119 | LTER gauges cover few channels/partial seasons — what about the rest? Non-LTER variables? | The driver-history step now leads with universality: "Build a driver history for every stream, gauged or not." Reanalysis (ERA5/AMPS) supplies temperature/radiation for every basin; per-basin insolation is computed from the project DEMs; substrate covariates need no field records. The 21 LTER gauge records calibrate the insolation-to-discharge regression for ungauged streams and the post-2015 thin record. "LTER data calibrate and validate the driver set; they do not limit its coverage." |

## Page-budget pass

The #89/#104/#119 additions (~8 lines) pushed body text onto page 7 (S/T/M limit is
6 pages; references don't count). Reclaimed without losing content:

- STV sentence condensed ("The method also positions the project for the possible
  future STV observing system.").
- NISAR sentence tail tightened ("not an elevation source." — dropped "for this analysis").
- Post-2014 REMA aside condensed to one sentence.
- O1 LTER parenthetical "(meteorology, stream gauges, glacier mass balance, and soil
  climate)" cut — the forcing list in the same sentence already enumerates these, and
  the sources stay named (LTER [8], ERA5 [9], AMPS).
- DMOS paragraph condensed to two lines pointing at the accompanying OSDMP (which
  carries the full product/format/archive detail).

Result: body ends on page 6 ("…the accompanying OSDMP."), References opens page 7 —
same layout as the accepted baseline.

## Reference list after renumber (all cited, appearance order)

[1] Barlow 2026 dissertation · [2] Fountain et al. 1999 · [3] Ronneberger et al. 2015 ·
[4] Barlow, Zhu & Glennie 2022 · [5] Howat et al. 2019 (REMA) · [6] Schenk et al. 2004 ·
[7] NISAR Science Users' Handbook 2nd ed. 2025 · [8] MCM-LTER/EDI ·
[9] Hersbach et al. 2020 (ERA5) · [10] Fountain et al. 2014 · [11] Bockheim et al. 2007 ·
[12] Höhle & Höhle 2009.

## Cascades to other package documents

- **OSDMP_reworked.docx**: added input rows for ICESat-2 (#60) and the substrate maps
  (#104) — Bockheim et al. 2007; Fountain et al. 2014, public. Still 2 pages.
- **Project Needs table (in-proposal)**: added "Permafrost / ground-ice and
  microclimate-zone maps — published MDV mapping [10], [11] — public, free."
- research readiness statement, mentoring plan, facilities: checked — no text
  contradicts the new O1 framing; no changes needed.

## Still open / human items

- The O1/O2/O3 → "Objective N" rephrase for the proposal is still deferred (user-driven,
  applies to 10 tokens incl. Glennie's own "(O1)/(O2)/(O3)" insertions).
- v10_working is a *working* copy in `finesst_final_v2/`; promotion to
  `A1_proposal_STM` and the anonymized package copy happens after the FI signs off.
- Anonymization note: the new text refers to "the PI's NSF proposal" nowhere; substrate
  framing cites only published literature. Safe for DAPR.

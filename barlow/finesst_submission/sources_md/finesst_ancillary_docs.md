# FINESST Ancillary Documents — Drafts

*Three short required package items in one working file: split into separate PDFs at
submission time per the solicitation's upload structure. [Brackets] = facts to confirm.*

---

## A. Facilities, Equipment, and Resources Statement

*(No page limit; half a page is typical. Non-anonymized is acceptable here — confirm
against the final F.5 text.)*

The proposed work requires modest, already-available resources; no facility development
or shared-instrument time is needed.

**Computing.** A workstation with a single consumer GPU ([model], [VRAM] GB) and [N] TB
of local storage, owned by [the research group / the FI], is sufficient for all model
training and elevation processing in the proposal. The institution provides
[institutional HPC name, if any] as surplus capacity; the project does not depend on it.

**Software.** The full processing stack is open source (Python scientific stack, PDAL,
GDAL/OGR, WhiteboxTools, PyTorch, QGIS). No commercial licenses are required.

**Data.** All required datasets are free and public (proposal §4 table); the single
author-gated item (training labels) has a budgeted fallback. No data purchases.

**Workspace.** The FI has [office/lab space] in [department], with institutional backup
storage for working data and the public archives (Zenodo, EDI) for released products.

**Field work.** None proposed. The project is entirely archival-data-based; no Antarctic
deployment, logistics support, or permitting is required.

---

## B. Acknowledgements (150-word limit, with AI disclosure)

*(Required statement identifying the FI as primary author and disclosing all
contributions, including AI tools. Count words before submission — target ≤150.)*

Draft:

> The Future Investigator conceived the proposed research and is the primary author of
> this proposal. The Principal Investigator provided scientific mentorship and
> editorial review. AI assistance (Anthropic's Claude, used as a drafting and editing
> tool under the FI's direction) contributed to text drafting, document formatting, and
> data-availability verification; all scientific content, claims, and decisions are the
> FI's own and were reviewed by the FI. Publicly archived datasets consulted in
> preparing this proposal are credited to their providers: NASA ATM (via USGS),
> NCALM/OpenTopography, the Polar Geospatial Center (REMA), the McMurdo Dry Valleys
> LTER program (via the Environmental Data Initiative), Copernicus/ECMWF (ERA5), and
> NCAR (AMPS). [Add any colleague who gave substantive feedback, including the
> dissertation author if her input shaped the plan.]

*(~120 words as drafted — room for additions.)*

---

## C. Budget Justification / Narrative skeleton

*(Typically ~2 pages; usually finalized by the PI and the institution's research office —
this skeleton gives them the project-specific content. FINESST budgets are capped at
~$50,000/year total; the composition below is the standard shape — confirm current caps
and allowable categories against the F.5 text and institutional rates.)*

**Year 1 (and similarly Years 2–3):**

| Item | Amount | Justification |
|---|---|---|
| FI stipend | $[per institutional rate] | [X] months graduate research assistantship — the FI performs all proposed research |
| Tuition & fees | $[per institutional rate] | Required for full-time enrollment, a FINESST eligibility condition |
| Conference travel | $[~2,500–4,000] | Yr 1: AGU (poster, cryosphere section). Yr 2–3: AGU talk + SCAR/ISAES — the venues named in the Mentoring Plan |
| Publication costs | $[~2,000–3,500] | Open-access fees for [1] paper/year (three first-author papers planned) |
| Computing/storage | $[~500–1,500] | Local storage expansion for full-valley raster stacks (tens of GB per epoch-derivative); no cloud compute required |
| Materials/other | $[small] | [Software-adjacent costs if any; otherwise omit] |

**Notes for the grants office:**
- No PI salary (FINESST does not fund the PI).
- No field-work or logistics costs (archival-data project).
- Indirect costs per the solicitation's rules for FINESST [confirm current F&A
  treatment in the F.5 text — it differs from standard research awards].
- Year-over-year totals should track the stipend/tuition escalation schedule;
  the travel/publication mix shifts from poster (Yr 1) to talks + synthesis-paper
  fees (Yr 3).

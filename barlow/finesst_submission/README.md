# FINESST-25 Submission Package

Consolidated proposal materials for the FINESST graduate research proposal
(MDV ephemeral-channel change → climate-driver attribution).

- **FI (Future Investigator / student, primary author):** Colton Goodrich, University of Houston
- **PI (mentor):** Craig Glennie, University of Houston
- **Division/program:** NASA Earth Science Division (see proposal "NASA Relevance")
- **Due:** 14 July 2026, 11:59 pm ET, via NSPIRES

This folder contains **only** files that are part of the submission. Editing sources,
the solicitation, blank templates, and other reference material live elsewhere under
`barlow/` and `barlow/docs/`, not here. When a deliverable is updated it is synced into
this folder in the same step, so the package always reflects what will be uploaded.

---

## How this maps to the NSPIRES upload

FINESST is submitted as **two PDFs** (plus optional HEC), each assembled by
concatenating the components below in order (solicitation §5.1).

### PDF 1 — Anonymized Technical Proposal  (`1_anonymized_technical/`)
Dual-anonymous: no names, no institutions, numerical `[n]` citations only.

| Order | File | Limit | Status |
|---|---|---|---|
| 1 | `proposal_STM_v10.docx` (Science/Technical/Management + References) | ≤6 pp excl. refs | ✅ 6 pp + refs on p7; DAPR-clean; 12-pt TNR; PI comments #1–#9 resolved (accepted v10) |
| 2 | `osdmp_v3.docx` (your v2 + 12-pt TNR conversion; content unchanged) | ≤2 pp | ✅ 2 pp; `osdmp_v2.docx` kept as your edited source |
| 3 | `mentoring_plan_v2.docx` (unsigned; notes stripped; 12-pt TNR) | ≤2 pp | ✅ 2 pp |

### PDF 2 — Expertise & Resources, NOT anonymized  (`2_expertise_resources_NOT_anonymized/`)
Real names/institutions here.

| Order | File | Limit | Status |
|---|---|---|---|
| 1 | `research_readiness_statement_v3.docx` (12-pt TNR) | ≤1 pp | ✅ 1 pp; 2 small brackets left (transcript courses, exam date) |
| 2 | `biosketch_FI_goodrich_v2.docx` | none | ✅ notes stripped; sign + date (NASA template — formatting left as-is) |
| 3 | **Biosketch — PI (Glennie)** | none | ❌ TODO — use blank template |
| 4 | `current_pending_FI_goodrichV3.docx` (your V2 + scope fix: "valley-floor" → "stream-corridor" to match the narrowed O2) | none | ✏️ fill red brackets + sign; V2 kept as your edited source. ⚠️ if the PI's NSF 25-526 proposal would fund your RA-ship, list it as pending here |
| 5 | **Current & Pending — PI (Glennie)** | none | ❌ TODO — must list his pending NSF 25-526 proposal (overlapping MDV work) |
| 6 | `facilities_acknowledgements_budget_v4.docx` (12-pt TNR) | budget ~2 pp | ✅ 2 pp; GPU corrected to NVIDIA GeForce GTX 1070 Ti (8 GB). ⚠️ budget Amount column is blank |

Older versions of each file are kept in-folder as history (nothing overwritten).

Note: NASA Biosketch and Current & Pending templates are **exempt** from the 1-inch
margin rule; everything else uses ≥1-inch margins.

---

## Folder contents (submission files only)

- `1_anonymized_technical/` — the 3 anonymized components (.docx + .pdf each)
- `2_expertise_resources_NOT_anonymized/` — the non-anonymized components present so far

Kept **outside** this folder (needed to build, but not submitted):
- Blank NASA forms → `barlow/docs/finesst_templates_blank/` (for Glennie's biosketch + C&P)
- Editable `.md` sources → `barlow/docs/` (built via `barlow/build/_md_to_*.py`)
- Solicitation, PI edits, figure sources → `barlow/` and `barlow/docs/`

---

## Outstanding before submission

1. **Glennie biosketch** — his content into `barlow/docs/finesst_templates_blank/biosketch-form.docx`.
2. **Current & Pending — PI (Glennie)** — his content into the blank C&P template.
   (FI Current & Pending is drafted — just fill the red brackets: tuition-waiver
   value, appointment length, person-months, period of performance.)
3. **Fill remaining `[bracketed]` placeholders** — readiness statement (transcript
   course numbers/grades, qualifying-exam date), C&P (tuition/fees confirm, funding
   source), and ancillary (GPU model/VRAM, budget dollar amounts).

### ⚠️ Two timing decisions (affect proposal, C&P, RRS, budget)
- **FINESST start must fall Jan–Jul 2027** (no earlier than Jan 2027; no later than one
  year after the 14 Jul 2026 due date). August 2026 and August 2027 are both invalid.
  Docs currently use **01/2027**.
- **A full 3-year award runs to ~12/2029**, but your stated **graduation is 08/2029**.
  Either extend expected graduation to ≥12/2029, or shorten the award to end at graduation.
  Docs currently show 01/2027–12/2029 with this flagged.
4. **Sign + date** the FI biosketch.
5. **Verify** reference `[9]` (Fountain et al. 1999) matches the source the PI intended.
6. **Assemble** the two PDFs in the order above and upload to NSPIRES with the
   anonymized Project Summary on the cover page — draft ready at
   `barlow/docs/finesst_project_summary.md` (paste into NSPIRES Section VII).
7. **ORCID** on file for both FI and PI in NSPIRES (funding-eligibility requirement).

Formatting note: all non-template components are now **12-pt Times New Roman,
single-spaced** (the solicitation's 15-chars-per-inch benchmark). NASA Biosketch and
C&P templates keep their own formatting (exempt). Every component re-rendered and
page-limit-verified 2026-07-09.

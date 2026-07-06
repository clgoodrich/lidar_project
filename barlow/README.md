# Barlow / FINESST — McMurdo Dry Valleys stream-change work

Self-contained subproject: reproducing **Mary C. Barlow's 2026 PhD dissertation**
(*"A Comprehensive Spatial Analysis of Stream Boundary and Geomorphological Change
Detection: McMurdo Dry Valleys, Antarctica"*, Univ. Houston) and the FINESST expansion
(coupling geomorphic change to physical/climate drivers). Kept separate from the WellSight
PA orphaned-wells work.

## Layout
```
barlow/
  build/
    _fetch_barlow_data.py    # acquire every dataset (lidar epochs, REMA, LTER, ERA5, AMPS, labels)
    _build_barlow_inputs.py  # 6-layer U-Net derivative stack (elev/slope/aspect/curv/MFD-flowacc/intensity)
    _change_detection.py     # multi-epoch DEM-of-Difference (median/NMAD/LOD95, ICP, per-stream rates)
    _finesst_figures.py      # builds the proposal figure set from real pipeline outputs
    _md_to_pdf.py            # render finesst_proposal.md -> .pdf (reportlab; DejaVu Unicode)
    _md_to_docx.py           # render finesst_proposal.md -> .docx (python-docx)
  docs/
    finesst_proposal.md              # full ~6-page NASA FINESST S/T/M section (SOURCE OF TRUTH)
    finesst_proposal.pdf/.docx       # rendered (regenerate via _md_to_pdf.py / _md_to_docx.py)
    finesst_proposal_plain.md        # same proposal, plain-language voice (own SOURCE OF TRUTH)
    finesst_proposal_plain.pdf/.docx # rendered plain version
    finesst_proposal_basic.md        # plan-only variant: NO preliminary results/figures; honest
    finesst_proposal_basic.pdf/.docx #  needs/risks framing (own SOURCE OF TRUTH; 4 pp rendered)
    finesst_osdmp.md/.pdf/.docx      # Open Science & Data Management Plan (2 pp, anonymized)
    finesst_readiness_statement.md/  # Research Readiness Statement skeleton (1 p, NOT anonymized;
      .pdf/.docx                     #  [bracketed] placeholders for the FI to fill in)
    finesst_figures/                 # fig1-5 PNGs shared by both versions (committed, small)
    finesst_reference.md             # personal lookup doc: facts, key numbers, Q&A, glossary
    finesst_reference.docx           # rendered (regenerate: _md_to_docx.py <md> --bold)
    barlow_data_manifest.md          # dataset inventory + "reproduce everything" recipe
    barlow_dissertation_explained.md # plain-language walkthrough of the dissertation
    barlow_dissertation_summary.md   # 2-page digest of the whole dissertation
    barlow_dissertation_summary.pdf  # rendered (regenerate: _md_to_pdf.py <md>)
    barlow_dissertation_readalong.md # section-level read-along companion (open next to the PDF)
    barlow_dissertation_pagenotes.md # per-page notes (drives the side-by-side PDF's right pane)
    BARLOW-DISSERTATION-2026.pdf     # the dissertation itself (413 MB, gitignored)
    BARLOW-DISSERTATION-2026_sidebyside.pdf          # dissertation page + guide notes per sheet (gitignored;
    BARLOW-DISSERTATION-2026_sidebyside_compact.pdf  #  regenerate: python barlow/build/_build_readalong_pdf.py [--raster])
    BARLOW-DISSERTATION-2026_readalong.epub          # e-reader version: page image then its note, alternating
                                                     #  (gitignored; regenerate: python barlow/build/_build_readalong_epub.py)
    FINESST_Barlow_Expansion_Concept.pdf  # earlier planning brief (superseded by finesst_proposal.md)
```

## FINESST program facts (kept HERE, not in the submission documents)

- **Program:** NASA ROSES F.5 FINESST; **division designation** (Earth Science) is set on
  the NSPIRES cover page, not written in the S/T/M.
- **Deadline:** 14 July 2026, 11:59 PM EDT (university internal routing runs days earlier).
- **Roles:** grad student = Future Investigator (FI), primary author/intellectual lead;
  advisor = PI of record (declared on the cover page).
- **Award:** up to ~$50,000/yr, up to 3 years.
- **Review:** dual-anonymous; scored on Scientific Merit, Relevance to SMD, Research Readiness.
- **S/T/M cap:** 6 pages (references/ToC excluded). Proposal abstract is typed into a
  separate NSPIRES box — reuse the summary paragraph minus any section cross-references.

## Data location
All heavy data is **off-repo on `E:\barlow_data_DO_NOT_DELETE\`** (regenerable; not committed per the
large-file rule). The scripts + docs here are the reproducible record. See
`docs/barlow_data_manifest.md` for the full command recipe and per-dataset status.

## Status (2026-07-01)
All four epochs' data + drivers downloaded; 6-layer derivative stack built & QC'd on a
Taylor Valley pilot. Change detection validated across **all three epochs** (2001→2014
NMAD 0.21 m; 2014→REMA 0.23 m — both in the dissertation's ranges), with ICP co-registration
and per-stream rates. Rates are now **specific (mm/yr, area-normalized)** with an automated
**standing-water screen** (Lake Fryxell's ~1.5 m rise was contaminating Aiken/Huey volumes).
**FINESST proposal drafted** (`docs/finesst_proposal.md`) with 5 figures from real outputs —
headline preliminary result: lidar-epoch specific gross rate vs mean gauged discharge,
r = +0.95 (p = 0.004), Spearman ρ = +0.94 (p = 0.005), leave-one-out robust; REMA epoch shows
no relation under sparse post-2015 gauging (motivates the O1 modeled-melt-energy driver).
Remaining/optional: per-valley stacks for O2, REMA time-stamped strips, full driver-energy
(PDD/insolation) model for O1. `_build_barlow_inputs.py` imports `run_pdal` from
`notebooks/wellsight_v2/_common.py` (shared PDAL helper).

**Update (2026-07-03):** Cami shared her working GIS data (`barlow/Shapefiles/`, gitignored —
author-private; see manifest 🎁 section), incl. her **final detected channel polygons per
epoch**. `_change_detection.py --channels cami` recomputes rates inside her exact masks:
attribution signal unchanged (r = +0.95, p = 0.003), leave-one-out worst case improves
(+0.82 → +0.87). Only her training tiles remain author-gated.

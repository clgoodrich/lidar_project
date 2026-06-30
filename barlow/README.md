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
    finesst_proposal.pdf             # rendered PDF (regenerate via _md_to_pdf.py)
    finesst_proposal.docx            # rendered Word doc (regenerate via _md_to_docx.py)
    finesst_figures/                 # fig1-5 PNGs used by the proposal (committed, small)
    barlow_data_manifest.md          # dataset inventory + "reproduce everything" recipe
    barlow_dissertation_explained.md # plain-language walkthrough of the dissertation
    FINESST_Barlow_Expansion_Concept.pdf  # earlier planning brief (superseded by finesst_proposal.md)
```

## Data location
All heavy data is **off-repo on `J:\barlow_data\`** (regenerable; not committed per the
large-file rule). The scripts + docs here are the reproducible record. See
`docs/barlow_data_manifest.md` for the full command recipe and per-dataset status.

## Status (2026-06-30)
All four epochs' data + drivers downloaded; 6-layer derivative stack built & QC'd on a
Taylor Valley pilot. Change detection validated across **all three epochs** (2001→2014
NMAD 0.21 m; 2014→REMA 0.23 m — both in the dissertation's ranges), with ICP co-registration
and per-stream rates. **FINESST proposal drafted** (`docs/finesst_proposal.md`) with 5 figures
from real outputs — including a preliminary attribution result (lidar-epoch gross rate vs
cumulative melt discharge, r = +0.89). Remaining/optional: per-valley stacks for O2, REMA
time-stamped strips, full driver-energy (PDD/insolation) model for O1. `_build_barlow_inputs.py`
imports `run_pdal` from `notebooks/wellsight_v2/_common.py` (shared PDAL helper).

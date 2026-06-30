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
    _change_detection.py     # 2001->2014 DEM-of-Difference (median/NMAD/LOD95, volumes)
  docs/
    barlow_data_manifest.md          # dataset inventory + "reproduce everything" recipe
    barlow_dissertation_explained.md # plain-language walkthrough of the dissertation
    FINESST_Barlow_Expansion_Concept.pdf
```

## Data location
All heavy data is **off-repo on `J:\barlow_data\`** (regenerable; not committed per the
large-file rule). The scripts + docs here are the reproducible record. See
`docs/barlow_data_manifest.md` for the full command recipe and per-dataset status.

## Status (2026-06-29)
All four epochs' data + drivers downloaded; 6-layer derivative stack built & QC'd on a
Taylor Valley pilot; 2001→2014 change detection validated (NMAD 0.21 m, in the dissertation's
range). Remaining: stream-channel masking for per-stream rates, ICP fine co-registration,
optional REMA time-stamped strips. `_build_barlow_inputs.py` imports `run_pdal` from
`notebooks/wellsight_v2/_common.py` (shared PDAL helper).

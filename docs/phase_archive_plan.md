# Archive plan — parked research threads

Moved, never deleted. Reversible with `tools/apply_moves.py --undo --phase archive`.

| Source | Destination | files | GB |
|---|---|---:|---:|
| `data/external/ramachandran_2024` | `data/99_archive/parked/permian_ramachandran/ramachandran_2024` | 87,535 | 4.91 |
| `label_grids/permian_01` | `data/99_archive/parked/permian_ramachandran/label_grids_permian_01` | 38 | 1.58 |
| `label_grids/permian_02` | `data/99_archive/parked/permian_ramachandran/label_grids_permian_02` | 13 | 0.49 |
| `label_grids/permian_03` | `data/99_archive/parked/permian_ramachandran/label_grids_permian_03` | 13 | 0.50 |
| `label_grids/permian_04` | `data/99_archive/parked/permian_ramachandran/label_grids_permian_04` | 13 | 0.49 |
| `barlow` | `data/99_archive/parked/barlow_finesst/barlow` | 911 | 1.48 |
| `barlow_data` | `data/99_archive/parked/barlow_finesst/barlow_data` | 0 | 0.00 |

**Total: 88,523 files, 9.46 GB**

## .gitignore rules that must be re-anchored

A rule anchored to the old location stops matching the moment the files move, and it fails silently. These must be updated in the same change:

- `data/external/ramachandran_2024/naip_chips/`
- `data/external/ramachandran_2024/naip_chips_pilot/`
- `data/external/ramachandran_2024/permian_denver_data.zip`
- `label_grids/permian_01/pad_unet_xfer/`
- `/barlow_data/`
- `barlow/docs/BARLOW-DISSERTATION-2026.pdf`
- `barlow/docs/BARLOW-DISSERTATION-2026_sidebyside*.pdf`
- `barlow/docs/BARLOW-DISSERTATION-2026_readalong.epub`
- `barlow/Shapefiles/`
- `barlow/MDV_Resources.docx`

The simplest correct fix is one recursive rule for the whole archive tree, since everything in it is parked and regenerable or externally sourced:

```
data/99_archive/**
```

with the manifest and any small text records force-added.

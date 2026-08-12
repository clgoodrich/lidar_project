# Phase 2 — consolidate loose rasters

`data/derivatives/` holds 282 loose files. **166 move**, 116 stay.

| Destination | files | MB | exists today |
|---|---:|---:|---|
| `data/derivatives/tiles/607594_1m` | 20 | 99 | **new** |
| `data/derivatives/tiles/610594_1m` | 19 | 99 | **new** |
| `data/derivatives/tiles/610605_1m` | 20 | 98 | **new** |
| `data/derivatives/tiles/616593_1m` | 19 | 100 | **new** |
| `data/derivatives/tiles/9t` | 24 | 938 | yes |
| `data/derivatives/tiles/mck_e1423n2238_05` | 31 | 2390 | **new** |
| `data/derivatives/tiles/mckean_1m` | 1 | 1 | **new** |
| `data/derivatives/tiles/mk5_1m` | 30 | 1984 | **new** |
| `data/derivatives/tiles/venango_1m` | 1 | 0 | **new** |
| `data/derivatives/tiles/washington_1m` | 1 | 3 | **new** |

Total moving: 5.58 GB

## Staying put

**name carries no <area>_<res> suffix** — 101 files
- `data/derivatives/_oilcreek_tiles_spec.txt`
- `data/derivatives/cornrow_demo_hillshade.png`
- `data/derivatives/cornrow_demo_hillshade.png.aux.xml`
- `data/derivatives/dem_demo_filtered.tif`
- `data/derivatives/dem_demo_unfiltered.tif`
- `data/derivatives/dep_wells_snapped_9tile.gpkg`
- `data/derivatives/expert_validation_misses.png`
- `data/derivatives/expert_validation_overview.png`
- `data/derivatives/hillshade.tif`
- `data/derivatives/hillshade_9t_1m_az135.tif`
- `data/derivatives/intensity_all.png`
- `data/derivatives/intensity_ground_stretch.png`
- … and 89 more

**referenced** — 15 files
- `data/derivatives/dem_9t_1m.tif`
- `data/derivatives/dem_mck_e1423n2238_05.tif`
- `data/derivatives/ground_density_noverlap_9t_1m.tif`
- `data/derivatives/hillshade_9t_1m.tif`
- `data/derivatives/hillshade_9t_1m.tif.aux.xml`
- `data/derivatives/hillshade_mk5_1m.tif`
- `data/derivatives/hillshade_mk5_1m.tif.aux.xml`
- `data/derivatives/intensity_ground_9t_1m.tif`
- `data/derivatives/lrm_25_9t_1m.tif`
- `data/derivatives/lrm_5_9t_1m.tif`
- `data/derivatives/openness_neg_9t_1m.tif`
- `data/derivatives/openness_pos_9t_1m.tif`
- … and 3 more

# Manual QGIS annotations — the labels we drew

What a human marked in QGIS, how the label set grew, and how it was split for
training so that a test score means something.

    annotation_<class>_*   the per-class before/after series, twelve images
    annotation_schema_*    what one pad and one pit look like as labels
    annotation_growth_*    how the label count grew, 426 -> 527 -> 712 pits
    split_blocks_12x12_9t  the block split, so train and test do not touch
    split_held_out_pits_9t which blocks were held out
    archive/               the earlier single 300 m square, one per class

Each class in the series is drawn over RRIM at a place chosen for THAT class,
with `no_lines` and `lines` being the same frame without and with the
shapefile. The RRIM base is drawn the way `qgis/wellsight.qgz` draws it --
multibandcolor, NoEnhancement, so the stored bytes reach the screen untouched.

<!-- annotation-series: generated, do not edit by hand -->

## The per-class before/after series

Twelve images. Each class is a pair on the same
frame: the terrain alone, then the same terrain with the
hand-drawn layer over it. Flicking between the two answers "is
that really in the terrain, or did somebody draw it". Pits get
four, because the floor and the rim are separate layers and the
floor is the one the model trains on.

| file | shows | centre (WGS84) | width |
|---|---|---|---|
| `annotation_roads_2km_no_lines_9t.png` | Roads — terrain only, nothing drawn on it | 41.499080 N, 79.541300 W | 2 km |
| `annotation_roads_2km_lines_9t.png` | Roads — with the hand-drawn roads | 41.499080 N, 79.541300 W | 2 km |
| `annotation_drainage_2km_no_lines_9t.png` | Drainage — terrain only, nothing drawn on it | 41.502510 N, 79.533711 W | 2 km |
| `annotation_drainage_2km_lines_9t.png` | Drainage — with the hand-drawn drainage | 41.502510 N, 79.533711 W | 2 km |
| `annotation_pads_2km_no_lines_9t.png` | Pads — terrain only, nothing drawn on it | 41.507320 N, 79.541360 W | 2 km |
| `annotation_pads_2km_lines_9t.png` | Pads — with the hand-drawn pads | 41.507320 N, 79.541360 W | 2 km |
| `annotation_pits_1km_no_lines_9t.png` | Pits — terrain only, nothing drawn on it | 41.494906 N, 79.537175 W | 1 km |
| `annotation_pits_1km_floors_9t.png` | Pits — pit floors only — this is what the model learns | 41.494906 N, 79.537175 W | 1 km |
| `annotation_pits_1km_rims_9t.png` | Pits — outer rims only | 41.494906 N, 79.537175 W | 1 km |
| `annotation_pits_1km_floors_and_rims_9t.png` | Pits — rims and floors together | 41.494906 N, 79.537175 W | 1 km |
| `annotation_all_3km_no_lines_9t.png` | All four annotation layers — terrain only, nothing drawn on it | dead centre of 9t | 3 km |
| `annotation_all_3km_lines_9t.png` | All four annotation layers — with all four layers drawn | dead centre of 9t | 3 km |

Rebuild with:

```bash
python docs/presentation/figures_30to45min/_build_rrim_annotation_series.py
```

<!-- /annotation-series -->

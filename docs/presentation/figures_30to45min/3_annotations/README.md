# Manual QGIS annotations — the labels we drew

What a human marked in QGIS, how the label set grew, and how it was split for
training so that a test score means something.

    annotation_schema_*        what one pad and one pit look like as labels
    annotation_growth_*        how the label count grew, 426 -> 527 -> 712 pits
    spatial_block_split_*      the 12x12 block split, so train and test do not touch
    pit_split_held_out_*       which blocks were held out
    1_ .. 5_annotation_*       the per-class before/after series, in talk order
    archive/                   the earlier single 300 m square, one per class

Each class in the numbered series is drawn over RRIM at a place chosen for THAT
class. The RRIM base is drawn the way `qgis/wellsight.qgz` draws it --
multibandcolor, NoEnhancement, so the stored bytes reach the screen untouched.

<!-- annotation-series: generated, do not edit by hand -->

## The per-class before/after series

Twelve images, in talk order. Each class is a pair on the same
frame: the terrain alone, then the same terrain with the
hand-drawn layer over it. Flicking between the two answers "is
that really in the terrain, or did somebody draw it". Pits get
four, because the floor and the rim are separate layers and the
floor is the one the model trains on.

| file | shows | centre (WGS84) | width |
|---|---|---|---|
| `1_annotation_roads_2km_before_no_annotation_9t_05.png` | Roads — terrain only, nothing drawn on it | 41.499080 N, 79.541300 W | 2 km |
| `1_annotation_roads_2km_after_roads_drawn_9t_05.png` | Roads — with the hand-drawn roads | 41.499080 N, 79.541300 W | 2 km |
| `2_annotation_drainage_2km_before_no_annotation_9t_05.png` | Drainage — terrain only, nothing drawn on it | 41.502510 N, 79.533711 W | 2 km |
| `2_annotation_drainage_2km_after_drainage_drawn_9t_05.png` | Drainage — with the hand-drawn drainage | 41.502510 N, 79.533711 W | 2 km |
| `3_annotation_pads_2km_before_no_annotation_9t_05.png` | Pads — terrain only, nothing drawn on it | 41.507320 N, 79.541360 W | 2 km |
| `3_annotation_pads_2km_after_pads_drawn_9t_05.png` | Pads — with the hand-drawn pads | 41.507320 N, 79.541360 W | 2 km |
| `4_annotation_pits_1km_before_no_annotation_9t_05.png` | Pits — terrain only, nothing drawn on it | 41.494906 N, 79.537175 W | 1 km |
| `4_annotation_pits_1km_after_floors_only_9t_05.png` | Pits — pit floors only — this is what the model learns | 41.494906 N, 79.537175 W | 1 km |
| `4_annotation_pits_1km_after_rims_only_9t_05.png` | Pits — outer rims only | 41.494906 N, 79.537175 W | 1 km |
| `4_annotation_pits_1km_after_rims_and_floors_9t_05.png` | Pits — rims and floors together | 41.494906 N, 79.537175 W | 1 km |
| `5_annotation_all_four_layers_3km_before_no_annotation_9t_05.png` | All four annotation layers — terrain only, nothing drawn on it | dead centre of 9t | 3 km |
| `5_annotation_all_four_layers_3km_after_all_four_drawn_9t_05.png` | All four annotation layers — with all four layers drawn | dead centre of 9t | 3 km |

Rebuild with:

```bash
python docs/presentation/figures_30to45min/_build_rrim_annotation_series.py
```

<!-- /annotation-series -->

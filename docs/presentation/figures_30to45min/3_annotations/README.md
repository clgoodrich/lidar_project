# Manual QGIS annotations — the labels we drew

What a human marked in QGIS, how the label set grew, and how it was split for
training so that a test score means something.

    annotation_schema_*        what one pad and one pit look like as labels
    annotation_growth_*        how the label count grew, 426 -> 527 -> 712 pits
    spatial_block_split_*      the 12x12 block split, so train and test do not touch
    pit_split_held_out_*       which blocks were held out
Each class is drawn over RRIM at a place chosen for THAT class, and every site
gives a pair: the same frame with no shapefile, and with it. Flicking between the
two answers "is that really in the terrain, or did somebody draw it".

    venango_roads_41p499080N_79p541300W/      2 km
    venango_drainage_41p502510N_79p533711W/   2 km
    venango_pads_41p507320N_79p541360W/       2 km
    venango_pits_41p494906N_79p537175W/       1 km, FOUR images -- terrain,
                                              floors, rims, and both together
    venango_all_9t_centre/                    3 km, dead centre of 9t

    archive/  the earlier single 300 m square, one frame for every class

The RRIM base is drawn the way `qgis/wellsight.qgz` draws it -- multibandcolor,
NoEnhancement, so the stored bytes reach the screen untouched.

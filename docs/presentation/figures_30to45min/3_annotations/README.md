# Manual QGIS annotations — the labels we drew

What a human marked in QGIS, how the label set grew, and how it was split for
training so that a test score means something.

    annotation_schema_*        what one pad and one pit look like as labels
    annotation_growth_*        how the label count grew, 426 -> 527 -> 712 pits
    spatial_block_split_*      the 12x12 block split, so train and test do not touch
    pit_split_held_out_*       which blocks were held out
    venango_site_.../          the annotations drawn over RRIM, by class

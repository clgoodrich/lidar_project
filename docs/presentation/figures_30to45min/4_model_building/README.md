# Model building — how the detector is put together

The pipeline itself and the decisions inside it.

    pipeline_diagram_unet_end_to_end_9t.png
        the whole pipeline as one path: data QA, terrain derivatives, hand
        annotation, training prep, training and QA. Built by
        `_build_pipeline_diagram.py`, which reads the channel list, the
        annotation layer names and the training parameters out of the data and
        the trainer rather than having them typed in.

    classical_vs_unet_*     the same scene, both methods
    road_chunking_*         why roads are cut into ~40 m chunks before training

    archive/
        pipeline_diagram_classical_and_unet_branches.png -- the old two-branch
        picture. The classical branch is retired: every model on the
        leaderboard, every probability raster and every threshold product is
        U-Net, so a two-branch diagram now misdescribes the project.

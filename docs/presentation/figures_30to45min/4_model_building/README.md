# Model building — how the detector is put together

The pipeline itself and the decisions inside it.

    pipeline_diagram_9t            the whole pipeline as one path: data QA,
                                   terrain derivatives, hand annotation,
                                   training prep, training and QA
    classical_vs_unet_pits_9t      the same scene, both methods
    road_chunking_cuts_40m_9t      where roads get cut
    road_chunking_by_split_40m_9t  and how the chunks fall across the splits

`_build_pipeline_diagram.py` reads the channel list, the annotation layer names
and the training parameters out of the data and the trainer rather than having
them typed in, so the diagram cannot drift from the code.

    archive/
        pipeline_diagram_classical_and_unet_branches.png -- the old two-branch
        picture. The classical branch is retired: every model on the
        leaderboard, every probability raster and every threshold product is
        U-Net, so a two-branch diagram now misdescribes the project.

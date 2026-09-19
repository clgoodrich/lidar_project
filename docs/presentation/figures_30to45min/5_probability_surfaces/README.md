# Probability surfaces — what the model outputs

The per-pixel probabilities the models produce, and what happens when you
threshold them.

    prob_layers_plain/      the raw probability rasters, one per class
    rrim_vs_prob/           the terrain beside the prediction, same frame
    venango_site_.../       one site: probability and argmax, per class
    tile_613590/            an out-of-domain tile the models never trained on
    pit_outcomes_*          matched, undecided and missed pits
    pit_undecided_*         the review queue, zoomed
    threshold_sweep_*       how much area gets flagged for a given recall

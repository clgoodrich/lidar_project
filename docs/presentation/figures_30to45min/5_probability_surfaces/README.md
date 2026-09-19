# Probability surfaces — what the model outputs

The per-pixel probabilities the models produce, and what happens when you
threshold them.

    prob_<class>_9t              the raw probability raster, whole area
    prob_<class>_300m_9t         the same class at one 300 m site
    argmax_<class>_300m_9t       the hard call at that site
    rrim_vs_prob_<class>_400m_*  terrain beside prediction, same frame,
                                 on 9t and on 613590
    pit_outcomes_9t              matched, undecided and missed pits
    pit_review_queue_9t          the undecided ones, zoomed
    threshold_sweep_9t           how much area gets flagged for a given recall

613590 is an out-of-domain tile the models never trained on:

    pit_pad_candidates_613590
    roads_generated_thr0p30_613590
    roads_found_vs_missed_thr0p50_613590
    roads_vs_tiger_613590

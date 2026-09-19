# Data QA — is the input any good?

Everything here is about the lidar we were handed, before any of our own
modelling. The finding that drives it: the PA WesternPA 2019 D20 March-2020
flight block stops calling anything ground past 18 degrees off nadir, so the
delivered ground surface has holes in it that run along the swath edges.

    scan_angle_cliff_by_survey_*   where ground stops, per map square, 258 squares
    scan_angle_accuracy_9t         how wrong the discarded returns actually are
    smrf_vs_vendor_*               our own ground classification vs the vendor's
    ground_delivered_9t            the ground surface as delivered
    ground_thrown_away_9t          only the ground that was discarded
    ground_both_9t                 the two together
    ground_cross_section_*         that slice edge-on, before and after
    cross_section_*                point classes seen edge-on, per feature
    report_1..8_*                  the plain-language report, one chart each
    nisar_radar_10m_9t             NISAR radar over the same ground

    archive/  superseded: the 7-tile cliff chart and the per-tile maps

Docs: `docs/iterations/nonground_classification_and_scan_angle_cut.md`,
`smrf_ground_reclassification.md`, `recovered_ground_maps_9t.md`.

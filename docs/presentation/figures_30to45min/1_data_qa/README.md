# Data QA — is the input any good?

Everything here is about the lidar we were handed, before any of our own
modelling. The finding that drives it: the PA WesternPA 2019 D20 March-2020
flight block stops calling anything ground past 18 degrees off nadir, so the
delivered ground surface has holes in it that run along the swath edges.

    scan_angle/            where ground stops, per map square, across 258 squares
    scan_angle/archive/    superseded: the 7-tile version and the per-tile maps
    recovered_ground_9t/   the 9t area with the discarded ground put back
    smrf_ground/           our own ground classification vs the vendor's
    cross_sections/        point classes seen edge-on
    report_lidar_ground/   the plain-language report, one chart per image

Docs: `docs/iterations/nonground_classification_and_scan_angle_cut.md`,
`smrf_ground_reclassification.md`, `recovered_ground_maps_9t.md`.

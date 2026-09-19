# Terrain derivatives — what we compute from the ground

The channels a model actually sees, built from the ground surface: hillshade,
slope, local relief, openness, roughness, TPI, canopy height, and RRIM.

Every `*_300m_9t.png` is the same 300 m site rendered in a different channel,
so the set flicks through as one stack. Styling comes from `qgis/wellsight.qgz`
rather than from colour ramps invented here, so these match what is on screen
in QGIS.

    dem chm slope hillshade        the surfaces and the shading
    lrm_5 lrm_25 tpi_05            local relief and position
    openness_pos openness_neg      how open the sky and the ground are
    roughness_11 rrim              texture, and the combined relief map
    aerial_300m_9t                 the aerial photo of the same frame
    rrim_200m_9t                   a second site, RRIM only
    rrim_formula_card              how RRIM is built, with the citation

    rrim_200m_source/  the GeoTIFF clips behind the 200 m RRIM images

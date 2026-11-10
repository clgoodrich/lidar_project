# AGU poster

Everything for the AGU poster on lidar detection of oil-well pits, pads and roads lives here.

| File | What it is |
|---|---|
| `poster_agu_layout_draft.md` | Layout plan: 44 x 44 in grid, boxes, hero figure, type and colour spec, open decisions |
| `agu_abstract_2026.md` | Abstract text, v17 |
| `agu abstract colton.docx` | Your Word copy of the abstract (not edited) |
| `AGU_poster.pptx` | Your poster template, 56 x 45 in, UH Cullen College frame (never edited; the build writes a new file) |
| `_make_agu_poster.py` | Builds the 44 x 44 poster from the template frame |
| `agu_poster_wireframe_44in.pptx` | Layout wireframe, grey blocks say what goes where |
| `agu_poster_mockup_44in.pptx` | Same layout with the built figures placed and draft text (`--mockup`) |
| `agu_poster_outline_44in.pptx` | Same layout and figures, every text slot a bracketed stand-in such as `[References here]` (`--outline`) |
| `_make_poster_figures.py` | Builds the poster figures from held-out model outputs on tile 9t |
| `figures/` | Poster figures: `poster_hero_heldout_9t.png`, `poster_optical_vs_lidar_9t.png`, `poster_channels_one_pit_9t.png`, `poster_signs_gallery_9t.png`, `poster_pipeline_diagram.png`, `poster_cv_folds_pit_9t.png`, `poster_pr_curves_heldout_9t.png` |
| `agu_poster_mockup_preview.png` | Low-resolution render of the mockup |
| `agu_poster_outline_preview.png` | Low-resolution render of the outline |

Moved here from `docs/` on 2026-11-08 with `tools/apply_moves.py` (logged in `docs/MOVES.csv`). Poster figures and the built `.pptx` go in this folder too.

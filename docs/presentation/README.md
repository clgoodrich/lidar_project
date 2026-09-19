# Presentation

Everything for the WellSight talk, in one place. Consolidated 2026-09-17.

```
docs/presentation/
    WellSight_Presentation.pptx                  the deck as it stands, 22 slides, 2026-05-04
    presentation_update_worklist_30to45min.md    the plan to take it to 30-45 minutes
    figures_30to45min/                           the nine new figures, their builder and notes
```

## What each piece is

**`WellSight_Presentation.pptx`** is the May deck. 22 slides, 17 content, 1
references, 4 appendix. Runtime 15-20 minutes. It stops at template matching and
the 48-feature gradient-boosting ensemble; slide 16 still lists U-Net as future
work. Nothing in this folder has been applied to it. Moved here from
`docs/publication/`, which now holds the paper only.

**`presentation_update_worklist_30to45min.md`** is the plan, not the change. It
carries the act structure, the slide-by-slide keep / revise / rewrite list, the
blockers, and the asset list. Read it before touching the deck.

**`figures_30to45min/`** holds nine PNGs, `_build_presentation_figures.py` which
regenerates all of them from data on disk, `_manifest.json`, and
`figure_notes_what_each_image_shows.md` which says what each figure shows, which
slide it serves, and where its numbers come from.

Rebuild every figure with:

```
python docs/presentation/figures_30to45min/_build_presentation_figures.py
```

## What is NOT here, and why

**The deck builders stayed in `archive/wellsight/paper/paper/`.** Nine scripts
there reference `WellSight_Presentation.pptx`:

```
_build_presentation.py   _update_slides.py     _modify_pptx_slides.py
_add_notes.py            _add_references.py    _add_feature_table.py
_apply_fixes.py          _rewrite_all_notes.py _update_notes.py
```

They sit alongside the paper builders in the same frozen archive directory and
import from each other, so pulling the presentation half out would split a
working set for filing reasons. They were written against the May deck and have
not been run since. Check that they still run before relying on them.

They open the deck by bare filename, not by path, so they expect to be run from
whatever directory holds the `.pptx`. That is now this one.

**The deck keeps its original filename.** The descriptive-filename rule would
prefer a date in it, but those nine scripts read and write the exact string
`WellSight_Presentation.pptx`. Renaming it buys a better name and costs a silent
breakage the next time one of them runs. Left alone deliberately.

**Reusable figures were not copied here.** The worklist's asset list points at
figures that already live beside the models and data that produced them, for
example `data/9t/models/road/unet_1m_corrected/compare_corrections_full.png`.
Copying them would create duplicates with no clear original. Pull them into the
deck at build time from the paths the worklist names.

"""Refuse to silently reassign spatial-block splits when annotation has grown.

`_build_pit_dataset.py` and `_build_pad_road_dataset.py` rasterize the
CURRENT annotation and write a fresh block/fold assignment every time they
run, with no dry-run mode and no output redirect -- they always overwrite the
canonical manifest under `data/derivatives/tiles/9t/`. Trained CV5 checkpoints
(`pit_unet_cv5`, `pad_unet_cv5`) are fold-assigned against a SPECIFIC
annotation count, frozen at train time. If the manifest is silently
regenerated against a different count later, the block/fold assignment shifts,
and any eval script that recomputes folds from the manifest (every CV5
consumer in `s5_eval` does) scores the existing checkpoints against a split
they were never trained against.

This happened for real on 2026-08-12: a golden-harness test run of
`_build_pit_dataset.py` regenerated `pit_blocks_9t.gpkg` against 655
currently-drawn pits instead of the 527 the deployed checkpoints were trained
against. Caught by diffing against the E: backup; restored. This guard is the
fix, so it cannot happen silently a second time.
"""
from __future__ import annotations

import sys
from pathlib import Path


def check_or_refuse(manifest_path: Path, id_col: str, new_count: int,
                    *, force: bool) -> None:
    """Compare `new_count` (the annotation count about to be written) against
    the row count already on disk at `manifest_path`. Refuse to proceed --
    unless `force` -- if they differ, because that means the block/fold
    assignment is about to change under whatever model was last trained.

    Silent when `manifest_path` does not exist yet: nothing to protect on a
    first run.
    """
    if not manifest_path.exists():
        return
    import pandas as pd
    old_count = len(pd.read_csv(manifest_path))
    if old_count == new_count:
        return
    if force:
        print(f"\n--force: overwriting {manifest_path.name} "
              f"({old_count} -> {new_count} rows). Any checkpoint trained "
              f"against the old split is now scored against a fold "
              f"assignment it never trained on until it is retrained.\n",
              file=sys.stderr)
        return
    msg = (
        f"\nREFUSING TO OVERWRITE {manifest_path.name}\n"
        f"  on disk now      : {old_count} {id_col} rows\n"
        f"  about to write   : {new_count} {id_col} rows\n"
        f"\n"
        f"Regenerating this manifest reassigns the spatial-block train/val/test\n"
        f"split -- and therefore the CV5 fold assignment -- away from whatever a\n"
        f"currently-deployed checkpoint under this tile's model directories was\n"
        f"trained against. Proceeding would silently invalidate the held-out\n"
        f"claim behind every number those checkpoints have produced.\n"
        f"\n"
        f"If this is intended -- annotation genuinely grew and you plan to\n"
        f"retrain everything downstream that depends on this manifest -- rerun\n"
        f"with --force.\n"
    )
    print(msg, file=sys.stderr)
    raise SystemExit(1)

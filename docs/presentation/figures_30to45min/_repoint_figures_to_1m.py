"""Repoint the figure builders from the 0.5 m stack to the 1 m stack.

WHY NOT A BLANKET FIND-AND-REPLACE
----------------------------------
`derived/05/` holds two different kinds of thing, and only one of them has a
1 m twin:

  terrain rasters      dem, dsm, chm, hillshade, lrm_5, lrm_25, openness_pos,
                       openness_neg, roughness_5, slope, tpi_05,
                       rrim_openness, intensity_ground
                       -> rebuilt at 1 m, safe to repoint

  everything else      labels_*, features_*, *_prob_*, *_argmax_*, the dataset
                       manifests, pit_blocks_9t.gpkg, road_chunks_9t.gpkg
                       -> these are model inputs, model OUTPUTS and split
                          bookkeeping. They exist only at the resolution their
                          model ran at. Repointing them would either crash on a
                          missing file or, worse, silently pick up a file that
                          means something different.

So this maps an explicit allow-list of basenames, and refuses to rewrite a
reference whose 1 m target does not exist on disk. Anything it will not touch
is printed, so the gap is visible rather than assumed.

Idempotent: running it twice changes nothing the second time.

Run:
    python docs/presentation/figures_30to45min/_repoint_figures_to_1m.py [--apply]
Without --apply it only reports.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIGDIR = ROOT / "docs/presentation/figures_30to45min"

#: basenames that were rebuilt at 1 m by _build_derivatives.py
TERRAIN = {
    "dem", "dsm", "chm", "hillshade", "slope", "tpi_05",
    "lrm_5", "lrm_25", "openness_pos", "openness_neg",
    "roughness_5", "rrim_openness", "intensity_ground",
    "ground_density_noverlap",
}

#: Two layers change name between the two resolutions.
#:   roughness_11 at 0.5 m is an 11-cell window, i.e. 5.5 m. The 1 m stack's
#:   roughness_5 is a 5-cell window, i.e. 5 m. The repo already treats these as
#:   the same product at the two resolutions.
#:   The directional hillshades do not exist at 1 m -- the builder writes one
#:   hillshade, azimuth 315 altitude 45. Same sun direction as az315_alt25 but a
#:   higher sun, so shadows are softer. Only backdrop figures use these.
RENAME = {
    "roughness_11": "roughness_5",
    "hillshade_az315_alt25": "hillshade",
    "hillshade_az315_alt70": "hillshade",
    "hillshade_az090_alt25": "hillshade",
    "hillshade_az270_alt25": "hillshade",
}

#: <stem>_<area>_05.tif  ->  the three pieces we need
RX = re.compile(r"\b([a-z0-9_]+?)_(9t|613590|mck_[a-z0-9]+)_05\.tif\b")


def target_for(stem: str, area: str) -> tuple[Path, str] | None:
    """The 1 m file this reference should point at, if it exists."""
    stem = RENAME.get(stem, stem)
    if stem not in TERRAIN:
        return None
    p = ROOT / f"data/{area}/derived/1m/{stem}_{area}_1m.tif"
    return (p, stem) if p.exists() else None


def main() -> int:
    apply = "--apply" in sys.argv
    skipped: dict[str, list[str]] = {}
    changed = 0

    for f in sorted(FIGDIR.glob("_*.py")):
        if f.name == Path(__file__).name:
            continue
        src = f.read_text(encoding="utf-8")
        out = src
        hits, misses = [], []

        for m in RX.finditer(src):
            stem, area = m.group(1), m.group(2)
            tgt = target_for(stem, area)
            ref = m.group(0)
            if tgt is None:
                misses.append(ref)
                continue
            _, newstem = tgt
            out = out.replace(ref, f"{newstem}_{area}_1m.tif")
            hits.append(ref if newstem == stem
                        else f"{ref} -> {newstem}_{area}_1m.tif")

        # the directory segment only moves for references we actually rewrote
        if hits:
            for area in ("9t", "613590"):
                out = out.replace(f"data/{area}/derived/05/{{}}", "")  # no-op guard
            out = re.sub(r"derived/05/([a-z0-9_]+_(?:9t|613590)_1m\.tif)",
                         r"derived/1m/\1", out)

        if out != src:
            changed += 1
            print(f"  {f.name}: {len(set(hits))} reference(s) -> 1 m")
            if apply:
                f.write_text(out, encoding="utf-8")
        if misses:
            skipped[f.name] = sorted(set(misses))

    if skipped:
        print("\n  left at 0.5 m (no 1 m twin exists -- model outputs, labels,"
              " split bookkeeping):")
        for name, refs in skipped.items():
            print(f"    {name}")
            for r in refs:
                print(f"      {r}")

    print(f"\n  {changed} script(s) {'updated' if apply else 'would change'}")
    if not apply:
        print("  re-run with --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

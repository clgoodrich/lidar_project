"""Build the multi-angle / multi-altitude hillshade family across every 3x3
block in ``data/derivatives/tiles/data_3x3/``.

Existing baseline (already on disk):
  hillshade_<key>_1m.tif              az=315 alt=45  (the default render)
  hillshade_az135_<key>_1m.tif        az=135 alt=45

New variants this script generates (all altitude=25 except the one alt=70):
  hillshade_az315_alt70_<key>_1m.tif   high sun, NW
  hillshade_az315_alt25_<key>_1m.tif   low sun, NW
  hillshade_az000_alt25_<key>_1m.tif   low sun, N
  hillshade_az090_alt25_<key>_1m.tif   low sun, E
  hillshade_az180_alt25_<key>_1m.tif   low sun, S
  hillshade_az270_alt25_<key>_1m.tif   low sun, W

CLI:
  python notebooks/wellsight/build/_build_hillshade_variants.py
  python notebooks/wellsight/build/_build_hillshade_variants.py --skip-existing
  python notebooks/wellsight/build/_build_hillshade_variants.py --only e1423n2238,604590
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV

ROOT_3X3 = DERIV / "tiles" / "data_3x3"
KEY_RE_WP = re.compile(r"^\d{6}$")
KEY_RE_NC = re.compile(r"^e\d{4}n\d{4}$")

# (azimuth_deg, altitude_deg) — alt=45 baselines already exist on disk.
VARIANTS: list[tuple[int, int]] = [
    (315, 70),
    (315, 25),
    (  0, 25),
    ( 90, 25),
    (180, 25),
    (270, 25),
]


SKIP_PARENTS = {"icp", "candidates", "validation", "model_archive",
                "ramachandran_verifier", "pilot_A", "annotations",
                "chm_age_proxy", "mck_inference"}


def _dem_to_target(dem: Path) -> tuple[str, Path, str]:
    """Derive (sfx, working_dir, dem_filename) from a path like
    .../<work>/dem_<sfx>.tif."""
    stem = dem.stem
    assert stem.startswith("dem_"), dem
    return (stem[len("dem_"):], dem.parent, dem.name)


def discover_targets() -> list[tuple[str, Path, str]]:
    """Return (sfx, working_dir, dem_name) for every real DEM under
    data/derivatives/ -- 3x3 blocks, region mosaics, single tiles, extras.
    Skips ICP change-detection rasters and other non-terrain outputs.
    """
    out = []
    # 1) data_3x3 blocks
    if ROOT_3X3.exists():
        for region_dir in sorted(p for p in ROOT_3X3.iterdir() if p.is_dir()):
            for sub in sorted(p for p in region_dir.iterdir() if p.is_dir()):
                key = sub.name
                if not (KEY_RE_WP.match(key) or KEY_RE_NC.match(key)):
                    continue
                dem = sub / f"dem_{key}_1m.tif"
                if dem.exists():
                    # Use the DEM-derived helper so the key is consistent
                    # with the rglob branch (e.g. "604590_1m", not "604590").
                    out.append(_dem_to_target(dem))
                    continue
    # 2) Any other dem_*.tif under data/derivatives/, walking up to 3 levels
    deriv = ROOT_3X3.parent
    seen = {t[1].resolve() / t[2] for t in out}
    for dem in deriv.rglob("dem_*.tif"):
        # depth filter to avoid descending into weird trees
        try:
            rel = dem.relative_to(deriv)
        except ValueError:
            continue
        if any(part in SKIP_PARENTS for part in rel.parts):
            continue
        # exclude demo/test fixtures and ICP outputs
        if "demo" in dem.stem.lower() or "_diff_" in dem.stem.lower():
            continue
        if dem.resolve() in seen:
            continue
        out.append(_dem_to_target(dem))
        seen.add(dem.resolve())
    return out


def main() -> int:
    import whitebox
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", help="comma-separated key filter")
    args = ap.parse_args()

    keys = set(args.only.split(",")) if args.only else None
    targets = discover_targets()
    if keys:
        targets = [t for t in targets if t[0] in keys]
    if not targets:
        print("no blocks found", file=sys.stderr); return 1

    print(f"{len(targets)} block(s) x {len(VARIANTS)} variants = "
          f"{len(targets) * len(VARIANTS)} hillshades total")

    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    ok = skip = err = 0
    for key, work, dem_name in targets:
        wbt.set_working_dir(str(work.resolve()))
        for az, alt in VARIANTS:
            # `key` already encodes resolution (e.g. "604590_1m", "9t_05",
            # "sw_marcellus_1m") -- do NOT append _1m again.
            out_name = f"hillshade_az{az:03d}_alt{alt}_{key}.tif"
            if args.skip_existing and (work / out_name).exists():
                skip += 1; continue
            rc = wbt.hillshade(dem=dem_name, output=out_name,
                               azimuth=float(az), altitude=float(alt))
            if rc != 0:
                err += 1; print(f"[{key}] az={az:3d} alt={alt:2d} FAILED rc={rc}")
            else:
                ok += 1
        print(f"[{key}] +{len(VARIANTS)} variants")

    print(f"\ndone: ok={ok} skip={skip} err={err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

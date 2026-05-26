"""Generate az=135 hillshades for every existing 1 m DEM in our 3x3 build dirs.

Existing hillshades use azimuth=315 (NW illumination). This script adds a
complementary azimuth=135 (SE illumination) hillshade alongside each DEM, so
edges that face away from NW (and disappear in the standard render) become
visible. Altitude stays at 45 to match the existing convention.

Targets (auto-discovered, but constrained to DEMs we built ourselves):
  - data/derivatives/mosaic_3x3/<key>/dem_1m.tif
        -> hillshade_az135_1m.tif
  - data/derivatives/mosaic_3x3_mckean/<key>/dem_1m.tif
        -> hillshade_az135_1m.tif
  - data/derivatives/<sfx>/dem_<sfx>.tif   (sw_marcellus_1m, nec_marcellus_1m, wc_coaloil_1m)
        -> hillshade_az135_<sfx>.tif

CLI:
  python notebooks/wellsight/build/_build_hillshade_az135.py
  python notebooks/wellsight/build/_build_hillshade_az135.py --skip-existing
  python notebooks/wellsight/build/_build_hillshade_az135.py --only 604590,e1423n2238
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV

AZIMUTH = 135.0
ALTITUDE = 45.0

REGION_DIRS = ("sw_marcellus_1m", "nec_marcellus_1m", "wc_coaloil_1m")


def discover_targets() -> list[tuple[str, Path, str, str]]:
    """Return (key, working_dir, dem_name, hs_name) tuples for each DEM."""
    targets: list[tuple[str, Path, str, str]] = []

    for parent in (DERIV / "mosaic_3x3", DERIV / "mosaic_3x3_mckean"):
        if not parent.exists():
            continue
        for sub in sorted(p for p in parent.iterdir() if p.is_dir()):
            key = sub.name
            # New layout: dem_<key>_1m.tif; legacy: dem_1m.tif.
            for dem_name in (f"dem_{key}_1m.tif", "dem_1m.tif"):
                if (sub / dem_name).exists():
                    hs_name = (f"hillshade_az135_{key}_1m.tif"
                               if dem_name.startswith(f"dem_{key}")
                               else "hillshade_az135_1m.tif")
                    targets.append((key, sub, dem_name, hs_name))
                    break

    for sfx in REGION_DIRS:
        sub = DERIV / sfx
        dem = sub / f"dem_{sfx}.tif"
        if dem.exists():
            targets.append((sfx, sub, f"dem_{sfx}.tif", f"hillshade_az135_{sfx}.tif"))

    return targets


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
        print("no DEMs found", file=sys.stderr)
        return 1

    print(f"az=135 hillshade pass over {len(targets)} DEM(s)")
    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)

    ok = skip = err = 0
    for key, work, dem_name, hs_name in targets:
        out_path = work / hs_name
        if args.skip_existing and out_path.exists():
            print(f"[{key}] skip (exists)")
            skip += 1
            continue
        wbt.set_working_dir(str(work.resolve()))
        rc = wbt.hillshade(dem=dem_name, output=hs_name,
                           azimuth=AZIMUTH, altitude=ALTITUDE)
        if rc != 0:
            print(f"[{key}] FAILED rc={rc}")
            err += 1
            continue
        print(f"[{key}] ok -> {out_path.name}")
        ok += 1

    print(f"\ndone: ok={ok} skip={skip} err={err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

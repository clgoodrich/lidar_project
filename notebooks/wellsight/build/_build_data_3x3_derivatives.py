"""Build the full WellSight derivative stack for every 3x3 block under
``data/derivatives/data_3x3/``.

Two regions are handled:
  westernpa_d20    -> data/files/USGS_LPC_PA_WesternPA_2019_D20_17T<band><e><n>.laz
                       (irregular F/G band scheme; reuse the existing
                       enumerator from _build_3x3_hillshades.py)
  northcentral_b19 -> data/mckean/USGS_LPC_PA_Northcentral_2019_B19_e<E>n<N>.laz
                       (regular 4-digit integer grid; compute directly)

For each block we read the UTM 17N bbox from the existing dem_<key>_1m.tif,
gather the 9 source LAZ tiles, and call _build_derivatives.build() with
out_dir = data/derivatives/data_3x3/<region>/<key>/ and suffix = <key>_1m.
Already-present outputs (DEM, hillshade) are skipped.

CLI:
  python notebooks/wellsight/build/_build_data_3x3_derivatives.py
  python notebooks/wellsight/build/_build_data_3x3_derivatives.py --only 604590,e1423n2238
  python notebooks/wellsight/build/_build_data_3x3_derivatives.py --regions westernpa_d20
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV, DST_CRS, ROOT
from _build_derivatives import build as build_derivatives  # type: ignore
from _build_3x3_hillshades import discover_tiles as discover_wp, enumerate_blocks as enumerate_wp_blocks  # type: ignore

ROOT_3X3 = DERIV / "data_3x3"
NC_RE = re.compile(r"^e(\d{4})n(\d{4})$")
NC_SRC_DIR = ROOT / "data" / "mckean"
NC_SRC_CRS = "EPSG:6350"


def wp_members_by_key() -> dict[str, list[Path]]:
    """Map WesternPA block key -> 9 source LAZ paths via existing enumerator."""
    tiles = discover_wp()
    blocks = enumerate_wp_blocks(tiles)
    return {b["key"]: list(b["members"]) for b in blocks}


def nc_members_for(key: str) -> list[Path]:
    m = NC_RE.match(key)
    if not m:
        raise ValueError(f"bad northcentral key: {key}")
    e0, n0 = int(m.group(1)), int(m.group(2))
    paths = []
    for de in range(3):
        for dn in range(3):
            p = NC_SRC_DIR / f"USGS_LPC_PA_Northcentral_2019_B19_e{e0+de}n{n0+dn}.laz"
            if not p.exists():
                raise FileNotFoundError(p)
            paths.append(p)
    return paths


def bbox_from_dem(dem_path: Path) -> tuple[float, float, float, float]:
    with rasterio.open(dem_path) as r:
        b = r.bounds
    return (b.left, b.bottom, b.right, b.top)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated block keys")
    ap.add_argument("--regions", help="comma-separated region subset")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    only_keys = set(args.only.split(",")) if args.only else None
    only_regions = set(args.regions.split(",")) if args.regions else None

    wp_lookup = wp_members_by_key()
    jobs = []
    for region in ("westernpa_d20", "northcentral_b19"):
        if only_regions and region not in only_regions:
            continue
        parent = ROOT_3X3 / region
        if not parent.exists():
            continue
        for sub in sorted(p for p in parent.iterdir() if p.is_dir()):
            key = sub.name
            if only_keys and key not in only_keys:
                continue
            dem = sub / f"dem_{key}_1m.tif"
            if not dem.exists():
                print(f"[{region}/{key}] no DEM, skipping"); continue
            try:
                if region == "westernpa_d20":
                    members = wp_lookup.get(key)
                    if not members:
                        print(f"[{region}/{key}] enumerator returned no members"); continue
                    src_crs = None
                else:
                    members = nc_members_for(key)
                    src_crs = NC_SRC_CRS
            except (ValueError, FileNotFoundError) as e:
                print(f"[{region}/{key}] {e}"); continue
            jobs.append((region, key, sub, dem, members, src_crs))

    if not jobs:
        print("no jobs", file=sys.stderr); return 1
    print(f"will process {len(jobs)} block(s):")
    for region, key, *_ in jobs:
        print(f"  {region}/{key}")

    t_total = time.time()
    for region, key, out_dir, dem_path, members, src_crs in jobs:
        sfx = f"{key}_1m"
        merge_path = ROOT / "data" / "files" / f"_merged_{region}_{sfx}.las"
        x0, y0, x1, y1 = bbox_from_dem(dem_path)
        print(f"\n========== {region}/{key} ==========")
        print(f"  bbox: {x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}  ({(x1-x0):.0f}x{(y1-y0):.0f} m)")
        t0 = time.time()
        try:
            build_derivatives(
                members, x0=x0, y0=y0, x1=x1, y1=y1,
                res=1.0, sfx=sfx, dst_crs=DST_CRS,
                src_crs=src_crs, merge_path=merge_path,
                skip_existing=(not args.overwrite),
                out_dir=out_dir,
            )
        except Exception as e:
            print(f"  [{region}/{key}] FAILED: {e}")
            continue
        print(f"  [{region}/{key}] done in {time.time()-t0:.1f}s")
        if merge_path.exists():
            sz = merge_path.stat().st_size / 1e9
            try:
                merge_path.unlink()
                print(f"  removed merge intermediate ({sz:.1f} GB)")
            except OSError:
                pass

    print(f"\nALL DONE in {(time.time()-t_total)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())

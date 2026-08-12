"""Build 1 m DEM + hillshade for non-overlapping 3x3 mosaics in data/source_laz/mckean/.

Source: ``USGS_LPC_PA_Northcentral_2019_B19`` (EPSG:6350, NAD83(2011) Conus
Albers, metres). Tile naming ``..._e<E>n<N>.laz`` with the SW corner at
``(E*1000, N*1000)`` in Albers metres and a 1000 m tile side. We reproject to
EPSG:6346 (UTM 17N) inside the PDAL pipeline so outputs sit on the same grid
as the existing mkf/mk5/9t derivatives.

Block selection: enumerate every complete 3x3 sliding window, then greedy
non-overlapping pick (SW-first).

Outputs go to ``data/derivatives/tiles/mosaic_3x3_mckean/<key>/`` where ``<key>`` is
the SW tile code (e.g. ``e1423n2235``).
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DST_CRS, ROOT, run_pdal

SRC_DIR = ROOT / "data" / "source_laz" / "mckean"
OUT_ROOT = ROOT / "data" / "derivatives" / "mosaic_3x3_mckean"
RES = 1.0
TILE_M = 1000.0
SRC_CRS = "EPSG:6350"

FNAME_RE = re.compile(r"^USGS_LPC_PA_Northcentral_2019_B19_e(\d{4})n(\d{4})\.laz$")


def discover_tiles() -> dict[tuple[int, int], Path]:
    out: dict[tuple[int, int], Path] = {}
    for p in sorted(SRC_DIR.glob("USGS_LPC_PA_Northcentral_2019_B19_*.laz")):
        m = FNAME_RE.match(p.name)
        if m is not None:
            out[(int(m.group(1)), int(m.group(2)))] = p
    return out


def find_blocks(grid: dict) -> list[tuple[int, int]]:
    """Enumerate complete 3x3 windows then greedy non-overlapping pick."""
    es = sorted({e for e, _ in grid}); ns = sorted({n for _, n in grid})
    windows: list[tuple[int, int]] = []
    for e0 in range(min(es), max(es) - 1):
        for n0 in range(min(ns), max(ns) - 1):
            if all((e0 + de, n0 + dn) in grid for de in range(3) for dn in range(3)):
                windows.append((e0, n0))
    chosen: list[tuple[int, int]] = []
    used: set[tuple[int, int]] = set()
    for w in sorted(windows, key=lambda w: (w[1], w[0])):
        e0, n0 = w
        block = {(e0 + de, n0 + dn) for de in range(3) for dn in range(3)}
        if not (block & used):
            chosen.append(w); used |= block
    return chosen


def utm_bbox_from_albers(ax0: float, ay0: float, ax1: float, ay1: float):
    """Tight UTM 17N bbox enclosing an axis-aligned Albers rectangle."""
    t = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)
    corners = [t.transform(x, y) for x in (ax0, ax1) for y in (ay0, ay1)]
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    return (math.floor(min(xs) / RES) * RES,
            math.floor(min(ys) / RES) * RES,
            math.ceil(max(xs) / RES) * RES,
            math.ceil(max(ys) / RES) * RES)


def build_block(b, *, skip_existing: bool) -> None:
    import whitebox
    out_dir = OUT_ROOT / b["key"]
    dem_name = f"dem_{b['key']}_1m.tif"
    hs_name = f"hillshade_{b['key']}_1m.tif"
    dem_tif = out_dir / dem_name
    hs_tif = out_dir / hs_name
    if skip_existing and dem_tif.exists() and hs_tif.exists():
        print(f"[{b['key']}] skip (outputs exist)")
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    ux0, uy0, ux1, uy1 = b["utm"]
    W = int(round((ux1 - ux0) / RES))
    H = int(round((uy1 - uy0) / RES))
    stages = [
        *[str(p) for p in b["members"]],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "in_srs": SRC_CRS, "out_srs": DST_CRS},
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster",
         "resolution": RES, "origin_x": ux0, "origin_y": uy0, "width": W, "height": H},
        {"type": "writers.raster", "filename": str(dem_tif), "data_type": "float32"},
    ]
    print(f"[{b['key']}] DEM ({W}x{H}) from 9 Albers tiles -> UTM ...")
    run_pdal(stages, label=f"dem_{b['key']}", tmp_dir=out_dir, timeout=3600)

    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(out_dir.resolve()))
    wbt.set_verbose_mode(False)
    rc = wbt.hillshade(dem=dem_name, output=hs_name,
                       azimuth=315.0, altitude=45.0)
    if rc != 0:
        print(f"[{b['key']}] WBT hillshade FAILED rc={rc}")
        return
    print(f"[{b['key']}] hillshade ok -> {hs_tif}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--list", action="store_true", help="enumerate and exit")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", help="comma-separated SW keys like e1423n2235")
    args = ap.parse_args()

    tiles = discover_tiles()
    if not tiles:
        print("no PA Northcentral LAZ tiles in data/source_laz/mckean/", file=sys.stderr)
        return 1
    print(f"discovered {len(tiles)} PA Northcentral LAZ tiles")

    blocks = []
    for e0, n0 in find_blocks(tiles):
        members = [tiles[(e0 + de, n0 + dn)] for de in range(3) for dn in range(3)]
        ax0, ay0 = e0 * 1000.0, n0 * 1000.0
        blocks.append({
            "key": f"e{e0}n{n0}",
            "members": members,
            "albers": (ax0, ay0, ax0 + 3 * TILE_M, ay0 + 3 * TILE_M),
            "utm": utm_bbox_from_albers(ax0, ay0, ax0 + 3 * TILE_M, ay0 + 3 * TILE_M),
        })

    print(f"complete 3x3 blocks: {len(blocks)}")
    for b in blocks:
        ux0, uy0, ux1, uy1 = b["utm"]
        print(f"  {b['key']}  UTM17N X[{ux0:.0f}..{ux1:.0f}] Y[{uy0:.0f}..{uy1:.0f}]")

    if args.list:
        return 0
    if args.only:
        keep = set(args.only.split(","))
        blocks = [b for b in blocks if b["key"] in keep]
    if args.pilot:
        blocks = blocks[:1]
        print(f"--pilot: running {blocks[0]['key'] if blocks else 'none'}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for b in blocks:
        try:
            build_block(b, skip_existing=args.skip_existing)
        except Exception as e:
            print(f"[{b['key']}] FAILED: {e}")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

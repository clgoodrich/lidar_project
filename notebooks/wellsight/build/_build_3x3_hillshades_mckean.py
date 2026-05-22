"""Build 1 m DEM + hillshade for every non-overlapping 3x3 mosaic in the
PA Northcentral 2019 B19 McKean LAZ set (data/mckean/).

Source CRS: EPSG:6350 (NAD83(2011) Conus Albers, metres). Tile naming:
..._e<E>n<N>.laz where (E*1000, N*1000) is the SW corner in Albers metres and
each tile is 1000 m on a side. We reproject to EPSG:6346 (UTM 17N) on the fly
inside the PDAL pipeline, so all McKean outputs sit on the same grid as the
existing mkf/mk5/9t derivatives.

Block selection: enumerate every complete 3x3 sliding window across the
discovered grid, then greedy non-overlapping pick (SW-first). For this
upload that yields 4 blocks.

Outputs go to data/derivatives/mosaic_3x3_mckean/<key>/ where <key> is the SW
tile code (e.g. e1423n2235). Files: dem_1m.tif, hillshade_1m.tif.

CLI:
  python notebooks/wellsight/build/_build_3x3_hillshades_mckean.py            # all complete blocks
  python notebooks/wellsight/build/_build_3x3_hillshades_mckean.py --pilot    # first complete block only
  python notebooks/wellsight/build/_build_3x3_hillshades_mckean.py --list     # enumerate, no work
  python notebooks/wellsight/build/_build_3x3_hillshades_mckean.py --skip-existing
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, time
from pathlib import Path
from pyproj import Transformer

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
SRC_DIR = ROOT / "data" / "mckean"
OUT_ROOT = ROOT / "data" / "derivatives" / "mosaic_3x3_mckean"
PDAL_EXE = shutil.which("pdal") or "pdal"
RES = 1.0
TILE_M = 1000.0
SRC_CRS = "EPSG:6350"
DST_CRS = "EPSG:6346"

FNAME_RE = re.compile(
    r"^USGS_LPC_PA_Northcentral_2019_B19_e(?P<e>\d{4})n(?P<n>\d{4})\.laz$"
)


def discover_tiles():
    found = {}
    for p in sorted(SRC_DIR.glob("USGS_LPC_PA_Northcentral_2019_B19_*.laz")):
        m = FNAME_RE.match(p.name)
        if not m:
            continue
        found[(int(m["e"]), int(m["n"]))] = p
    return found


def find_blocks(grid: dict):
    es = sorted({e for e, _ in grid})
    ns = sorted({n for _, n in grid})
    # Complete 3x3 sliding windows
    windows = []
    for e0 in range(min(es), max(es) - 1):
        for n0 in range(min(ns), max(ns) - 1):
            if all((e0 + de, n0 + dn) in grid for de in range(3) for dn in range(3)):
                windows.append((e0, n0))
    # Greedy non-overlapping
    chosen = []
    used = set()
    for w in sorted(windows, key=lambda w: (w[1], w[0])):
        e0, n0 = w
        block = {(e0 + de, n0 + dn) for de in range(3) for dn in range(3)}
        if not (block & used):
            chosen.append(w)
            used |= block
    return chosen


def utm_bbox_from_albers(ax0, ay0, ax1, ay1):
    """Tight UTM 17N bbox enclosing an axis-aligned Albers rectangle."""
    t = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)
    corners = [t.transform(x, y) for x in (ax0, ax1) for y in (ay0, ay1)]
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    import math
    x0 = math.floor(min(xs) / RES) * RES
    y0 = math.floor(min(ys) / RES) * RES
    x1 = math.ceil(max(xs) / RES) * RES
    y1 = math.ceil(max(ys) / RES) * RES
    return x0, y0, x1, y1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="only first block")
    ap.add_argument("--list", action="store_true", help="enumerate blocks and exit")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", help="comma-separated SW keys like e1423n2235")
    args = ap.parse_args()

    tiles = discover_tiles()
    if not tiles:
        print("no PA Northcentral LAZ tiles found in data/mckean/", file=sys.stderr)
        return 1
    print(f"discovered {len(tiles)} PA Northcentral LAZ tiles")

    blocks = find_blocks(tiles)
    out = []
    for e0, n0 in blocks:
        members = [tiles[(e0 + de, n0 + dn)] for de in range(3) for dn in range(3)]
        ax0 = e0 * 1000.0
        ay0 = n0 * 1000.0
        ax1 = ax0 + 3 * TILE_M
        ay1 = ay0 + 3 * TILE_M
        ux0, uy0, ux1, uy1 = utm_bbox_from_albers(ax0, ay0, ax1, ay1)
        key = f"e{e0}n{n0}"
        out.append({"key": key, "members": members,
                    "albers": (ax0, ay0, ax1, ay1),
                    "utm": (ux0, uy0, ux1, uy1)})

    print(f"complete 3x3 blocks: {len(out)}")
    for b in out:
        ux0, uy0, ux1, uy1 = b["utm"]
        print(f"  {b['key']}  UTM17N X[{ux0:.0f}..{ux1:.0f}] Y[{uy0:.0f}..{uy1:.0f}]")

    if args.list:
        return 0

    if args.only:
        keep = set(args.only.split(","))
        out = [b for b in out if b["key"] in keep]
    if args.pilot:
        out = out[:1]
        print(f"--pilot: running {out[0]['key'] if out else 'none'}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    import whitebox

    for b in out:
        out_dir = OUT_ROOT / b["key"]
        dem_tif = out_dir / "dem_1m.tif"
        hs_tif = out_dir / "hillshade_1m.tif"
        if args.skip_existing and dem_tif.exists() and hs_tif.exists():
            print(f"[{b['key']}] skip (outputs exist)")
            continue
        out_dir.mkdir(exist_ok=True)

        ux0, uy0, ux1, uy1 = b["utm"]
        W = int(round((ux1 - ux0) / RES))
        H = int(round((uy1 - uy0) / RES))

        pipeline = {"pipeline": [
            *[str(p) for p in b["members"]],
            {"type": "filters.merge"},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "filters.reprojection",
             "in_srs": SRC_CRS, "out_srs": DST_CRS},
            {"type": "filters.delaunay"},
            {"type": "filters.faceraster",
             "resolution": RES, "origin_x": ux0, "origin_y": uy0,
             "width": W, "height": H},
            {"type": "writers.raster",
             "filename": str(dem_tif), "data_type": "float32"},
        ]}
        tmp = out_dir / "_tmp_dem_pipeline.json"
        tmp.write_text(json.dumps(pipeline, indent=2))

        print(f"[{b['key']}] DEM ({W}x{H}) from 9 Albers tiles -> UTM ...")
        t0 = time.time()
        r = subprocess.run([PDAL_EXE, "pipeline", str(tmp)],
                           capture_output=True, text=True, timeout=3600)
        if r.returncode != 0:
            print(f"[{b['key']}] PDAL FAILED rc={r.returncode}")
            print(r.stderr[-2000:])
            continue
        print(f"[{b['key']}] DEM ok in {time.time()-t0:.1f}s")
        tmp.unlink(missing_ok=True)

        wbt = whitebox.WhiteboxTools()
        wbt.set_working_dir(str(out_dir.resolve()))
        wbt.set_verbose_mode(False)
        rc = wbt.hillshade(dem="dem_1m.tif", output="hillshade_1m.tif",
                           azimuth=315.0, altitude=45.0)
        if rc != 0:
            print(f"[{b['key']}] WBT hillshade FAILED rc={rc}")
            continue
        print(f"[{b['key']}] hillshade ok -> {hs_tif}")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

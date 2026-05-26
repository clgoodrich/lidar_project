"""Build 1 m DEM + hillshade for every non-overlapping 3x3 mosaic in data/files/.

Source: ``USGS_LPC_PA_WesternPA_2019_D20`` (EPSG:6346, UTM 17N). Each LAZ tile
is 1500 m on a side and named ``..._17TP<F|G><E><N>.laz`` where ``E``/``N`` are
3-digit codes whose UTM start is recovered from the sorted-code index (every
tile = +1500 m).

For every complete 3x3 block of present tiles aligned to the SW corner of the
discovered grid, one PDAL pipeline reads 9 LAZs -> merges -> keeps
Classification=2 (ground) -> delaunay -> faceraster (DEM). WhiteboxTools then
renders the hillshade.

Outputs go to ``data/derivatives/mosaic_3x3/<key>/`` where ``<key>`` is the SW
tile code (e.g. 604590). Files: ``dem_1m.tif``, ``hillshade_1m.tif``.

CLI:
  python notebooks/wellsight/build/_build_3x3_hillshades.py [--pilot|--list|--skip-existing]
  python notebooks/wellsight/build/_build_3x3_hillshades.py --only 619593,604590
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DST_CRS, ROOT, run_pdal

SRC_DIR = ROOT / "data" / "files"
OUT_ROOT = ROOT / "data" / "derivatives" / "mosaic_3x3"
RES = 1.0
TILE_M = 1500.0

FNAME_RE = re.compile(
    r"^USGS_LPC_PA_WesternPA_2019_D20_17TP(?P<band>[FG])(?P<e>\d{3})(?P<n>\d{3})\.laz$"
)

# Anchor: tile code "619" -> 619500 m E; ("F", "593") -> 4593000 m N.
ANCHOR_E_CODE = "619"; ANCHOR_E_UTM = 619500.0
ANCHOR_N_BAND = "F"; ANCHOR_N_CODE = "593"; ANCHOR_N_UTM = 4593000.0


def discover_tiles() -> dict[tuple[str, str, str], Path]:
    """Return {(band, e_code, n_code): path} for plain .laz only."""
    out: dict[tuple[str, str, str], Path] = {}
    for p in sorted(SRC_DIR.glob("USGS_LPC_PA_WesternPA_2019_D20_17T*.laz")):
        if ".copc." in p.name:
            continue
        m = FNAME_RE.match(p.name)
        if m is not None:
            out[(m["band"], m["e"], m["n"])] = p
    return out


def build_indices(tiles):
    """Map e- and (band,n)-codes to monotonic axis indices."""
    e_codes = sorted({k[1] for k in tiles})
    n_codes_f = sorted({k[2] for k in tiles if k[0] == "F"})
    n_codes_g = sorted({k[2] for k in tiles if k[0] == "G"})
    e_idx = {c: i for i, c in enumerate(e_codes)}
    n_idx: dict[tuple[str, str], int] = {("F", c): i for i, c in enumerate(n_codes_f)}
    n_idx.update({("G", c): len(n_codes_f) + i for i, c in enumerate(n_codes_g)})
    return e_idx, n_idx


def axis_origins(e_idx, n_idx) -> tuple[float, float]:
    if ANCHOR_E_CODE not in e_idx:
        raise SystemExit(f"calibration tile code {ANCHOR_E_CODE!r} not in dataset")
    if (ANCHOR_N_BAND, ANCHOR_N_CODE) not in n_idx:
        raise SystemExit("calibration tile (F,593) missing — can't anchor northing")
    return (ANCHOR_E_UTM - e_idx[ANCHOR_E_CODE] * TILE_M,
            ANCHOR_N_UTM - n_idx[(ANCHOR_N_BAND, ANCHOR_N_CODE)] * TILE_M)


def enumerate_blocks(tiles):
    e_idx, n_idx = build_indices(tiles)
    e_origin, n_origin = axis_origins(e_idx, n_idx)
    grid = {(e_idx[e], n_idx[(b, n)]): (b, e, n, p) for (b, e, n), p in tiles.items()}
    if not grid:
        return []
    max_ei = max(k[0] for k in grid); max_ni = max(k[1] for k in grid)
    blocks = []
    for ei0 in range(0, max_ei + 1, 3):
        for ni0 in range(0, max_ni + 1, 3):
            members = [grid.get((ei0 + de, ni0 + dn))
                       for de in range(3) for dn in range(3)]
            if all(m is not None for m in members):
                sw = members[0]
                x0 = e_origin + ei0 * TILE_M
                y0 = n_origin + ni0 * TILE_M
                blocks.append({
                    "key": f"{sw[1]}{sw[2]}",
                    "members": [m[3] for m in members],
                    "x0": x0, "y0": y0,
                    "x1": x0 + 3 * TILE_M, "y1": y0 + 3 * TILE_M,
                })
    blocks.sort(key=lambda b: (b["y0"], b["x0"]))
    return blocks


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

    W = int(round((b["x1"] - b["x0"]) / RES))
    H = int(round((b["y1"] - b["y0"]) / RES))
    stages = [
        *[str(p) for p in b["members"]],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster",
         "resolution": RES, "origin_x": b["x0"], "origin_y": b["y0"],
         "width": W, "height": H},
        {"type": "writers.raster",
         "filename": str(dem_tif), "data_type": "float32"},
    ]
    print(f"[{b['key']}] DEM ({W}x{H}) from {len(b['members'])} tiles ...")
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
    ap.add_argument("--list", action="store_true", help="enumerate blocks and exit")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", help="comma-separated SW tile keys (e.g. 619593,604590)")
    args = ap.parse_args()

    tiles = discover_tiles()
    if not tiles:
        print("no LAZ tiles in data/files/", file=sys.stderr)
        return 1
    print(f"discovered {len(tiles)} LAZ tiles")

    blocks = enumerate_blocks(tiles)
    print(f"complete 3x3 blocks: {len(blocks)}")
    for b in blocks:
        print(f"  {b['key']}  x={b['x0']:.0f}..{b['x1']:.0f}  y={b['y0']:.0f}..{b['y1']:.0f}")

    if args.list:
        return 0
    if args.only:
        keep = set(args.only.split(","))
        blocks = [b for b in blocks if b["key"] in keep]
        print(f"--only filter: {len(blocks)} block(s)")
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

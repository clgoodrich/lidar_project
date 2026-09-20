"""Cut small clips of the heavy rasters, so nothing has to open 14.5 GB.

WHY
---
Every presentation figure draws a 120-400 m window, and every one of them opens
a full 9000x9000 raster to do it. The 9t and 613590 derivative stacks alone are
14.5 GB across 53 files, and a single figure rebuild reads several of them. That
is what makes a figure pass take tens of minutes instead of seconds.

A 300 m window at 0.5 m is 600x600 cells. Clipped and deflate-compressed, the
whole seven-band stack for one window is under a megabyte. Same numbers, same
grid, same CRS -- just the part anyone actually looks at.

WHAT IT GUARANTEES
------------------
Clips are cut with rasterio's windowed read on the source transform, so a clip
is pixel-aligned with its parent: cell centres, CRS and nodata are carried over
unchanged, and a clip of the DEM lines up exactly with a clip of the slope. No
resampling happens at any point. That matters because these feed figures that
overlay one product on another.

Out of range is not an error. A window that falls outside a raster's footprint
is skipped and reported, rather than writing a tile of nodata that looks real.

NAMING follows the descriptive-filename rule: what it is, where it is, how big
the window is, and the resolution, e.g.

    dem_9t_scanlinedropout_120m_0p5m.tif

Clips live beside their parent in a `clips/` directory, which is gitignored --
they are regenerable in seconds by re-running this.

Run:
    python tools/make_raster_clips.py --list
    python tools/make_raster_clips.py                     # every AOI
    python tools/make_raster_clips.py --aoi scanlinedropout
    python tools/make_raster_clips.py --aoi panel300 --dry-run
"""
from __future__ import annotations

import argparse
from pathlib import Path

import rasterio
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[1]

#: name -> (easting, northing, side_m, what it is for). EPSG:6346 throughout.
AOIS = {
    "panel300": (621359.6, 4594467.4, 300.0,
                 "the terrain-derivative panels, slides 19-29"),
    "scanlinedropout": (621392.0, 4594510.0, 120.0,
                        "the CHM NoData bands and the 3D viewer"),
    "rimfloor240": (622025.0, 4595475.0, 240.0,
                    "the rim/floor pairing corner, slide 37"),
    "crosssection300": (622025.0, 4595475.0, 300.0,
                        "the before/after ground cross-section, slide 17"),
    "prob400_9t": (621359.6, 4594467.4, 400.0,
                   "RRIM against probability, slides 46-49"),
    "prob400_613590": (615200.0, 4592825.0, 400.0,
                       "RRIM against probability on 613590, slides 50-53"),
}

#: Directories whose rasters are worth clipping, and the areas they belong to.
SOURCES = [
    ("data/9t/derived/05", ("panel300", "scanlinedropout", "rimfloor240",
                            "crosssection300", "prob400_9t")),
    ("data/9t/derived/smrf05", ("panel300", "crosssection300")),
    ("data/9t/results/recovered_ground_9t", ("panel300", "crosssection300")),
    ("data/613590/derived/inference_05", ("prob400_613590",)),
    ("data/613590/derived/05", ("prob400_613590",)),
]

MIN_MB = 8.0          # below this a clip saves nothing worth the clutter


def res_tag(res: float) -> str:
    return f"{res:g}".replace(".", "p") + "m"


def clip_one(src: Path, out_dir: Path, name: str, cx: float, cy: float,
             side: float, dry: bool) -> tuple[str, str]:
    with rasterio.open(src) as r:
        h = side / 2.0
        b = (cx - h, cy - h, cx + h, cy + h)
        rb = r.bounds
        if (b[2] <= rb.left or b[0] >= rb.right
                or b[3] <= rb.bottom or b[1] >= rb.top):
            return "outside", ""
        win = from_bounds(*b, transform=r.transform).round_offsets().round_lengths()
        # clamp to the raster, so a window overhanging an edge still yields the
        # part that exists rather than a band of invented nodata
        col_off = max(0, int(win.col_off))
        row_off = max(0, int(win.row_off))
        width = min(int(win.width), r.width - col_off)
        height = min(int(win.height), r.height - row_off)
        if width <= 0 or height <= 0:
            return "outside", ""
        win = Window(col_off, row_off, width, height)

        stem = src.stem
        out = out_dir / f"{stem}_{name}_{side:.0f}m_{res_tag(r.res[0])}.tif"
        if dry:
            return "would write", str(out)

        prof = r.profile.copy()
        prof.update(width=width, height=height,
                    transform=r.window_transform(win),
                    compress="deflate", predictor=2, tiled=True,
                    blockxsize=256, blockysize=256)
        prof.pop("nbits", None)
        out_dir.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out, "w", **prof) as d:
            d.write(r.read(window=win))
            if r.descriptions and any(r.descriptions):
                d.descriptions = r.descriptions
        return "wrote", str(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aoi", nargs="*", default=None)
    ap.add_argument("--min-mb", type=float, default=MIN_MB)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        print("areas of interest (EPSG:6346):")
        for k, (x, y, s, why) in AOIS.items():
            print(f"  {k:18s} {x:.1f} E {y:.1f} N   {s:.0f} m   {why}")
        return 0

    want = set(a.aoi) if a.aoi else set(AOIS)
    bad = want - set(AOIS)
    if bad:
        print(f"unknown aoi: {sorted(bad)}")
        return 1

    n_in = n_out = 0
    bytes_in = bytes_out = 0
    for rel, aoi_names in SOURCES:
        d = ROOT / rel
        if not d.is_dir():
            print(f"skip (missing) {rel}")
            continue
        srcs = [p for p in sorted(d.glob("*.tif"))
                if p.stat().st_size / 1e6 >= a.min_mb]
        if not srcs:
            continue
        print(f"\n{rel}   {len(srcs)} rasters over {a.min_mb:g} MB")
        for name in aoi_names:
            if name not in want:
                continue
            cx, cy, side, _ = AOIS[name]
            wrote = 0
            for s in srcs:
                status, out = clip_one(s, d / "clips", name, cx, cy, side,
                                       a.dry_run)
                if status == "outside":
                    continue
                n_in += 1
                bytes_in += s.stat().st_size
                if status == "wrote":
                    n_out += 1
                    bytes_out += Path(out).stat().st_size
                wrote += 1
            print(f"  {name:18s} {wrote:3d} clips")

    if n_in:
        print(f"\n{n_out} clips written from {n_in} source reads")
        print(f"  sources touched  {bytes_in/1e9:7.2f} GB")
        print(f"  clips on disk    {bytes_out/1e6:7.1f} MB"
              f"   ({bytes_in / max(bytes_out, 1):,.0f}x smaller)")
        print(f"\nclips live in <source dir>/clips/ and are gitignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

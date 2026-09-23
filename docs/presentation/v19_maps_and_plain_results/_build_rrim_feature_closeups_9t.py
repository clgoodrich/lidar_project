# -*- coding: utf-8 -*-
"""RRIM close-ups of pits, pads and roads on 9t, with nothing drawn on them.

WHY
---
After presenting v18 the ask was simple: more of what the map itself shows.
Zoomed in, RRIM only, no annotation outlines. Every other map figure in the
deck carries shapefile outlines, so the audience never sees what the eye has
to find without help.

NOTHING IS DRAWN ON THE TERRAIN
-------------------------------
No outline, arrow or marker on any feature. The only overlays are a scale bar
(and, on the zoom sequence, a thin box showing where the next panel sits).
Annotation layers are read ONLY to decide where to centre each window.

EXAMPLES ARE PICKED BY RULE, NOT BY EYE
---------------------------------------
Hand-picking the prettiest pit would oversell what the map shows. So:

  pits   A depth is computed for every paired pit in 9t: median elevation in a
         3 m ring outside the rim minus median elevation inside the floor. This
         is a RANKING measure only. It is simpler than the depth quoted on the
         morphology slide (0.54 m median) and runs lower (0.43 m median here),
         so no slide quotes it. "typical" is jointly closest to the median depth
         and median rim area. "deeper" is closest to the 90th depth percentile,
         "shallower" to the 20th. Depth is not visibility: a shallow pit on
         flat ground can be the easiest to see.
  pads   By drawn area: "typical" nearest the median, "large" the 85th
         percentile, "small" the 20th. Pads holding a pit are excluded here so
         the pad reads on its own. The well-site slide uses those instead.
  roads  The context window is a 300 m square at the 75th percentile of road
         length per window, over a 15 x 15 grid of the tile. The two close-ups
         are the median-length line of bold_roads.shp and of faint_roads.shp,
         the user's own examples of each kind.
  site   A pad holding at least one pit and touching at least one road,
         nearest the median area of such pads.

Every window must sit fully inside 9t with a 10 m margin.

RRIM is read with _figure_style.read_rrim: raw bytes, no stretch, exactly as
QGIS shows it. Display is Lanczos-resampled for the slide. The data is 0.5 m.

Run:
    .venv/Scripts/python.exe docs/presentation/v19_maps_and_plain_results/_build_rrim_feature_closeups_9t.py
Writes into docs/presentation/v19_maps_and_plain_results/figures/:
    rrim_zoom_sequence_tile_to_pit_9t_05.png
    rrim_pit_{typical,deeper,shallower}_50m_9t_05.png
    rrim_pad_{typical,large,small}_90m_9t_05.png
    rrim_roads_context_300m_9t_05.png
    rrim_road_{bold,faint}_120m_9t_05.png
    rrim_well_site_road_pad_pit_150m_9t_05.png
    _closeup_selection_9t.json      which feature each image is centred on, and why
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "docs/presentation/figures_30to45min"))
from _figure_style import read_rrim  # noqa: E402

RRIM = ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif"
DEM = ROOT / "data/9t/derived/05/dem_9t_05.tif"
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
BOLD = ROOT / "qgis/annotations/bold_roads.shp"
FAINT = ROOT / "qgis/annotations/faint_roads.shp"
OUT = HERE / "figures"

TILE = (619500.0, 4593000.0, 624000.0, 4597500.0)
MARGIN = 10.0
FONT = "C:/Windows/Fonts/calibrib.ttf"


def inside(cx, cy, half):
    return (cx - half - MARGIN >= TILE[0] and cx + half + MARGIN <= TILE[2]
            and cy - half - MARGIN >= TILE[1] and cy + half + MARGIN <= TILE[3])


def bounds(cx, cy, half):
    return (cx - half, cy - half, cx + half, cy + half)


def render(cx, cy, half, px, path, boxes=(), bar_m=None):
    """Crop RRIM, upsample for the slide, add a scale bar. Nothing else."""
    a = read_rrim(RRIM, bounds(cx, cy, half))
    im = Image.fromarray((np.nan_to_num(a) * 255).round().astype("uint8"))
    im = im.resize((px, px), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    m_per_px = 2 * half / px
    for (bx0, by0, bx1, by1) in boxes:               # zoom locator only
        x0 = (bx0 - (cx - half)) / m_per_px; x1 = (bx1 - (cx - half)) / m_per_px
        y0 = ((cy + half) - by1) / m_per_px; y1 = ((cy + half) - by0) / m_per_px
        w = max(3, px // 220)
        d.rectangle([x0, y0, x1, y1], outline=(20, 26, 31), width=w + 2)
        d.rectangle([x0, y0, x1, y1], outline=(255, 255, 255), width=w)
    if bar_m is None:                                 # ~1/4 of the width, round
        raw = 2 * half / 4
        bar_m = min((1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000),
                    key=lambda v: abs(v - raw))
    L = bar_m / m_per_px
    pad = px * 0.045
    h = max(8, px // 90)
    x0, y1 = pad, px - pad
    d.rectangle([x0 - 2, y1 - h - 2, x0 + L + 2, y1 + 2], fill=(20, 26, 31))
    d.rectangle([x0, y1 - h, x0 + L, y1], fill=(255, 255, 255))
    fs = max(30, px // 16)                         # legible on a 2.6 in thumbnail
    f = ImageFont.truetype(FONT, fs)
    label = f"{bar_m:g} m" if bar_m < 1000 else f"{bar_m / 1000:g} km"
    tx, ty = x0, y1 - h - fs - 12
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        d.text((tx + dx, ty + dy), label, font=f, fill=(20, 26, 31))
    d.text((tx, ty), label, font=f, fill=(255, 255, 255))
    im.save(path, optimize=True)
    print(f"  wrote {path}")
    return bar_m


def pit_depths(dem, rims, floors):
    rec = []
    fl = floors.set_index("pit_inside_id")
    for _, r in rims.iterrows():
        pid = r.matched_pit_id
        if pid is None or pid != pid or pid not in fl.index:
            continue
        f = fl.loc[pid].geometry
        if hasattr(f, "__len__") and not hasattr(f, "geom_type"):
            f = f.iloc[0]
        c = r.geometry.centroid
        if not inside(c.x, c.y, 25):
            continue
        b = r.geometry.buffer(3.0).bounds
        with rasterio.open(dem) as s:
            w = from_bounds(*b, transform=s.transform)
            z = s.read(1, window=w, boundless=True, fill_value=np.nan).astype("f8")
            tf = s.window_transform(w)
        ring = r.geometry.buffer(3.0).difference(r.geometry)
        m_ring = ~geometry_mask([ring], z.shape, tf)
        m_floor = ~geometry_mask([f], z.shape, tf)
        if m_ring.sum() < 10 or m_floor.sum() < 4:
            continue
        depth = np.nanmedian(z[m_ring]) - np.nanmedian(z[m_floor])
        rec.append(dict(pit_outside_id=int(r.pit_outside_id), pit_inside_id=int(pid),
                        cx=c.x, cy=c.y, depth_m=float(depth),
                        rim_area_m2=float(r.geometry.area)))
    return rec


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tile = box(*TILE)
    sel = {}

    rims = gpd.read_file(ANN, layer="pit_outside").to_crs(6346)
    floors = gpd.read_file(ANN, layer="pit_inside").to_crs(6346)
    plats = gpd.read_file(ANN, layer="plat").to_crs(6346)
    roads = gpd.read_file(ANN, layer="roads").to_crs(6346)
    rims = rims[rims.within(tile)]
    plats = plats[plats.within(tile)]

    # ---- pits ----
    P = pit_depths(DEM, rims, floors)
    d = np.array([p["depth_m"] for p in P]); a = np.array([p["rim_area_m2"] for p in P])
    md, ma = np.median(d), np.median(a)
    sd, sa = d.std(), a.std()
    typ = int(np.argmin(((d - md) / sd) ** 2 + ((a - ma) / sa) ** 2))
    deeper = int(np.argmin(np.abs(d - np.percentile(d, 90))))
    shallower = int(np.argmin(np.abs(d - np.percentile(d, 20))))
    print(f"pits measured: {len(P)}   median depth {md:.2f} m, "
          f"median rim area {ma:.0f} m2")
    for name, i in (("typical", typ), ("deeper", deeper), ("shallower", shallower)):
        p = P[i]
        px = 1400 if name == "typical" else 800
        render(p["cx"], p["cy"], 25, px, OUT / f"rrim_pit_{name}_50m_9t_05.png")
        sel[f"pit_{name}"] = {**p, "rule": {"typical": "joint nearest median depth + rim area",
                                            "deeper": "depth nearest 90th pct",
                                            "shallower": "depth nearest 20th pct"}[name],
                              "population": {"n": len(P), "median_depth_m": md,
                                             "p20_depth_m": float(np.percentile(d, 20)),
                                             "p90_depth_m": float(np.percentile(d, 90)),
                                             "median_rim_area_m2": ma}}

    # ---- pads (no pits inside) ----
    pads = plats[(plats.n_pits == 0)].copy()
    pads["ex"] = pads.centroid.x; pads["ey"] = pads.centroid.y
    pads = pads[[inside(x, y, 45) for x, y in zip(pads.ex, pads.ey)]]
    for name, q, px in (("typical", 50, 1400), ("large", 85, 800), ("small", 20, 800)):
        target = np.percentile(pads.area_m2, q)
        r = pads.iloc[int(np.argmin(np.abs(pads.area_m2.values - target)))]
        render(r.ex, r.ey, 45, px, OUT / f"rrim_pad_{name}_90m_9t_05.png")
        sel[f"pad_{name}"] = dict(pad_id=int(r.pad_id), area_m2=float(r.area_m2),
                                  cx=float(r.ex), cy=float(r.ey),
                                  rule=f"area nearest {q}th pct of pads with no pit",
                                  n_pool=int(len(pads)))

    # ---- roads: context window ----
    step = 300.0
    best = []
    for i in range(15):
        for j in range(15):
            b = box(TILE[0] + i * step, TILE[1] + j * step,
                    TILE[0] + (i + 1) * step, TILE[1] + (j + 1) * step)
            best.append((roads.intersection(b).length.sum(), b))
    lens = np.array([x[0] for x in best])
    pos = lens[lens > 0]
    target = np.percentile(pos, 75)
    k = int(np.argmin(np.where(lens > 0, np.abs(lens - target), np.inf)))
    b = best[k][1]; c = b.centroid
    cx = min(max(c.x, TILE[0] + 150 + MARGIN), TILE[2] - 150 - MARGIN)
    cy = min(max(c.y, TILE[1] + 150 + MARGIN), TILE[3] - 150 - MARGIN)
    render(cx, cy, 150, 1400, OUT / "rrim_roads_context_300m_9t_05.png")
    sel["roads_context"] = dict(cx=cx, cy=cy, road_m_in_window=float(lens[k]),
                                rule="300 m window at 75th pct road length, 15x15 grid")

    for name, f in (("bold", BOLD), ("faint", FAINT)):
        g = gpd.read_file(f).to_crs(6346)
        g = g[g.within(tile)]
        g["L"] = g.length
        g = g.sort_values("L").reset_index(drop=True)
        mid = g.iloc[len(g) // 2]
        pt = mid.geometry.interpolate(0.5, normalized=True)
        render(pt.x, pt.y, 60, 800, OUT / f"rrim_road_{name}_120m_9t_05.png")
        sel[f"road_{name}"] = dict(id=int(mid["id"]) if mid["id"] == mid["id"] else None,
                                   length_m=float(mid.L), cx=pt.x, cy=pt.y,
                                   rule=f"median-length line of {f.name}", n_pool=int(len(g)))

    # ---- well site: road + pad + pit ----
    site = plats[(plats.n_pits > 0) & (plats.n_roads > 0)].copy()
    site["ex"] = site.centroid.x; site["ey"] = site.centroid.y
    site = site[[inside(x, y, 75) for x, y in zip(site.ex, site.ey)]]
    r = site.iloc[int(np.argmin(np.abs(site.area_m2.values - np.median(site.area_m2))))]
    render(r.ex, r.ey, 75, 1400, OUT / "rrim_well_site_road_pad_pit_150m_9t_05.png")
    sel["well_site"] = dict(pad_id=int(r.pad_id), area_m2=float(r.area_m2),
                            n_pits=int(r.n_pits), n_roads=int(r.n_roads),
                            cx=float(r.ex), cy=float(r.ey),
                            rule="pad with >=1 pit and >=1 road, area nearest median",
                            n_pool=int(len(site)))

    # ---- zoom sequence: tile -> 1 km -> 250 m -> 50 m, landing on the site's pit ----
    fl = floors.set_index("pit_inside_id")
    on_pad = floors[floors.pad_id == r.pad_id]
    pc = on_pad.geometry.iloc[0].centroid if len(on_pad) else r.geometry.centroid
    tcx, tcy = (TILE[0] + TILE[2]) / 2, (TILE[1] + TILE[3]) / 2
    halves = [2250.0, 500.0, 125.0, 25.0]
    centres = [(tcx, tcy)]
    for h in halves[1:]:
        centres.append((min(max(pc.x, TILE[0] + h), TILE[2] - h),
                        min(max(pc.y, TILE[1] + h), TILE[3] - h)))
    panels = []
    for n, (h, (x, y)) in enumerate(zip(halves, centres)):
        nxt = [] if n == 3 else [bounds(*centres[n + 1], halves[n + 1])]
        p = OUT / f"_zoom_panel_{n}.png"
        render(x, y, h, 700, p, boxes=nxt)
        panels.append(Image.open(p))
    gap = 24
    strip = Image.new("RGB", (4 * 700 + 3 * gap, 700), (247, 248, 246))
    for n, im in enumerate(panels):
        strip.paste(im, (n * (700 + gap), 0))
    zp = OUT / "rrim_zoom_sequence_tile_to_pit_9t_05.png"
    strip.save(zp, optimize=True)
    for n in range(4):
        (OUT / f"_zoom_panel_{n}.png").unlink()
    print(f"  wrote {zp}")
    sel["zoom_sequence"] = dict(half_widths_m=halves, centres=centres,
                                lands_on="first pit floor on the well-site pad")

    (OUT / "_closeup_selection_9t.json").write_text(json.dumps(sel, indent=2))
    print(f"  wrote {OUT / '_closeup_selection_9t.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

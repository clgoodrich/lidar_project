"""Colour the pit interiors by how weak their ground laser returns are, as a Google Earth file for checking by eye.

Measure: median intensity of ground-classified returns inside the pit_inside outline divided by the same median in a ring
10 to 30 m out (2019 USGS 3DEP D20, data/9t/derived/smrf05/_laz). Water absorbs the near-infrared pulse, so wet pits read low.
Calibrated on 12 pits labelled from Google Earth imagery: 7 wet (ratio 0.14 to 0.90) and 5 dry (1.26 to 1.74). There was no
held-out set, which is what this file is for.

Tiers: under 0.6 probably wet, 0.6 to 0.8 likely wet, 0.8 to 1.2 grey zone, 1.2 or more probably dry, not measured
(outside the 9t tiles, under 10 ground returns inside the outline, or a thin ring).

Run:
  python notebooks/wellsight_v2/s5_eval/_pit_inside_wet_kml.py
"""
from __future__ import annotations

import glob
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import laspy
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely import contains_xy

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
OUT_CSV = ROOT / "data/9t/results/pit/pit_inside_wet_intensity_9t.csv"
OUT_KML = ROOT / "data/_results/pit_inside_wet_tiers_gearth.kml"
# (name, hex colour, line width). No red/green pair. Not run through the all-pairs validator; the tier name is also in each label.
TIERS = [("probably wet (under 0.6)", "#1F5FA8", 3), ("likely wet (0.6 to 0.8)", "#7FB2E5", 3),
         ("grey zone (0.8 to 1.2)", "#D97706", 4), ("probably dry (1.2 or more)", "#FFFFFF", 2), ("not measured", "#8E959B", 1)]


def kml_color(h):
    h = h.lstrip("#")
    return "ff" + h[4:6] + h[2:4] + h[0:2]


def tier(r):
    if not np.isfinite(r):
        return 4
    return 0 if r < 0.6 else 1 if r < 0.8 else 2 if r < 1.2 else 3


def measure(pi):
    tiles = [(f,) + tuple(laspy.open(f).header.mins[:2]) + tuple(laspy.open(f).header.maxs[:2])
             for f in sorted(glob.glob(str(ROOT / "data/9t/derived/smrf05/_laz/*.laz")))]
    out = {}
    for f, x0, y0, x1, y1 in tiles:
        sel = pi[pi.geometry.centroid.apply(lambda p: x0 <= p.x <= x1 and y0 <= p.y <= y1)]
        if sel.empty:
            continue
        las = laspy.read(f)
        g = np.asarray(las.classification) == 2
        X, Y, I = (np.asarray(v)[g] for v in (las.x, las.y, las.intensity))
        tree = cKDTree(np.c_[X, Y])
        for _, r in sel.iterrows():
            x, y = r.geometry.centroid.coords[0]
            rad = np.sqrt(r.geometry.area / np.pi)
            idx = np.array(tree.query_ball_point([x, y], rad * 2.5 + 5), dtype=int)
            gi = idx[contains_xy(r.geometry, X[idx], Y[idx])] if len(idx) else idx
            rg = np.array(tree.query_ball_point([x, y], 30), dtype=int)
            if len(rg):
                rg = rg[np.hypot(X[rg] - x, Y[rg] - y) > 10]
            out[int(r.pit_inside_id)] = (len(gi), float(np.median(I[gi]) / np.median(I[rg])) if len(gi) >= 10 and len(rg) >= 50 else np.nan)
    return out


def ring(c):
    return " ".join(f"{x:.7f},{y:.7f},0" for x, y in c)


def poly(p):
    s = f"<Polygon><tessellate>1</tessellate><outerBoundaryIs><LinearRing><coordinates>{ring(p.exterior.coords)}</coordinates></LinearRing></outerBoundaryIs>"
    for h in p.interiors:
        s += f"<innerBoundaryIs><LinearRing><coordinates>{ring(h.coords)}</coordinates></LinearRing></innerBoundaryIs>"
    return s + "</Polygon>"


def main():
    pi = gpd.read_file(G, layer="pit_inside")
    m = measure(pi)
    D = pd.DataFrame([(i, *m.get(i, (0, np.nan))) for i in pi.pit_inside_id.astype(int)], columns=["pit_inside_id", "n_ground_in", "int_ratio"])
    D["tier"] = [TIERS[tier(r)][0] for r in D.int_ratio]
    D.to_csv(OUT_CSV, index=False)
    print(D.tier.value_counts().to_string())
    pw = pi.to_crs(4326)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>', "<name>Pit interiors by laser intensity (wet check), 9t</name>"]
    for k, (name, col, w) in enumerate(TIERS):
        parts.append(f'<Style id="t{k}"><LineStyle><color>{kml_color(col)}</color><width>{w}</width></LineStyle><PolyStyle><fill>0</fill><outline>1</outline></PolyStyle></Style>')
    for k, (name, col, w) in enumerate(TIERS):
        parts.append(f"<Folder><name>{name}</name>")
        for (_, r), (_, d) in zip(pw.iterrows(), D.iterrows()):
            if tier(d.int_ratio) != k:
                continue
            polys = list(r.geometry.geoms) if r.geometry.geom_type == "MultiPolygon" else [r.geometry]
            geom = poly(polys[0]) if len(polys) == 1 else "<MultiGeometry>" + "".join(poly(p) for p in polys) + "</MultiGeometry>"
            lab = f"{int(d.pit_inside_id)}" + (f" r{d.int_ratio:.2f}" if np.isfinite(d.int_ratio) else "")
            desc = f"pit_inside_id {int(d.pit_inside_id)}; tier {name}; intensity ratio {d.int_ratio:.2f}; ground returns inside {int(d.n_ground_in)}"
            parts.append(f"<Placemark><name>{lab}</name><description>{escape(desc)}</description><styleUrl>#t{k}</styleUrl>{geom}</Placemark>")
        parts.append("</Folder>")
    parts.append("</Document></kml>")
    OUT_KML.write_text("\n".join(parts), encoding="utf-8")
    print("->", OUT_KML)


if __name__ == "__main__":
    main()

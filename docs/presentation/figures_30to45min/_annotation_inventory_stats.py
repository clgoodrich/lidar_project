"""How much was drawn by hand, counted -- for the Manual Annotation slides.

WHAT THIS ANSWERS
-----------------
Roads and drainage: how much length went in, and in how many pieces.
Pads, pit interiors, pit exteriors: how many, how much area, how big on average.

WHICH FILE IT READS, AND WHY THAT ONE
-------------------------------------
qgis/annotations/annotations_proj.gpkg -- the projected set, EPSG:6346, which
is what every figure builder in docs/presentation/figures_30to45min reads and
what the deck's existing numbers (712 floors, 723 rims, 586 walls) came from.

Do NOT switch this to annotations_proj_v2.gpkg to "get the newer numbers". v2
holds 841 pit_full against v1's 723 pit_outside and would put a third set of
counts on slides that already quote v1 elsewhere. If v2 is meant to supersede
v1, that is a separate change that moves every figure at once.

The .shp copies in the same folder are NOT interchangeable: drainage.shp has no
.prj and drops 986 of its 2777 rows to unreadable geometry, and roads.shp holds
3698 features against the GeoPackage's 3690.

FEATURES, AND NETWORKS BUILT FROM THEM
--------------------------------------
A road feature here IS a drawn line -- mean length 145 m, median 104 m. The
roughly 40 m chunking happens later, when the training dataset is built, not in
this file. Drainage is the exception: it carries parent_id, the drawn line each
segment was cut from, so drainage reports both.

Separately, both layers report how many CONNECTED networks the lines form, by
joining any two that share an endpoint (within 0.5 m) and counting components.
That is the "how many separate roads are there" number, as against how many
strokes drew them.

Do NOT compute that with linemerge(unary_union(...)). unary_union nodes every
crossing, so a line crossed twice comes back as three pieces and the count ends
up HIGHER than the feature count -- 4,972 against 3,690 here, which is how this
was caught.

WHERE IT ALL SITS
-----------------
These layers are not 9t-only. Roads in particular run from Oil Creek east into
McKean, so a bare total answers a different question than "how much did we draw
on the tile we trained on". Every layer is therefore also split three ways, by
intersection with the two DEM footprints: 9t, 613590, and elsewhere. A feature
straddling a boundary is counted in both areas, so the per-area feature counts
can sum to more than the total; the elsewhere row is the strict complement.

Areas are planar, in EPSG:6346 metres. At this latitude the UTM scale factor is
within about 0.1 percent of 1, so no correction is applied.

Run:
    python docs/presentation/figures_30to45min/_annotation_inventory_stats.py
Writes:
    docs/presentation/figures_30to45min/annotation_inventory_9t_613590.json
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
#: The two DEMs whose footprints define the areas, so the split follows the
#: actual raster extents rather than a bounding box typed in here.
AREA_DEM = {
    "9t": ROOT / "data/9t/derived/05/dem_9t_05.tif",
    "613590": ROOT / "data/613590/derived/05/dem_613590_05.tif",
}
OUT = Path(__file__).resolve().parent / "annotation_inventory_9t_613590.json"


def line_stats(g, name, parent_col=None):
    L = g.geometry.length
    d = dict(
        layer=name,
        n_segments=int(len(g)),
        total_length_m=float(L.sum()),
        total_length_km=float(L.sum() / 1000.0),
        mean_segment_m=float(L.mean()),
        median_segment_m=float(L.median()),
    )
    if parent_col and parent_col in g.columns:
        d["n_drawn_lines"] = int(g[parent_col].nunique())
        d["n_drawn_lines_source"] = parent_col
    else:
        d["n_drawn_lines"] = int(len(g))
        d["n_drawn_lines_source"] = "one feature = one drawn line"
    d["n_networks"] = n_components(g, tol=0.5)
    return d


def area_boxes():
    import rasterio
    from shapely.geometry import box
    out = {}
    for k, p in AREA_DEM.items():
        with rasterio.open(p) as r:
            out[k] = box(*r.bounds)
    return out


def split_by_area(g, boxes, line):
    def amount(h):
        return float(h.geometry.length.sum() if line else h.geometry.area.sum())

    d = {}
    for k, bx in boxes.items():
        h = g[g.intersects(bx)]
        d[k] = {"n": int(len(h)),
                ("length_km" if line else "area_ha"):
                    round(amount(h) / (1000.0 if line else 10000.0), 2)}
    allb = None
    for bx in boxes.values():
        allb = bx if allb is None else allb.union(bx)
    h = g[~g.intersects(allb)]
    d["elsewhere"] = {"n": int(len(h)),
                      ("length_km" if line else "area_ha"):
                          round(amount(h) / (1000.0 if line else 10000.0), 2)}
    return d


def n_components(g, tol=0.5):
    """Connected pieces, joining lines that share an endpoint within `tol` m."""
    snap = {}
    parent = list(range(len(g)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    for i, geom in enumerate(g.geometry):
        if geom is None or geom.is_empty:
            continue
        cs = list(geom.coords)
        for pt in (cs[0], cs[-1]):
            key = (round(pt[0] / tol), round(pt[1] / tol))
            if key in snap:
                union(i, snap[key])
            else:
                snap[key] = i
    return len({find(i) for i in range(len(g))})


def poly_stats(g, name):
    A = g.geometry.area
    return dict(
        layer=name,
        n=int(len(g)),
        total_area_m2=float(A.sum()),
        total_area_ha=float(A.sum() / 10000.0),
        mean_area_m2=float(A.mean()),
        median_area_m2=float(A.median()),
        p10_area_m2=float(np.percentile(A, 10)),
        p90_area_m2=float(np.percentile(A, 90)),
    )


def main() -> int:
    out = {"source": str(ANN.relative_to(ROOT)).replace("\\", "/"),
           "crs": "EPSG:6346", "lines": [], "polygons": []}
    boxes = area_boxes()

    roads = gpd.read_file(ANN, layer="roads")
    rs = line_stats(roads, "roads")
    if "src" in roads.columns:
        by = roads.assign(_l=roads.geometry.length).groupby(
            roads["src"].fillna("unlabelled"))["_l"]
        rs["by_source_km"] = {k: round(v / 1000.0, 2)
                              for k, v in by.sum().items()}
        rs["by_source_segments"] = {k: int(v) for k, v in by.count().items()}
    rs["by_area"] = split_by_area(roads, boxes, True)
    out["lines"].append(rs)

    nr = gpd.read_file(ANN, layer="not_roads")
    ns_ = line_stats(nr, "not_roads")
    ns_["by_area"] = split_by_area(nr, boxes, True)
    out["lines"].append(ns_)

    dr = gpd.read_file(ANN, layer="drainage")
    ds = line_stats(dr, "drainage", parent_col="parent_id")
    if "klass" in dr.columns:
        by = dr.assign(_l=dr.geometry.length).groupby(
            dr["klass"].fillna("unlabelled"))["_l"]
        ds["by_class_km"] = {k: round(v / 1000.0, 2) for k, v in by.sum().items()}
        ds["by_class_segments"] = {k: int(v) for k, v in by.count().items()}
    ds["by_area"] = split_by_area(dr, boxes, True)
    out["lines"].append(ds)

    for lay, label in (("plat", "pads"), ("pit_inside", "pit interiors"),
                       ("pit_outside", "pit exteriors"), ("pit_wall", "pit walls")):
        g = gpd.read_file(ANN, layer=lay)
        st = poly_stats(g, lay)
        st["label"] = label
        st["by_area"] = split_by_area(g, boxes, False)
        out["polygons"].append(st)

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    for d in out["lines"]:
        print(f"\n{d['layer']}")
        print(f"  {d['total_length_km']:.1f} km over {d['n_segments']:,} segments")
        print(f"  {d['n_drawn_lines']:,} drawn lines ({d['n_drawn_lines_source']})")
        print(f"  {d['n_networks']:,} connected networks")
        print(f"  segment mean {d['mean_segment_m']:.1f} m, "
              f"median {d['median_segment_m']:.1f} m")
        for k in ("by_source_km", "by_class_km"):
            if k in d:
                print(f"  {k}: {d[k]}")
        print("  by area: " + "  ".join(
            f"{k} {v['n']}/{v['length_km']}km" for k, v in d["by_area"].items()))
    for d in out["polygons"]:
        print(f"\n{d['layer']}  ({d['label']})")
        print(f"  {d['n']:,} polygons, {d['total_area_ha']:.2f} ha total")
        print(f"  mean {d['mean_area_m2']:.1f} m2, median {d['median_area_m2']:.1f} m2, "
              f"p10-p90 {d['p10_area_m2']:.1f}-{d['p90_area_m2']:.1f} m2")
        print("  by area: " + "  ".join(
            f"{k} {v['n']}/{v['area_ha']}ha" for k, v in d["by_area"].items()))
    print(f"\n  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

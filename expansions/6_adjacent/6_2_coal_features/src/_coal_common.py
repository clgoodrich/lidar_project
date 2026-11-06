"""Shared helpers for 6.2. Reuses the 6.3 machinery (path resolution, candidates, matching, sheets).

Purpose
    Load config_6_2.json, read the assumed PA DEP mine-feature layers, map their type codes to the classes
    M (portal), S (subsidence) and H (spoil heap) without guessing (unmapped codes are listed), and apply the
    per-class matching tolerance of framework section 3.
Inputs
    expansions/6_adjacent/6_2_coal_features/src/config_6_2.json
    expansions/6_adjacent/6_3_confuser_classes/src/_confuser_common_9t.py (imported)
Outputs
    None. Imported by the _coal_*.py scripts.
Run
    Not a script.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SRC_63 = HERE.parents[1] / "6_3_confuser_classes" / "src"
sys.path.insert(0, str(SRC_63))
import _confuser_common_9t as C  # noqa: E402
from _confuser_common_9t import ek  # noqa: E402

DEFAULT_CONFIG = HERE / "config_6_2.json"
MissingInput = C.MissingInput


def load_config(path=None) -> dict:
    return C.load_config(path or DEFAULT_CONFIG)


def map_type(code, type_map: dict) -> str | None:
    c = str(code).strip().upper()
    for cls in ("M", "S", "H"):
        if c in type_map.get(cls, []):
            return cls
    return None


def read_mine_layers(cfg: dict, overrides: dict | None = None):
    """All mine layers in one frame with class, source layer, record id and geometry (EPSG:6346)."""
    import geopandas as gpd
    o = overrides or {}
    parts, unmapped = [], {}
    for spec in cfg["mine_layers"]:
        p = Path(o[spec["name"]]) if spec["name"] in o else C.resolve(spec)
        if not p.exists():
            raise MissingInput(f"missing mine layer '{spec['name']}' ({spec['state']}) at {p}. Expected fields "
                               f"{spec['type_field']} and {spec['id_field']}. VERIFY the DEP catalogue in S0.")
        g = C.read_vector(p, cfg["crs"])
        for f in (spec["type_field"], spec["id_field"]):
            if f not in g:
                raise MissingInput(f"{p} lacks field {f}. Fields are {list(g.columns)}. Edit config_6_2.json mine_layers.")
        cls = g[spec["type_field"]].map(lambda v: map_type(v, cfg["type_map"]))
        um = g.loc[cls.isna(), spec["type_field"]].astype(str).value_counts().to_dict()
        if um:
            unmapped[spec["name"]] = um
        vf = set(cfg["type_map"].get("H_sublabel_valley_fill", []))
        parts.append(gpd.GeoDataFrame({"record_id": spec["name"] + ":" + g[spec["id_field"]].astype(str),
                                       "layer": spec["name"], "type_code": g[spec["type_field"]].astype(str),
                                       "cls": cls, "valley_fill": g[spec["type_field"]].astype(str).str.upper().isin(vf)},
                                      geometry=g.geometry.values, crs=cfg["crs"]))
    rec = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=cfg["crs"])
    ek.assert_unique(rec, "record_id")
    return rec, unmapped


def class_match(cls: str, cand_geom, truth_geom, tol: dict) -> bool:
    """Per-class tolerance from framework section 3 (re-chosen after S0, fixed before scoring).

    A point record has no area, so an IoU rule can never match it (review 6.2, verified 2026-11-06). For IoU
    classes a point record (or any zero-area record) matches by distance instead. The point must lie inside the
    candidate polygon or within the class offset_m of it (tolerance._point_rule). Without offset_m it must lie inside.
    """
    t = tol[cls]
    if t["rule"] == "centroid":
        return cand_geom.centroid.distance(truth_geom.centroid) <= t["m"]
    if truth_geom.area == 0:
        return cand_geom.distance(truth_geom) <= float(t.get("offset_m", 0.0))
    inter = cand_geom.intersection(truth_geom).area
    iou = inter / (cand_geom.area + truth_geom.area - inter) if inter > 0 else 0.0
    if iou >= t["iou"]:
        return True
    if "fallback_centroid_m" in t and truth_geom.area >= t["fallback_min_ha"] * 1e4:
        return cand_geom.centroid.distance(truth_geom.centroid) <= t["fallback_centroid_m"]
    return False


def make_blocks(bounds, size_m: float, crs: str):
    """Complete square blocks over an extent (including blocks with no features)."""
    import geopandas as gpd
    from shapely.geometry import box
    x0, y0, x1, y1 = bounds
    x0, y0 = np.floor(x0 / size_m) * size_m, np.floor(y0 / size_m) * size_m
    rows = []
    for iy, y in enumerate(np.arange(y0, y1, size_m)):
        for ix, x in enumerate(np.arange(x0, x1, size_m)):
            rows.append({"block_id": len(rows), "ix": ix, "iy": iy, "geometry": box(x, y, x + size_m, y + size_m)})
    return gpd.GeoDataFrame(rows, crs=crs)

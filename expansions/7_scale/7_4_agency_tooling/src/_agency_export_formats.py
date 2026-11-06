"""Candidate export to agency formats. GeoPackage, CSV and KML (7.4 section 6 candidate schema).

Purpose
    Turn scored blobs into the documented candidate table and write it three ways.
    Every row is labelled "candidate" with evidence level (a), the detection method, the model hash, a
    raw score, an optional calibrated score, ranks, the validity flag of its tile, and the distance to
    the nearest known well when a known-well file is given (read-only, its hash recorded).
    A guard scans every text field and the KML for forbidden wording ("confirmed", "well found" and the
    internal project name) and refuses to write if any appears. Candidates are never presented as wells.
    cand_id is a stable hash of run id, class and the centroid rounded to 0.1 m.

Inputs
    a GeoDataFrame of blobs (geometry, score, area_m2, tile_id) per class, run metadata
    optional known wells (any vector or CSV with x/y or lon/lat), never written to
Outputs (in the run folder)
    candidates.gpkg (layers pit, pad), candidates.csv, candidates.kml (EPSG:4326 placemarks)

Run
    python expansions/7_scale/7_4_agency_tooling/src/_agency_export_formats.py --blobs blobs.gpkg --layer pit \
        --class pit --run-id 20261105_agency_abc1234 --model-id m --model-sha256 <sha> --out <folder>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _agency_las_validity import CFG, ek, load_cfg  # noqa: E402

COLUMNS = ["cand_id", "class", "score", "score_cal", "area_m2", "centroid_x", "centroid_y", "tile_id", "rank_in_run",
           "rank_per_km2", "validity_flag", "model_id", "model_sha256", "method", "evidence_level", "label",
           "dist_nearest_known_m", "run_id"]


def stable_id(run_id: str, cls: str, x: float, y: float) -> str:
    return hashlib.sha256(f"{run_id}|{cls}|{x:.1f}|{y:.1f}".encode()).hexdigest()[:16]


def read_known_wells(path: Path, crs):
    """Read-only. Vector file, or CSV with x,y (in `crs`) or lon,lat / longitude,latitude (EPSG:4326)."""
    import geopandas as gpd
    p = Path(path)
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
        cols = {c.lower(): c for c in df.columns}
        for xc, yc, src in (("x", "y", crs), ("lon", "lat", "EPSG:4326"), ("longitude", "latitude", "EPSG:4326")):
            if xc in cols and yc in cols:
                g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[cols[xc]], df[cols[yc]]), crs=src)
                break
        else:
            raise ValueError(f"{p.name}: need x/y or lon/lat columns")
    else:
        g = gpd.read_file(p)
    return g.to_crs(crs)


def nearest_known_m(cx, cy, wells) -> np.ndarray:
    from scipy.spatial import cKDTree
    if wells is None or not len(wells):
        return np.full(len(cx), np.nan)
    c = wells.geometry.centroid
    d, _ = cKDTree(np.c_[c.x, c.y]).query(np.c_[cx, cy])
    return d


def build_table(blobs, cls: str, meta: dict, area_km2: float, k_per_km2: float, wells=None, validity=None,
                calibrate=None):
    """blobs: GeoDataFrame with geometry, score, area_m2, tile_id. Returns the candidate GeoDataFrame."""
    import geopandas as gpd
    if blobs.crs is None:
        raise AssertionError("blobs have no CRS")
    b = blobs.sort_values(["score", "area_m2"], ascending=[False, False], kind="stable").reset_index(drop=True)
    cen = b.geometry.centroid
    out = gpd.GeoDataFrame({
        "cand_id": [stable_id(meta["run_id"], cls, x, y) for x, y in zip(cen.x, cen.y)],
        "class": cls, "score": b["score"].astype(float).round(6),
        "score_cal": calibrate(b["score"].to_numpy()) if calibrate else np.nan,
        "area_m2": b["area_m2"].astype(float).round(3), "centroid_x": cen.x.round(3), "centroid_y": cen.y.round(3),
        "tile_id": b["tile_id"].astype(str), "rank_in_run": np.arange(1, len(b) + 1),
    }, geometry=b.geometry.values, crs=blobs.crs)
    k = int(np.floor(k_per_km2 * area_km2))
    out["rank_per_km2"] = out["rank_in_run"] / max(area_km2, 1e-12)
    out["within_review_budget"] = out["rank_in_run"] <= k
    vf = validity or {}
    out["validity_flag"] = [vf.get(t, "ok") for t in out["tile_id"]]
    out["model_id"], out["model_sha256"], out["method"] = meta["model_id"], meta["model_sha256"], meta["method"]
    out["evidence_level"], out["label"] = "a", "candidate"
    out["dist_nearest_known_m"] = np.round(nearest_known_m(out["centroid_x"], out["centroid_y"], wells), 2)
    out["run_id"] = meta["run_id"]
    if out["cand_id"].duplicated().any():
        raise AssertionError("duplicate candidate ids")
    return out


def guard_text(texts, forbidden) -> None:
    for t in texts:
        for w in forbidden:
            if re.search(re.escape(w), str(t), flags=re.IGNORECASE):
                raise ValueError(f"forbidden wording {w!r} in output: {str(t)[:80]}")


def to_kml(cands, path: Path, title: str) -> str:
    c = cands.to_crs("EPSG:4326")
    pm = []
    for _, r in c.iterrows():
        p = r.geometry.centroid
        d = r["dist_nearest_known_m"]
        dist = "not given" if pd.isna(d) else f"{d:.0f} m"
        desc = (f"Label: {r['label']} (evidence level {r['evidence_level']}). Not a well location. "
                f"Score {r['score']:.3f}. Rank {int(r['rank_in_run'])}. Method {r['method']}. "
                f"Tile validity {r['validity_flag']}. Distance to nearest known well {dist}.")
        pm.append(f"<Placemark><name>{escape(r['class'])} candidate {escape(r['cand_id'])}</name>"
                  f"<description>{escape(desc)}</description><Point><coordinates>{p.x:.7f},{p.y:.7f},0</coordinates></Point></Placemark>")
    kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f"<name>{escape(title)}</name>" + "".join(pm) + "</Document></kml>\n")
    Path(path).write_text(kml, encoding="utf-8")
    return kml


def write_all(tables: dict, out: Path, forbidden, title: str = "Terrain-feature candidates") -> dict:
    import geopandas as gpd
    out.mkdir(parents=True, exist_ok=True)
    allc = pd.concat([t for t in tables.values() if len(t)], ignore_index=True) if any(len(t) for t in tables.values()) else None
    gp = out / "candidates.gpkg"
    gp.unlink(missing_ok=True)
    for cls, t in tables.items():
        if len(t):
            guard_text(t.select_dtypes(include="object").astype(str).to_numpy().ravel(), forbidden)
            t.to_file(gp, layer=cls, driver="GPKG")
    cols = COLUMNS + ["within_review_budget"]
    if allc is None:
        pd.DataFrame(columns=cols).to_csv(out / "candidates.csv", index=False)
        to_kml(gpd.GeoDataFrame(columns=cols, geometry=[], crs="EPSG:4326"), out / "candidates.kml", title)
        return {"n": 0}
    allc = gpd.GeoDataFrame(allc, geometry="geometry", crs=next(t for t in tables.values() if len(t)).crs)
    allc[cols].to_csv(out / "candidates.csv", index=False, float_format="%.6f", lineterminator="\n")
    guard_text([to_kml(allc, out / "candidates.kml", title)], forbidden)
    return {"n": len(allc), "by_class": allc["class"].value_counts().to_dict()}


def main(argv=None) -> int:
    import geopandas as gpd
    ap = argparse.ArgumentParser(description="7.4 candidate export.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--blobs", required=True)
    ap.add_argument("--layer", default=None)
    ap.add_argument("--class", dest="cls", choices=["pit", "pad"], required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--model-sha256", required=True)
    ap.add_argument("--method", default=None)
    ap.add_argument("--area-km2", type=float, required=True)
    ap.add_argument("--known-wells", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    if not Path(a.blobs).exists():
        print(f"missing blobs {a.blobs}", file=sys.stderr)
        return 2
    b = gpd.read_file(a.blobs, layer=a.layer)
    wells = read_known_wells(Path(a.known_wells), b.crs) if a.known_wells else None
    meta = {"run_id": a.run_id, "model_id": a.model_id, "model_sha256": a.model_sha256,
            "method": a.method or cfg["models"][a.cls]["method"]}
    t = build_table(b, a.cls, meta, a.area_km2, cfg["k_per_km2"], wells)
    print(json.dumps(write_all({a.cls: t}, Path(a.out), cfg["forbidden_words"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

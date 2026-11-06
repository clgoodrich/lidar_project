"""S5 of framework 4.6. Compare adjudicated historic marks with drawn features, DEP records and model candidates.

Purpose. Three separate comparisons, none of which decides source readiness (review revision 2, 2026-11-04).
  1. Distance from each mark to the nearest drawn pit (pit_inside) and pad.
  2. Association with DEP records. Observed count of marks with a record within r, against a shifted-set null.
     Only records that existed by the source date enter (spud date on or before it, compared by year when the
     source date is a year). Records with no usable spud date (missing or the 1800 sentinel) are left out of the
     primary count and enter a labelled sensitivity run. Without this filter a 1922 map was compared with wells
     drilled decades later (review 4.6-01, 2026-11-06). A source with no parseable date is refused.
     Each null draw moves every record 200 to 500 m in a random direction, redrawn until it stays inside the oil
     field footprint, 300 draws. r is the source's measured check-point RMSE unless the config fixes it.
  3. Marks against model candidates at K = 40 per km2 (threshold 0.10, blobs of 4 m2 or more, mean-probability
     score, ties by larger area, same polygonize as the operating-point sweep), and the model score at each mark.
Historical positives with low scores are listed. A low score is a model miss, not a label failure.
Inputs.
  data/9t/results/historic/historic_well_marks_9t.gpkg (from S4)
  qgis/annotations/annotations_proj_v2.gpkg layers pit_inside, pad (held)
  data/_source/reference/dep_wells/venango_wells_all.gpkg (held)
  expansions/4_modalities/4_6_historic_maps_aerials/data/raw/oil_field_footprint_9t.gpkg (assumed, fallback logged)
  data/9t/results/pit/pit_prob_floor_oof_mosaic_9t_05.tif (assumed, comparison 3 is skipped without it)
Outputs.
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_marks_compare_<source>_9t.json
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_marks_compare_<source>_9t.csv   one row per mark
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_marks_vs_records_9t.py --source NAME [--marks GPKG] [--prob TIF] [--n-shifts 300]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import _hist_kit_4_6 as hk


def shifted_null(rec_xy: np.ndarray, marks_xy: np.ndarray, footprint, r: float, n: int, dmin: float, dmax: float,
                 seed: int, tries: int = 50) -> np.ndarray:
    """Count of marks with a shifted record within r, per null draw."""
    from scipy.spatial import cKDTree
    from shapely import contains_xy
    rng = np.random.default_rng(seed)
    out = np.zeros(n, int)
    for k in range(n):
        xy = rec_xy.copy()
        todo = np.arange(len(xy))
        new = np.full_like(xy, np.nan)
        for _ in range(tries):
            if not len(todo):
                break
            th = rng.uniform(0, 2 * np.pi, len(todo))
            d = rng.uniform(dmin, dmax, len(todo))
            cand = xy[todo] + np.column_stack([d * np.cos(th), d * np.sin(th)])
            ok = contains_xy(footprint, cand[:, 0], cand[:, 1])
            new[todo[ok]] = cand[ok]
            todo = todo[~ok]
        new = new[np.isfinite(new[:, 0])]
        if len(new) and len(marks_xy):
            dd, _ = cKDTree(new).query(marks_xy)
            out[k] = int((dd <= r).sum())
    return out


def association(marks_xy, rec_xy, footprint, r, n, dmin, dmax, seed) -> dict:
    from scipy.spatial import cKDTree
    dd, _ = cKDTree(rec_xy).query(marks_xy) if len(rec_xy) else (np.full(len(marks_xy), np.inf), None)
    obs = int((dd <= r).sum())
    null = shifted_null(rec_xy, marks_xy, footprint, r, n, dmin, dmax, seed)
    lo, hi = np.percentile(obs - null, [2.5, 97.5])
    return {"radius_m": r, "observed": obs, "null_mean": float(null.mean()), "excess": float(obs - null.mean()),
            "excess_lo": float(lo), "excess_hi": float(hi), "p_one_sided": float((1 + (null >= obs).sum()) / (n + 1)),
            "n_shifts": n, "note": "association only, never a readiness test. Excess is not PPV"}


def source_date(dates) -> tuple[pd.Timestamp, bool]:
    """(date, year_only). One date per source. Refuses a missing, unparseable or mixed date."""
    vals = sorted({str(d).strip() for d in dates if d is not None and str(d).strip() not in ("", "nan", "None")})
    if len(vals) != 1:
        raise ValueError(f"source date must be one value, got {vals or 'none'}. The date filter needs it")
    v = vals[0]
    if v.isdigit() and len(v) == 4:
        return pd.Timestamp(f"{v}-12-31"), True
    t = pd.to_datetime(v, errors="coerce")
    if pd.isna(t):
        raise ValueError(f"source date {v!r} does not parse")
    return t, False


def records_by_date(dep, when: pd.Timestamp, year_only: bool, field: str, sentinel_year: int):
    """Boolean masks (existed, unknown) per record. existed = spud on or before the source date."""
    if field not in dep:
        raise KeyError(f"DEP export lacks {field}. The date filter needs it")
    sp = pd.to_datetime(dep[field], errors="coerce")
    unknown = sp.isna() | (sp.dt.year <= sentinel_year)
    before = (sp.dt.year <= when.year) if year_only else (sp <= when)
    return (before & ~unknown).to_numpy(), unknown.to_numpy()


def candidates_topk(prob_path: Path, cfg) -> tuple:
    """Top-K candidate polygons (K per km2 of valid raster area) and the open raster for sampling."""
    import rasterio
    sys.path.insert(0, str(hk.ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"))
    from _threshold_common import polygonize
    pr = cfg["prereg"]
    with rasterio.open(prob_path) as d:
        hk.ek.assert_crs(d, cfg["crs"])
        prob = d.read(1).astype("float32")
        if d.nodata is not None:
            prob[prob == d.nodata] = np.nan
        if np.nanmax(prob) > 1.0:          # uint8 mosaics store DN / 254
            prob = prob / 254.0
        tf, px_area = d.transform, abs(d.transform.a * d.transform.e)
    area_km2 = float(np.isfinite(prob).sum() * px_area / 1e6)
    cand = polygonize(np.nan_to_num(prob, nan=0.0), tf, cfg["crs"], pr["prob_threshold"], pr["min_blob_m2"])
    cand["area"] = cand.area
    cand = cand.sort_values(["score", "area"], ascending=[False, False]).reset_index(drop=True)
    k = int(round(pr["k_per_km2"] * area_km2))
    return cand.head(k), prob, tf, area_km2, k


def main(argv=None) -> int:
    import geopandas as gpd
    cfg = hk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--marks", default=None)
    ap.add_argument("--annotations", default=None)
    ap.add_argument("--dep", default=None)
    ap.add_argument("--footprint", default=None)
    ap.add_argument("--prob", default=None)
    ap.add_argument("--n-shifts", type=int, default=pr["null_n_shifts"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    I = cfg["inputs"]
    mk = gpd.read_file(hk.need(Path(a.marks) if a.marks else hk.resolve(cfg["outputs"]["marks_gpkg"]), "S4 mark layer"),
                       layer="marks")
    hk.ek.assert_crs(mk, cfg["crs"])
    mk = mk[(mk.source == a.source) & mk.adjudicated.isin(["agreed", "keep"])].reset_index(drop=True)
    if not len(mk):
        raise ValueError(f"no agreed or kept marks for {a.source}")
    ann = hk.need(Path(a.annotations) if a.annotations else hk.resolve(I["annotations"]), "annotations")
    pits, pads = gpd.read_file(ann, layer="pit_inside"), gpd.read_file(ann, layer="pad")
    hk.ek.assert_crs(pits, cfg["crs"]), hk.ek.assert_crs(pads, cfg["crs"])
    rows = pd.DataFrame({"mark_id": mk.mark_id, "symbol": mk.symbol, "x": mk.geometry.x, "y": mk.geometry.y})
    rows["dist_pit_m"] = [pits.distance(p).min() for p in mk.geometry]
    rows["dist_pad_m"] = [pads.distance(p).min() for p in mk.geometry]
    rows["in_pad"] = [bool(pads.contains(p).any()) for p in mk.geometry]
    res = {"source": a.source, "n_marks": int(len(mk)),
           "dist_pit_q": rows.dist_pit_m.quantile([.1, .25, .5, .75, .9]).round(1).tolist(),
           "dist_pad_q": rows.dist_pad_m.quantile([.1, .25, .5, .75, .9]).round(1).tolist(),
           "in_pad": hk.ek.clopper_pearson(int(rows.in_pad.sum()), len(rows))}
    dep = gpd.read_file(hk.need(Path(a.dep) if a.dep else hk.resolve(I["dep_wells"]), "DEP export"))
    hk.ek.assert_crs(dep, cfg["crs"])
    x0, y0, x1, y1 = cfg["bbox_9t"]
    pad_m = pr["null_shift_max_m"] * 2
    dep = dep.cx[x0 - pad_m:x1 + pad_m, y0 - pad_m:y1 + pad_m]
    fp_path = Path(a.footprint) if a.footprint else hk.resolve(I["oil_field_footprint"])
    if fp_path.exists():
        fp = gpd.read_file(fp_path).to_crs(cfg["crs"]).union_all()
        res["footprint"] = str(fp_path)
    else:
        fp = dep.union_all().convex_hull.buffer(250.0)
        res["footprint"] = "fallback: DEP record hull buffered 250 m (oil field footprint not supplied)"
    r = pr["assoc_radius_m"] or float(mk.accuracy_m.iloc[0])
    when, year_only = source_date(mk.date)
    if pr.get("undated_records") != "sensitivity_only":
        raise ValueError(f"prereg.undated_records is {pr.get('undated_records')!r}. The accepted rule (2026-11-06) is "
                         "'sensitivity_only'. Undated records never enter the primary association")
    existed, unknown = records_by_date(dep, when, year_only, pr["record_date_field"], int(pr["record_sentinel_year_max"]))
    res["record_date_filter"] = {"source_date": str(when.date()) if not year_only else str(when.year),
                                 "field": pr["record_date_field"], "n_records_in_window": int(len(dep)),
                                 "n_existed_by_date": int(existed.sum()), "n_unknown_date": int(unknown.sum()),
                                 "n_after_date": int((~existed & ~unknown).sum()),
                                 "undated_records": pr["undated_records"]}
    xy = np.column_stack([dep.geometry.x, dep.geometry.y])
    res["dep_association"] = association(rows[["x", "y"]].to_numpy(), xy[existed], fp, r, a.n_shifts,
                                         pr["null_shift_min_m"], pr["null_shift_max_m"], pr["master_seed"])
    res["dep_association_with_unknown_dates"] = {
        **association(rows[["x", "y"]].to_numpy(), xy[existed | unknown], fp, r, a.n_shifts,
                      pr["null_shift_min_m"], pr["null_shift_max_m"], pr["master_seed"]),
        "label": "sensitivity. Records with no usable spud date counted as existing"}
    prob_path = Path(a.prob) if a.prob else hk.resolve(I["prob_raster"])
    if prob_path.exists():
        import rasterio
        top, prob, tf, area_km2, k = candidates_topk(prob_path, cfg)
        inside = [bool(top.contains(p).any()) for p in mk.geometry]
        rr, cc = rasterio.transform.rowcol(tf, rows.x, rows.y)
        H, W = prob.shape
        rows["model_score"] = [float(prob[i, j]) if 0 <= i < H and 0 <= j < W else np.nan for i, j in zip(rr, cc)]
        rows["in_topk"] = inside
        res["topk"] = {"k": k, "area_km2": area_km2, "in_topk": hk.ek.clopper_pearson(int(sum(inside)), len(inside)),
                       "n_low_score_marks": int((rows.model_score < pr["prob_threshold"]).sum())}
    else:
        res["topk"] = f"skipped: probability raster not found at {prob_path} (assumed input, VERIFY)"
    out = Path(a.out) if a.out else hk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    jf, cf = out / f"hist_marks_compare_{a.source}_9t.json", out / f"hist_marks_compare_{a.source}_9t.csv"
    jf.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    rows.to_csv(cf, index=False)
    hk.prov(out, f"hist_marks_vs_records_{a.source}", inputs=[ann, prob_path], outputs=[jf, cf],
            params={"radius_m": r, "n_shifts": a.n_shifts}, seeds={"null": pr["master_seed"]})
    print(json.dumps(res, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

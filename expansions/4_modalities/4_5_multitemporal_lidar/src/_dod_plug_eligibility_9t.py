"""S1. Plug eligibility. Which 9t DEP wells were plugged strictly between the two lidar flights, and which pads hold them.

Purpose
    Applies the eligibility rule of fw_4_5 section 3 to every DEP well in the 9t box, with the flight windows of S0.
    eligible     plug date > end of the early window and < start of the late window, both for the well's tiles
    ambiguous    plug date inside either flight window (could be before or after a flight)
    excluded     not plugged, plugged before the early window, plugged after the late window, no date, or the
                 1800 sentinel
    Wells join a pad when the pad polygon lies within well_to_pad_m. Pads within complex_link_m form one pad complex,
    the unit of clustering. A pad is treated when it holds at least one eligible well and no ambiguous well.
    If eligible pads fall below the preregistered minimum the script writes the counts, prints STOP and exits 2.

Inputs
    flight_windows_9t.csv from the newest S0 run (expansions/4_modalities/4_5_multitemporal_lidar/results/<run>/) or --windows
    data/_source/reference/dep_wells/venango_wells_all.gpkg (held), qgis/annotations/annotations_proj_v2.gpkg layer pad (held)
    expansions/4_modalities/4_5_multitemporal_lidar/data/raw/dep_restoration_records.csv (optional, R7)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_elig_<hash7>/)
    plug_eligible_wells_9t.csv   one row per DEP well in the box with class, reason, pad_id, complex_id
    plug_eligible_pads_9t.csv    one row per pad with well counts by class, treated flag, complex_id, restoration
    plug_eligible_counts_9t.json counts, the bounds used, and the readiness verdict
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_plug_eligibility_9t.py [--windows CSV] [--out-root DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dod_shared_io as io  # noqa: E402
from _dod_shared_io import ek  # noqa: E402


def well_bounds(wells, windows: pd.DataFrame) -> pd.DataFrame:
    """Per well, the widest window over the tiles that cover it (earliest start, latest end), per survey.
    Rows without a bbox (project-level rows) apply to every well."""
    x, y = wells.geometry.x.to_numpy(), wells.geometry.y.to_numpy()
    W = windows.copy()
    for c in ("minx", "miny", "maxx", "maxy"):
        if c not in W:
            W[c] = np.nan
    W["s"], W["e"] = pd.to_datetime(W.window_start), pd.to_datetime(W.window_end)
    out = {k: [None] * len(wells) for k in ("early_start", "early_end", "late_start", "late_end")}
    for which in ("early", "late"):
        S = W[W.which == which]
        for i in range(len(wells)):
            hit = S[S.minx.isna() | ((S.minx <= x[i]) & (S.maxx >= x[i]) & (S.miny <= y[i]) & (S.maxy >= y[i]))]
            if len(hit):
                out[f"{which}_start"][i], out[f"{which}_end"][i] = hit.s.min(), hit.e.max()
    return pd.DataFrame(out, index=wells.index)


def classify(plug, e_start, e_end, l_start, l_end, sentinel_year: int) -> tuple[str, str]:
    if plug is None or pd.isna(plug):
        return "excluded", "not plugged or no plug date"
    plug = pd.Timestamp(plug)
    if plug.year <= sentinel_year:
        return "excluded", "sentinel date"
    if e_end is None or l_start is None:
        return "excluded", "no flight window covers the well"
    e_start = pd.Timestamp(e_start) if e_start is not None else pd.Timestamp(e_end)
    l_end = pd.Timestamp(l_end) if l_end is not None else pd.Timestamp(l_start)
    if pd.Timestamp(e_end) < plug < pd.Timestamp(l_start):
        return "eligible", "plugged strictly between the flights"
    if e_start <= plug <= pd.Timestamp(e_end) or pd.Timestamp(l_start) <= plug <= l_end:
        return "ambiguous", "plug date inside a flight window"
    if plug < e_start:
        return "excluded", "plugged before the early flight"
    return "excluded", "plugged after the late flight"


def pad_complexes(pads, link_m: float) -> np.ndarray:
    """Connected components of pads whose polygons lie within link_m of each other."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    import geopandas as gpd
    b = gpd.GeoDataFrame(geometry=pads.geometry.buffer(link_m / 2), crs=pads.crs).reset_index(drop=True)
    j = gpd.sjoin(b, b, predicate="intersects")
    n = len(b)
    A = coo_matrix((np.ones(len(j)), (j.index.to_numpy(), j["index_right"].to_numpy())), shape=(n, n))
    return connected_components(A, directed=False)[1]


def run(cfg: dict, out_root: Path | None = None, windows_csv: Path | None = None, wells=None, pads=None) -> dict:
    import geopandas as gpd
    el = cfg["eligibility"]
    crs = cfg["crs"]
    wp = io.stage_file(windows_csv, "dod_flight", "flight_windows_9t.csv", out_root, "S0 flight windows")
    windows = pd.read_csv(wp)
    inputs = [wp]
    if wells is None:
        p = io.resolve(cfg["wells_gpkg"])
        wells = io.read_layer(p, None, crs)
        inputs.append(p)
    if pads is None:
        p = io.resolve(cfg["annotations_gpkg"])
        pads = io.read_layer(p, cfg["pad_layer"], crs)
        inputs.append(p)
    x0, y0, x1, y1 = cfg["bbox_9t"]
    wells = wells.cx[x0:x1, y0:y1].copy()
    pads = pads.reset_index(drop=True).copy()
    run_dir = ek.new_run(io.EXP, "dod_elig", {"eligibility": el, "windows": str(wp)}, base=out_root,
                         why="S1 plug eligibility (fw_4_5 section 6).")

    B = well_bounds(wells, windows)
    plug = pd.to_datetime(wells[el["date_field"]], errors="coerce")
    cls = [classify(p if pd.notna(p) else None, es, ee, ls, le, int(el["sentinel_year_max"]))
           for p, es, ee, ls, le in zip(plug, B.early_start, B.early_end, B.late_start, B.late_end)]
    wells["elig_class"] = [c for c, _ in cls]
    wells["elig_reason"] = [r for _, r in cls]
    wells["plug_date"] = plug
    wells["early_end"], wells["late_start"] = B.early_end, B.late_start

    pads["complex_id"] = pad_complexes(pads, float(el["complex_link_m"]))
    near = gpd.sjoin_nearest(wells[["geometry"]], pads[["pad_id", "complex_id", "geometry"]], how="left",
                             max_distance=float(el["well_to_pad_m"]), distance_col="pad_dist_m")
    near = near[~near.index.duplicated(keep="first")]
    wells["pad_id"], wells["complex_id"], wells["pad_dist_m"] = near.pad_id, near.complex_id, near.pad_dist_m
    ek.assert_rows(near, len(wells), "wells after pad join")

    keep_cols = [c for c in ("PERMIT_NUM", "WELL_NAME", "WELL_STATU", el["spud_field"]) if c in wells]
    wt = pd.DataFrame(wells[keep_cols + ["plug_date", "early_end", "late_start", "elig_class", "elig_reason", "pad_id",
                                         "complex_id", "pad_dist_m"]])
    wt["x"], wt["y"] = wells.geometry.x.round(2), wells.geometry.y.round(2)
    w_csv = run_dir / "plug_eligible_wells_9t.csv"
    wt.to_csv(w_csv, index=False)

    on_pad = wt[wt.pad_id.notna()]
    cnt = on_pad.pivot_table(index="pad_id", columns="elig_class", values="x", aggfunc="count", fill_value=0)
    for c in ("eligible", "ambiguous", "excluded"):
        if c not in cnt:
            cnt[c] = 0
    pt = pads[["pad_id", "complex_id"]].merge(cnt[["eligible", "ambiguous", "excluded"]].reset_index(), on="pad_id", how="left")
    pt[["eligible", "ambiguous", "excluded"]] = pt[["eligible", "ambiguous", "excluded"]].fillna(0).astype(int)
    pt["n_wells"] = pt[["eligible", "ambiguous", "excluded"]].sum(axis=1)
    pt["treated"] = (pt.eligible > 0) & (pt.ambiguous == 0)
    first_plug = on_pad[on_pad.elig_class == "eligible"].groupby("pad_id").plug_date.min()
    pt["first_eligible_plug"] = pt.pad_id.map(first_plug)
    rp = io.resolve(cfg.get("restoration_csv"))
    if rp is not None and rp.exists() and "PERMIT_NUM" in wt:
        R = pd.read_csv(rp)
        wt2 = wt.merge(R, left_on="PERMIT_NUM", right_on="permit_num", how="left")
        pt["dated_earthwork"] = pt.pad_id.map(wt2[wt2.earthwork.astype(str).str.lower() == "true"].groupby("pad_id").size()).fillna(0) > 0
        inputs.append(rp)
    else:
        pt["dated_earthwork"] = pd.NA
    ek.assert_unique(pt, "pad_id")
    p_csv = run_dir / "plug_eligible_pads_9t.csv"
    pt.to_csv(p_csv, index=False)

    n_treated = int(pt.treated.sum())
    minimum = int(el["min_eligible_pads"])
    counts = {"wells_in_box": int(len(wt)), "wells_by_class": wt.elig_class.value_counts().to_dict(),
              "reasons": wt.elig_reason.value_counts().to_dict(),
              "wells_on_pads_by_class": on_pad.elig_class.value_counts().to_dict(),
              "pads": int(len(pt)), "treated_pads": n_treated, "treated_complexes": int(pt[pt.treated].complex_id.nunique()),
              "pads_with_ambiguous": int((pt.ambiguous > 0).sum()), "min_eligible_pads": minimum,
              "bounds_methods": windows.method.value_counts().to_dict(),
              "readiness": "ready" if n_treated >= minimum else "STOP: eligible pads below the preregistered minimum"}
    js = run_dir / "plug_eligible_counts_9t.json"
    js.write_text(json.dumps(counts, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(run_dir, inputs=inputs, outputs=[w_csv, p_csv, js], params=el)
    return {"run_dir": run_dir, "wells": w_csv, "pads": p_csv, "counts": counts}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--windows", type=Path, default=None, help="flight_windows_9t.csv (default newest S0 run)")
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.windows)
    print(json.dumps(r["counts"], indent=2, default=str))
    if r["counts"]["readiness"] != "ready":
        print("STOP. Eligible n is below the minimum. Report and do not run S2 to S5 as confirmatory.")
        sys.exit(2)


if __name__ == "__main__":
    main()

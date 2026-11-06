"""4.3 stage V1. Observability of pads at 10, 20 and 30 m optical pixels (9t).

Purpose
    Per pad and pixel size. Pad area over pixel area. Count of pixels lying wholly inside the pad on a
    grid at grid_origin. Count of those interior pixels that are open (share of 1 m CHM cells below
    chm_open_max_m at least 0.5), because an index from a pixel under canopy reads canopy. Canopy
    overhang, the share of the inner edge band (edge_band_m) with CHM above chm_open_max_m. Usable
    scenes per season, a scene being usable when at least half its pixels carry a valid SCL class.
    Gate per pixel size. Success when the median open interior count is at least 4 and every season has
    at least 3 usable scenes. Failure when the median is under 1. Else inconclusive.
Inputs
    pads    truth/annotations_proj_v2.gpkg layer pad (held)
    chm     nine_t_1m/chm_9t_1m.tif (held)
    scenes  config scenes list (held Sentinel-2 5 m stacks) plus the optional scene index
Outputs (expansions/4_modalities/4_3_vegetation_stress/results/<YYYYMMDD>_vegstress_observe_<hash7>/)
    vegstress_observability_by_pad_9t.csv, vegstress_observability_9t.json, provenance
Run
    python expansions/4_modalities/4_3_vegetation_stress/src/_vegstress_observability_9t.py [--max-pads N]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _vegstress_shared_io as io
from _vegstress_shared_io import ek

SHORT = "vegstress_observe"


def scene_list(cfg: dict) -> pd.DataFrame:
    rows = [{"scene_id": s["scene_id"], "date": s["date"], "season": s["season"], "path": str(io.resolve(s["path"]))}
            for s in cfg["scenes"]]
    ip = io.resolve(cfg.get("scene_index"))
    if ip is not None and ip.exists():
        x = pd.read_csv(ip)
        x["path"] = [str(p if Path(p).is_absolute() else ip.parent / p) for p in x["path"]]
        rows += x[["scene_id", "date", "season", "path"]].to_dict("records")
    s = pd.DataFrame(rows)
    ek.assert_unique(s, "scene_id")
    return s


def scl_valid_frac(path: str, names: list[str], valid: list[int]) -> float:
    import rasterio
    with rasterio.open(path) as r:
        desc = [d.lower() if d else "" for d in r.descriptions]
        if "scl" not in desc:
            return float("nan")
        a = r.read(desc.index("scl") + 1)
    fin = np.isfinite(a)
    return float(np.isin(a[fin], valid).mean()) if fin.any() else 0.0


def pad_pixels(geom, p: float, origin, chm, chm_T, open_max: float) -> tuple[int, int]:
    """(whole interior pixels, open interior pixels) for one pad on a p-metre grid."""
    import shapely
    from rasterio.transform import rowcol
    x0, y0 = origin
    minx, miny, maxx, maxy = geom.bounds
    ii, jj = np.meshgrid(np.arange(np.floor((minx - x0) / p), np.floor((maxx - x0) / p) + 1),
                         np.arange(np.floor((miny - y0) / p), np.floor((maxy - y0) / p) + 1))
    xs, ys = x0 + ii.ravel() * p, y0 + jj.ravel() * p
    boxes = shapely.box(xs, ys, xs + p, ys + p)
    inside = shapely.contains(geom, boxes)
    n_in, n_open = int(inside.sum()), 0
    for bx, by in zip(xs[inside], ys[inside]):
        r0, c0 = rowcol(chm_T, bx, by + p)
        r1, c1 = rowcol(chm_T, bx + p, by)
        sub = chm[max(r0, 0):max(r1, 0), max(c0, 0):max(c1, 0)]
        sub = sub[np.isfinite(sub)]
        if sub.size and (sub < open_max).mean() >= 0.5:
            n_open += 1
    return n_in, n_open


def run(cfg: dict, out_root: Path | None = None, max_pads: int | None = None) -> dict:
    import rasterio
    from rasterio.windows import from_bounds, Window
    o = cfg["observability"]
    pin = cfg["inputs"]["pads"]
    pp = io.resolve(pin)
    pads = io.read_polys(pp, pin.get("layer"), pin["id_col"], "pad polygons").rename(columns={pin["id_col"]: "pad_id"})
    chm_p = io.need(io.resolve(cfg["inputs"]["chm"]), "CHM raster", "single band metres EPSG:6346")
    pads = io.within_raster(pads, chm_p)
    if max_pads:
        pads = pads.head(max_pads)
    scenes = scene_list(cfg)
    run_dir = ek.new_run(io.EXP, SHORT, {"observability": o, "n_pads": len(pads), "scenes": scenes["scene_id"].tolist()},
                         base=out_root, why="V1 observability.")
    rows = []
    with rasterio.open(chm_p) as s:
        ek.assert_crs(s, "EPSG:6346")
        for pid, geom in zip(pads["pad_id"], pads.geometry):
            b = geom.buffer(max(o["pixels_m"])).bounds
            try:
                w = from_bounds(*b, transform=s.transform).round_offsets().round_lengths().intersection(
                    Window(0, 0, s.width, s.height))
                chm = s.read(1, window=w, masked=True).astype(float).filled(np.nan)
                T = s.window_transform(w)
            except Exception:  # noqa: BLE001 - pad outside CHM
                chm, T = None, None
            r = {"pad_id": pid, "area_m2": geom.area}
            for p in o["pixels_m"]:
                tag = f"{int(p)}m"
                r[f"area_px_{tag}"] = geom.area / p ** 2
                if chm is None:
                    r[f"interior_px_{tag}"], r[f"open_px_{tag}"] = np.nan, np.nan
                else:
                    r[f"interior_px_{tag}"], r[f"open_px_{tag}"] = pad_pixels(geom, p, o["grid_origin"], chm, T,
                                                                               o["chm_open_max_m"])
            if chm is not None:
                band = geom.difference(geom.buffer(-o["edge_band_m"]))
                v = io.weighted_mean((chm > o["chm_open_max_m"]).astype(float) + np.where(np.isfinite(chm), 0, np.nan),
                                     T, band) if not band.is_empty else {"mean": np.nan}
                r["edge_overhang_frac"] = v["mean"]
            else:
                r["edge_overhang_frac"] = np.nan
            rows.append(r)
    df = pd.DataFrame(rows)
    ek.assert_rows(df, len(pads), "pads to observability rows")
    scenes["valid_frac"] = [scl_valid_frac(p, cfg["band_names"], cfg["scl_valid"]) if Path(p).exists() else np.nan
                            for p in scenes["path"]]
    scenes["usable"] = scenes["valid_frac"] >= 0.5
    by_season = scenes[scenes.usable].groupby("season").size().reindex(
        sorted(set(scenes["season"]) | {"leaf_on", "leaf_off", "shoulder"}), fill_value=0).to_dict()
    seasons_ok = all(v >= o["min_scenes_per_season"] for v in by_season.values())
    gates = {}
    for p in o["pixels_m"]:
        med = float(df[f"open_px_{int(p)}m"].median())
        v = ("failure" if med < o["fail_interior_px"] else
             "success" if med >= o["min_interior_px"] and seasons_ok else "inconclusive")
        gates[f"{int(p)}m"] = {"median_interior_px": float(df[f"interior_px_{int(p)}m"].median()),
                               "median_open_interior_px": med,
                               "share_pads_ge_min": float((df[f"open_px_{int(p)}m"] >= o["min_interior_px"]).mean()),
                               "verdict": v}
    summary = {"stage": "V1", "n_pads": int(len(df)), "n_pads_on_chm": int(df["edge_overhang_frac"].notna().sum()),
               "median_area_m2": float(df["area_m2"].median()), "median_edge_overhang_frac": float(df["edge_overhang_frac"].median()),
               "usable_scenes_by_season": by_season, "seasons_ok": seasons_ok, "per_pixel_size": gates,
               "scenes": scenes.to_dict("records")}
    out_c = run_dir / "vegstress_observability_by_pad_9t.csv"
    out_j = run_dir / "vegstress_observability_9t.json"
    df.to_csv(out_c, index=False)
    out_j.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return io.finish(run_dir, summary, inputs=[pp, chm_p], outputs=[out_c, out_j], params=o)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--max-pads", type=int, default=None)
    a = ap.parse_args()
    s = run(io.load_config(a.config), a.out_root, a.max_pads)
    print(json.dumps({k: s[k] for k in ("per_pixel_size", "usable_scenes_by_season", "median_edge_overhang_frac", "run_dir")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()

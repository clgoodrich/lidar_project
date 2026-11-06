"""6.1 S1. Eligibility and blind-zone mask per block.

Purpose
    Decide per block whether the inventory had a chance to see a surface feature. A block is eligible when its
    mean ground density meets the stated rule and its void fraction (cells with no ground return) is at or under
    the declared limit. Both cuts are a chosen eligibility rule, not the QL2 definition. Canopy class and
    annotation status are recorded per block but do not cut.
Inputs
    blocks          data/9t/derived/05/pit_blocks_9t.gpkg (layer blocks)            held
    ground_density  data/9t/derived/05/ground_density_9t_05.tif (returns per cell)   held
    chm             data/9t/derived/05/chm_9t_05.tif                                held
    annotation      data/9t/results/transfer/transfer_blocks.csv                   assumed (3.0), optional
Outputs (in the run folder data/9t/results/screening/<run_id>/ unless --out)
    screen_eligible_mask_9t.gpkg   layers blocks, eligible, blind_zone
    screen_eligible_summary_9t.json  counts, cut values and the reason for each cut
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_eligible_mask_9t.py [--out DIR] [--profile co2]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _co2_screen_lib as L
from _co2_screen_lib import ek


def block_stats(blocks, dens_path: Path, chm_path: Path | None, canopy_h: float):
    """Windowed zonal stats per block. Returns a DataFrame keyed by block_id."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds
    rows = []
    with rasterio.open(dens_path) as dr:
        if L.horizontal_epsg(dr.crs) != L.horizontal_epsg(blocks.crs):
            raise AssertionError(f"ground density CRS {dr.crs} != blocks {blocks.crs}")
        cell_m2 = abs(dr.res[0] * dr.res[1])
        cr = rasterio.open(chm_path) if chm_path else None
        if cr is not None and (cr.transform != dr.transform or cr.shape != dr.shape):
            raise AssertionError("CHM and ground density grids differ")
        for b in blocks.itertuples():
            win = from_bounds(*b.geometry.bounds, transform=dr.transform).round_offsets().round_lengths()
            cnt = dr.read(1, window=win, boundless=True, fill_value=0).astype(np.float64)
            inside = geometry_mask([b.geometry], out_shape=cnt.shape, transform=dr.window_transform(win), invert=True)
            n = int(inside.sum())
            if n == 0:
                rows.append({"block_id": b.block_id, "n_cells": 0})
                continue
            c = cnt[inside]
            r = {"block_id": b.block_id, "n_cells": n,
                 "ground_density_pts_m2": float(c.sum() / (n * cell_m2)),
                 "void_frac": float((c == 0).mean())}
            if cr is not None:
                h = cr.read(1, window=win, boundless=True, fill_value=cr.nodata).astype(np.float64)[inside]
                h = h[h != cr.nodata]
                r["canopy_share"] = float((h > canopy_h).mean()) if len(h) else np.nan
            rows.append(r)
        if cr is not None:
            cr.close()
    return pd.DataFrame(rows)


def classify(st: pd.DataFrame, p: dict) -> pd.DataFrame:
    st = st.copy()
    st["cut_density"] = st["ground_density_pts_m2"].fillna(0) < p["min_ground_density_pts_m2"]
    st["cut_void"] = st["void_frac"].fillna(1) > p["max_void_frac"]
    st["eligible"] = ~(st.cut_density | st.cut_void)
    if "canopy_share" in st:
        st["canopy_class"] = np.where(st.canopy_share.isna(), "unknown",
                                      np.where(st.canopy_share >= p["closed_canopy_share"], "closed",
                                               np.where(st.canopy_share >= 0.2, "mixed", "open")))
    st["reason"] = np.where(st.eligible, "eligible",
                            np.where(st.cut_density & st.cut_void, "low ground density and high void fraction",
                                     np.where(st.cut_density, "low ground density", "high void fraction")))
    return st


def build(cfg: dict, prof: dict, out_dir: Path, overrides: dict | None = None) -> dict:
    o = overrides or {}
    p = cfg["params"]
    bspec = cfg["inputs"]["blocks"]
    blocks = L.read_vector(L.input_path(cfg, "blocks", o.get("blocks")), cfg["crs"], layer=bspec.get("layer"))
    ek.assert_unique(blocks, "block_id")
    ek.assert_no_nan(blocks.block_id, "block_id")
    st = block_stats(blocks, L.input_path(cfg, "ground_density", o.get("ground_density")),
                     L.input_path(cfg, "chm", o.get("chm"), required=False), p["canopy_height_m"])
    ek.assert_rows(st, len(blocks), "block stats")
    st = classify(st, p)
    ann = L.input_path(cfg, "annotation_status", o.get("annotation_status"), required=False)
    if ann is not None:
        a = pd.read_csv(ann)[["block_id", "annotation_status"]]
        st = st.merge(a, on="block_id", how="left")
        ek.assert_rows(st, len(blocks), "annotation join")
    else:
        st["annotation_status"] = "unknown (3.0 transfer_blocks.csv not built)"
    g = blocks[["block_id", "geometry"]].merge(st, on="block_id", how="left")
    g["evidence_level"] = "coverage"
    area = cfg["area"]
    gpkg = out_dir / f"screen_eligible_mask_{area}.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    g.to_file(gpkg, layer="blocks", driver="GPKG")
    for name, sel in (("eligible", g.eligible), ("blind_zone", ~g.eligible)):
        part = g[sel]
        dis = part.dissolve(by="evidence_level").reset_index() if len(part) else part
        dis = dis[["evidence_level", "geometry"]] if len(dis) else g.iloc[:0][["evidence_level", "geometry"]]
        dis.to_file(gpkg, layer=name, driver="GPKG")
    tot = float(g.area.sum())
    summ = {"n_blocks": int(len(g)), "n_eligible": int(g.eligible.sum()), "n_blind": int((~g.eligible).sum()),
            "eligible_km2": float(g[g.eligible].area.sum() / 1e6), "total_km2": tot / 1e6,
            "eligible_share_area": float(g[g.eligible].area.sum() / tot) if tot else float("nan"),
            "rule": {"min_ground_density_pts_m2": p["min_ground_density_pts_m2"], "max_void_frac": p["max_void_frac"]},
            "rule_note": "A chosen eligibility rule. It is not the QL2 definition. Density is measured per block.",
            "reasons": g["reason"].value_counts().to_dict(),
            "void_frac_overall": float((g.void_frac * g.n_cells).sum() / g.n_cells.sum())}
    js = out_dir / f"screen_eligible_summary_{area}.json"
    js.write_text(json.dumps(summ, indent=2), encoding="utf-8")
    return {"gpkg": gpkg, "json": js, "summary": summ}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", default=None, help="run folder (default data/<area>/results/screening/<run_id>/)")
    ap.add_argument("--blocks", default=None)
    ap.add_argument("--ground-density", default=None)
    ap.add_argument("--chm", default=None)
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out = L.run_dir(cfg, prof, a.out)
    r = build(cfg, prof, out, {"blocks": a.blocks, "ground_density": a.ground_density, "chm": a.chm})
    ek.write_provenance(out, inputs=[L.input_path(cfg, "ground_density", a.ground_density)],
                        outputs=[r["gpkg"], r["json"]], params=cfg["params"])
    print(json.dumps(r["summary"], indent=2))
    print(f"wrote {r['gpkg']}\nwrote {r['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

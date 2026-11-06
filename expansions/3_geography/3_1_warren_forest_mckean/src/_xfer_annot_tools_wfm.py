"""3.1 S4 and S6. Blind annotation package, block timing log, and annotator agreement.

Purpose
    Annotation is a people step. This script prepares and checks it.
    package    Writes a blind package for the test blocks. One GeoPackage with the block
               outlines (test and recheck flags only, no role of other blocks, no scores) and
               empty layers pit_inside, pit_full and pad in EPSG:6346 for the reviewer to draw
               in. An exposure log CSV, one row per block and reviewer, to be filled in. The
               package is refused if any model output or well record sits in the package
               folder (file-name and layer-name scan).
    timing     Appends one timed block (reviewer, minutes, features drawn) to the timing log
               and reports minutes per block and projected reviewer-hours (S4).
    agreement  IoU-matched recall between two independent annotations of the recheck blocks
               (S6 completeness). Reported both ways. A reproducibility reference, not a ceiling.

Inputs
    S1 roles     results/tables/<area>/xfer_blocks_roles_<area>.gpkg
    agreement    assumed.truth and assumed.truth_recheck (config), or --a / --b paths

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/data/interim/<area>/annot_package/
        xfer_annot_blocks_<area>.gpkg, xfer_exposure_log_<area>.csv
    .../results/tables/<area>/xfer_annot_timing_<area>.csv
    .../results/tables/<area>/xfer_annot_agreement_<area>.json

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_annot_tools_wfm.py package --area warren
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_annot_tools_wfm.py timing --area warren --block 40 --reviewer R1 --minutes 18 --features 3
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_annot_tools_wfm.py agreement --area warren --layer pit_inside
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"
FORBIDDEN = re.compile(r"(prob|score|cand|pred|argmax|wells?|dep_|record)", re.I)
LAYERS = {"pit_inside": "pit_inside_id", "pit_full": "pit_inside_id", "pad": "pad_id"}


def empty_layer(name, crs=ek.DST_CRS):
    import geopandas as gpd
    return gpd.GeoDataFrame({LAYERS[name]: pd.Series(dtype="int64"), "reviewer": pd.Series(dtype="str"),
                             "class": pd.Series(dtype="str")}, geometry=[], crs=crs)


def build_package(blocks, out_dir: Path, area: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = [p.name for p in out_dir.iterdir() if FORBIDDEN.search(p.name)]
    if bad:
        raise AssertionError(f"blind package folder holds model or record files: {bad}")
    t = blocks[blocks.role == "test"][["block_id", "recheck", "geometry"]].copy()
    gp = out_dir / f"xfer_annot_blocks_{area}.gpkg"
    t.to_file(gp, layer="test_blocks", driver="GPKG")
    for name in LAYERS:
        empty_layer(name).to_file(gp, layer=name, driver="GPKG")
    from pyogrio import list_layers
    names = [n for n, _ in list_layers(str(gp))]
    leak = [n for n in names if FORBIDDEN.search(n)]
    if leak:
        raise AssertionError(f"package layers leak model output: {leak}")
    log = out_dir / f"xfer_exposure_log_{area}.csv"
    if not log.exists():
        pd.DataFrame({"block_id": t.block_id, "reviewer": "", "saw_model_output": "", "saw_well_points": "",
                      "saw_9t_outputs_for_area": "", "date": "", "notes": ""}).to_csv(log, index=False)
    return gp, log, len(t)


def agreement(a, b, blocks, tau=xl.IOU_TAU, id_col="truth_id"):
    """IoU-matched recall of b against a and a against b, inside the recheck blocks."""
    rb = blocks[blocks.recheck.astype(bool)][["block_id", "geometry"]]
    a = a.copy(); b = b.copy()
    a[id_col] = np.arange(len(a)); b[id_col] = np.arange(len(b))
    a = a[a.geometry.representative_point().within(rb.geometry.union_all())]
    b = b[b.geometry.representative_point().within(rb.geometry.union_all())]
    b2 = b.assign(score=1.0, cand_id=b[id_col])
    m = xl.match_iou(a, b2, tau=tau, truth_id=id_col)
    k = int(m.notna().sum())
    return {"n_a": int(len(a)), "n_b": int(len(b)), "matched": k,
            "recall_b_vs_a": k / len(a) if len(a) else np.nan, "recall_a_vs_b": k / len(b) if len(b) else np.nan,
            "ci_b_vs_a": ek.clopper_pearson(k, len(a))[1:] if len(a) else None,
            "n_recheck_blocks": int(len(rb)), "tau": tau}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["package", "timing", "agreement"])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--block", type=int)
    ap.add_argument("--reviewer")
    ap.add_argument("--minutes", type=float)
    ap.add_argument("--features", type=int)
    ap.add_argument("--layer", default="pit_inside")
    ap.add_argument("--a", default=None, help="first annotation gpkg (default assumed.truth)")
    ap.add_argument("--b", default=None, help="second annotation gpkg (default assumed.truth_recheck)")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    import geopandas as gpd
    roles = xl.need(ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg", "S1 roles", "run _xfer_blocks_roles_wfm.py")
    blocks = gpd.read_file(roles, layer="blocks")
    if a.cmd == "package":
        out = xl.resolve_path({"exp": cfg["exp_id"], "rel": f"data/interim/{a.area}/annot_package"})
        gp, log, n = build_package(blocks, out, a.area)
        print(f"{n} test blocks\nwrote {gp}\n      {log}")
    elif a.cmd == "timing":
        if None in (a.block, a.reviewer, a.minutes, a.features):
            ap.error("timing needs --block --reviewer --minutes --features")
        p = ctx["tables"] / f"xfer_annot_timing_{a.area}.csv"
        row = pd.DataFrame([{"date": dt.date.today().isoformat(), "block_id": a.block, "reviewer": a.reviewer,
                             "minutes": a.minutes, "features": a.features}])
        log = pd.concat([pd.read_csv(p), row]) if p.exists() else row
        log.to_csv(p, index=False)
        n_test = int((blocks.role == "test").sum())
        mpb = log.minutes.mean()
        print(f"{len(log)} timed blocks, {mpb:.1f} min per block. {n_test} test blocks x 2 reviewers "
              f"+ {int(blocks.recheck.sum())} rechecks = {(2 * n_test + blocks.recheck.sum()) * mpb / 60:.1f} reviewer-hours")
        print(f"wrote {p}")
    else:
        from _common import read_layer
        pa = Path(a.a) if a.a else xl.assumed_path(cfg, "truth", a.area)
        pb = Path(a.b) if a.b else xl.assumed_path(cfg, "truth_recheck", a.area)
        res = agreement(read_layer(pa, a.layer).to_crs(ek.DST_CRS), read_layer(pb, a.layer).to_crs(ek.DST_CRS), blocks)
        res.update({"layer": a.layer, "a": str(pa), "b": str(pb)})
        o = ctx["tables"] / f"xfer_annot_agreement_{a.area}.json"
        o.write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
        print(json.dumps(res, indent=2, default=float))
        print(f"wrote {o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

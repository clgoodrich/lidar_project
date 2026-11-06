"""3.1 S7a. Frozen inference on a target 0.5 m stack (declared ensemble policy, run once).

Purpose
    Applies the declared model policy (mean class probability over the five fold checkpoints)
    to the target stack built by S3. mu and sd come from each checkpoint, never from the
    target. The stack's band descriptions must equal each checkpoint's channel order.
    Checkpoints are the P1 isolated set (assumed). --allow-cv5 uses the original CV5 set and
    labels every output provisional (original sampler, protocol section 3).
    Nothing is tuned here. No threshold is chosen. The probability raster is the only output.

Inputs
    features   data/processed/<area>/05/features_pit_<area>_05.tif (S3, heavy)
    ckpts      assumed.isolated_ckpt, or with --allow-cv5 data/9t/models/{pit,pad}/unet_cv5/fold{k}/best.pt

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/data/processed/<area>/05/<task>_prob_ens_<area>_05.tif  (heavy, gitignored)
    expansions/3_geography/3_1_warren_forest_mckean/results/<run_id>/_PROVENANCE.json, _RUN.md, xfer_infer_<task>_<area>.json

Run (GPU, minutes per window; not run by the build agent)
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_frozen_infer_wfm.py --area warren --task pit
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_frozen_infer_wfm.py --area mckean --task pad --allow-cv5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"


def ckpt_paths(cfg, task, allow_cv5):
    M = cfg["models"]
    try:
        xl.assumed_path(cfg, "isolated_ckpt", task=task, k=0)
        spec, prov = str(xl.resolve_path(cfg["assumed"]["isolated_ckpt"]["spec"])), False
        paths = [Path(spec.format(task=task, k=k)) for k in range(M["n_folds"])]
    except xl.MissingInput:
        if not allow_cv5:
            raise
        prov = True
        c = M[task]["cv5"]
        paths = [xl.resolve_path({**c, "rel": c["rel"].format(k=k)}) for k in range(M["n_folds"])]
    for p in paths:
        xl.need(p, f"{task} checkpoint")
    return paths, prov


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--task", choices=["pit", "pad"], default="pit")
    ap.add_argument("--features", default=None, help="override the S3 stack path")
    ap.add_argument("--allow-cv5", action="store_true")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    feats = Path(a.features) if a.features else ctx["heavy"] / f"features_pit_{a.area}_05.tif"
    xl.need(feats, f"S3 feature stack for {a.area}", "run _xfer_build_derivs_wfm.py --execute")
    ckpts, prov = ckpt_paths(cfg, a.task, a.allow_cv5)
    M = cfg["models"][a.task]
    run = ek.new_run(cfg["exp_id"], f"xfer_infer_{a.task}_{a.area}",
                     {"area": a.area, "task": a.task, "ckpts": [str(c) for c in ckpts], "features": str(feats)},
                     why="S7a frozen inference, declared ensemble policy.")
    prob, prof, meta = xl.ensemble_prob(feats, ckpts, n_classes=M["n_classes"], patch=M["patch"],
                                        overlap=M["overlap"], cls=M["cls"])
    import rasterio
    out = ctx["heavy"] / f"{a.task}_prob_ens_{a.area}_05.tif"
    pr = dict(prof)
    pr.update(count=1, dtype="float32", nodata=-1.0, compress="deflate", predictor=2, BIGTIFF="IF_SAFER")
    with rasterio.open(out, "w", **pr) as d:
        d.write(prob, 1)
        d.set_band_description(1, f"{a.task}_prob_{cfg['models']['policy']}")
    rec = {"area": a.area, "task": a.task, "policy": cfg["models"]["policy"], "provisional_cv5": prov,
           "ckpts": meta, "prob": str(out), "prob_mean": float(np.nanmean(prob))}
    (run / f"xfer_infer_{a.task}_{a.area}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    ek.write_provenance(run, inputs=[feats, *ckpts], outputs=[out], params=rec, hash_limit_mb=500)
    print(json.dumps(rec, indent=2))
    print(f"wrote {out}\n      {run}\nRun the >100 MB audit (CLAUDE.md Large-file rule) now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

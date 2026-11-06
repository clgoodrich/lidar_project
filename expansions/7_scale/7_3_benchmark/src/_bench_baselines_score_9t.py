"""Clip baseline predictions to dev-test tiles, ship them, and score them (7.3 S3).

Purpose
    For each baseline in config_7_3.json whose fold rasters exist, clip every dev-test block from the
    fold raster of the fold that held that block out, read from the model's own split file. Pit and pad
    folds differ, so one fold number cannot serve both. Write the clips into the release and score the
    shipped clips with the official scorer. The fresh-checkout test reruns
    exactly these commands, so the shipped numbers must come from the shipped files.
    Baselines whose rasters are absent are listed as missing, not scored.

Inputs
    release folder from _bench_export_release_9t.py (splits, labels/labels_devtest.gpkg, blocks/blocks_devtest.gpkg)
    fold rasters path_for("models") / <baseline rel with {k}>   (pit_unet_cv5 and pad_unet_cv5_iso are held)
Outputs
    <release>/baselines/preds/<model>/blk<id>.tif     float32 clips, nodata -1
    <release>/baselines/<model>_score.json, <model>_cands.csv, <model>_blocks.csv
    <release>/baselines/baseline_scores.csv           one row per scored baseline
    <release>/baselines/baseline_commands.json         scorer argv relative to the release root

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_baselines_score_9t.py --B 2000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_evaluate_recall_k as sc  # noqa: E402
from _bench_export_release_9t import CFG, cfg_path, load_cfg, write_manifest  # noqa: E402

TASK_LAYER = {"pit_floor": "pit_floor", "pad": "pad"}


def clip(src: Path, bounds, out: Path) -> None:
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open(src) as r:
        ek.assert_crs(r, "EPSG:6346")
        w = from_bounds(*bounds, transform=r.transform).round_offsets().round_lengths()
        a = r.read(1, window=w, boundless=True, fill_value=-1).astype(np.float32)
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = -1
        prof = dict(driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype="float32", crs=r.crs,
                    transform=r.window_transform(w), nodata=-1, compress="deflate", predictor=3)
    with rasterio.open(out, "w", **prof) as o:
        o.write(a, 1)


def held_out_fold(b: dict) -> dict:
    """{block_id: fold that held it out} from the baseline's own split file."""
    sp = ek.path_for(b["split_file"]["key"]) / b["split_file"]["rel"]
    if not sp.exists():
        return {}
    h = pd.read_csv(sp)
    h = h[h["role"].astype(str).str.startswith("held")].dropna(subset=["block_id"])
    if h["block_id"].duplicated().any():
        raise AssertionError(f"{sp}: a block is held out by two folds")
    return dict(zip(h["block_id"].astype(int), h["fold"].astype(int)))


def run(cfg: dict, root: Path, B: int, only: list[str] | None = None) -> pd.DataFrame:
    import geopandas as gpd
    split = json.loads(next((root / "splits").glob("splits_*.json")).read_text())
    k_dev = int(split["devtest_fold"])
    bdev = gpd.read_file(root / "blocks" / "blocks_devtest.gpkg")
    lab = root / "labels" / "labels_devtest.gpkg"
    out = root / "baselines"
    (out / "preds").mkdir(parents=True, exist_ok=True)
    sp = cfg["scorer"]
    rows, cmds = [], {}
    for name, b in cfg["baselines"].items():
        if name.startswith("_"):
            continue
        if only and name not in only:
            continue
        fold_of = held_out_fold(b)
        need_k = {fold_of.get(int(x)) for x in bdev["block_id"]}
        if None in need_k:
            rows.append({"model": name, "task": b["task"], "status": "some dev-test blocks are held out by no fold of this model"})
            continue
        srcs = {k: ek.path_for(b["fold_raster"]["key"]) / b["fold_raster"]["rel"].format(k=k) for k in sorted(need_k)}
        miss = [str(p) for p in srcs.values() if not p.exists()]
        if miss:
            rows.append({"model": name, "task": b["task"], "status": f"missing {miss[0]}"})
            continue
        pdir = out / "preds" / name
        pdir.mkdir(parents=True, exist_ok=True)
        specs = []
        for _, r in bdev.sort_values("block_id").iterrows():
            p = pdir / f"blk{int(r['block_id']):04d}.tif"
            clip(srcs[fold_of[int(r["block_id"])]], r.geometry.bounds, p)
            specs.append(p.relative_to(root).as_posix())
        argv = ["--pred", *specs, "--labels", lab.relative_to(root).as_posix(), "--layer", TASK_LAYER[b["task"]],
                "--blocks", "blocks/blocks_devtest.gpkg", "--out", f"baselines/{name}_score.json",
                "--candidates-out", f"baselines/{name}_cands.csv", "--blocks-out", f"baselines/{name}_blocks.csv",
                "--B", str(B), "--seed", str(sp["seed"]), "--task", b["task"], "--mode", sp.get("mode", "primary")]
        cmds[name] = argv
        import os
        cwd = os.getcwd()
        try:
            os.chdir(root)
            rc = sc.main(argv)
        finally:
            os.chdir(cwd)
        if rc != 0:
            rows.append({"model": name, "task": b["task"], "status": f"scorer rc {rc}"})
            continue
        s = json.loads((out / f"{name}_score.json").read_text())
        rows.append({"model": name, "task": b["task"], "status": "scored", "note": b.get("note", ""),
                     "eval_set": f"devtest (release fold {k_dev}), out-of-fold per the model's own split", "recall": s["recall"], "lo": s["ci95"][0],
                     "hi": s["ci95"][1], "k": s["k"], "hits": s["hits"], "n_truth": s["n_truth"],
                     "n_blocks": s["n_blocks"], "truth_per_km2": s["truth_density_per_km2"],
                     "cutoff": s["policy"]["cutoff"], "match_order": s["policy"]["match_order"],
                     "policy_version": s["policy"]["version"], "policy_hash": s["policy"]["policy_hash"],
                     "bootstrap_undefined_share": s["bootstrap_undefined_share"], "evidence_level": "a"})
    df = pd.DataFrame(rows)
    df.to_csv(out / "baseline_scores.csv", index=False, float_format="%.10g", lineterminator="\n")
    (out / "baseline_commands.json").write_text(json.dumps(cmds, indent=2), encoding="utf-8")
    write_manifest(root)
    return df


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score baselines on shipped dev-test clips (7.3 S3).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--release", default=None)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    root = Path(a.release) if a.release else cfg_path(cfg["release_root"]) / cfg["release_name"]
    if not (root / "blocks" / "blocks_devtest.gpkg").exists():
        print(f"missing release dev-test blocks under {root}. Run the export first.", file=sys.stderr)
        return 2
    print(run(cfg, root, a.B, a.only).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

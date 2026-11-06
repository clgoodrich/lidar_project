"""3.0 S2 new baseline and mosaic check. Score 9t out-of-fold predictions twice from a clean state and compare.

Purpose
    New baseline. Build the out-of-fold mosaic from the per-fold probability rasters of one model family
    (each block takes the probability of the fold model that held it out, P1 split file), as float32 so
    scores are not quantised. Then run the frozen scorer (`_transfer_score_run.py`) twice, each in a fresh
    Python process with the same settings, into two separate run folders. The gate is exact repetition. The
    score JSON (volatile fields removed) and the per-block CSV must be byte-identical.
    Mosaic check (`--mosaic-check`). Score the saved uint8 mosaic (DN / 254) once and report the gap to the
    archival rebuilt recall at the same K. Quantisation and fold seams are expected to differ. Not gated.
    Neither check is a transfer result.

Inputs
    per-fold rasters from config_3_0.json reference_9t.<task>.fold_rasters (pad iso held, pit iso after P1 S6)
    P1 split file (--splits), blocks and truth from config_3_0.json reference_9t.<task>
    archival result expansions/3_geography/3_0_transfer_protocol/results/tables/transfer_archival_check_9t.json

Outputs
    expansions/3_geography/3_0_transfer_protocol/data/interim/<task>_prob_oof_mosaic_9t.tif (float32, over 100 MB, gitignored folder)
    <out-dir>/transfer_baseline_repeat_<task>_9t.json  verdict and the two run folders
    <out-dir>/transfer_mosaic_check_<task>_9t.json     mosaic recall, archival recall, gap
    Default out-dir expansions/3_geography/3_0_transfer_protocol/results/tables/
    The scorer run folders go under C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/transfer/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_baseline_repeat_9t.py --task pad --splits data/9t/results/splits/cv_splits_future_9t_v1.json --fold-rasters "data/9t/models/pad/unet_cv5_iso/fold{k}/pad_prob_cvfold{k}_9t_05.tif"
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_baseline_repeat_9t.py --task pit --mosaic-check
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))
VOLATILE = ("settings", "prereg")


def ref_path(task: str, name: str) -> Path:
    s = CFG["reference_9t"][task][name]
    return ek.path_for(s["key"]) / s["rel"]


def truth_spec(task: str) -> tuple[str, str]:
    s = CFG["reference_9t"][task]["truth"]
    return f"{ek.path_for(s['key']) / s['rel']}:{s['layer']}", s["id"]


def build_mosaic(fold_pattern: str, splits: Path, blocks_path: Path, task: str, dst: Path) -> Path:
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    doc = json.loads(Path(splits).read_text(encoding="utf-8"))["tasks"][task]["folds"]
    blocks = gpd.read_file(blocks_path, layer="blocks")
    mosaic, prof = None, None
    for f, roles in sorted(doc.items()):
        p = Path(fold_pattern.format(k=f))
        if not p.exists():
            raise SystemExit(f"fold raster missing: {p}")
        with rasterio.open(p) as r:
            ek.assert_crs(r)
            a = r.read(1).astype(np.float32)
            if r.dtypes[0] == "uint8":
                a = np.where(a == 255, np.nan, a / 254.0)
            elif r.nodata is not None:
                a[a == r.nodata] = np.nan
            if prof is None:
                prof = r.profile.copy()
                mosaic = np.full(a.shape, np.nan, np.float32)
            elif a.shape != mosaic.shape or r.transform != prof["transform"]:
                raise AssertionError(f"{p} grid differs from fold 0")
        hm = rasterize([(g, 1) for g in blocks[blocks.block_id.astype(int).isin(roles["held_out"])].geometry],
                       out_shape=a.shape, transform=prof["transform"], fill=0, dtype="uint8").astype(bool)
        mosaic[hm] = a[hm]
    prof.update(dtype="float32", nodata=np.nan, count=1, compress="deflate", predictor=2, tiled=True, BIGTIFF="YES",
                blockxsize=256, blockysize=256)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst, "w", **prof) as d:
        d.write(mosaic, 1)
    return dst


def score_fresh(args: list[str], out_base: Path) -> Path:
    cmd = [sys.executable, str(HERE.parent / "_transfer_score_run.py"), *args, "--out-base", str(out_base)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-3000:])
    line = [x for x in r.stdout.splitlines() if x.startswith("run folder ")][-1]
    return Path(line[len("run folder "):].strip())


def stable(js: Path) -> str:
    d = json.loads(js.read_text(encoding="utf-8"))
    for k in VOLATILE:
        d.pop(k, None)
    return json.dumps(d, sort_keys=True)


def repeat(args: list[str], base: Path, area: str = "9t") -> dict:
    r1, r2 = score_fresh(args, base / "repeat_a"), score_fresh(args, base / "repeat_b")
    same_json = stable(r1 / f"transfer_score_{area}.json") == stable(r2 / f"transfer_score_{area}.json")
    same_csv = (r1 / f"transfer_blocks_{area}.csv").read_bytes() == (r2 / f"transfer_blocks_{area}.csv").read_bytes()
    return {"run_a": str(r1), "run_b": str(r2), "json_identical": same_json, "blocks_csv_identical": same_csv,
            "gate": "pass" if same_json and same_csv else "fail"}


def main(argv=None) -> int:
    d = CFG["scoring_defaults"]
    ap = argparse.ArgumentParser(description="3.0 S2 new baseline repeat and mosaic check")
    ap.add_argument("--task", choices=("pit", "pad"), required=True)
    ap.add_argument("--splits", type=Path, default=None, help="P1 split file")
    ap.add_argument("--fold-rasters", default=None, help="pattern with {k}. Default config fold_rasters")
    ap.add_argument("--prob", type=Path, default=None, help="score this raster instead of building a mosaic")
    ap.add_argument("--k", type=float, default=d["k_per_km2"])
    ap.add_argument("--k-rule", choices=("global", "per_group"), default="per_group")
    ap.add_argument("--seed", type=int, default=d["seed"])
    ap.add_argument("--mosaic-check", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--runs-base", type=Path, default=None, help="parent of the scorer run folders. Default data/9t/results/transfer/")
    a = ap.parse_args(argv)
    out = a.out_dir or ek.sub("3.0", "results/tables")
    out.mkdir(parents=True, exist_ok=True)
    truth, tid = truth_spec(a.task)
    blocks = ref_path(a.task, "blocks")
    base = a.runs_base or (ek.area_dir("9t") / "results" / "transfer")
    common = ["--area", "9t", "--task", a.task, "--blocks", str(blocks), "--truth", truth, "--truth-id", tid,
              "--k", str(a.k), "--seed", str(a.seed)]
    if a.mosaic_check:
        if a.task != "pit":
            raise SystemExit("the saved uint8 mosaic exists for pits only")
        prob = ref_path("pit", "prob")
        grp = ["--k-rule", a.k_rule] + (["--groups", str(a.splits)] if a.k_rule == "per_group" else [])
        if a.k_rule == "per_group" and not a.splits:
            raise SystemExit("--k-rule per_group needs --splits")
        rd = score_fresh(common + ["--prob", str(prob)] + grp, base / "mosaic_check")
        s = json.loads((rd / "transfer_score_9t.json").read_text(encoding="utf-8"))
        arch = ek.sub("3.0", "results/tables") / "transfer_archival_check_9t.json"
        ar = json.loads(arch.read_text())["results"]["pit"].get(str(int(a.k)), {}).get("rebuilt", {}) if arch.exists() else {}
        doc = {"check": "mosaic", "run": str(rd), "mosaic_recall": s["primary"]["recall"],
               "mosaic_interval": [s["primary"]["lo"], s["primary"]["hi"]], "archival_recall": ar.get("recall"),
               "gap": (s["primary"]["recall"] - ar["recall"]) if ar else None, "gated": False,
               "cutoff": json.loads((rd / "transfer_score_9t.json").read_text())["params"]["cutoff"],
               "note": "uint8 DN/254 quantisation and fold seams can differ. The proposal cutoff must equal the sweep's."}
        js = out / "transfer_mosaic_check_pit_9t.json"
        js.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        print(json.dumps(doc, indent=1))
        return 0
    if a.prob is None:
        if not a.splits or not a.splits.exists():
            raise SystemExit("--splits (P1 S2 split file) is required to build the out-of-fold mosaic")
        pat = a.fold_rasters or str(ref_path(a.task, "fold_rasters")).replace("%7Bk%7D", "{k}")
        a.prob = build_mosaic(pat, a.splits, blocks, a.task, ek.sub("3.0", "data/interim") / f"{a.task}_prob_oof_mosaic_9t.tif")
    grp = ["--k-rule", a.k_rule] + (["--groups", str(a.splits)] if a.k_rule == "per_group" else [])
    res = repeat(common + ["--prob", str(a.prob)] + grp, base / f"baseline_{a.task}")
    res.update(prob=str(a.prob), prob_sha256=ek.sha256(a.prob), k=a.k, k_rule=a.k_rule, label="new baseline")
    js = out / f"transfer_baseline_repeat_{a.task}_9t.json"
    js.write_text(json.dumps(res, indent=1), encoding="utf-8")
    run = ek.new_run("3.0", f"baseline_repeat_{a.task}", {k: str(v) for k, v in vars(a).items()}, why="S2 new baseline repeat.")
    ek.write_provenance(run, inputs=[a.prob] + ([a.splits] if a.splits else []), outputs=[js])
    print(json.dumps(res, indent=1))
    return 0 if res["gate"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

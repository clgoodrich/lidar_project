"""3.0 reference block tables. Export the 9t out-of-fold candidates per block for the 3.4 to 3.8 builds.

Purpose
    Score a 9t out-of-fold probability raster with the frozen scorer (`_transfer_score_lib.score`) and write
    every ranked candidate per eligible block in the interface format the later geography builds read.
        {block_id: {"cands": [{"blob_id", "score", "area_m2", "truth_id"}], "n_truth": int, "km2": float}}
    truth_id is null for an unmatched candidate. Second pieces of a matched feature are already dropped
    (scorer dedupe rule). Every eligible block is written, including blocks with no candidates.
    Pit default. The saved uint8 mosaic at the sweep's cutoff 0.35 (it reproduces the archival 0.909 at K 40).
    Pad default. The float32 isolated out-of-fold mosaic built by `_transfer_baseline_repeat_9t.py`, cutoff 0.525.
    Replace the pit raster with the isolated pit mosaic once P1 S6 trains it.

Inputs
    --prob (defaults above), blocks and truth from config_3_0.json reference_9t.<task>

Outputs
    expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_9t.json      (pit)
    expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_pad_9t.json  (pad)
    Run record under expansions/3_geography/3_0_transfer_protocol/results/<run_id>/

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_ref_tables_9t.py --task pit
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_ref_tables_9t.py --task pad
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
from _transfer_baseline_repeat_9t import ref_path, truth_spec  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))
OUT_NAME = {"pit": "xfer_ref_block_tables_9t.json", "pad": "xfer_ref_block_tables_pad_9t.json"}


def tables(res: dict) -> dict:
    c, b = res["candidates"], res["blocks"]
    out = {}
    for r in b.itertuples():
        sub = c[c.block_id == r.block_id].sort_values(["score", "area_m2", "cand_id"], ascending=[False, False, True])
        out[str(int(r.block_id))] = {
            "cands": [{"blob_id": int(x.cand_id), "score": float(x.score), "area_m2": float(x.area_m2),
                       "truth_id": None if x.matched is None or x.matched != x.matched else int(x.matched)}
                      for x in sub.itertuples()],
            "n_truth": int(r.n_truth), "km2": float(r.area_km2)}
    return out


def main(argv=None) -> int:
    d = CFG["scoring_defaults"]
    ap = argparse.ArgumentParser(description="3.0 export 9t reference block tables")
    ap.add_argument("--task", choices=("pit", "pad"), required=True)
    ap.add_argument("--prob", type=Path, default=None)
    ap.add_argument("--cutoff", type=float, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    prob = a.prob or (ref_path("pit", "prob") if a.task == "pit"
                      else ek.sub("3.0", "data/interim") / "pad_prob_oof_mosaic_9t.tif")
    if not prob.exists():
        raise SystemExit(f"probability raster missing: {prob}. For pads run _transfer_baseline_repeat_9t.py --task pad first.")
    cutoff = a.cutoff if a.cutoff is not None else d["cutoff_by_task"][a.task]
    truth, tid = truth_spec(a.task)
    res = tl.score(prob, ref_path(a.task, "blocks"), truth, d["k_per_km2"], truth_id=tid, cutoff=cutoff,
                   B=200, seed=d["seed"])
    t = tables(res)
    out = a.out_dir or ek.sub("3.0", "results/tables")
    js = out / OUT_NAME[a.task]
    js.write_text(json.dumps(t), encoding="utf-8")
    run = ek.new_run("3.0", f"ref_tables_{a.task}", {"prob": str(prob), "cutoff": cutoff}, why="reference block tables.")
    ek.write_provenance(run, inputs=[prob, ref_path(a.task, "blocks")], outputs=[js],
                        params={"cutoff": cutoff, "module_sha256": tl.module_sha256()})
    n = sum(len(v["cands"]) for v in t.values())
    print(f"{a.task}: {len(t)} blocks, {n} candidates, {sum(v['n_truth'] for v in t.values())} truth features, "
          f"cutoff {cutoff}\nwrote {js}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

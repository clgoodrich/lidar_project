"""3.0 S1 and S6. Frozen scoring harness. Score one probability raster against one area's annotated features.

Purpose
    Command-line wrapper around `_transfer_score_lib.score`. With `--prereg` every setting comes from the
    filled preregistration (its ```json prereg``` block), so a second person can run the test from that file
    alone. Explicit flags are for the 9t reproduction and for tests. A flag that disagrees with the
    preregistration is refused. The run folder holds the score JSON, the per-block table, a recall-versus-K
    figure, `_CONFIG.json`, `_RUN.md` and `_PROVENANCE.json` with the hash of every input, the
    preregistration and the scoring module.
    Pads (S6) use the same scorer with the pad raster and pad truth (`--task pad`). Roads are out of scope.

Inputs
    --prob      probability raster (float 0-1, or uint8 DN / 254 with 255 nodata)
    --blocks    blocks GeoPackage, layer `blocks`, column `block_id` (EPSG:6346)
    --truth     truth `path.gpkg:layer`, with --truth-id for the feature id column
    --footprint optional polygon layer, --void optional void-fraction raster, --void-cap
    --groups    optional P1 split file. Held-out fold of each block becomes its group for `--k-rule per_group`

Outputs (run folder, default C:/Users/colto/Documents/GitHub/lidar_project/data/<area>/results/transfer/<run_id>/)
    transfer_score_<area>.json, transfer_blocks_<area>.csv, transfer_recall_vs_k_<area>.png, optional
    transfer_candidates_<area>.gpkg, _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_score_run.py --prereg docs/iterations/transfer_warren_prereg.md
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_score_run.py --area 9t --task pit --prob data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif --blocks data/9t/derived/05/pit_blocks_9t.gpkg --truth qgis/annotations/annotations_proj.gpkg:pit_inside --truth-id pit_inside_id --k 40 --seed 20261105
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))

SCORE_KEYS = ("prob", "blocks", "truth", "truth_id", "footprint", "void", "void_cap", "k", "seed", "B", "k_rule",
              "order", "dedupe", "density_c", "cutoff", "min_area", "iou", "groups", "area", "task")


def groups_from_split(path: Path, task: str) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(b): int(f) for f, r in doc["tasks"][task]["folds"].items() for b in r["held_out"]}


def figure(summary: dict, path: Path, label: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c = summary["recall_vs_k"]
    fig, ax = plt.subplots(figsize=(6, 3.8))
    # ek.PALETTE. Lost/found palette, worst pair dE 21.1 deutan, 22.6 normal (CLAUDE.md, --pairs all).
    ax.plot([r["k_per_km2"] for r in c], [r["recall"] for r in c], color=ek.PALETTE["blue"], marker="o", lw=1.8,
            label="recall at K")
    p = summary["primary"]
    ax.errorbar([summary["k_per_km2"]], [p["recall"]], yerr=[[p["recall"] - p["lo"]], [p["hi"] - p["recall"]]],
                color=ek.PALETTE["orange"], marker="s", capsize=4, lw=1.5, label="primary K, 95% block bootstrap")
    ax.set_ylim(0, 1)
    ax.set_xlabel("review budget K (candidates per km2)")
    ax.set_ylabel("recall of drawn features")
    ax.set_title(label, loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def resolve(a: argparse.Namespace) -> dict:
    """Merge explicit flags with the preregistration. Conflicts are refused."""
    flags = {k: getattr(a, k) for k in SCORE_KEYS if getattr(a, k, None) is not None}
    if not a.prereg:
        return flags
    full = tl.read_prereg(a.prereg)
    pr = dict(full.get("scoring", {}))
    if pr.get("density_c") is None and full.get("density_c") is not None:
        pr["density_c"] = full["density_c"]          # the secondary's c is a top-level prereg field
    pr = {k: v for k, v in pr.items() if v is not None}
    for k, v in flags.items():
        if k in pr and str(pr[k]) != str(v):
            raise SystemExit(f"--{k} {v} disagrees with the preregistration ({pr[k]}). The preregistration wins. Refusing.")
    return {**pr, **flags}


def run(s: dict, out_base: Path | None = None, prereg: Path | None = None, write_candidates: bool = False,
        quiet: bool = False) -> Path:
    d = CFG["scoring_defaults"]
    need = [k for k in ("prob", "blocks", "truth", "area") if not s.get(k)]
    if need:
        raise SystemExit(f"missing settings {need}. Give them as flags or in the preregistration.")
    for k in ("prob", "blocks", "footprint", "void", "groups"):
        if s.get(k) and not Path(s[k]).exists():
            raise SystemExit(f"input missing: {k} = {s[k]}")
    truth_path = Path(str(s["truth"]).rsplit(":", 1)[0])
    if not truth_path.exists():
        raise SystemExit(f"input missing: truth = {truth_path}")
    task = s.get("task", "pit")
    groups = groups_from_split(Path(s["groups"]), task) if s.get("groups") else None
    k_rule = s.get("k_rule", d["k_rule"])
    if k_rule == "per_group" and not groups:
        raise SystemExit("k_rule per_group needs --groups (a P1 split file)")
    res = tl.score(Path(s["prob"]), Path(s["blocks"]), str(s["truth"]), float(s.get("k", d["k_per_km2"])),
                   truth_id=s.get("truth_id"), footprint_path=Path(s["footprint"]) if s.get("footprint") else None,
                   void_path=Path(s["void"]) if s.get("void") else None,
                   void_cap=float(s["void_cap"]) if s.get("void_cap") is not None else None,
                   cutoff=float(s.get("cutoff", d["cutoff_by_task"].get(task, d["cutoff"]))), min_area=float(s.get("min_area", d["min_area_m2"])),
                   iou=float(s.get("iou", d["iou"])), order=s.get("order", d["order"]),
                   dedupe=s.get("dedupe", d["dedupe"]), k_rule=k_rule, group_of_block=groups,
                   density_c=float(s["density_c"]) if s.get("density_c") is not None else None,
                   B=int(s.get("B", d["B"])), seed=int(s.get("seed", d["seed"])))
    area = s["area"]
    base = out_base or (ek.area_dir(area) / "results" / "transfer")
    rd = ek.new_run("3.0", f"score_{task}_{area}", {**{k: str(v) for k, v in s.items()}, "module": tl.module_sha256()},
                    base=base, why=f"3.0 frozen scorer, {task} on {area}.")
    js, csv, png = rd / f"transfer_score_{area}.json", rd / f"transfer_blocks_{area}.csv", rd / f"transfer_recall_vs_k_{area}.png"
    summ = {**res["summary"], "settings": {k: str(v) for k, v in s.items()}, "prereg": str(prereg) if prereg else None,
            "prereg_sha256": ek.sha256(prereg) if prereg else None, "evidence_level": "(a) drawn feature"}
    js.write_text(json.dumps(summ, indent=1, default=float), encoding="utf-8")
    res["blocks"].to_csv(csv, index=False)
    figure(summ, png, f"{task} recall at K, {area}")
    outs = [js, csv, png]
    if write_candidates:
        gp = rd / f"transfer_candidates_{area}.gpkg"
        c = res["candidates"].copy()
        c["matched"] = c["matched"].astype(str)
        c.to_file(gp, layer="candidates", driver="GPKG")
        outs.append(gp)
    ins = [Path(s["prob"]), Path(s["blocks"]), truth_path] + [Path(s[k]) for k in ("footprint", "void", "groups") if s.get(k)]
    ek.write_provenance(rd, inputs=ins + ([prereg] if prereg else []) + [tl.HERE], outputs=outs,
                        params={**{k: str(v) for k, v in s.items()}, "module_sha256": tl.module_sha256()},
                        seeds={"bootstrap": int(s.get("seed", d["seed"]))})
    if not quiet:
        p = summ["primary"]
        print(f"{task} {area}: recall at K {summ['k_per_km2']}/km2 = {p['recall']:.3f} [{p['lo']:.3f}, {p['hi']:.3f}] "
              f"over {summ['n_blocks_eligible']} blocks, {summ['n_truth']} features, "
              f"density {summ['truth_density_per_km2']:.1f}/km2, K total {summ['k_total']}")
        print(f"run folder {rd}")
    return rd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="3.0 frozen scoring harness")
    ap.add_argument("--prereg", type=Path, default=None)
    ap.add_argument("--area"); ap.add_argument("--task", choices=("pit", "pad"))
    ap.add_argument("--prob"); ap.add_argument("--blocks"); ap.add_argument("--truth"); ap.add_argument("--truth-id", dest="truth_id")
    ap.add_argument("--footprint"); ap.add_argument("--void"); ap.add_argument("--void-cap", dest="void_cap", type=float)
    ap.add_argument("--k", type=float); ap.add_argument("--seed", type=int); ap.add_argument("--B", type=int)
    ap.add_argument("--k-rule", dest="k_rule", choices=("global", "per_group"))
    ap.add_argument("--order", choices=("score", "iou")); ap.add_argument("--dedupe", choices=("truth_matched", "none"))
    ap.add_argument("--density-c", dest="density_c", type=float); ap.add_argument("--cutoff", type=float)
    ap.add_argument("--min-area", dest="min_area", type=float); ap.add_argument("--iou", type=float)
    ap.add_argument("--groups", help="P1 split file for per-group K")
    ap.add_argument("--out-base", type=Path, default=None, help="parent of the run folder")
    ap.add_argument("--write-candidates", action="store_true")
    a = ap.parse_args(argv)
    run(resolve(a), a.out_base, a.prereg, a.write_candidates)
    return 0


if __name__ == "__main__":
    sys.exit(main())

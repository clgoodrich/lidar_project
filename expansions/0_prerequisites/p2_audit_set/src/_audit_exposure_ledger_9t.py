"""P2 S0. Exposure ledger. Every use of every 9t block in training, selection, calibration, mining and inspection.

Purpose
    One row per 9t block (144). One column per CV model and fold, holding `held_out` or `used`. Inner roles
    are unrecoverable (P1 S0), so every block a model did not hold out counts as used by it. Further columns
    come from `config_p2.json` `exposure_uses`, one per use, of four kinds.
        all_non_heldout_per_model  count of models whose selection steps (epoch, F1/F2 cutoff) used the block
        blocks_from_csv            1 where the block appears in a saved table (calibration, sweeps)
        all_blocks                 1 for every block (context models trained on the whole tile)
        unknown                    1 for every block, marked "unknown, treated as used"
    `n_uses` sums the used marks. The expected finding is at least four model uses per block.
    A grep of the scripts lists every file that names block ids or split files, so a person can extend the
    config with uses this ledger does not yet know.

Inputs
    P1 split file (held-out lists, verified equal to the checkpoints by P1 S0) via --splits, or the
    checkpoints themselves (through P1 `_split_recover_roles_9t.py`)
    data/9t/derived/05/pit_blocks_9t.gpkg, tables named in config_p2.json, notebooks/wellsight_v2/**/*.py

Outputs
    <out-dir>/block_exposure_9t.csv          block_id, one column per model fold and per use, n_uses
    <out-dir>/block_exposure_scripts_9t.csv  script, pattern, hits
    <doc>                                    audit_set_history.md (default docs/iterations/audit_set_history.md)
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p2_audit_set/results/<run_id>/

Run
    python expansions/0_prerequisites/p2_audit_set/src/_audit_exposure_ledger_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json [--out-dir DIR] [--doc PATH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "p1_splits_manifests" / "src"))
import _audit_guard_lib as ag  # noqa: E402
ek = ag.ek
CFG = json.loads((HERE.parent / "config_p2.json").read_text(encoding="utf-8"))

MODELS = (("pit_unet_cv5", "pit"), ("pad_unet_cv5", "pad"), ("pad_unet_cv5_iso", "pad"))


def held_lists(splits: Path | None) -> dict[str, dict[int, list[int]]]:
    """Held-out lists per model. From the split file when given, else from the checkpoints."""
    out = {}
    if splits is not None:
        doc = json.loads(Path(splits).read_text(encoding="utf-8"))
        for m, task in MODELS:
            t = doc["tasks"][task]
            excl = set(t.get("excluded_audit_blocks", []))
            if excl:
                raise SystemExit("the split file excludes audit blocks. Give the v1 (historical held-out) file.")
            out[m] = {int(f): r["held_out"] for f, r in t["folds"].items()}
        return out
    import _split_recover_roles_9t as rr
    for spec in rr.model_specs():
        if spec["dir"].exists():
            out[spec["model"]] = {f: rr.checkpoint_held(spec["dir"] / f"fold{f}" / "best.pt") for f in range(5)}
    return out


def ledger(block_ids: list[int], held: dict, uses: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame({"block_id": sorted(int(b) for b in block_ids)})
    model_cols = []
    for m, folds in held.items():
        for f, ids in sorted(folds.items()):
            c = f"{m}_f{f}"
            hs = set(int(b) for b in (ids or []))
            df[c] = ["held_out" if b in hs else "used" for b in df.block_id]
            model_cols.append(c)
    df["n_model_uses"] = (df[model_cols] == "used").sum(1) if model_cols else 0
    use_cols = []
    for u in uses:
        k, name = u["kind"], u["name"]
        if k == "split_recovery":
            continue
        if k == "all_non_heldout_per_model":
            df[name] = df["n_model_uses"]
        elif k == "blocks_from_csv":
            p = ek.path_for(u["path_key"]) / u["rel"]
            if not p.exists():
                df[name] = "missing input, treated as used"
                df[name + "_flag"] = 1
                use_cols.append(name + "_flag")
                continue
            ids = set(pd.read_csv(p, usecols=[u["column"]])[u["column"]].dropna().astype(int))
            df[name] = df.block_id.isin(ids).astype(int)
        elif k == "all_blocks":
            df[name] = 1
        elif k == "unknown":
            df[name] = "unknown, treated as used"
            df[name + "_flag"] = 1
            use_cols.append(name + "_flag")
            continue
        else:
            raise ValueError(f"unknown use kind {k}")
        use_cols.append(name)
    num = df[use_cols].apply(pd.to_numeric, errors="coerce").fillna(0).clip(upper=1) if use_cols else 0
    df["n_uses"] = df["n_model_uses"] + (num.sum(1) if use_cols else 0)
    return df


def script_inventory(roots: list[str], patterns: list[str]) -> pd.DataFrame:
    rows = []
    rx = {p: re.compile(re.escape(p)) for p in patterns}
    for r in roots:
        for f in sorted((ek.REPO / r).rglob("*.py")):
            if "archive" in f.parts or "__pycache__" in f.parts:
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")
            for p, x in rx.items():
                n = len(x.findall(txt))
                if n:
                    rows.append({"script": f.relative_to(ek.REPO).as_posix(), "pattern": p, "hits": n})
    return pd.DataFrame(rows, columns=["script", "pattern", "hits"])


def write_doc(df: pd.DataFrame, inv: pd.DataFrame, uses: list[dict], path: Path, csv_name: str) -> None:
    mc = [c for c in df.columns if re.search(r"_f\d$", c)]
    lines = ["# Audit set history, tile 9t", "",
             "Written by `expansions/0_prerequisites/p2_audit_set/src/_audit_exposure_ledger_9t.py`.",
             f"Every number below comes from `{csv_name}` in the data folder.", "",
             "## Finding",
             f"- Blocks in the ledger. {len(df)}.",
             f"- Minimum model uses per block. {int(df.n_model_uses.min())}. Maximum {int(df.n_model_uses.max())}.",
             f"- Blocks with fewer than four model uses. {int((df.n_model_uses < 4).sum())}.",
             f"- Model fold columns. {len(mc)}.",
             "- No 9t block is untouched. A 9t audit set supports comparisons between new models only.", "",
             "## Uses recorded", ""]
    lines += [f"- `{u['name']}` ({u['kind']}). {u.get('note', '')}" for u in uses]
    lines += ["", "## Scripts that name blocks or splits",
              f"{inv.script.nunique()} scripts. Listed in `block_exposure_scripts_9t.csv`. Read each before trusting the ledger.",
              "", "## Gaps", "Unknown uses are treated as used. Add any use found later to `config_p2.json` and rerun.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P2 S0 block exposure ledger")
    ap.add_argument("--splits", type=Path, default=None, help="P1 v1 split file. Default reads checkpoints")
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    ap.add_argument("--doc", type=Path, default=None, help="default docs/iterations/audit_set_history.md")
    a = ap.parse_args(argv)
    import geopandas as gpd
    import _split_core_lib_9t as sc
    blocks = gpd.read_file(sc.trainer("pit").BLOCKS, layer="blocks")
    ek.assert_rows(blocks, 144, "9t blocks")
    held = held_lists(a.splits)
    if not held:
        raise SystemExit("no held-out lists found. Give --splits (P1 S2) or check data/9t/models/*/unet_cv5*/")
    df = ledger(list(blocks.block_id), held, CFG["exposure_uses"])
    ek.assert_rows(df, 144, "exposure ledger")
    ek.assert_unique(df, "block_id")
    inv = script_inventory(CFG["script_grep_roots"], CFG["script_grep_patterns"])
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    out.mkdir(parents=True, exist_ok=True)
    csv, icsv = out / "block_exposure_9t.csv", out / "block_exposure_scripts_9t.csv"
    df.to_csv(csv, index=False)
    inv.to_csv(icsv, index=False)
    doc = a.doc or (ek.path_for("docs") / "iterations" / "audit_set_history.md")
    write_doc(df, inv, CFG["exposure_uses"], doc, csv.name)
    run = ek.new_run("p2", "exposure_ledger", {"splits": str(a.splits)}, why="S0 exposure inventory.")
    ek.write_provenance(run, inputs=[a.splits] if a.splits else [], outputs=[csv, icsv, doc])
    print(f"{len(df)} blocks. model uses per block min {df.n_model_uses.min()} max {df.n_model_uses.max()}. "
          f"n_uses min {df.n_uses.min()}. {inv.script.nunique()} scripts name blocks or splits.")
    print(f"wrote {csv}\nwrote {icsv}\nwrote {doc}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

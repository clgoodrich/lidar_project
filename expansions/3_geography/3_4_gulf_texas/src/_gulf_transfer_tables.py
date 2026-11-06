"""S10 and S11 (3.4). Arm tables, A1 paired gain, A2 wetland-exclusion view, error review, RRC hand-off.

Purpose
    Collect every xfer_score_k40_<arm>_<area>.json into one table. A0 appears in every table and arms
    are never mixed. C0 (Pecos) is a separate contrast row and is never pooled with Gulf rows.
    A2 rows (dry and mixed blocks only) are a different target population and sit beside A0.
    Error review. Misses and unmatched top-K candidates by wetland and void stratum.
    Hand-off. RRC records inside the scored windows, with their reliability class, go to 5.6 unscored.
Inputs
    data/<area>/results/transfer/<run_id>/xfer_score_k40_<arm>_<area>.json and xfer_candidates_*.csv
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg
    expansions/3_geography/3_4_gulf_texas/data/interim/rrc_orphans_norm_tx.gpkg  (S0)
Outputs
    expansions/3_geography/3_4_gulf_texas/results/tables/gulf_transfer_arms.csv
    expansions/3_geography/3_4_gulf_texas/results/tables/gulf_error_review_strata.csv
    expansions/3_geography/3_4_gulf_texas/results/figures/gulf_recall_by_arm.png
    expansions/3_geography/3_4_gulf_texas/data/processed/gulf_rrc_handoff_5_6.gpkg
Run
    python expansions/3_geography/3_4_gulf_texas/src/_gulf_transfer_tables.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.4"


def collect_scores(areas: list[str]) -> pd.DataFrame:
    rows = []
    for area in areas:
        for p in sorted(gt.area_transfer_dir(area).glob("*/xfer_score_k40_*.json")):
            r = json.loads(p.read_text())
            rows.append({"area": area, "arm": r.get("arm"), "contrast_only": r.get("contrast_only", False),
                         "recall": r["recall_target"], "lo": r["recall_target_ci"][0], "hi": r["recall_target_ci"][1],
                         "diff": r["diff"], "diff_lo": r["diff_ci"][0], "diff_hi": r["diff_ci"][1],
                         "decision": r["decision"], "n_blocks": r["n_blocks_target"],
                         "density": r["density_target"], "warning": r.get("warning", ""), "file": str(p)})
    return pd.DataFrame(rows)


def error_review(cands: pd.DataFrame, blocks: pd.DataFrame, k_per_km2: float = gt.K_PER_KM2) -> pd.DataFrame:
    """Top-K unmatched and missed truth by stratum. cands needs block_id, score, truth_id."""
    km2 = blocks["area_km2"].sum()
    k = int(round(k_per_km2 * km2))
    top = cands.sort_values(["score", "area_m2"], ascending=[False, False]).head(k)
    top = top.merge(blocks[["block_id", "wet_stratum", "void_stratum"]], on="block_id", how="left")
    top["unmatched"] = top["truth_id"].isna()
    return top.groupby(["wet_stratum", "void_stratum"]).agg(top_k=("blob_id", "size"),
                                                            unmatched=("unmatched", "sum")).reset_index()


def rrc_handoff(areas: dict) -> "object":
    import geopandas as gpd
    from shapely.geometry import box
    rp = gt.require_input(ek.sub(EXP, "data/interim") / "rrc_orphans_norm_tx.gpkg", "normalised RRC rows (S0)")
    g = gpd.read_file(rp)
    parts = []
    for area, ac in areas.items():
        if not ac.get("centre_lonlat"):
            continue
        w = gpd.GeoSeries([gt.window_box(*ac["centre_lonlat"], ac["crs"])], crs=ac["crs"]).to_crs(4326).iloc[0]
        sub = g[g.within(w)].copy()
        sub["area"] = area
        parts.append(sub)
    out = pd.concat(parts) if parts else g.iloc[:0]
    out["evidence_level"] = "(b) administrative, unscored here"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    tables, figs = ek.sub(EXP, "results/tables"), ek.sub(EXP, "results/figures")
    df = collect_scores(list(cfg["areas"]))
    if df.empty:
        print("No score JSONs yet. Run core 'score' for A0 on T1 and T2 first.", file=sys.stderr)
    else:
        df.to_csv(tables / "gulf_transfer_arms.csv", index=False)
        plot = df.rename(columns={"area": "stratum"})
        gt.plot_recall_strata(plot, figs / "gulf_recall_by_arm.png", "Gulf transfer by arm (level a)")
        print(df[["area", "arm", "recall", "diff", "decision"]].to_string(index=False))
        import geopandas as gpd
        rev = []
        for area in df["area"].unique():
            bp = gt.area_transfer_dir(area) / f"xfer_blocks_roles_{area}.gpkg"
            for cp in gt.area_transfer_dir(area).glob("*/xfer_candidates_A0_*.csv"):
                if bp.exists():
                    b = gpd.read_file(bp)
                    rev.append(error_review(pd.read_csv(cp), b[b["eligible"] & (b["role"] == "test")]).assign(area=area))
        if rev:
            pd.concat(rev).to_csv(tables / "gulf_error_review_strata.csv", index=False)
    try:
        h = rrc_handoff(cfg["areas"])
        hp = ek.sub(EXP, "data/processed") / "gulf_rrc_handoff_5_6.gpkg"
        h.to_file(hp, driver="GPKG")
        print(f"RRC rows handed to 5.6: {len(h)} -> {hp}")
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

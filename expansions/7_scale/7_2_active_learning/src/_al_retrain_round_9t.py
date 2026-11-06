"""Build the training labels of one policy after a round and launch the retrain (7.2 S2, S3 step 4).

Purpose
    For one policy, gather every label it has acquired up to this round. Burn kept candidates and added
    features as pit floor (1), and rejected candidates as background (0), the hard negatives of the road
    loop. Unsure items become ignore (255). Start from the base label raster outside the stopping set.
    Stopping and audit blocks are set to ignore everywhere and asserted absent from every training list.
    Write per-item inverse-probability weights (1 / pi, self-normalised, clipped at the 95th percentile,
    and an unclipped sensitivity file). Then run the trainer command from config_7_2.json with the
    placeholders filled. Every policy starts from the same checkpoint.
    The trainer command is null until the P1 isolated pit trainer exists. The script then stops after
    writing the inputs and says so.

Inputs
    round folders results/live/round_<nn>/ with labels.csv and inclusion_log.csv (from the review and select steps)
    data/interim/al_items_9t.gpkg, data/interim/al_review_idmap_al_r<nn>.csv, review diff GeoPackage
    base pit labels path_for("nine_t") / labels_pit_9t_05.tif, blocks, split JSON
Outputs (results/live/round_<nn>/train_<policy>/)
    labels_<policy>_r<nn>.tif, weights_<policy>_r<nn>.csv, weights_unclipped_<policy>_r<nn>.csv, train_manifest.json

Run
    python expansions/7_scale/7_2_active_learning/src/_al_retrain_round_9t.py --round 3 --policy U --init round0.pt
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _al_policies_select_9t import CFG, cfg_path, ek, load_cfg, need  # noqa: E402
from _al_replay_sim_9t import ipw  # noqa: E402


def gather(live: Path, policy: str, upto: int) -> pd.DataFrame:
    rows = []
    for r in range(1, upto + 1):
        rd = live / f"round_{r:02d}"
        if not (rd / "labels.csv").exists():
            raise FileNotFoundError(f"labels for round {r} missing at {rd / 'labels.csv'}")
        lab = pd.read_csv(rd / "labels.csv")
        lab = lab[lab["policies"].astype(str).str.split(";").apply(lambda p: policy in p)]
        inc = pd.read_csv(need(rd / "inclusion_log.csv", f"inclusion log round {r}"))
        inc = inc[(inc["policy"] == policy) & inc["selected"]]
        lab = lab.merge(inc[["item_id", "pi"]], on="item_id", how="left").assign(round=r)
        if lab["pi"].isna().any() or (lab["pi"] <= 0).any():
            raise AssertionError(f"round {r}: labelled items without a positive pi for policy {policy}")
        rows.append(lab)
    return pd.concat(rows, ignore_index=True)


def burn_labels(base_lbl: Path, items_geo, lab: pd.DataFrame, added_geoms, blocks, forbidden: set, out: Path) -> dict:
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(base_lbl) as r:
        ek.assert_crs(r, "EPSG:6346")
        lbl, prof, tf = r.read(1), r.profile, r.transform
    g = items_geo.set_index("item_id")
    def burn(geoms, val):
        if len(geoms):
            m = rasterize([(x, 1) for x in geoms], out_shape=lbl.shape, transform=tf, fill=0).astype(bool)
            lbl[m] = val
            return int(m.sum())
        return 0
    n = {"reject_px": burn([g.loc[i, "geometry"] for i in lab.loc[lab["status"] == "reject", "item_id"]], 0),
         "keep_px": burn([g.loc[i, "geometry"] for i in lab.loc[lab["status"] == "keep", "item_id"]], 1),
         "added_px": burn(list(added_geoms), 1),
         "unsure_px": burn([g.loc[i, "geometry"] for i in lab.loc[lab["status"] == "unsure", "item_id"]], 255)}
    fb = blocks[blocks["block_id"].isin(forbidden)]
    n["forbidden_px"] = burn(list(fb.geometry), 255)
    prof.update(compress="deflate")
    with rasterio.open(out, "w", **prof) as o:
        o.write(lbl, 1)
    return n


def main(argv=None) -> int:
    import geopandas as gpd
    ap = argparse.ArgumentParser(description="7.2 per-policy retrain inputs and launch.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--init", default=None, help="common starting checkpoint (round 0 model)")
    ap.add_argument("--live", default=None, help="default results/live/")
    ap.add_argument("--split", default=str(ek.sub("7.2", "results/tables") / "al_split_9t_v1.json"))
    ap.add_argument("--items-geo", default=str(ek.sub("7.2", "data/interim") / "al_items_9t.gpkg"))
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    live = Path(a.live) if a.live else ek.sub("7.2", "results/live")
    try:
        split = json.loads(need(Path(a.split), "AL split").read_text())
        lab = gather(live, a.policy, a.round)
        items_geo = gpd.read_file(need(Path(a.items_geo), "item polygons"))
        blocks = gpd.read_file(need(cfg_path(cfg["inputs"]["blocks"]), "blocks"))
        base = need(cfg_path(cfg["inputs"]["base_labels"]), "base pit labels")
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    forbidden = set(split["stopping"]) | set(split["audit"]) | set(split.get("buffer", []))
    used = set(items_geo.set_index("item_id").loc[lab["item_id"], "block_id"].astype(int))
    ek.assert_disjoint(used, forbidden, "training items vs stopping/audit/buffer blocks")
    added = []
    for r in range(1, a.round + 1):
        dp = live / f"round_{r:02d}" / "review" / f"corrections_diff_pits_al_r{r:02d}.gpkg"
        if dp.exists():
            import pyogrio
            if "added" in {n for n, _ in pyogrio.list_layers(str(dp))}:
                added += list(gpd.read_file(dp, layer="added").geometry)
    out = live / f"round_{a.round:02d}" / f"train_{a.policy}"
    out.mkdir(parents=True, exist_ok=True)
    lbl_p = out / f"labels_{a.policy}_r{a.round:02d}.tif"
    counts = burn_labels(base, items_geo, lab, added, blocks, forbidden, lbl_p)
    c = lab[lab["status"].isin(["keep", "reject"])].copy()
    c["w"] = ipw(c["pi"], cfg["ipw_clip_quantile"])
    c[["item_id", "round", "pi", "w"]].to_csv(out / f"weights_{a.policy}_r{a.round:02d}.csv", index=False)
    c["w"] = ipw(c["pi"], None)
    c[["item_id", "round", "pi", "w"]].to_csv(out / f"weights_unclipped_{a.policy}_r{a.round:02d}.csv", index=False)
    man = {"policy": a.policy, "round": a.round, "n_labels": len(lab), "status": lab["status"].value_counts().to_dict(),
           "pixels": counts, "init": a.init, "init_sha256": ek.sha256(Path(a.init)) if a.init and Path(a.init).exists() else None}
    (out / "train_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    if not cfg.get("trainer_cmd"):
        print("inputs written. trainer_cmd is null in config_7_2.json (P1 isolated pit trainer pending). Not training.")
        return 0
    cmd = [t.format(labels=lbl_p, weights=out / f"weights_{a.policy}_r{a.round:02d}.csv", out=out, init=a.init or "")
           for t in cfg["trainer_cmd"]]
    r = subprocess.run(cmd)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())

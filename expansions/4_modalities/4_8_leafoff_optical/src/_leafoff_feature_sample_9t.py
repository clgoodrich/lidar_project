"""S1 of framework 4.8. Draw the preregistered random sample of annotated features for the chip check.

Purpose. Draw n_features (60) features at random from the annotated pit_inside and pad layers with the master seed,
stratified by layer in proportion to its count, before any chip is looked at. The sample file is the
preregistration artefact. Commit it before S2 runs. Rerunning with the same seed gives the same rows.
Inputs.
  qgis/annotations/annotations_proj_v2.gpkg layers pit_inside, pad (held)
Outputs.
  expansions/4_modalities/4_8_leafoff_optical/results/tables/leafoff_feature_sample_9t.csv
  (feature_key, layer, feature_id, x, y, area_m2, sample_order)
Run.
  python expansions/4_modalities/4_8_leafoff_optical/src/_leafoff_feature_sample_9t.py [--n 60] [--seed S] [--annotations GPKG] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _leafoff_kit_4_8 as lk

ID_COL = {"pit_inside": "pit_inside_id", "pad": "pad_id"}


def draw(layers: dict, n: int, seed: int) -> pd.DataFrame:
    """layers maps name -> GeoDataFrame. Proportional allocation, largest remainder, then a seeded draw per layer."""
    rng = np.random.default_rng(seed)
    tot = sum(len(g) for g in layers.values())
    raw = {k: n * len(g) / tot for k, g in layers.items()}
    alloc = {k: int(np.floor(v)) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - alloc[k], reverse=True)[: n - sum(alloc.values())]:
        alloc[k] += 1
    rows = []
    for k in sorted(layers):
        g = layers[k].reset_index(drop=True)
        pick = rng.choice(len(g), alloc[k], replace=False)
        for i in pick:
            c = g.geometry.iloc[i].centroid
            fid = g[ID_COL.get(k, g.columns[0])].iloc[i]
            rows.append({"feature_key": f"{k}:{fid}", "layer": k, "feature_id": fid, "x": c.x, "y": c.y,
                         "area_m2": g.geometry.iloc[i].area})
    df = pd.DataFrame(rows)
    df["sample_order"] = rng.permutation(len(df))
    return df.sort_values("sample_order").reset_index(drop=True)


def main(argv=None) -> int:
    import geopandas as gpd
    cfg = lk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=pr["n_features"])
    ap.add_argument("--seed", type=int, default=pr["master_seed"])
    ap.add_argument("--annotations", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ann = lk.need(Path(a.annotations) if a.annotations else lk.resolve(cfg["inputs"]["annotations"]), "annotations")
    layers = {}
    for k in pr["feature_layers"]:
        g = gpd.read_file(ann, layer=k)
        lk.ek.assert_crs(g, cfg["crs"])
        x0, y0, x1, y1 = cfg["areas"]["9t"]
        layers[k] = g[g.geometry.centroid.x.between(x0, x1) & g.geometry.centroid.y.between(y0, y1)]
    df = draw(layers, a.n, a.seed)
    lk.ek.assert_rows(df, a.n, "sample")
    lk.ek.assert_unique(df, "feature_key")
    out = Path(a.out) if a.out else lk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    f = out / "leafoff_feature_sample_9t.csv"
    df.to_csv(f, index=False)
    lk.prov(out, "leafoff_feature_sample_9t", inputs=[ann], outputs=[f], params={"n": a.n}, seeds={"master": a.seed})
    print(f, df.layer.value_counts().to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

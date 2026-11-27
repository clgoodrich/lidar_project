"""Run the five 9t fold models (pit, pad) on the 1.5 km tile 616500,4591500 of Area B (613590) and score them
against the 2026-11-27 annotation drop (qgis/annotations/pad.shp, pit_inside.shp).

Frozen from 9t: F2 cutoffs per fold (pit/pad *_cv5_per_fold_9t.csv), mu/sd from each checkpoint. Nothing tuned here.
Recall is valid. Precision is a LOWER BOUND: the tile is not known to be fully drawn (many pads have no pits drawn).
Outputs: data/613590/results/tile616591/
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, rasterio, torch
from rasterio.windows import from_bounds
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _dl import DEVICE, UNet, predict_array
from _transfer_pit_cv5_to_613590_05 import polygonize, match_scores

ROOT = Path(__file__).resolve().parents[3]
FEAT = ROOT / "data/613590/derived/inference_05/features_613590_05.tif"
MOD = ROOT / "data/9t/models"
ANN = ROOT / "qgis/annotations"
OUT = ROOT / "data/613590/results/tile616591"
T = (616500.0, 4591500.0, 618000.0, 4593000.0)
PAD_M = 96.0
TASKS = {"pit": ("pit/unet_cv5", 3, 256, 128, "pit_inside"), "pad": ("pad/unet_cv5", 2, 384, 192, "pad")}


def read_feats():
    b = (T[0] - PAD_M, T[1] - PAD_M, T[2] + PAD_M, T[3] + PAD_M)
    with rasterio.open(FEAT) as r:
        a = r.read(window=from_bounds(*b, r.transform), boundless=True, fill_value=np.nan).astype(np.float32)
        crs = r.crs
    return a, crs


def truth(layer):
    g = gpd.read_file(ANN / f"{layer}.shp")
    g = g[g.geometry.notna() & ~g.geometry.is_empty].to_crs(6346)
    from shapely.geometry import box
    g = g[g.geometry.representative_point().within(box(*T))]
    return g.reset_index(drop=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    feats, crs = read_feats()
    i = int(PAD_M / 0.5)
    tf = rasterio.transform.from_origin(T[0], T[3], 0.5, 0.5)
    summary = {"tile_bounds_epsg6346": T, "annotation_files": "qgis/annotations/{pad,pit_inside}.shp (2026-11-27)", "tasks": {}}
    for task, (sub, ncls, patch, ov, layer) in TASKS.items():
        gt = truth(layer)
        thr_tab = pd.read_csv(MOD / sub.split("/")[0] / "unet_cv5" / f"{task}_cv5_per_fold_9t.csv")
        thr_tab = thr_tab[thr_tab.objective == "f2"].set_index("fold").prob_threshold
        probs, rows = [], []
        for k in range(5):
            ck = torch.load(MOD / sub / f"fold{k}" / "best.pt", map_location=DEVICE, weights_only=False)
            m = UNet(in_ch=len(ck["channels"]), n_classes=ncls, base=32).to(DEVICE)
            m.load_state_dict(ck["state_dict"]); m.eval()
            p = predict_array(m, feats, np.asarray(ck["mu"], np.float32), np.asarray(ck["sd"], np.float32),
                              patch=patch, overlap=ov, n_classes=ncls, hann=True)[1][i:-i, i:-i]
            probs.append(p)
            pred = polygonize(p, tf, crs, float(thr_tab[k]), min_area=4.0 if task == "pit" else 50.0)
            s = match_scores(gt, pred)
            rows.append(dict(fold=k, thr=float(thr_tab[k]), n_gt=len(gt), n_pred=len(pred),
                             recall_iou30=s[0.3]["recall"], recall_iou50=s[0.5]["recall"],
                             precision_iou30_lower_bound=s[0.3]["tp"] / max(len(pred), 1)))
            print(task, rows[-1], flush=True)
        ens = np.mean(probs, 0).astype(np.float32)
        thr = float(np.mean(list(thr_tab.values)))
        pred = polygonize(ens, tf, crs, thr, min_area=4.0 if task == "pit" else 50.0)
        s = match_scores(gt, pred)
        ensd = dict(thr=thr, n_gt=len(gt), n_pred=len(pred), recall_iou30=s[0.3]["recall"], recall_iou50=s[0.5]["recall"],
                    precision_iou30_lower_bound=s[0.3]["tp"] / max(len(pred), 1))
        print(task, "ensemble", ensd, flush=True)
        prof = dict(driver="GTiff", height=ens.shape[0], width=ens.shape[1], count=1, dtype="float32", crs=crs, transform=tf, compress="deflate")
        with rasterio.open(OUT / f"{task}_prob_ens_tile616591.tif", "w", **prof) as d:
            d.write(ens, 1)
        pred.to_file(OUT / f"{task}_pred_ens_tile616591.gpkg", driver="GPKG")
        gt["found_iou30"] = [j in set(s[0.3]["matched_gt_idx"]) for j in range(len(gt))]
        gt.to_file(OUT / f"{task}_truth_scored_tile616591.gpkg", driver="GPKG")
        pd.DataFrame(rows).to_csv(OUT / f"{task}_per_fold_tile616591.csv", index=False)
        summary["tasks"][task] = dict(per_fold_mean_recall_iou30=float(np.mean([r["recall_iou30"] for r in rows])),
                                      per_fold_sd_recall_iou30=float(np.std([r["recall_iou30"] for r in rows])), ensemble=ensd)
    (OUT / "summary_tile616591.json").write_text(json.dumps(summary, indent=2))


main()

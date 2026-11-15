"""PCA of the NISAR feature bands on the lidar-placed stack, tile 9t.

Question. The scorer uses about 340 NISAR bands. How many independent directions do they hold?
Reads   nisar/derived/9t/nisar_features_5m/nisar_feat_<product>_9t_slc_5m.tif (13 products, no road context)
        nisar/derived/9t/nisar_features_5m/nisar_feature_stack_9t_slc_5m.tif (first 32 bands = amplitude statistics)
Writes  nisar/results/9t/nisar_feat_pca_{scree,group_share,loadings}_9t_slc.csv,
        nisar_feat_pca_summary_9t_slc.json, figures/nisar_feat_pca_9t_slc.png
Method  60,000 random pixels. Drop bands with over 20% missing (the scorer's rule), median-impute the rest,
        clip each band to its 1st-99th percentile, z-score, PCA by SVD. Same pixel sample for every band.
Run from the repo root: python nisar/code/s5_eval/_nisar_feat_pca_9t.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[3]
FEAT = ROOT / "nisar" / "derived" / "9t" / "nisar_features_5m"
RES = ROOT / "nisar" / "results" / "9t"
N, SEED, MISS = 60000, 20261115, 0.20
PRODUCTS = ["amp", "coherence", "dualpol", "events", "geometry", "heightresid", "losmotion",
            "rainfreeze", "spatial", "subaperture", "temporal", "texture"]

rng = np.random.default_rng(SEED)
with rasterio.open(FEAT / "nisar_feature_stack_9t_slc_5m.tif") as s:
    H, W = s.height, s.width
ix = np.sort(rng.choice(H * W, N, replace=False))
rows, cols = ix // W, ix % W

cols_data, names, groups = [], [], []


def take(path, keep=None, group=None):
    with rasterio.open(path) as s:
        arr = s.read().astype(np.float32)
        desc = list(s.descriptions)
    for b in range(arr.shape[0]):
        if keep is not None and b >= keep:
            break
        v = arr[b][rows, cols]
        v[~np.isfinite(v)] = np.nan
        cols_data.append(v)
        names.append(desc[b])
        groups.append(group)


take(FEAT / "nisar_feature_stack_9t_slc_5m.tif", keep=32, group="amp_stats")
for p in PRODUCTS:
    take(FEAT / f"nisar_feat_{p}_9t_slc_5m.tif", group=p)

X = np.array(cols_data, dtype=np.float64).T
names, groups = np.array(names), np.array(groups)
print("bands built", X.shape[1], "pixels", X.shape[0], flush=True)

miss = np.isnan(X).mean(0)
keep = miss <= MISS
X, names, groups, miss = X[:, keep], names[keep], groups[keep], miss[keep]
print("kept", X.shape[1], "dropped", int((~keep).sum()), flush=True)
X = np.where(np.isnan(X), np.nanmedian(X, 0), X)
lo, hi = np.percentile(X, [1, 99], axis=0)
X = np.clip(X, lo, hi)
sd = X.std(0)
good = sd > 1e-9
X, names, groups = X[:, good], names[good], groups[good]
Z = (X - X.mean(0)) / X.std(0)

U, S, Vt = np.linalg.svd(Z, full_matrices=False)
ev = S ** 2 / (Z.shape[0] - 1)
frac = ev / ev.sum()
cum = np.cumsum(frac)
pr = float(ev.sum() ** 2 / (ev ** 2).sum())          # participation ratio, an effective dimension
n_at = {f"pcs_for_{int(t * 100)}pct": int(np.searchsorted(cum, t) + 1) for t in (0.5, 0.8, 0.9, 0.95, 0.99)}

scree = pd.DataFrame({"pc": np.arange(1, len(frac) + 1), "var_share": frac, "cum_share": cum})
scree.to_csv(RES / "nisar_feat_pca_scree_9t_slc.csv", index=False)

track = np.array([re.search(r"_t(\d{3})$", n).group(1) if re.search(r"_t\d{3}$", n) else "cross" for n in names])
L = Vt[:10].T
load = pd.DataFrame(L, columns=[f"pc{i + 1}" for i in range(10)])
load.insert(0, "track", track)
load.insert(0, "group", groups)
load.insert(0, "band", names)
load.to_csv(RES / "nisar_feat_pca_loadings_9t_slc.csv", index=False)

# share of each PC's squared loading that sits in each product group and each track
share = []
for i in range(10):
    w = L[:, i] ** 2
    for kind, lab in (("group", groups), ("track", track)):
        for g in sorted(set(lab)):
            share.append((i + 1, kind, g, float(w[lab == g].sum())))
sh = pd.DataFrame(share, columns=["pc", "kind", "label", "share_of_pc"])
sh.to_csv(RES / "nisar_feat_pca_group_share_9t_slc.csv", index=False)

summary = dict(pixels=int(Z.shape[0]), bands_input=int(len(miss)), bands_kept=int(Z.shape[1]),
               missing_rule=MISS, seed=SEED, participation_ratio=round(pr, 1),
               var_pc1=round(float(frac[0]), 3), var_first5=round(float(cum[4]), 3),
               var_first10=round(float(cum[9]), 3), **n_at)
json.dump(summary, open(RES / "nisar_feat_pca_summary_9t_slc.json", "w"), indent=2)
print(json.dumps(summary, indent=2))

# a second, tighter view: the same PCA within each track alone (are the three tracks redundant?)
per_track = {}
for t in ("026", "090", "162"):
    m = track == t
    ev_t = np.linalg.svd(Z[:, m], compute_uv=False) ** 2
    c = np.cumsum(ev_t / ev_t.sum())
    per_track[t] = dict(bands=int(m.sum()), pcs_for_90pct=int(np.searchsorted(c, 0.9) + 1))
print("per track", per_track)
summary["per_track_alone"] = per_track
json.dump(summary, open(RES / "nisar_feat_pca_summary_9t_slc.json", "w"), indent=2)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
BLUE, ORANGE, GREY = "#1F5FA8", "#D97706", "#8E959B"
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
k = min(60, len(frac))
ax[0].bar(range(1, k + 1), frac[:k] * 100, color=BLUE)
ax[0].set_xlabel("principal component")
ax[0].set_ylabel("share of variance (%)")
ax[0].set_title("Variance in each component", fontsize=10)
a2 = ax[0].twinx()
a2.plot(range(1, k + 1), cum[:k] * 100, color=ORANGE, marker="o", ms=3)
a2.set_ylabel("cumulative (%)")
for t, ls in ((0.9, "--"), (0.99, ":")):
    a2.axhline(t * 100, color=GREY, ls=ls, lw=1)
sub = sh[(sh.kind == "group") & (sh.pc <= 5)].pivot(index="label", columns="pc", values="share_of_pc")
sub = sub.loc[sub.mean(1).sort_values(ascending=False).index]
im = ax[1].imshow(sub.values, cmap="Blues", aspect="auto")
ax[1].set_yticks(range(len(sub)))
ax[1].set_yticklabels(sub.index, fontsize=8)
ax[1].set_xticks(range(5))
ax[1].set_xticklabels([f"PC{i}" for i in range(1, 6)])
for r in range(sub.shape[0]):
    for c in range(5):
        ax[1].text(c, r, f"{sub.values[r, c] * 100:.0f}", ha="center", va="center", fontsize=7)
ax[1].set_title("Where each component's weight sits (% by product)", fontsize=10)
fig.tight_layout()
(RES / "figures").mkdir(exist_ok=True)
fig.savefig(RES / "figures" / "nisar_feat_pca_9t_slc.png", dpi=150)
print("done")

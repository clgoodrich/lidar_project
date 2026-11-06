"""Survey-identity probe on frozen pretrained embeddings (7.1 QC item 7). Reported, not a gate.

Purpose
    A linear probe predicts the survey window of a chip from the frozen bottleneck embedding
    (global-average-pooled output of the U-Net `bot` block). Accuracy well above chance warns that the
    encoder learned the sensor or vintage, not terrain. Five-fold cross-validation grouped so that
    overlapping chips never sit on both sides. Also reports the embedding std across chips (collapse).

Inputs
    --ckpt  checkpoint from _ssl_pretrain_objectives_us.py
    --index chip index CSV and --stats NPZ from _ssl_corpus_chips_us.py
Outputs
    expansions/7_scale/7_1_pretraining/results/tables/ssl_identity_probe_<arm>_seed<s>.json

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_identity_probe_us.py --ckpt expansions/7_scale/7_1_pretraining/models/A2_seed0/ssl_A2_seed0.pt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ssl_pretrain_objectives_us import CFG, ChipDataset, ek, load_cfg, need  # noqa: E402
from _dl import UNet  # noqa: E402


def embed(ckpt: Path, index: pd.DataFrame, mu, sd, max_chips: int, seed: int, device: str = "cpu"):
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    m = UNet(in_ch=ck["in_ch"], n_classes=ck["out_ch"], base=ck["base"])
    m.load_state_dict(ck["state_dict"])
    m.eval().to(device)
    feats = {}
    m.bot.register_forward_hook(lambda mod, i, o: feats.__setitem__("z", o.mean((2, 3)).detach().cpu()))
    idx = index.iloc[np.random.default_rng(seed).permutation(len(index))[:max_chips]].copy()
    idx["win_code"] = idx["window_id"].astype("category").cat.codes
    ds = ChipDataset(idx, mu, sd, seed=seed, augment=False)
    Z = []
    with torch.no_grad():
        for i in range(len(ds)):
            x, _, _ = ds[i]
            m(x[None].to(device))
            Z.append(feats["z"][0].numpy())
    return np.stack(Z), idx, ck


def probe(Z: np.ndarray, idx: pd.DataFrame, seed: int) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler
    y = idx["window_id"].astype(str).to_numpy()
    # Group chips by a 2 x chip-size grid cell so overlapping chips stay on one side.
    grp = (idx["window_id"].astype(str) + "_" + (idx["row"] // (2 * idx["size"])).astype(str) + "_" +
           (idx["col"] // (2 * idx["size"])).astype(str)).to_numpy()
    n_classes = len(set(y))
    chance = float(pd.Series(y).value_counts(normalize=True).max())
    if n_classes < 2:
        return {"accuracy": None, "chance": 1.0, "note": "one window only. The probe needs at least two"}
    k = min(5, len(set(grp)))
    accs = []
    for tr, te in GroupKFold(n_splits=k).split(Z, y, grp):
        if len(set(y[tr])) < 2:
            continue
        sc = StandardScaler().fit(Z[tr])
        clf = LogisticRegression(max_iter=2000, random_state=seed).fit(sc.transform(Z[tr]), y[tr])
        accs.append(float((clf.predict(sc.transform(Z[te])) == y[te]).mean()))
    return {"accuracy": float(np.mean(accs)) if accs else None, "fold_acc": accs, "chance": chance,
            "n_windows": n_classes, "n_chips": len(y),
            "warning": bool(accs and np.mean(accs) > chance + 0.5 * (1 - chance))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.1 survey-identity probe.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--index", default=str(ek.sub("7.1", "data/processed") / "ssl_chip_index_us.csv"))
    ap.add_argument("--stats", default=str(ek.sub("7.1", "data/processed") / "ssl_norm_stats_us.npz"))
    ap.add_argument("--max-chips", type=int, default=2000)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        ck = need(Path(a.ckpt), "pretrained checkpoint")
        st = np.load(need(Path(a.stats), "norm stats"))
        index = pd.read_csv(need(Path(a.index), "chip index"))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    Z, idx, meta = embed(ck, index, st["mu"], st["sd"], a.max_chips, cfg["master_seed"], a.device)
    res = {"ckpt": str(ck), "ckpt_sha256": ek.sha256(ck), "arm": meta["arm"], "seed": meta["seed"],
           "embed_std_mean": float(Z.std(0).mean()), **probe(Z, idx, cfg["master_seed"])}
    out = ek.sub("7.1", "results/tables") / f"ssl_identity_probe_{meta['arm']}_seed{meta['seed']}.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

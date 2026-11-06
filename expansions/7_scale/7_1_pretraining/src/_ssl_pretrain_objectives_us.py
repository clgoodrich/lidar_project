"""Self-supervised pretraining of the 7.8 M U-Net on unlabelled terrain chips (7.1 S2).

Purpose
    Three objectives on the same network as the supervised arms (notebooks/wellsight_v2/_dl.py UNet).
    A1 masked reconstruction. Mask 50% of 16 px patches in every channel. Reconstruct the detrended
       elevation (lrm_25) and local relief (lrm_5) in masked patches. L1 on masked pixels only.
    A2 cross-channel contrast. View one keeps the slope and texture channels, view two the relief and
       openness channels. The network's 1x1 output conv is the projection head. Per-pixel InfoNCE
       (temperature 0.1). Positives are the same pixel in both views. Negatives are other pixels in the
       batch. Half of each batch comes from one survey window, so window identity alone cannot solve it.
    A3 both losses summed with equal weights fixed before running.
    The supervised fine-tune (_ssl_finetune_pit_9t.py) loads the trunk and replaces the output conv.

    Collapse checks (fw_7_1 section 9 item 6) are logged every epoch. Embedding std across the batch
    must stay above a floor. Reconstruction L1 must fall below the mean-fill baseline.

Inputs
    --index  chip index CSV from _ssl_corpus_chips_us.py (window_id, stack_path, row, col, size, ...)
    --stats  corpus normalisation stats NPZ (mu, sd) from the same script
    config_7_1.json (objective parameters)
Outputs
    expansions/7_scale/7_1_pretraining/models/<arm>_seed<s>/ssl_<arm>_seed<s>.pt  (gitignored)
    .../pretrain_log.csv, _PROVENANCE.json with the checkpoint SHA-256

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_pretrain_objectives_us.py --arm A1 --seed 0 \
        --index expansions/7_scale/7_1_pretraining/data/processed/ssl_chip_index_us.csv \
        --stats expansions/7_scale/7_1_pretraining/data/processed/ssl_norm_stats_us.npz
    Smoke (one CPU batch): add --max-steps 1 --device cpu --batch 2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
from _dl import UNet, normalize, random_d4  # noqa: E402

HERE = Path(__file__).resolve().parent
CFG = HERE / "config_7_1.json"
ARMS = ("A1", "A2", "A3")


def load_cfg(path: Path = CFG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cfg_path(entry: dict) -> Path:
    return ek.path_for(entry["key"]) / entry["rel"]


def need(path: Path, what: str) -> Path:
    if not Path(path).exists():
        raise FileNotFoundError(f"missing input for 7.1 ({what}): {path}. See config_7_1.json")
    return Path(path)


# ----------------------------------------------------------------------------- data
class ChipDataset(torch.utils.data.Dataset):
    """Reads chips lazily from per-window stacks. Normalises with corpus stats. D4 augmentation."""

    def __init__(self, index: pd.DataFrame, mu: np.ndarray, sd: np.ndarray, seed: int, augment: bool = True):
        self.index = index.reset_index(drop=True)
        self.mu, self.sd = mu.astype(np.float32), sd.astype(np.float32)
        self.seed, self.augment = seed, augment
        self._open: dict = {}

    def __len__(self) -> int:
        return len(self.index)

    def _src(self, path):
        import rasterio
        if path not in self._open:
            self._open[path] = rasterio.open(path)
        return self._open[path]

    def __getitem__(self, i):
        from rasterio.windows import Window
        r = self.index.iloc[i]
        s = int(r["size"])
        a = self._src(r["stack_path"]).read(window=Window(int(r["col"]), int(r["row"]), s, s),
                                            boundless=True, fill_value=np.nan).astype(np.float32)
        valid = np.isfinite(a).all(0)
        x = normalize(a, self.mu, self.sd).astype(np.float32)
        if self.augment:
            rng = np.random.default_rng(self.seed * 1_000_003 + i)
            x, v = random_d4(x, valid.astype(np.uint8), rng)
            valid = v.astype(bool)
        return torch.from_numpy(np.ascontiguousarray(x)), torch.from_numpy(np.ascontiguousarray(valid)), int(r["win_code"])


class WindowGroupedBatchSampler(torch.utils.data.Sampler):
    """Each batch takes `share` of its chips from one window, non-overlapping, the rest at random."""

    def __init__(self, index: pd.DataFrame, batch: int, share: float, seed: int, n_batches: int):
        self.index, self.batch, self.share, self.seed, self.n = index.reset_index(drop=True), batch, share, seed, n_batches
        self.by_win = {w: g.index.to_numpy() for w, g in self.index.groupby("window_id")}

    def __len__(self) -> int:
        return self.n

    def __iter__(self):
        rng = np.random.default_rng(self.seed)
        wins = sorted(self.by_win)
        for _ in range(self.n):
            w = wins[rng.integers(len(wins))]
            pool = rng.permutation(self.by_win[w])
            pick: list[int] = []
            for j in pool:
                r = self.index.loc[j]
                if all(abs(r["row"] - self.index.loc[k, "row"]) >= r["size"] or
                       abs(r["col"] - self.index.loc[k, "col"]) >= r["size"] for k in pick):
                    pick.append(int(j))
                if len(pick) >= max(1, int(round(self.batch * self.share))):
                    break
            rest = rng.choice(len(self.index), self.batch - len(pick), replace=len(self.index) < self.batch - len(pick))
            yield pick + [int(x) for x in rest]


# ----------------------------------------------------------------------------- objectives
def patch_mask(shape, patch: int, ratio: float, gen: torch.Generator) -> torch.Tensor:
    """(B, H, W) bool, True where masked. Whole patch x patch squares."""
    B, H, W = shape
    gh, gw = -(-H // patch), -(-W // patch)
    m = torch.rand((B, gh, gw), generator=gen) < ratio
    return m.repeat_interleave(patch, 1).repeat_interleave(patch, 2)[:, :H, :W]


def masked_l1(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    m = mask.unsqueeze(1).expand_as(target).float()
    return (torch.abs(pred - target) * m).sum() / m.sum().clamp_min(1)


def mean_fill_l1(x_target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Baseline. Predict each chip's mean of visible pixels at masked pixels."""
    vis = (~mask).unsqueeze(1).float()
    mean = (x_target * vis).sum((2, 3), keepdim=True) / vis.sum((2, 3), keepdim=True).clamp_min(1)
    return masked_l1(mean.expand_as(x_target), x_target, mask)


def info_nce(z1: torch.Tensor, z2: torch.Tensor, valid: torch.Tensor, n_pix: int, tau: float,
             gen: torch.Generator) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-pixel symmetric InfoNCE. z (B, D, H, W). Samples n_pix valid pixels per chip.

    Returns (loss, embedding std across sampled pixels, mean over dims) for the collapse check.
    """
    B, D, H, W = z1.shape
    e1, e2 = [], []
    for b in range(B):
        idx = torch.nonzero(valid[b].flatten(), as_tuple=False).flatten()
        if len(idx) == 0:
            continue
        sel = idx[torch.randint(len(idx), (n_pix,), generator=gen)]
        e1.append(z1[b].flatten(1)[:, sel].T)
        e2.append(z2[b].flatten(1)[:, sel].T)
    a = F.normalize(torch.cat(e1), dim=1)
    c = F.normalize(torch.cat(e2), dim=1)
    logits = a @ c.T / tau
    y = torch.arange(len(a), device=a.device)
    loss = 0.5 * (F.cross_entropy(logits, y) + F.cross_entropy(logits.T, y))
    return loss, a.std(0).mean()


def view(x: torch.Tensor, keep: list[int]) -> torch.Tensor:
    v = torch.zeros_like(x)
    v[:, keep] = x[:, keep]
    return v


def out_channels(arm: str, cfg: dict) -> int:
    p = cfg["pretrain"]
    nt, d = len(p["mask"]["targets"]), p["contrast"]["embed_dim"]
    return {"A1": nt, "A2": d, "A3": nt + d}[arm]


def build_model(arm: str, cfg: dict) -> UNet:
    return UNet(in_ch=len(cfg["channels"]), n_classes=out_channels(arm, cfg), base=cfg["unet_base"])


def step_loss(model, x, valid, arm: str, cfg: dict, gen: torch.Generator) -> dict:
    """One batch of the chosen objective. Returns dict of tensors (loss) and floats (diagnostics)."""
    p, ch = cfg["pretrain"], cfg["channels"]
    nt = len(p["mask"]["targets"])
    tgt_idx = [ch.index(c) for c in p["mask"]["targets"]]
    out = {}
    total = 0.0
    if arm in ("A1", "A3"):
        m = patch_mask(valid.shape, p["mask"]["patch_px"], p["mask"]["ratio"], gen).to(x.device) & valid
        xin = x.masked_fill(m.unsqueeze(1), 0.0)
        pred = model(xin)[:, :nt]
        tgt = x[:, tgt_idx]
        l_rec = masked_l1(pred, tgt, m)
        out["rec_l1"] = float(l_rec.detach())
        out["mean_fill_l1"] = float(mean_fill_l1(tgt, m))
        total = total + p["combined_weights"][0] * l_rec
    if arm in ("A2", "A3"):
        c = p["contrast"]
        v1 = [ch.index(k) for k in c["view1"]]
        v2 = [ch.index(k) for k in c["view2"]]
        off = nt if arm == "A3" else 0
        z1 = model(view(x, v1))[:, off:off + c["embed_dim"]]
        z2 = model(view(x, v2))[:, off:off + c["embed_dim"]]
        l_nce, estd = info_nce(z1, z2, valid, c["pixels_per_chip"], c["temperature"], gen)
        out["nce"] = float(l_nce.detach())
        out["embed_std"] = float(estd.detach())
        total = total + (p["combined_weights"][1] if arm == "A3" else 1.0) * l_nce
    out["loss"] = total
    return out


# ----------------------------------------------------------------------------- driver
def pretrain(arm: str, seed: int, index: pd.DataFrame, mu, sd, cfg: dict, out_dir: Path, *,
             device: str = "auto", max_steps: int | None = None, batch: int | None = None,
             epochs: int | None = None) -> Path:
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    dev = torch.device("cuda" if device == "auto" and torch.cuda.is_available() else
                       "cpu" if device == "auto" else device)
    s = ek.child_seed(cfg["master_seed"], 0, ARMS.index(arm) + 1) + 100 * seed
    torch.manual_seed(s); np.random.seed(s % (2**32))
    p = cfg["pretrain"]
    batch = batch or p["batch"]
    epochs = epochs or p["epochs"]
    index = index.copy()
    index["win_code"] = index["window_id"].astype("category").cat.codes
    ds = ChipDataset(index, mu, sd, seed=s)
    n_batches = max(1, len(index) // batch)
    model = build_model(arm, cfg).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=p["lr"], weight_decay=p["weight_decay"])
    gen = torch.Generator().manual_seed(s)
    out_dir.mkdir(parents=True, exist_ok=True)
    log, step = [], 0
    for ep in range(1, epochs + 1):
        sampler = WindowGroupedBatchSampler(index, batch, p["contrast"]["same_window_share"], s + ep, n_batches)
        loader = torch.utils.data.DataLoader(ds, batch_sampler=sampler, num_workers=0)
        t0 = time.time()
        model.train()
        agg: dict = {}
        for x, valid, _ in loader:
            x, valid = x.to(dev), valid.to(dev)
            opt.zero_grad(set_to_none=True)
            o = step_loss(model, x, valid, arm, cfg, gen)
            o["loss"].backward()
            opt.step()
            for k, v in o.items():
                agg.setdefault(k, []).append(float(v))
            step += 1
            if max_steps and step >= max_steps:
                break
        row = {"epoch": ep, "sec": time.time() - t0, **{k: float(np.mean(v)) for k, v in agg.items()}}
        row["collapse_flag"] = bool(("embed_std" in row and row["embed_std"] < p["collapse_embed_std_floor"]) or
                                    ("rec_l1" in row and row["rec_l1"] >= row["mean_fill_l1"] and ep > 1))
        log.append(row)
        print(json.dumps(row))
        if max_steps and step >= max_steps:
            break
    ck = out_dir / f"ssl_{arm}_seed{seed}.pt"
    torch.save({"state_dict": model.state_dict(), "arm": arm, "seed": seed, "child_seed": s,
                "in_ch": len(cfg["channels"]), "out_ch": out_channels(arm, cfg), "base": cfg["unet_base"],
                "channels": cfg["channels"], "corpus_mu": np.asarray(mu), "corpus_sd": np.asarray(sd),
                "pretrain_cfg": p, "steps": step}, ck)
    pd.DataFrame(log).to_csv(out_dir / "pretrain_log.csv", index=False)
    ek.write_provenance(out_dir, outputs=[ck, out_dir / "pretrain_log.csv"], params={"arm": arm, **p},
                        seeds={"master": cfg["master_seed"], "child": s})
    return ck


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SSL pretraining (7.1 S2).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--index", default=str(ek.sub("7.1", "data/processed") / "ssl_chip_index_us.csv"))
    ap.add_argument("--stats", default=str(ek.sub("7.1", "data/processed") / "ssl_norm_stats_us.npz"))
    ap.add_argument("--out", default=None, help="default models/<arm>_seed<s>/")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        index = pd.read_csv(need(Path(a.index), "chip index (run _ssl_corpus_chips_us.py)"))
        st = np.load(need(Path(a.stats), "corpus norm stats"))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else ek.sub("7.1", f"models/{a.arm}_seed{a.seed}")
    ck = pretrain(a.arm, a.seed, index, st["mu"], st["sd"], cfg, out, device=a.device, max_steps=a.max_steps,
                  batch=a.batch, epochs=a.epochs)
    print(f"checkpoint {ck} sha256 {ek.sha256(ck)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Fine-tune pit segmentation from a pretrained or random trunk at one label fraction (7.1 S3, S4, S6).

Purpose
    One run = one arm x fold x fraction x seed. Same loss, epochs, sampler, augmentation and rejection
    rule in every arm. Epoch count is not tuned per arm.
    Arms. A0 random init. A1, A2, A3 load a checkpoint from _ssl_pretrain_objectives_us.py and replace
    the output conv with a new 3-class head. A4 is random init plus validated labels from 6.3 added to
    the fraction's blocks. A5 (generic ImageNet encoder) is not built here and exits with a message.
    Isolation (protocol section 3 rule 3).
      - Training windows never touch a held-out, inner-validation or audit block. A window that does is
        rejected whole and redrawn.
      - Label pixels outside the fraction's blocks are set to ignore (255), so unused labels never train.
      - Normalisation statistics are fitted on the fraction's training blocks only.
    Best epoch by inner-validation floor IoU only (repo _dl.train_loop). The held-out fold is scored once.
    Held-out prediction runs per block with _dl.predict_full_tile on a clipped stack, then candidates are
    extracted and matched with the 7.3 scorer (fw_00 section 4 rules).

Inputs (config_7_1.json)
    feature stack, pit label raster, blocks (held). Label subsets JSON from _ssl_label_subsets_9t.py.
    Pretrained checkpoint for A1 to A3 (--init). Audit block CSV (from P2, optional until P2 exists,
    stated in the run record). Validated labels for A4 (from 6.3, assumed).
Outputs
    expansions/7_scale/7_1_pretraining/results/<run_id>/ with
        best.pt (gitignored copy goes to models/ft_<arm>_f<f>_s<s>_k<fold>/), train_log.csv,
        oof_candidates_<arm>_f<f>_s<seed>_k<fold>.csv, oof_blocks_<arm>_f<f>_s<seed>_k<fold>.csv,
        _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_finetune_pit_9t.py --arm A1 --fold 0 --fraction 0.25 --seed 0 \
        --init expansions/7_scale/7_1_pretraining/models/A1_seed0/ssl_A1_seed0.pt
    Smoke: add --device cpu --epochs 1 --samples 2 --batch 1
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ssl_pretrain_objectives_us import CFG, cfg_path, ek, load_cfg, need  # noqa: E402

import _dl  # noqa: E402  (path added by the import above)
from _dl import FocalCE, UNet, normalize, random_d4  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "7_3_benchmark" / "src"))
import _bench_evaluate_recall_k as sc  # noqa: E402

ARMS = ("A0", "A1", "A2", "A3", "A4", "A5")


# ----------------------------------------------------------------------------- model init
def build_init(arm: str, init: Path | None, cfg: dict) -> tuple[nn.Module, dict]:
    nc, base, cin = cfg["finetune"]["n_classes"], cfg["unet_base"], len(cfg["channels"])
    if arm in ("A0", "A4"):
        return UNet(in_ch=cin, n_classes=nc, base=base), {"init": "random"}
    if arm == "A5":
        raise NotImplementedError("A5 (unetpp_r34_imagenet reference encoder) is not built. It needs the "
                                  "segmentation_models_pytorch architecture, not the repo UNet")
    ck = torch.load(need(init, f"pretrained checkpoint for {arm}"), map_location="cpu", weights_only=False)
    if ck.get("arm") != arm:
        raise AssertionError(f"checkpoint arm {ck.get('arm')} != requested {arm}")
    if list(ck["channels"]) != list(cfg["channels"]):
        raise AssertionError("checkpoint channel order differs from config")
    m = UNet(in_ch=ck["in_ch"], n_classes=ck["out_ch"], base=ck["base"])
    m.load_state_dict(ck["state_dict"])
    m.out = nn.Conv2d(ck["base"], nc, 1)          # new segmentation head, trunk kept
    return m, {"init": str(init), "init_sha256": ek.sha256(init), "pretrain_seed": ck["seed"]}


# ----------------------------------------------------------------------------- rasters
def block_raster(blocks, transform, shape) -> np.ndarray:
    from rasterio.features import rasterize
    return rasterize([(g, int(b)) for g, b in zip(blocks.geometry, blocks["block_id"])], out_shape=shape,
                     transform=transform, fill=-1, dtype="int32")


def fold_local_stats(feat: np.ndarray, braster: np.ndarray, allowed: set, seed: int, n_px: int = 200_000):
    """Per-channel mean and sd from a random sample of pixels inside the allowed blocks only."""
    rng = np.random.default_rng(seed)
    rr, cc = np.nonzero(np.isin(braster, list(allowed)))
    pick = rng.choice(len(rr), min(n_px, len(rr)), replace=False)
    vals = feat[:, rr[pick], cc[pick]].astype(np.float64)
    mu = np.nanmean(vals, 1).astype(np.float32)
    sd = np.maximum(np.nanstd(vals, 1), 1e-6).astype(np.float32)
    return mu, sd


class IsolatedPitDataset(torch.utils.data.Dataset):
    """Windows centred on pits or random points inside allowed blocks. Whole-window rejection.

    allowed     blocks whose labels may train
    forbidden   held-out, inner-validation and audit blocks. No window pixel may fall in one
    """

    def __init__(self, feat, lbl, braster, allowed, forbidden, patch, n, mu, sd, seed, augment=True):
        self.feat, self.lbl, self.br = feat, lbl, braster
        self.allowed, self.forbidden = np.array(sorted(allowed)), np.array(sorted(forbidden))
        self.patch, self.n, self.mu, self.sd, self.seed, self.augment = patch, n, mu, sd, seed, augment
        h = patch // 2
        H, W = braster.shape
        inside = np.isin(braster, self.allowed)
        inside[:h, :] = inside[-h:, :] = False
        inside[:, :h] = inside[:, -h:] = False
        self.rand_rc = np.argwhere(inside[::4, ::4]) * 4
        self.pit_rc = np.argwhere(inside & (lbl == 1))
        self.rejected = 0
        if len(self.rand_rc) == 0:
            raise AssertionError("no admissible window centre inside the allowed blocks")

    def __len__(self):
        return self.n

    def _window_ok(self, r0, c0):
        w = self.br[r0:r0 + self.patch, c0:c0 + self.patch]
        return w.shape == (self.patch, self.patch) and not np.isin(w, self.forbidden).any()

    def __getitem__(self, i):
        rng = np.random.default_rng(self.seed * 7_919 + i)
        h = self.patch // 2
        for _ in range(200):
            pool = self.pit_rc if (i % 2 == 0 and len(self.pit_rc)) else self.rand_rc
            r, c = pool[rng.integers(len(pool))]
            r0, c0 = int(r) - h + int(rng.integers(-h // 2, h // 2 + 1)), int(c) - h + int(rng.integers(-h // 2, h // 2 + 1))
            if self._window_ok(r0, c0):
                break
            self.rejected += 1
        else:
            raise RuntimeError("could not draw an isolated window in 200 tries")
        x = normalize(self.feat[:, r0:r0 + self.patch, c0:c0 + self.patch].astype(np.float32), self.mu, self.sd)
        y = self.lbl[r0:r0 + self.patch, c0:c0 + self.patch].copy()
        y[~np.isin(self.br[r0:r0 + self.patch, c0:c0 + self.patch], self.allowed)] = 255
        if self.augment:
            x, y = random_d4(x, y, rng)
        return torch.from_numpy(np.ascontiguousarray(x, dtype=np.float32)), torch.from_numpy(np.ascontiguousarray(y).astype(np.int64))


def add_validated_labels(lbl: np.ndarray, gpkg: Path, transform, braster, extra_blocks: set) -> np.ndarray:
    """A4. Burn validated features (status == valid) as floor in their blocks. Undecided are ignore."""
    import geopandas as gpd
    from rasterio.features import rasterize
    g = gpd.read_file(need(gpkg, "validated labels from 6.3"), layer="pit_inside")
    out = lbl.copy()
    for status, val in (("valid", 1), ("undecided", 255)):
        sel = g[g["status"] == status]
        if len(sel):
            m = rasterize([(x, 1) for x in sel.geometry], out_shape=lbl.shape, transform=transform, fill=0).astype(bool)
            m &= np.isin(braster, list(extra_blocks))
            out[m] = val
    return out


# ----------------------------------------------------------------------------- held-out prediction
def predict_blocks(model, feat_path: Path, blocks, ids, mu, sd, patch, overlap):
    """Per-block clipped stack -> _dl.predict_full_tile -> floor probability cropped to the block."""
    import rasterio
    from rasterio.windows import from_bounds
    out = []
    with tempfile.TemporaryDirectory(prefix="ssl_pred_") as td, rasterio.open(feat_path) as src:
        for b in ids:
            geom = blocks.loc[blocks["block_id"] == b, "geometry"].iloc[0]
            m = patch // 2 * src.res[0]
            x0, y0, x1, y1 = geom.bounds
            w = from_bounds(x0 - m, y0 - m, x1 + m, y1 + m, transform=src.transform).round_offsets().round_lengths()
            a = src.read(window=w, boundless=True, fill_value=np.nan)
            tf = src.window_transform(w)
            p = Path(td) / f"b{b}.tif"
            with rasterio.open(p, "w", driver="GTiff", width=a.shape[2], height=a.shape[1], count=a.shape[0],
                               dtype="float32", crs=src.crs, transform=tf, nodata=np.nan) as o:
                o.write(a.astype(np.float32))
            prob, _, _ = _dl.predict_full_tile(model, p, mu, sd, patch=min(patch, a.shape[1], a.shape[2]),
                                                overlap=min(overlap, patch // 2), n_classes=3, batch=4)
            out.append(((prob[1], tf), [int(b)]))
    return out


# ----------------------------------------------------------------------------- driver
def run(cfg: dict, arm: str, fold: int, fraction: float, seed: int, subsets: dict, init: Path | None, *,
        device: str = "auto", epochs: int | None = None, samples: int | None = None, batch: int | None = None,
        audit_csv: Path | None = None, validated: Path | None = None, base_dir: Path | None = None,
        models_dir: Path | None = None) -> Path:
    import geopandas as gpd
    import rasterio
    if device != "auto":
        _dl.DEVICE = torch.device(device)
    ft = cfg["finetune"]
    epochs, samples, batch = epochs or ft["epochs"], samples or ft["samples_per_epoch"], batch or ft["batch"]
    key = f"{fold}|{seed}|{fraction}"
    if key not in subsets["subsets"]:
        raise KeyError(f"label subset {key} absent from subsets JSON")
    fobj = next(f for f in subsets["folds"] if f["fold"] == fold)
    allowed = set(subsets["subsets"][key]["blocks"])
    audit = set()
    if audit_csv is not None and Path(audit_csv).exists():
        audit = set(pd.read_csv(audit_csv)["block_id"].astype(int))
    forbidden = set(fobj["heldout"]) | set(fobj["val"]) | audit
    ek.assert_disjoint(allowed, forbidden, "fine-tune allowed vs forbidden blocks")
    cs = ek.child_seed(cfg["master_seed"], fold, ARMS.index(arm)) + 100 * seed
    torch.manual_seed(cs); np.random.seed(cs % (2**32))
    run_cfg = {"arm": arm, "fold": fold, "fraction": fraction, "seed": seed, "subset_sha256": subsets["subsets"][key]["sha256"],
               "split_source": subsets["split_source"], "epochs": epochs, "samples": samples, "batch": batch,
               "audit_guard": "P2 audit list applied" if audit else "no audit list on disk (P2 pending)"}
    rd = ek.new_run("7.1", f"ft_{arm}_f{str(fraction).replace('.', 'p')}_s{seed}_k{fold}", run_cfg, base=base_dir,
                    why="7.1 fine-tune at one label fraction.")
    inp = cfg["inputs"]
    feat_p, lbl_p = need(cfg_path(inp["feature_stack_9t"]), "feature stack"), need(cfg_path(inp["labels_pit_9t"]), "pit labels")
    blocks = gpd.read_file(need(cfg_path(inp["blocks_9t"]), "blocks"))
    blocks["block_id"] = blocks["block_id"].astype(int)
    with rasterio.open(feat_p) as r, rasterio.open(lbl_p) as rl:
        ek.assert_crs(r, "EPSG:6346"); ek.assert_crs(rl, "EPSG:6346")
        if r.transform != rl.transform or r.shape != rl.shape:
            raise AssertionError("feature stack and label raster grids differ")
        feat, lbl, tf = r.read(), rl.read(1), r.transform
    br = block_raster(blocks, tf, lbl.shape)
    if arm == "A4":
        lbl = add_validated_labels(lbl, Path(validated or cfg_path(inp["validated_labels"])), tf, br, allowed)
    mu, sd = fold_local_stats(feat, br, allowed, cs)
    model, init_info = build_init(arm, init, cfg)
    patch = ft["patch_px"] if feat.shape[1] >= 2 * ft["patch_px"] else max(32, (min(feat.shape[1:]) // 4) // 16 * 16)
    gen = torch.Generator().manual_seed(cs)
    tr = IsolatedPitDataset(feat, lbl, br, allowed, forbidden, patch, samples, mu, sd, cs)
    va = IsolatedPitDataset(feat, lbl, br, set(fobj["val"]), set(fobj["heldout"]) | audit, patch,
                            max(2, samples // 4), mu, sd, cs + 1, augment=False)
    tl = torch.utils.data.DataLoader(tr, batch_size=batch, shuffle=True, generator=gen, num_workers=0)
    vl = torch.utils.data.DataLoader(va, batch_size=batch, shuffle=False, num_workers=0)
    loss = FocalCE(ft["focal_alpha"], gamma=ft["focal_gamma"])
    res = _dl.train_loop(model=model, train_loader=tl, val_loader=vl, loss_fn=loss, epochs=epochs, lr=ft["lr"],
                         n_classes=3, out_dir=rd, score=lambda iou: iou[1] if np.isfinite(iou[1]) else 0.0,
                         checkpoint_extra={"mu": mu, "sd": sd, "arm": arm, "fold": fold, "fraction": fraction,
                                           "seed": seed, "channels": cfg["channels"], "patch": patch, **init_info},
                         extra_iou_names=("bg", "floor", "wall"))
    best = torch.load(rd / "best.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(best["state_dict"])
    specs = predict_blocks(model, feat_p, blocks, fobj["heldout"], mu, sd, patch, ft["overlap_px"])
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import read_layer
    truth = read_layer(need(cfg_path(inp["truth"]), "truth"), inp["truth"]["layer"])
    sp = cfg["scoring"]
    summ, cands = sc.evaluate(specs, truth, blocks, thr=sp["thr"], min_area_m2=sp["min_area_m2"],
                              iou_thr=sp["iou_thr"], k_per_km2=sp["k_per_km2"], B=0)
    tag = f"{arm}_f{str(fraction).replace('.', 'p')}_s{seed}_k{fold}"
    for col, v in (("arm", arm), ("fraction", fraction), ("seed", seed), ("fold", fold)):
        cands[col] = v
        summ["_blocks"][col] = v
    cands.to_csv(rd / f"oof_candidates_{tag}.csv", index=False)
    summ["_blocks"].to_csv(rd / f"oof_blocks_{tag}.csv", index=False)
    mdir = (models_dir / f"ft_{tag}") if models_dir else ek.sub("7.1", f"models/ft_{tag}")
    mdir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rd / "best.pt", mdir / "best.pt")
    (rd / "best.pt").unlink()
    ek.write_provenance(rd, inputs=[feat_p, lbl_p] + ([init] if init else []),
                        outputs=[mdir / "best.pt", rd / f"oof_candidates_{tag}.csv"],
                        params={**run_cfg, "best_score": res["best_score"], "window_rejections": tr.rejected,
                                "fold_mu": mu.tolist(), "fold_sd": sd.tolist(), **init_info},
                        seeds={"master": cfg["master_seed"], "child": cs})
    return rd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.1 fine-tune at one arm, fold, fraction and seed.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--fold", type=int, required=True)
    ap.add_argument("--fraction", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--init", default=None, help="pretrained checkpoint (A1 to A3)")
    ap.add_argument("--subsets", default=str(ek.sub("7.1", "data/processed") / "ssl_label_subsets_9t.json"))
    ap.add_argument("--audit", default=None, help="P2 audit block CSV (default config inputs.audit_blocks)")
    ap.add_argument("--validated", default=None, help="A4 validated labels GeoPackage")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        subsets = json.loads(need(Path(a.subsets), "label subsets (run _ssl_label_subsets_9t.py)").read_text())
        rd = run(cfg, a.arm, a.fold, a.fraction, a.seed, subsets, Path(a.init) if a.init else None,
                 device=a.device, epochs=a.epochs, samples=a.samples, batch=a.batch,
                 audit_csv=Path(a.audit) if a.audit else cfg_path(cfg["inputs"]["audit_blocks"]),
                 validated=Path(a.validated) if a.validated else None)
    except (FileNotFoundError, NotImplementedError) as e:
        print(e, file=sys.stderr)
        return 2
    print(f"run folder {rd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

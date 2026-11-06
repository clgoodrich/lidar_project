"""Wall-clock runtime benchmark for SSL pretraining and fine-tuning (7.1 S0, run first).

Purpose
    Time real optimiser steps of the repo U-Net by wall clock, never the dry-run estimator, which
    under-reported epoch time by 1.8 times (BACKLOG). Grid over batch sizes and patch sizes, with and
    without mixed precision. Record step time, the data-loader share of time, and peak GPU memory.
    The 1070 Ti has no tensor cores, so little AMP gain is expected. Extrapolate GPU hours only from here.
    Reads real chips from the 9t feature stack so the loader cost is real. --synthetic skips disk.

Inputs
    path_for("nine_t") / features_pit_9t_05.tif (held), config_7_1.json
Outputs
    expansions/7_scale/7_1_pretraining/results/tables/ssl_runtime_bench_9t.json
        one record per (objective, batch, patch, amp) with sec_per_step, loader_share, peak_mem_mb,
        and the extrapolated hours for the S3 loop (114 full-run equivalents of 40 epochs)

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_runtime_bench_9t.py
    Smoke: --device cpu --synthetic --steps 1 --batch-sizes 1 --patch-sizes 32
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ssl_pretrain_objectives_us import CFG, build_model, cfg_path, ek, load_cfg, need, step_loss  # noqa: E402


def chip_reader(stack: Path | None, patch: int, n_ch: int, seed: int):
    rng = np.random.default_rng(seed)
    if stack is None:
        return lambda b: torch.from_numpy(rng.normal(size=(b, n_ch, patch, patch)).astype(np.float32))
    import rasterio
    from rasterio.windows import Window
    src = rasterio.open(stack)

    def read(b):
        out = []
        for _ in range(b):
            r, c = rng.integers(0, src.height - patch), rng.integers(0, src.width - patch)
            a = src.read(window=Window(int(c), int(r), patch, patch)).astype(np.float32)
            out.append(np.nan_to_num(a))
        return torch.from_numpy(np.stack(out))
    return read


def bench_one(cfg, objective, batch, patch, amp, steps, dev, read) -> dict:
    model = build_model(objective, cfg).to(dev) if objective != "supervised" else None
    if model is None:
        import _dl
        model = _dl.UNet(in_ch=len(cfg["channels"]), n_classes=3, base=cfg["unet_base"]).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=amp and dev.type == "cuda")
    gen = torch.Generator().manual_seed(0)
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t_load = t_total = 0.0
    for i in range(steps + 1):                      # step 0 is warm-up, not timed
        t0 = time.perf_counter()
        x = read(batch).to(dev)
        t1 = time.perf_counter()
        valid = torch.ones(x.shape[0], x.shape[2], x.shape[3], dtype=torch.bool, device=dev)
        opt.zero_grad(set_to_none=True)
        with torch.amp.autocast(device_type="cuda", enabled=amp and dev.type == "cuda"):
            if objective == "supervised":
                loss = torch.nn.functional.cross_entropy(model(x), torch.zeros(x.shape[0], *x.shape[2:], dtype=torch.long, device=dev))
            else:
                loss = step_loss(model, x, valid, objective, cfg, gen)["loss"]
        scaler.scale(loss).backward() if scaler.is_enabled() else loss.backward()
        scaler.step(opt) if scaler.is_enabled() else opt.step()
        if scaler.is_enabled():
            scaler.update()
        if dev.type == "cuda":
            torch.cuda.synchronize()
        t2 = time.perf_counter()
        if i:
            t_load += t1 - t0; t_total += t2 - t0
    rec = {"objective": objective, "batch": batch, "patch": patch, "amp": amp, "steps": steps,
           "sec_per_step": t_total / steps, "loader_share": t_load / t_total if t_total else None,
           "peak_mem_mb": torch.cuda.max_memory_allocated() / 2**20 if dev.type == "cuda" else None}
    del model, opt
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return rec


def extrapolate(rec: dict, cfg: dict) -> dict:
    ft = cfg["finetune"]
    steps_per_epoch = ft["samples_per_epoch"] / rec["batch"]
    ep_h = rec["sec_per_step"] * steps_per_epoch / 3600
    n_full = sum(ft["fractions"]) * 5 * len(ft["arms"]) * len(ft["seeds"])   # 1.9 x 5 x 4 x 3 = 114
    return {"epoch_hours": ep_h, "full_run_equivalents": n_full, "s3_loop_hours": ep_h * ft["epochs"] * n_full}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.1 S0 runtime benchmark.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--device", default="auto")
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--batch-sizes", type=int, nargs="*", default=None)
    ap.add_argument("--patch-sizes", type=int, nargs="*", default=None)
    ap.add_argument("--objectives", nargs="*", default=["A1", "A2", "A3", "supervised"])
    ap.add_argument("--out", default=str(ek.sub("7.1", "results/tables") / "ssl_runtime_bench_9t.json"))
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    rb = cfg["runtime_bench"]
    dev = torch.device("cuda" if a.device == "auto" and torch.cuda.is_available() else
                       "cpu" if a.device == "auto" else a.device)
    try:
        stack = None if a.synthetic else need(cfg_path(cfg["inputs"]["feature_stack_9t"]), "9t feature stack")
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    recs = []
    for patch in a.patch_sizes or rb["patch_sizes"]:
        read = chip_reader(stack, patch, len(cfg["channels"]), cfg["master_seed"])
        for batch in a.batch_sizes or rb["batch_sizes"]:
            for obj in a.objectives:
                for amp in ([False, True] if dev.type == "cuda" else [False]):
                    try:
                        r = bench_one(cfg, obj, batch, patch, amp, a.steps or rb["steps"], dev, read)
                    except torch.cuda.OutOfMemoryError:
                        r = {"objective": obj, "batch": batch, "patch": patch, "amp": amp, "error": "out of memory"}
                        torch.cuda.empty_cache()
                    if "sec_per_step" in r and obj == "supervised":
                        r.update(extrapolate(r, cfg))
                    recs.append(r)
                    print(json.dumps(r))
    out = {"device": str(dev), "gpu": torch.cuda.get_device_name(0) if dev.type == "cuda" else None,
           "torch": torch.__version__, "synthetic": a.synthetic, "records": recs}
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

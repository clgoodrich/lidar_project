"""Roads Studio — Model Lab engine.

Launches road U-Net training runs (recreate cldice, or design a new variant)
by driving the existing sweep driver ``_road_sweep_202607.py`` with a custom
config. Training is a long GPU job, so this spawns a background subprocess,
streams its log to a file, and parses the ``ep N/M`` prints + ``train_log.csv``
for a live progress bar and loss/IoU curve. When a run finishes it writes
``road_prob_613590_1m.tif`` under ``road_sweep_202607/<name>/`` — which
``core.discover()`` then surfaces in the Extract tab's model dropdown.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRIVER = REPO / "notebooks" / "wellsight_v2" / "s3_train" / "_road_sweep_202607.py"
SWEEP = REPO / "data" / "derivatives" / "tiles" / "9t" / "road_sweep_202607"
RUNLOGS = Path(__file__).resolve().parent / "runs"
RUNLOGS.mkdir(exist_ok=True)

# The five built-in recipes, mirrored from the driver's VARIANTS so the UI can
# prefill without importing torch. `base` tells the driver which preset to
# inherit from when we hand it a custom config.
PRESETS: dict[str, dict] = {
    "cldice": dict(base="cldice", res="1m", init="corrected", loss="cldice",
                   model="unet", ep=12, lr=2e-4, corr=True, alpha_road=0.72,
                   cldice_w=0.3, cldice_iters=6),
    "boundary": dict(base="boundary", res="1m", init="corrected", loss="boundary",
                     model="unet", ep=12, lr=2e-4, corr=True, alpha_road=0.72,
                     edge_w=3.0),
    "alpha078": dict(base="alpha078", res="1m", init="corrected", loss="focal",
                     model="unet", ep=12, lr=2e-4, corr=True, alpha_road=0.78,
                     gamma=2.0),
    "orient": dict(base="orient", res="1m", init="scratch", loss="orient",
                   model="orient", ep=30, lr=1e-3, corr=True, alpha_road=0.72,
                   ori_w=0.3),
    "champion (focal, from scratch-ish)": dict(
        base="alpha078", res="1m", init="corrected", loss="focal",
        model="unet", ep=12, lr=2e-4, corr=True, alpha_road=0.72, gamma=2.0),
}

LOSSES = ["focal", "cldice", "boundary", "orient"]


def build_config(name: str, ui: dict) -> dict:
    """Turn Model Lab control values into the driver's config JSON.

    alpha is the 3-tuple (bg, road, drainage); the UI only exposes the road
    weight (the lever that matters), holding bg=0.10, drainage=0.25.
    """
    cfg = dict(
        name=name,
        base=ui.get("base", "cldice"),
        res=ui["res"],
        init=ui["init"],
        loss=ui["loss"],
        model=("orient" if ui["loss"] == "orient" else "unet"),
        ep=int(ui["ep"]),
        lr=float(ui["lr"]),
        corr=bool(ui["corr"]),
        alpha=[0.10, round(float(ui["alpha_road"]), 3), 0.25],
    )
    if ui["loss"] == "cldice":
        cfg["cldice_w"] = float(ui.get("cldice_w", 0.3))
        cfg["cldice_iters"] = int(ui.get("cldice_iters", 6))
    elif ui["loss"] == "boundary":
        cfg["edge_w"] = float(ui.get("edge_w", 3.0))
    elif ui["loss"] == "orient":
        cfg["ori_w"] = float(ui.get("ori_w", 0.3))
    else:
        cfg["gamma"] = float(ui.get("gamma", 2.0))
    return cfg


def safe_name(raw: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", raw.strip().lower()).strip("_")
    return s or "custom"


@dataclass
class TrainRun:
    name: str
    cfg: dict
    proc: subprocess.Popen
    log_path: Path
    cfg_path: Path

    @property
    def out_dir(self) -> Path:
        return SWEEP / self.name

    def running(self) -> bool:
        return self.proc.poll() is None

    def returncode(self):
        return self.proc.poll()

    def stop(self):
        """Terminate this run's process tree — matched by our recorded PID
        only, never by port or name scan."""
        if not self.running():
            return
        try:
            import psutil

            p = psutil.Process(self.proc.pid)
            for ch in p.children(recursive=True):
                ch.terminate()
            p.terminate()
        except Exception:
            self.proc.terminate()


def launch(name: str, cfg: dict) -> TrainRun:
    """Write the config, spawn the driver, tee stdout+stderr to a log file."""
    name = safe_name(name)
    cfg["name"] = name
    cfg_path = RUNLOGS / f"{name}.config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    log_path = RUNLOGS / f"{name}.log"
    log_f = open(log_path, "w", encoding="utf-8", buffering=1)
    proc = subprocess.Popen(
        [sys.executable, "-u", str(DRIVER), "--config", str(cfg_path)],
        cwd=str(REPO),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return TrainRun(name=name, cfg=cfg, proc=proc, log_path=log_path,
                    cfg_path=cfg_path)


_EP_RE = re.compile(r"ep\s+(\d+)\s*/\s*(\d+)\s+tr_loss=([\d.]+)\s+val_road_iou=([\d.]+)")


def parse_progress(log_path: Path) -> dict:
    """Scan the log tail for the latest 'ep N/M' line -> progress + metrics."""
    if not log_path.exists():
        return dict(frac=0.0, epoch=0, total=0, tr_loss=None, val_iou=None,
                    done=False, tail="")
    text = log_path.read_text(encoding="utf-8", errors="replace")
    last = None
    for m in _EP_RE.finditer(text):
        last = m
    done = "DONE ->" in text
    d = dict(done=done, tail="\n".join(text.splitlines()[-14:]))
    if last:
        ep, tot = int(last.group(1)), int(last.group(2))
        d.update(frac=ep / tot if tot else 0.0, epoch=ep, total=tot,
                 tr_loss=float(last.group(3)), val_iou=float(last.group(4)))
    else:
        d.update(frac=(1.0 if done else 0.0), epoch=0, total=0,
                 tr_loss=None, val_iou=None)
    return d


def curve(out_dir: Path) -> list[dict]:
    """Read train_log.csv (epoch, tr_loss, val_road_iou) if present."""
    p = out_dir / "train_log.csv"
    if not p.exists():
        return []
    import csv

    rows = []
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(dict(epoch=int(float(r["epoch"])),
                             tr_loss=float(r["tr_loss"]),
                             val_iou=float(r["val_road_iou"])))
    return rows

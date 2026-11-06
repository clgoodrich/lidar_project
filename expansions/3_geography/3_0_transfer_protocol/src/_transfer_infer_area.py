"""3.0 S3. Inference wrapper for a new area. Same 0.5 m derivative code as 9t, frozen weights, one declared policy.

Purpose
    1. Build 0.5 m derivatives from native target lidar with the 9t code path, by running
       `notebooks/wellsight_v2/s1_build/_build_derivatives.py` and `_build_extra_channels.py` as subprocesses.
       Native density is primary. A thinned arm is a separate sensitivity run with its own tile list.
    2. Stack the channels in the checkpoint's own channel order (0.5 m uses roughness_11). Refuse if any band
       is missing or entirely NaN, or if the count differs from the model.
    3. Load the frozen checkpoints of one model family. Normalisation comes from each checkpoint (mu, sd), or
       from the fold's `norm_stats_fold{k}.npz` when it exists (isolated trainer). Never recomputed on target.
    4. Policy. `single_fold:<k>` runs one named fold model. `fold_mean` averages class probabilities over every
       fold. Only the preregistered policy is allowed.
    5. Write the class probability raster (float32) and a 0.5 m void raster (1 where no ground return), which
       the scorer turns into a void fraction per block.
    `--dry-run` checks every input and prints the planned commands. It builds and infers nothing.
    Inference needs the GPU (minutes to an hour per area). Do not run it before the preregistration is committed.

Inputs (assumed, see config_3_0.json `infer.assumed_inputs`)
    --tiles   LAS/LAZ paths or @file with one path per line (for example data/_source/lidar/warren_sheffield/*.laz)
    --bbox    X0,Y0,X1,Y1 in EPSG:6346
    --model-dir  folder with fold{k}/best.pt (data/9t/models/pit/unet_iso_cv5/ after P1 S6, or unet_cv5)

Outputs (default C:/Users/colto/Documents/GitHub/lidar_project/data/<area>/results/transfer/inference_05/)
    derived/   derivative rasters from the 9t builder (suffix <area>_05)
    features_<area>_05.tif, <task>_prob_<area>_05.tif, void_<area>_05.tif, _PROVENANCE.json
    These rasters exceed 100 MB for a county. data/<area>/results/transfer/inference_05/ needs a .gitignore rule (lead).

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_infer_area.py --area warren --tiles "data/_source/lidar/warren_sheffield/*.laz" --bbox X0,Y0,X1,Y1 --task pit --model-dir data/9t/models/pit/unet_cv5 --policy single_fold:0 --dry-run
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _transfer_score_lib as tl  # noqa: E402
ek = tl.ek
CFG = json.loads((HERE.parent / "config_3_0.json").read_text(encoding="utf-8"))["infer"]
S1 = ek.REPO / "notebooks" / "wellsight_v2" / "s1_build"


def resolve_tiles(spec: list[str]) -> list[Path]:
    out = []
    for s in spec:
        if s.startswith("@"):
            out += [Path(x.strip()) for x in Path(s[1:]).read_text().splitlines() if x.strip()]
        else:
            out += [Path(p) for p in sorted(glob.glob(s))] or [Path(s)]
    return out


def channel_files(deriv: Path, sfx: str, channels) -> list[tuple[str, Path]]:
    """Channel rasters as the 9t builder names them. 0.5 m uses roughness_11 (see _predict_on_tile.find_channel_files)."""
    out = []
    for c in channels:
        p = deriv / f"{c}_{sfx}.tif"
        if not p.exists():
            raise SystemExit(f"channel {c} missing: {p}")
        out.append((c, p))
    return out


def stack(files: list[tuple[str, Path]], dst: Path) -> Path:
    import rasterio
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import make_profile
    with rasterio.open(files[0][1]) as r0:
        ek.assert_crs(r0)
        H, W, tf, crs = r0.height, r0.width, r0.transform, r0.crs
    prof = make_profile(width=W, height=H, transform=tf, crs=crs, dtype="float32", nodata=np.nan,
                        count=len(files), bigtiff=True)
    with rasterio.open(dst, "w", **prof) as d:
        for i, (name, p) in enumerate(files, 1):
            with rasterio.open(p) as r:
                if (r.height, r.width) != (H, W) or r.transform != tf:
                    raise AssertionError(f"{p} grid differs from {files[0][1]}")
                a = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    a[a == r.nodata] = np.nan
            if not np.isfinite(a).any():
                raise AssertionError(f"band {name} is entirely NaN")
            d.write(a, i)
            d.set_band_description(i, name)
    return dst


def load_models(model_dir: Path, policy: str, n_classes: int):
    """[(fold, model, mu, sd, ckpt_path)] for the declared policy."""
    import torch
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _dl import DEFAULT_CHANNELS, UNet
    if policy.startswith("single_fold:"):
        folds = [int(policy.split(":")[1])]
    elif policy == "fold_mean":
        folds = sorted(int(p.parent.name[4:]) for p in Path(model_dir).glob("fold*/best.pt"))
    else:
        raise SystemExit(f"policy {policy} not in {CFG['policy_choices']}")
    out = []
    for k in folds:
        cp = Path(model_dir) / f"fold{k}" / "best.pt"
        if not cp.exists():
            raise SystemExit(f"checkpoint missing: {cp}")
        ck = torch.load(cp, map_location="cpu", weights_only=False)
        chans = tuple(ck.get("channels", DEFAULT_CHANNELS))
        if chans != tuple(DEFAULT_CHANNELS):
            raise AssertionError(f"{cp} channel order {chans} differs from the 9t stack")
        npz = cp.parent / f"norm_stats_fold{k}.npz"
        if npz.exists():
            z = np.load(npz)
            mu, sd = z["mu"].astype(np.float32), z["sd"].astype(np.float32)
        else:
            mu, sd = np.asarray(ck["mu"], np.float32), np.asarray(ck["sd"], np.float32)
        m = UNet(in_ch=len(chans), n_classes=n_classes, base=32)
        m.load_state_dict(ck["model"] if "model" in ck else ck["state_dict"])
        out.append((k, m, mu, sd, cp))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="3.0 S3 inference wrapper for a new area")
    ap.add_argument("--area", required=True)
    ap.add_argument("--tiles", nargs="+", default=None)
    ap.add_argument("--bbox", default=None)
    ap.add_argument("--task", choices=("pit", "pad"), required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--policy", required=True, help="single_fold:<k> or fold_mean, as preregistered")
    ap.add_argument("--src-crs", default=None)
    ap.add_argument("--skip-build", action="store_true", help="derivatives already built in <out>/derived")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    t = CFG["tasks"][a.task]
    out = a.out_dir or (ek.area_dir(a.area) / "results" / "transfer" / "inference_05")
    deriv, sfx = out / "derived", f"{a.area}_05"
    cmds = []
    if not a.skip_build:
        if not a.tiles or not a.bbox:
            raise SystemExit("assumed inputs missing. Give --tiles (target LAS/LAZ) and --bbox (EPSG:6346), "
                             "see config_3_0.json infer.assumed_inputs")
        tiles = resolve_tiles(a.tiles)
        miss = [str(p) for p in tiles if not p.exists()]
        if miss:
            raise SystemExit(f"tiles missing: {miss[:5]}")
        b = [sys.executable, str(S1 / "_build_derivatives.py"), "--tiles", ",".join(str(p) for p in tiles),
             "--bbox", a.bbox, "--suffix", sfx, "--res", str(CFG["res_m"]), "--out-dir", str(deriv)]
        if a.src_crs:
            b += ["--src-crs", a.src_crs]
        cmds += [b, [sys.executable, str(S1 / "_build_extra_channels.py"), "--dir", str(deriv), "--sfx", sfx,
                     "--res", str(CFG["res_m"])]]
    if not a.model_dir.exists():
        raise SystemExit(f"model dir missing: {a.model_dir}")
    if a.dry_run:
        for c in cmds:
            print("would run:", " ".join(c))
        print(f"would load {a.policy} from {a.model_dir} and write {out}/{a.task}_prob_{a.area}_05.tif")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for c in cmds:
        r = subprocess.run(c)
        if r.returncode != 0:
            raise SystemExit(f"builder failed: {' '.join(c)}")
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    import rasterio
    from _common import make_profile
    from _dl import DEFAULT_CHANNELS, predict_full_tile
    feats = stack(channel_files(deriv, sfx, DEFAULT_CHANNELS), out / f"features_{a.area}_05.tif")
    models = load_models(a.model_dir, a.policy, t["n_classes"])
    acc, prof = None, None
    for k, m, mu, sd, _ in models:
        prob, _, prof = predict_full_tile(m, feats, mu, sd, patch=t["patch"], overlap=t["overlap"], n_classes=t["n_classes"])
        p = prob[t["class_index"]].astype(np.float32)
        acc = p if acc is None else acc + p
        del prob
    acc /= len(models)
    with rasterio.open(feats) as r:
        valid = np.isfinite(r.read(1))
    acc[~valid] = np.nan
    pp = make_profile(width=acc.shape[1], height=acc.shape[0], transform=prof["transform"], crs=prof["crs"],
                      dtype="float32", nodata=np.nan, bigtiff=True)
    ptif = out / f"{a.task}_prob_{a.area}_05.tif"
    with rasterio.open(ptif, "w", **pp) as d:
        d.write(acc, 1)
    gd = deriv / f"ground_density_{sfx}.tif"
    vtif = out / f"void_{a.area}_05.tif"
    if gd.exists():
        with rasterio.open(gd) as r:
            v = (r.read(1) == 0).astype(np.uint8)
            vp = make_profile(width=r.width, height=r.height, transform=r.transform, crs=r.crs, dtype="uint8",
                              nodata=255, bigtiff=True)
        with rasterio.open(vtif, "w", **vp) as d:
            d.write(v, 1)
    ek.write_provenance(out, inputs=[c for *_, c in models] + [feats], outputs=[ptif, vtif],
                        params={"policy": a.policy, "task": a.task, "area": a.area, "res_m": CFG["res_m"]})
    print(f"wrote {ptif}\nwrote {vtif}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

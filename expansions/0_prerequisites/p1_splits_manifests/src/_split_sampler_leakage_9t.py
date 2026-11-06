"""P1 S5. Window-level leakage test of the training samplers, and a trace check on fitted normalisation.

Purpose
    For every fold, draw N training windows from (a) the historical `CenteredPatchSampler` and (b) the
    isolated sampler (`IsolatedSampler` from `_pad_unet_iso_cv5.py`, the one the isolated pit trainer uses).
    The real `__getitem__` of each sampler runs. Only the raster reads are replaced by a recorder, so the
    test exercises the production window logic without reading pixels. Each window is turned into a world
    rectangle and tested exactly (shapely, positive-area overlap) against the forbidden polygons: the
    held-out and inner-validation blocks of that fold, dilated by `--buffer-m`.
    Gate. The isolated sampler gives zero leaking windows in every fold. The historical count is reported.
    It measures the original leakage and is expected to be non-zero.
    `--check-norm DIR` also checks every `norm_stats_fold{k}.npz` written by the isolated pit trainer.
    Every window it was fitted on must clear the forbidden set, and the statistics must differ between folds.

Inputs
    split file from P1 S2 (data/9t/results/splits/cv_splits_future_9t_v1.json), the manifests and blocks
    (through the trainers), the 9t feature raster header (data/9t/derived/05/features_pit_9t_05.tif)

Outputs
    <out-dir>/sampler_leakage_test_9t.json  per task and fold: windows drawn, leaking windows for each
                                            sampler, share, and the norm trace result if requested
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_sampler_leakage_9t.py --splits data/9t/results/splits/cv_splits_future_9t_v1.json [--n 100000] [--tasks pit,pad] [--check-norm data/9t/models/pit/unet_iso_cv5]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split_core_lib_9t as sc  # noqa: E402
from _split_future_write_9t import split_file_for  # noqa: E402
ek = sc.ek


class _Recorder:
    """Stands in for an open rasterio dataset. Records every window and returns 1x1 arrays."""

    def __init__(self, height: int, width: int, count: int):
        self.height, self.width, self.count = height, width, count
        self.windows: list[tuple[int, int, int, int]] = []

    def read(self, *args, window=None, **kw):
        self.windows.append((int(window.row_off), int(window.col_off), int(window.height), int(window.width)))
        if args:                                   # label read, band 1
            return np.zeros((1, 1), np.uint8)
        return np.zeros((self.count, 1, 1), np.float32)


def draw_windows(sampler, n: int, height: int, width: int, n_ch: int, seed: int | None = None) -> np.ndarray:
    """Run the sampler's own __getitem__ n times. Returns an (n, 2) array of (row_off, col_off)."""
    feat, lbl = _Recorder(height, width, n_ch), _Recorder(height, width, 1)
    sampler._feat, sampler._lbl = feat, lbl
    if seed is not None:
        sampler._rng = np.random.default_rng(seed)
    sampler.augment = False
    fails = 0
    for i in range(n):
        try:
            sampler[i]
        except RuntimeError:                      # isolated sampler found no clear window in 300 draws
            fails += 1
    rc = np.array([(w[0], w[1]) for w in feat.windows], int).reshape(-1, 2)
    draw_windows.last_failures = fails
    return rc


def forbidden_polys(blocks_gdf, ids, buffer_m: float = 0.0):
    g = blocks_gdf[blocks_gdf.block_id.astype(int).isin([int(b) for b in ids])].geometry
    return list(g.buffer(buffer_m, join_style="mitre") if buffer_m > 0 else g)


def build_samplers(task: str, roles: dict, man, blocks_gdf, feat_path: Path, transform, patch: int,
                   jitter: float, n_ch: int, buffer_m: float, seed: int):
    """Historical and isolated training samplers for one fold, built the way the trainers build them."""
    from _dl import CenteredPatchSampler
    iso_mod = isolated_module()
    tr, forbid_ids = roles["train"], roles["held_out"] + roles["inner_val"]
    pts = man.loc[man.block_id.isin(tr), ["centroid_x", "centroid_y"]].to_numpy()
    bb = np.array([g.bounds for g in blocks_gdf[blocks_gdf.block_id.astype(int).isin(tr)].geometry])
    mu, sd = np.zeros(n_ch, np.float32), np.ones(n_ch, np.float32)
    kw = dict(feat_path=feat_path, lbl_path=feat_path, policies=[(task, pts, jitter)], block_bounds=bb,
              transform=transform, mu=mu, sd=sd, patch=patch, augment=False, seed=seed)
    forbid = forbidden_polys(blocks_gdf, forbid_ids, buffer_m)
    return CenteredPatchSampler(**kw), iso_mod.IsolatedSampler(**kw, forbid=forbid), forbid


def isolated_module():
    """The isolated pad trainer module, imported read-only for its IsolatedSampler."""
    import importlib
    if str(sc.S3_TRAIN) not in sys.path:
        sys.path.insert(0, str(sc.S3_TRAIN))
    return importlib.import_module("_pad_unet_iso_cv5")


def leakage_for_task(task: str, splits: dict, man, blocks_gdf, feat_path: Path, n: int, buffer_m: float,
                     patch: int, jitter: float) -> dict:
    import rasterio
    with rasterio.open(feat_path) as r:
        H, W, C, tf = r.height, r.width, r.count, r.transform
    out = {}
    for f, roles in splits.items():
        hist, iso, forbid = build_samplers(task, roles, man, blocks_gdf, feat_path, tf, patch, jitter, C,
                                           buffer_m, seed=ek.child_seed(1, f))
        res = {"n_windows": n, "patch_px": patch, "buffer_m": buffer_m, "n_forbidden_blocks": len(forbid)}
        for name, s in (("historical", hist), ("isolated", iso)):
            rc = draw_windows(s, n, H, W, C, seed=ek.child_seed(7, f))
            boxes = sc.window_boxes(rc[:, 0], rc[:, 1], patch, tf)
            k, _ = sc.count_window_leaks(boxes, forbid)
            res[f"{name}_no_window"] = draw_windows.last_failures
            res[f"{name}_leaking"] = k
            res[f"{name}_share"] = round(k / max(len(rc), 1), 6)
        out[str(f)] = res
    return out


def check_norm(model_dir: Path, splits: dict, blocks_gdf, transform, buffer_m: float = 0.0) -> dict:
    """Every fitted normalisation object traced to training windows only, and fold-local."""
    res, mus = {}, []
    for f, roles in splits.items():
        p = Path(model_dir) / f"fold{f}" / f"norm_stats_fold{f}.npz"
        if not p.exists():
            res[str(f)] = {"present": False}
            continue
        z = np.load(p)
        forbid = forbidden_polys(blocks_gdf, roles["held_out"] + roles["inner_val"], buffer_m)
        boxes = sc.window_boxes(z["r0"], z["c0"], int(z["patch"]), transform)
        k, _ = sc.count_window_leaks(boxes, forbid)
        mus.append(z["mu"])
        res[str(f)] = {"present": True, "n_windows": int(len(z["r0"])), "leaking_windows": k,
                       "split_sha256": str(z["split_sha256"]) if "split_sha256" in z else None}
    distinct = len({m.tobytes() for m in mus}) == len(mus) if len(mus) > 1 else None
    res["stats_differ_between_folds"] = distinct
    res["pass"] = bool(mus) and all(v.get("leaking_windows", 0) == 0 for k, v in res.items()
                                    if isinstance(v, dict) and v.get("present")) and distinct is not False
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S5 sampler leakage test")
    ap.add_argument("--splits", type=Path, required=True, help="split file from P1 S2")
    ap.add_argument("--tasks", default="pit,pad")
    ap.add_argument("--n", type=int, default=100_000, help="windows per fold per sampler")
    ap.add_argument("--buffer-m", type=float, default=0.0, help="dilate forbidden blocks (P1 S4 buffer)")
    ap.add_argument("--check-norm", type=Path, default=None, help="isolated pit model dir with norm_stats_fold*.npz")
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    a = ap.parse_args(argv)
    if not a.splits.exists():
        raise SystemExit(f"split file not found: {a.splits}. Run _split_future_write_9t.py first (P1 S2).")
    import geopandas as gpd
    import rasterio
    res = {"splits": str(a.splits), "splits_sha256": ek.sha256(a.splits), "tasks": {}}
    for task in a.tasks.split(","):
        p = sc.task_params(task)
        man = sc.load_manifest(task)
        blocks = gpd.read_file(p["blocks"], layer="blocks")
        ek.assert_crs(blocks)
        feat = sc.trainer(task).FEATURES
        res["tasks"][task] = leakage_for_task(task, split_file_for(task, a.splits), man, blocks, Path(feat),
                                              a.n, a.buffer_m, p["patch"], p["jitter_m"])
    if a.check_norm:
        p = sc.task_params("pit")
        blocks = gpd.read_file(p["blocks"], layer="blocks")
        with rasterio.open(sc.trainer("pit").FEATURES) as r:
            tf = r.transform
        res["norm_trace"] = check_norm(a.check_norm, split_file_for("pit", a.splits), blocks, tf, a.buffer_m)
    iso_ok = all(v["isolated_leaking"] == 0 for t in res["tasks"].values() for v in t.values())
    res["gate"] = "pass" if iso_ok and res.get("norm_trace", {}).get("pass", True) else "fail"
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    out.mkdir(parents=True, exist_ok=True)
    js = out / "sampler_leakage_test_9t.json"
    js.write_text(json.dumps(res, indent=2), encoding="utf-8")
    run = ek.new_run("p1", "sampler_leakage", {"n": a.n, "tasks": a.tasks, "buffer_m": a.buffer_m},
                     why="S5 window-level leakage test.")
    ek.write_provenance(run, inputs=[a.splits], outputs=[js])
    for t, v in res["tasks"].items():
        print(t, {f: (x["historical_leaking"], x["isolated_leaking"]) for f, x in v.items()},
              "(historical, isolated) leaking windows per fold")
    print(f"gate {res['gate']}\nwrote {js}\nrun record {run}")
    return 0 if res["gate"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

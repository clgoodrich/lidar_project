"""Build the unlabelled pretraining corpus index and its normalisation stats (7.1 S1).

Purpose
    For each admitted window (one 7-band 0.5 m derivative stack), list 256 px chips at stride 192.
    Drop a chip when over 20% of its pixels are nodata, or when its footprint touches any exclusion
    geometry (all of 9t, all of Warren, every audit block plus buffer). Counts of each drop are logged.
    Chips are an index into the stacks, not copies, so the corpus costs no extra disk.
    Normalisation statistics come from corpus chips only. Fine-tuning refits its own fold-local stats.
    Optional --build-missing calls the repo derivative builder for windows whose stack is absent but
    whose laz_glob and bbox are given (notebooks/wellsight_v2/s1_build/_build_derivatives.py, then the
    stacking step of s4_infer/_predict_on_tile.py). Those products land in data/<window_id>/ (area-major).

Inputs
    corpus window CSV (config inputs.corpus_windows, assumed). Columns window_id, stack_path, ground_ppsm,
    optional laz_glob, bbox.
    exclusion vectors (config inputs.corpus_exclusions). A missing exclusion file is an error, never a skip.
Outputs
    expansions/7_scale/7_1_pretraining/data/processed/ssl_chip_index_us.csv
        window_id, stack_path, row, col, size, x0, y0, x1, y1, nodata_frac, ground_ppsm, density_bin
    expansions/7_scale/7_1_pretraining/data/processed/ssl_norm_stats_us.npz   (mu, sd, channels)
    expansions/7_scale/7_1_pretraining/data/processed/ssl_corpus_summary_us.json

Run
    python expansions/7_scale/7_1_pretraining/src/_ssl_corpus_chips_us.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ssl_pretrain_objectives_us import CFG, cfg_path, ek, load_cfg, need  # noqa: E402


def load_exclusions(entries: list, crs: str):
    import geopandas as gpd
    from shapely.ops import unary_union
    geoms = []
    for e in entries:
        p = need(cfg_path(e), f"exclusion footprint {e.get('what', '')}")
        g = gpd.read_file(p).to_crs(crs)
        geoms.append(unary_union(g.geometry.values))
    return unary_union(geoms) if geoms else None


def build_missing(row, cfg) -> Path:
    """Build a 0.5 m stack for one window with the repo builder. Returns the stack path."""
    sfx = f"{row['window_id']}_05"
    cmd = [sys.executable, str(ek.REPO / "notebooks/wellsight_v2/s1_build/_build_derivatives.py"),
           "--tiles", str(row["laz_glob"]), "--bbox", str(row["bbox"]), "--suffix", sfx, "--res", "0.5"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"derivative build failed for {row['window_id']}: {r.stderr[-800:]}")
    sys.path.insert(0, str(ek.REPO / "notebooks/wellsight_v2/s4_infer"))
    from _predict_on_tile import stack_features
    out = ek.area_dir(sfx) / "derived" / f"features_{sfx}.tif"
    return stack_features(sfx, out)


def chips_for_window(stack: Path, wid: str, ppsm: float, cfg: dict, excl):
    import rasterio
    from rasterio.windows import Window
    from shapely.geometry import box
    c = cfg["corpus"]
    size, stride = c["chip_px"], c["stride_px"]
    rows, drops = [], {"nodata": 0, "excluded": 0}
    with rasterio.open(stack) as r:
        if r.crs is None or not r.crs.is_projected:
            raise AssertionError(f"{stack}: CRS missing or geographic ({r.crs})")
        if r.count != len(cfg["channels"]):
            raise AssertionError(f"{stack}: {r.count} bands, expected {len(cfg['channels'])}")
        for row in range(0, max(r.height - size, 0) + 1, stride):
            for col in range(0, max(r.width - size, 0) + 1, stride):
                w = Window(col, row, size, size)
                x0, y1 = r.transform * (col, row)
                x1, y0 = r.transform * (col + size, row + size)
                fp = box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                if excl is not None and fp.intersects(excl):
                    drops["excluded"] += 1
                    continue
                b1 = r.read(1, window=w).astype(np.float32)
                bad = ~np.isfinite(b1) if r.nodata is None or np.isnan(r.nodata) else (b1 == r.nodata) | ~np.isfinite(b1)
                frac = float(bad.mean())
                if frac > c["max_nodata_frac"]:
                    drops["nodata"] += 1
                    continue
                rows.append({"window_id": wid, "stack_path": str(stack), "row": row, "col": col, "size": size,
                             "x0": fp.bounds[0], "y0": fp.bounds[1], "x1": fp.bounds[2], "y1": fp.bounds[3],
                             "nodata_frac": round(frac, 4), "ground_ppsm": ppsm})
    return rows, drops


def norm_stats(index: pd.DataFrame, n_sample: int, seed: int, n_ch: int):
    import rasterio
    from rasterio.windows import Window
    rng = np.random.default_rng(seed)
    pick = index.iloc[rng.permutation(len(index))[:n_sample]]
    s, s2, n = np.zeros(n_ch), np.zeros(n_ch), np.zeros(n_ch)
    for path, g in pick.groupby("stack_path"):
        with rasterio.open(path) as r:
            for _, c in g.iterrows():
                a = r.read(window=Window(int(c["col"]), int(c["row"]), int(c["size"]), int(c["size"]))).astype(np.float64)
                for k in range(n_ch):
                    v = a[k][np.isfinite(a[k])]
                    s[k] += v.sum(); s2[k] += (v * v).sum(); n[k] += v.size
    mu = s / np.maximum(n, 1)
    sd = np.sqrt(np.maximum(s2 / np.maximum(n, 1) - mu * mu, 1e-12))
    return mu.astype(np.float32), np.maximum(sd, 1e-6).astype(np.float32)


def build_corpus(cfg: dict, windows: pd.DataFrame, out_dir: Path, build: bool = False) -> dict:
    excl = load_exclusions(cfg["inputs"]["corpus_exclusions"], "EPSG:6346")
    all_rows, summary = [], {"windows": {}}
    for _, w in windows.iterrows():
        stack = Path(str(w["stack_path"]))
        if not stack.exists():
            if build and isinstance(w.get("laz_glob"), str):
                stack = build_missing(w, cfg)
            else:
                summary["windows"][w["window_id"]] = {"status": f"missing stack {stack}"}
                continue
        rows, drops = chips_for_window(stack, str(w["window_id"]), float(w["ground_ppsm"]), cfg, excl)
        all_rows += rows
        summary["windows"][w["window_id"]] = {"status": "ok", "chips": len(rows), **drops}
    if not all_rows:
        raise FileNotFoundError("no admitted chips. Check the corpus window list and stack paths")
    idx = pd.DataFrame(all_rows)
    bins = cfg["corpus"]["density_bins_ppsm"]
    idx["density_bin"] = pd.cut(idx["ground_ppsm"], bins, labels=False, include_lowest=True)
    ek.assert_no_nan(idx["density_bin"], "density_bin")
    out_dir.mkdir(parents=True, exist_ok=True)
    idx.to_csv(out_dir / "ssl_chip_index_us.csv", index=False)
    mu, sd = norm_stats(idx, cfg["corpus"]["norm_sample_chips"], cfg["master_seed"], len(cfg["channels"]))
    np.savez(out_dir / "ssl_norm_stats_us.npz", mu=mu, sd=sd, channels=np.array(cfg["channels"]))
    summary.update(n_chips=len(idx), by_density_bin=idx["density_bin"].value_counts().sort_index().to_dict(),
                   mu=mu.tolist(), sd=sd.tolist())
    (out_dir / "ssl_corpus_summary_us.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(out_dir, inputs=[Path(p) for p in idx["stack_path"].unique()],
                        outputs=[out_dir / "ssl_chip_index_us.csv", out_dir / "ssl_norm_stats_us.npz"],
                        params=cfg["corpus"], hash_limit_mb=500)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the SSL corpus chip index (7.1 S1).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--windows", default=None, help="corpus window CSV (default config inputs.corpus_windows)")
    ap.add_argument("--out", default=str(ek.sub("7.1", "data/processed")))
    ap.add_argument("--build-missing", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        wpath = Path(a.windows) if a.windows else need(cfg_path(cfg["inputs"]["corpus_windows"]), "corpus window list")
        s = build_corpus(cfg, pd.read_csv(wpath), Path(a.out), a.build_missing)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    print(json.dumps({k: s[k] for k in ("n_chips", "by_density_bin")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""S3 of framework 4.7. Random thinning ladder of one native drone cloud through the PDAL CLI.

Purpose. For every rung rate below 1 and every seed, keep round(rate x n) points of each class group (ground,
non-ground) chosen at random. One PDAL pipeline per rung and seed splits the cloud by class (filters.range),
shuffles each part with a fixed seed (filters.randomize), keeps the head (filters.head) and merges. Thinning is never
by grid, which would change spacing. The native rung (rate 1) is the original file, listed once. Each output is
checked against the original. Every thinned point must exist in the original with identical scaled X, Y, Z (no
re-projection, no re-quantisation), and the measured ground count must match the target. Seeds come from
expkit.child_seed(master, rung, seed), written to the ladder table.
Inputs.
  one native LAS/LAZ (assumed, from data/_source/drone_netl/)
  <stem>_density_oc.json from S2 (for footprint area)
Outputs (default data/oilcreek/derived/drone_thinned/, *.las is ignored by git).
  <stem>_r<rate>_s<k>_oc.las           one per rung and seed
  <stem>_ladder_oc.csv                 rung, rate, seed index, seed, path, counts, measured density, position check
Run.
  python expansions/4_modalities/4_7_drone_lidar/src/_drone_thin_ladder_oc.py --las PATH [--density-json JSON] [--rates 0.5 0.25] [--seeds 5] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _drone_kit_4_7 as dk


def thin_pipeline(src: Path, dst: Path, n_ground: int, n_non: int, seed: int, gc: int) -> list:
    g = f"Classification[{gc}:{gc}]"
    return [
        {"type": "readers.las", "filename": str(src), "tag": "r"},
        {"type": "filters.range", "limits": g, "inputs": ["r"], "tag": "g"},
        {"type": "filters.randomize", "seed": int(seed), "inputs": ["g"], "tag": "gr"},
        {"type": "filters.head", "count": int(n_ground), "inputs": ["gr"], "tag": "gh"},
        {"type": "filters.range", "limits": f"Classification![{gc}:{gc}]", "inputs": ["r"], "tag": "n"},
        {"type": "filters.randomize", "seed": int(seed) + 1, "inputs": ["n"], "tag": "nr"},
        {"type": "filters.head", "count": int(n_non), "inputs": ["nr"], "tag": "nh"},
        {"type": "filters.merge", "inputs": ["gh", "nh"], "tag": "m"},
        {"type": "writers.las", "filename": str(dst), "inputs": ["m"], "forward": "all", "compression": "false"},
    ]


def _keys(pts) -> np.ndarray:
    X, Y, Z = (np.asarray(pts.X, np.int64), np.asarray(pts.Y, np.int64), np.asarray(pts.Z, np.int64))
    return np.unique(np.stack([X, Y, Z], 1).view([("x", np.int64), ("y", np.int64), ("z", np.int64)]).ravel())


def positions_unchanged(orig: Path, thin: Path, sample: int = 20000, seed: int = 0) -> bool:
    """Every sampled thinned point has an exact scaled-integer match in the original. Same scale and offset first."""
    import laspy
    with laspy.open(str(orig)) as fo, laspy.open(str(thin)) as ft:
        if not (np.allclose(fo.header.scales, ft.header.scales) and np.allclose(fo.header.offsets, ft.header.offsets)):
            return False
        t = ft.read()
        idx = np.random.default_rng(seed).choice(len(t), min(sample, len(t)), replace=False) if len(t) else []
        want = _keys(t[idx]) if len(t) else np.array([])
        found = np.zeros(len(want), bool)
        for pts in fo.chunk_iterator(2_000_000):
            found |= np.isin(want, _keys(pts))
    return bool(found.all())


def ladder(las: Path, out: Path, rates, n_seeds: int, master: int, gc: int, footprint_m2: float) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    info = dk.las_info(las, gc)
    rows = [{"rung": 0, "rate": 1.0, "seed_idx": 0, "seed": None, "path": str(las), "n_ground": info["n_ground"],
             "n_nonground": info["n_nonground"], "target_ground": info["n_ground"], "positions_ok": True}]
    for ri, rate in enumerate([r for r in rates if r < 1.0], start=1):
        for k in range(n_seeds):
            seed = dk.ek.child_seed(master, ri, k)
            rtag = f"{rate:.2f}".replace(".", "p")
            dst = out / f"{las.stem}_r{rtag}_s{k}_oc.las"
            tg, tn = int(round(rate * info["n_ground"])), int(round(rate * info["n_nonground"]))
            dk.run_pdal(thin_pipeline(las, dst, tg, tn, seed, gc), label=f"thin_{dst.stem}", tmp_dir=out, verbose=False)
            ti = dk.las_info(dst, gc)
            rows.append({"rung": ri, "rate": rate, "seed_idx": k, "seed": seed, "path": str(dst), "n_ground": ti["n_ground"],
                         "n_nonground": ti["n_nonground"], "target_ground": tg, "positions_ok": positions_unchanged(las, dst, seed=seed)})
    df = pd.DataFrame(rows)
    df["ground_ppsm"] = df.n_ground / footprint_m2
    df["retained_ground_share"] = df.n_ground / info["n_ground"]
    bad = df[(df.n_ground != df.target_ground) | ~df.positions_ok]
    if len(bad):
        raise AssertionError(f"thinning check failed:\n{bad[['path', 'n_ground', 'target_ground', 'positions_ok']]}")
    return df


def main(argv=None) -> int:
    cfg = dk.load_cfg()
    L = cfg["ladder"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--las", required=True)
    ap.add_argument("--density-json", default=None, help="S2 output (default <native>/<stem>_density_oc.json)")
    ap.add_argument("--rates", type=float, nargs="+", default=L["rates"])
    ap.add_argument("--seeds", type=int, default=L["seeds_per_rung"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    las = dk.need(Path(a.las), "native drone cloud", cfg["inputs"]["raw_las"])
    dj = Path(a.density_json) if a.density_json else dk.resolve(cfg["outputs"]["native"]) / f"{las.stem}_density_oc.json"
    dens = json.loads(dk.need(dj, "S2 density JSON (run _drone_ingest_density_oc.py first)").read_text())
    out = Path(a.out) if a.out else dk.resolve(cfg["outputs"]["thinned"])
    df = ladder(las, out, a.rates, a.seeds, L["master_seed"], L["ground_class"], dens["footprint_m2"])
    f = out / f"{las.stem}_ladder_oc.csv"
    df.to_csv(f, index=False)
    dk.prov(out, f"drone_thin_{las.stem}", inputs=[las, dj], outputs=[f, *map(Path, df.path[1:])],
            params={"rates": a.rates, "seeds": a.seeds}, seeds={"master": L["master_seed"], "per_row": df.seed.tolist()})
    print(df.groupby("rate").ground_ppsm.agg(["mean", "min", "max"]).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

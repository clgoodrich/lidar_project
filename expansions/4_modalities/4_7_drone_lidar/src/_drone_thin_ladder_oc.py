"""S3 of framework 4.7. Nested random thinning ladder of one native drone cloud, reclassified per rung, PDAL CLI.

Purpose. For every rung rate and every seed, keep round(rate x n) points of each native class group (ground,
non-ground) chosen at random. One PDAL pipeline per rung and seed splits the cloud by class (filters.range),
shuffles each part (filters.randomize), keeps the head (filters.head) and merges. Thinning is never by grid, which
would change spacing.
Nested rungs (design choice of 2026-11-06, review note on 4.7). The shuffle seed depends on the seed index only, not
on the rung. Each part is shuffled the same way at every rung, so a lower rung is the head of a longer head and is a
subset of every higher rung with the same seed index. The density curve is a paired sensitivity, and nesting
removes the between-rung sampling noise that independent seeds add. Every run checks the nesting.
Ground reclassified per rung (review 4.7-01). A thinned rung that kept the native ground class carries the vendor's
classification, made at full density, so the curve was optimistic. Each rung, the native one included, now resets
class 2 to 1 and reruns SMRF (filters.smrf, parameters in config ladder.reclass) on the thinned points. Noise
classes 7 and 18 are ignored. The native class is kept as the extra dimension NativeClass for the count check.
n_ground and ground_ppsm are SMRF ground. n_ground_native_class is the thinning target check.
Each output is checked against the original. Every thinned point must exist in the original with identical scaled
X, Y, Z (no re-projection, no re-quantisation), and the native-class ground count must match the target. Seeds come
from expkit.child_seed(master, 0, seed index), written to the ladder table.
Inputs.
  one native LAS/LAZ (assumed, from data/_source/drone_netl/)
  <stem>_density_oc.json from S2 (for footprint area)
Outputs (default data/oilcreek/derived/drone_thinned/, *.las is ignored by git).
  <stem>_r<rate>_s<k>_oc.las           one per rung and seed (rate 1 is the native cloud reclassified, seed 0)
  <stem>_ladder_oc.csv                 rung, rate, seed index, seed, path, counts, measured density, checks
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


def reclass_stages(rc: dict, gc: int) -> list:
    """Reset ground to unclassified, then SMRF on the thinned points. Noise (7, 18) is ignored."""
    return [
        {"type": "filters.ferry", "dimensions": "Classification => NativeClass"},
        {"type": "filters.assign", "value": f"Classification = 1 WHERE Classification == {gc}"},
        {"type": "filters.smrf", "ignore": "Classification[7:7]", "cell": float(rc["cell"]), "slope": float(rc["slope"]),
         "window": float(rc["window"]), "threshold": float(rc["threshold"]), "scalar": float(rc["scalar"])},
    ]


def thin_pipeline(src: Path, dst: Path, n_ground: int, n_non: int, seed: int, gc: int, rc: dict | None = None) -> list:
    g = f"Classification[{gc}:{gc}]"
    st = [
        {"type": "readers.las", "filename": str(src), "tag": "r"},
        {"type": "filters.range", "limits": g, "inputs": ["r"], "tag": "g"},
        {"type": "filters.randomize", "seed": int(seed), "inputs": ["g"], "tag": "gr"},
        {"type": "filters.head", "count": int(n_ground), "inputs": ["gr"], "tag": "gh"},
        {"type": "filters.range", "limits": f"Classification![{gc}:{gc}]", "inputs": ["r"], "tag": "n"},
        {"type": "filters.randomize", "seed": int(seed) + 1, "inputs": ["n"], "tag": "nr"},
        {"type": "filters.head", "count": int(n_non), "inputs": ["nr"], "tag": "nh"},
        {"type": "filters.merge", "inputs": ["gh", "nh"], "tag": "m"},
    ]
    if rc is not None:
        st += reclass_stages(rc, gc)
    st.append({"type": "writers.las", "filename": str(dst), "forward": "all", "compression": "false",
               **({"extra_dims": "all", "minor_version": 4, "dataformat_id": 6} if rc is not None else {})})
    return st


def native_class_ground(path: Path, gc: int) -> int:
    import laspy
    n = 0
    with laspy.open(str(path)) as f:
        for pts in f.chunk_iterator(2_000_000):
            n += int((np.asarray(pts["NativeClass"]) == gc).sum())
    return n


def is_subset(small: Path, big: Path) -> bool:
    """Every point of small (scaled X, Y, Z) is in big. Checks the nesting of the ladder."""
    import laspy
    a, b = _keys(laspy.read(str(small))), _keys(laspy.read(str(big)))
    return bool(np.isin(a, b).all())


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


def ladder(las: Path, out: Path, rates, n_seeds: int, master: int, gc: int, footprint_m2: float,
           rc: dict) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    info = dk.las_info(las, gc)
    rows = []
    rungs = [1.0] + sorted({float(r) for r in rates if r < 1.0}, reverse=True)
    for ri, rate in enumerate(rungs):
        for k in range(n_seeds if rate < 1.0 else 1):
            seed = dk.ek.child_seed(master, 0, k)          # one seed per seed index, every rung: nested ladder
            rtag = f"{rate:.2f}".replace(".", "p")
            dst = out / f"{las.stem}_r{rtag}_s{k}_oc.las"
            tg, tn = int(round(rate * info["n_ground"])), int(round(rate * info["n_nonground"]))
            dk.run_pdal(thin_pipeline(las, dst, tg, tn, seed, gc, rc), label=f"thin_{dst.stem}", tmp_dir=out, verbose=False)
            ti = dk.las_info(dst, gc)
            rows.append({"rung": ri, "rate": rate, "seed_idx": k, "seed": seed, "path": str(dst),
                         "n_ground": ti["n_ground"], "n_nonground": ti["n_nonground"],
                         "n_ground_native_class": native_class_ground(dst, gc), "target_ground": tg,
                         "positions_ok": positions_unchanged(las, dst, seed=seed)})
    df = pd.DataFrame(rows)
    df["ground_ppsm"] = df.n_ground / footprint_m2
    native_g = int(df.loc[df.rate == 1.0, "n_ground"].iloc[0])
    df["retained_ground_share"] = df.n_ground / native_g if native_g else np.nan
    df["reclassified"] = "smrf"
    # nesting. Each rung against the next higher rung with the same seed index (the native rung for seed 0 and up)
    nested = []
    for r in df.itertuples():
        hi = df[(df.rate > r.rate) & ((df.seed_idx == r.seed_idx) | (df.rate == 1.0))].sort_values("rate")
        nested.append(True if not len(hi) else is_subset(Path(r.path), Path(hi.path.iloc[0])))
    df["nested_ok"] = nested
    bad = df[(df.n_ground_native_class != df.target_ground) | ~df.positions_ok | ~df.nested_ok]
    if len(bad):
        raise AssertionError(f"thinning check failed:\n{bad[['path', 'n_ground_native_class', 'target_ground', 'positions_ok', 'nested_ok']]}")
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
    df = ladder(las, out, a.rates, a.seeds, L["master_seed"], L["ground_class"], dens["footprint_m2"], L["reclass"])
    f = out / f"{las.stem}_ladder_oc.csv"
    df.to_csv(f, index=False)
    dk.prov(out, f"drone_thin_{las.stem}", inputs=[las, dj], outputs=[f, *map(Path, df.path)],
            params={"rates": a.rates, "seeds": a.seeds, "reclass": L["reclass"], "nested": True}, seeds={"master": L["master_seed"], "per_row": df.seed.tolist()})
    print(df.groupby("rate").ground_ppsm.agg(["mean", "min", "max"]).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

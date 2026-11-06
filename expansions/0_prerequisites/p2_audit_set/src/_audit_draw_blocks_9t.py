"""P2 S1 and S5. Draw the comparative 9t audit set, add its buffer, test it, and freeze it on request.

Purpose
    1. Eligible blocks are the pit-bearing 9t blocks (feature count from the pit manifest).
    2. Strata. Feature density tercile by slope tercile (3 x 3). Slope is the mean of the `slope` band of the
       0.5 m feature stack per block, read on a 5 m grid. Terciles use ranks, so ties split by block id.
    3. Allocation. Target share of eligible blocks (default 15%). Proportional to stratum size by largest
       remainder. Every density tercile and every slope tercile must hold at least `min_per_tercile` blocks.
       The framework's "at least 3 per stratum" cannot hold for 9 joint strata at 17 blocks, so the minimum
       applies to the marginal terciles (decisions_p2.md).
    4. Draw within each stratum with `np.random.default_rng(seed)`, seed 20261104, strata in sorted order.
    5. Buffer. The P1 S4 buffer in metres. Mode `window` (default) keeps neighbouring blocks for training and
       forbids any training window within the buffer of an audit block. Mode `block` (framework text) also
       excludes every block that overlaps the dilated audit area. Both losses are reported.
       If the training blocks left fall below `min_remaining_share`, the share drops to 10% and the draw
       repeats. The buffer is never relaxed.
    6. Two-sample Kolmogorov-Smirnov tests of density and slope, audit against the rest. Reported, never gated.
    7. QC against a P1 split file. Counts audit (and buffer) blocks inside train and inner-val lists. A v1
       future split predates the audit set, so a split built with `--exclude-audit` is needed before
       training (see `_split_future_write_9t.py`).
    Default is a dry run. Nothing is frozen. `--freeze` writes the v1 file, its `.sha256` sidecar and a line in
    the registry, and refuses to overwrite. Freezing is a user decision.

Inputs
    data/9t/derived/05/pit_dataset_manifest.csv, pit_blocks_9t.gpkg, features_pit_9t_05.tif (through the pit trainer)
    P1 buffer file data/9t/results/splits/buffer_derivation_9t.json (--buffer-json) or --buffer-m
    optional P1 split file (--splits)

Outputs
    dry run   <out-dir>/audit_blocks_9t_dryrun.csv and audit_draw_9t_dryrun.json
              default out-dir expansions/0_prerequisites/p2_audit_set/data/interim/
    freeze    C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/audit_blocks_9t_v1.csv (+ .sha256)
              expansions/0_prerequisites/p2_audit_set/results/tables/audit_registry_p2.json
    Run record under expansions/0_prerequisites/p2_audit_set/results/<run_id>/

Run
    python expansions/0_prerequisites/p2_audit_set/src/_audit_draw_blocks_9t.py --buffer-json data/9t/results/splits/buffer_derivation_9t.json
    python expansions/0_prerequisites/p2_audit_set/src/_audit_draw_blocks_9t.py --buffer-json ... --freeze
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "p1_splits_manifests" / "src"))
import _audit_guard_lib as ag  # noqa: E402
ek = ag.ek

CFG = json.loads((HERE.parent / "config_p2.json").read_text(encoding="utf-8"))


def block_slope(feat: Path, blocks, band_name: str = "slope", step_m: float = 5.0) -> pd.Series:
    """Mean slope per block from the feature stack on a step_m grid."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import rasterize
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _dl import DEFAULT_CHANNELS
    band = DEFAULT_CHANNELS.index(band_name) + 1
    with rasterio.open(feat) as r:
        ek.assert_crs(r)
        f = max(1, int(round(step_m / abs(r.transform.a))))
        h, w = r.height // f, r.width // f
        a = r.read(band, out_shape=(h, w), resampling=Resampling.nearest).astype(np.float64)
        tf = r.transform * r.transform.scale(r.width / w, r.height / h)
        nd = r.nodata
    ok = np.isfinite(a) & ((a != nd) if nd is not None and np.isfinite(nd) else True)
    lab = rasterize([(g, int(b) + 1) for g, b in zip(blocks.geometry, blocks.block_id)], out_shape=a.shape,
                    transform=tf, fill=0, dtype="int32")
    m = ok & (lab > 0)
    s = np.bincount(lab[m], weights=a[m], minlength=lab.max() + 1)
    n = np.bincount(lab[m], minlength=lab.max() + 1)
    return pd.Series({int(b): (s[int(b) + 1] / n[int(b) + 1] if n[int(b) + 1] else np.nan) for b in blocks.block_id})


def terciles(x: pd.Series) -> pd.Series:
    r = x.rank(method="first")
    return pd.qcut(r, 3, labels=[0, 1, 2]).astype(int)


def allocate(sizes: dict, n: int) -> dict:
    """Largest-remainder proportional allocation, capped by stratum size."""
    tot = sum(sizes.values())
    raw = {s: n * v / tot for s, v in sizes.items()}
    alloc = {s: min(int(np.floor(v)), sizes[s]) for s, v in raw.items()}
    for s in sorted(raw, key=lambda s: (-(raw[s] - np.floor(raw[s])), s)):
        if sum(alloc.values()) >= n:
            break
        if alloc[s] < sizes[s]:
            alloc[s] += 1
    return alloc


def draw(tab: pd.DataFrame, share: float, seed: int, min_per_tercile: int) -> list[int]:
    """tab has block_id, dens_t, slope_t. Returns sorted audit ids."""
    n = int(round(share * len(tab)))
    strata = tab.groupby(["dens_t", "slope_t"]).block_id.apply(lambda s: sorted(s.astype(int))).to_dict()
    alloc = allocate({k: len(v) for k, v in strata.items()}, n)
    for col in ("dens_t", "slope_t"):
        for t in range(3):
            have = sum(v for k, v in alloc.items() if k[0 if col == "dens_t" else 1] == t)
            while have < min_per_tercile:
                cands = [k for k in alloc if k[0 if col == "dens_t" else 1] == t and alloc[k] < len(strata[k])]
                if not cands:
                    raise AssertionError(f"{col} tercile {t} cannot reach {min_per_tercile} audit blocks")
                k = max(cands, key=lambda k: (len(strata[k]) - alloc[k], k))
                alloc[k] += 1
                have += 1
    rng = np.random.default_rng(seed)
    out = []
    for k in sorted(strata):
        if alloc[k]:
            out += [int(b) for b in rng.choice(strata[k], alloc[k], replace=False)]
    return sorted(out)


def buffer_blocks(blocks, audit_ids: list[int], buffer_m: float) -> list[int]:
    """Blocks (not audit) that overlap the audit area dilated by buffer_m with positive area."""
    au = blocks[blocks.block_id.isin(audit_ids)].geometry.union_all().buffer(buffer_m, join_style="mitre")
    rest = blocks[~blocks.block_id.isin(audit_ids)]
    return sorted(int(b) for b, g in zip(rest.block_id, rest.geometry) if g.intersection(au).area > 1e-6)


def build(tab: pd.DataFrame, blocks, buffer_m: float, mode: str, share: float, seed: int, min_per_tercile: int,
          min_remaining_share: float) -> dict:
    eligible = len(tab)
    tries = [share] + ([0.10] if share > 0.10 else [])
    for sh in tries:
        aud = draw(tab, sh, seed, min_per_tercile)
        buf = buffer_blocks(blocks, aud, buffer_m)
        buf_elig = sorted(set(buf) & set(tab.block_id))
        lost = len(aud) + (len(buf_elig) if mode == "block" else 0)
        remaining = (eligible - lost) / eligible
        res = {"share": sh, "audit": aud, "buffer": buf, "buffer_pit_blocks": buf_elig,
               "remaining_pit_block_share": remaining,
               "remaining_if_block_mode": (eligible - len(aud) - len(buf_elig)) / eligible,
               "remaining_if_window_mode": (eligible - len(aud)) / eligible}
        if remaining >= min_remaining_share:
            return res
    res["warning"] = (f"remaining training share {remaining:.2f} < {min_remaining_share} even at 10%. "
                      "Buffer not relaxed. Prefer the absolute audit area.")
    return res


def ks_tests(tab: pd.DataFrame, audit: list[int]) -> dict:
    from scipy.stats import ks_2samp
    a = tab[tab.block_id.isin(audit)]
    r = tab[~tab.block_id.isin(audit)]
    out = {}
    for col in ("n_feat", "slope"):
        t = ks_2samp(a[col].dropna(), r[col].dropna())
        out[col] = {"D": float(t.statistic), "p": float(t.pvalue), "n_audit": int(a[col].notna().sum()),
                    "n_rest": int(r[col].notna().sum())}
    return out


def split_overlap(split_path: Path, forbidden: set[int]) -> dict:
    doc = json.loads(Path(split_path).read_text(encoding="utf-8"))
    out = {}
    for task, t in doc["tasks"].items():
        out[task] = {f: sorted(set(r["train"] + r["inner_val"]) & forbidden) for f, r in t["folds"].items()}
    return out


def write_audit_csv(path: Path, tab, res, mode, buffer_m, seed) -> None:
    rows = [dict(block_id=b, role="audit", stratum=f"d{int(tab.set_index('block_id').dens_t[b])}"
                 f"s{int(tab.set_index('block_id').slope_t[b])}", area="9t") for b in res["audit"]]
    if mode == "block":
        rows += [dict(block_id=b, role="buffer", stratum="", area="9t") for b in res["buffer"]]
    head = ["# Comparative audit set for tile 9t. It supports comparisons between new models only.",
            "# Every 9t block trained or validated four of the five historical CV models.",
            "# Audit and buffer rows are excluded from all training, calibration, mining and selection.",
            f"# seed={seed} share={res['share']} buffer_m={buffer_m} buffer_mode={mode}",
            f"# written={dt.datetime.now().isoformat(timespec='seconds')}"]
    body = pd.DataFrame(rows).to_csv(index=False, lineterminator="\n")
    path.write_text("\n".join(head) + "\n" + body, encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    c = CFG["draw_9t"]
    ap = argparse.ArgumentParser(description="P2 S1 draw the 9t comparative audit set")
    ap.add_argument("--buffer-json", type=Path, default=None, help="P1 S4 buffer_derivation_9t.json")
    ap.add_argument("--buffer-m", type=float, default=None, help="overrides --buffer-json")
    ap.add_argument("--buffer-mode", choices=("window", "block"), default=c["buffer_mode"])
    ap.add_argument("--share", type=float, default=c["share"])
    ap.add_argument("--seed", type=int, default=c["seed"])
    ap.add_argument("--min-per-tercile", type=int, default=c["min_per_tercile"])
    ap.add_argument("--min-remaining-share", type=float, default=c["min_remaining_share"])
    ap.add_argument("--splits", type=Path, default=None, help="P1 split file for the overlap QC")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--freeze", action="store_true", help="write the immutable v1 file (user decision)")
    a = ap.parse_args(argv)
    if a.buffer_m is None:
        if a.buffer_json is None or not a.buffer_json.exists():
            raise SystemExit("buffer missing. Give --buffer-json (P1 S4 output buffer_derivation_9t.json) or --buffer-m.")
        a.buffer_m = float(json.loads(a.buffer_json.read_text())["buffer_m"])
    import geopandas as gpd
    import _split_core_lib_9t as sc
    pit = sc.trainer("pit")
    man = sc.load_manifest("pit")
    blocks = gpd.read_file(pit.BLOCKS, layer="blocks")
    ek.assert_crs(blocks)
    ek.assert_rows(blocks, 144, "9t blocks")
    blocks["block_id"] = blocks.block_id.astype(int)
    n = man.dropna(subset=["block_id"]).block_id.astype(int).value_counts()
    tab = pd.DataFrame({"block_id": n.index.astype(int), "n_feat": n.values})
    tab["slope"] = tab.block_id.map(block_slope(Path(pit.FEATURES), blocks))
    tab = tab.sort_values("block_id").reset_index(drop=True)
    tab["dens_t"], tab["slope_t"] = terciles(tab.n_feat).values, terciles(tab.slope.fillna(-1)).values
    res = build(tab, blocks, a.buffer_m, a.buffer_mode, a.share, a.seed, a.min_per_tercile, a.min_remaining_share)
    res["ks"] = ks_tests(tab, res["audit"])
    forbidden = set(res["audit"]) | (set(res["buffer"]) if a.buffer_mode == "block" else set())
    if a.splits:
        res["split_overlap"] = split_overlap(a.splits, forbidden)
    res.update(buffer_m=a.buffer_m, buffer_mode=a.buffer_mode, seed=a.seed, n_eligible=len(tab))
    if a.freeze:
        dst = ek.path_for("results_9t") / "splits" / "audit_blocks_9t_v1.csv"
        if dst.exists():
            raise SystemExit(f"{dst} exists and is frozen. A new audit set needs a new version and a user decision.")
    else:
        dst = (a.out_dir or ek.sub("p2", "data/interim")) / "audit_blocks_9t_dryrun.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    write_audit_csv(dst, tab, res, a.buffer_mode, a.buffer_m, a.seed)
    h = ek.sha256(dst)
    res["file"], res["sha256"] = str(dst), h
    js = dst.with_name("audit_draw_9t_" + ("v1" if a.freeze else "dryrun") + ".json")
    js.write_text(json.dumps(res, indent=1, default=int), encoding="utf-8")
    if a.freeze:
        Path(str(dst) + ".sha256").write_text(f"{h}  {dst.name}\n", encoding="utf-8")
        reg = ek.sub("p2", "results/tables") / "audit_registry_p2.json"
        r = json.loads(reg.read_text()) if reg.exists() else []
        r.append({"file": str(dst.relative_to(ek.REPO)), "sha256": h, "frozen": dt.date.today().isoformat(),
                  "n_audit": len(res["audit"]), "buffer_m": a.buffer_m, "mode": a.buffer_mode})
        reg.write_text(json.dumps(r, indent=1), encoding="utf-8")
        print(f"analysis_log line: P2 audit set frozen, {dst.name} sha256 {h}")
    run = ek.new_run("p2", "audit_draw" + ("_freeze" if a.freeze else "_dry"), {k: str(v) for k, v in vars(a).items()},
                     why="S1 draw the comparative 9t audit set.")
    ek.write_provenance(run, inputs=[Path(pit.MANIFEST), Path(pit.BLOCKS)], outputs=[dst, js],
                        seeds={"draw": a.seed})
    print(f"{len(res['audit'])} audit blocks at share {res['share']}: {res['audit']}")
    print(f"buffer {a.buffer_m} m, {len(res['buffer_pit_blocks'])} pit blocks overlap it. remaining pit-block share "
          f"window mode {res['remaining_if_window_mode']:.2f}, block mode {res['remaining_if_block_mode']:.2f}")
    print(f"KS density D {res['ks']['n_feat']['D']:.3f} p {res['ks']['n_feat']['p']:.3f}, slope D "
          f"{res['ks']['slope']['D']:.3f} p {res['ks']['slope']['p']:.3f}")
    if "warning" in res:
        print("WARNING", res["warning"])
    print(f"wrote {dst} (sha256 {h})\nwrote {js}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

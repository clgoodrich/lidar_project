"""S5 of framework 4.7. Recall at K against retained ground density, paired over sites, with a seed band.

Purpose. For each rung and seed, turn the pit probability raster into candidates (threshold 0.10, blobs of 4 m2 or
more, mean-probability score, the polygonize of notebooks/wellsight_v2/s5_eval/_threshold_common.py), match them one
to one to the NETL sites (IoU 0.3 for polygons, 10 m for points, greedy), keep the top K = 40 per km2 of the scored
footprint and record which sites are hit. Sites are the resampling unit, stratified by hillside, B = 2000, and every
draw is applied to every rung (paired curve). The seed band is the min and max over seeds. The script also reports
the density where recall falls to 90% and 75% of native, by log-linear interpolation, with a bootstrap interval.
Every output is labelled conditional on lidar-visible sites. There is no pass or fail.
Inputs.
  <stem>_rungs_oc.csv from S4 full mode (prob paths)
  data/_source/drone_netl/netl_sites_oc.gpkg (assumed; site_id, hillside, geometry)
  <stem>_density_oc.json from S2 (footprint area)
Outputs (default data/oilcreek/results/drone/).
  drone_recall_by_rung_oc.csv      one row per rung and seed (hits, K, recall)
  drone_density_curve_oc.csv       one row per rung (density, recall mean, seed band, 95% interval, share of native)
  drone_density_curve_oc.json      thresholds at 90% and 75% of native with intervals, design notes
  drone_density_curve_oc.png       figure (blue observed, grey seed band, orange 9t anchor, labelled directly)
Run.
  python expansions/4_modalities/4_7_drone_lidar/src/_drone_density_curve_oc.py --rungs CSV --density-json JSON [--sites GPKG] [--B 2000] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import _drone_kit_4_7 as dk


def candidates(prob_path: Path, crs: str, thr: float, min_area: float):
    import rasterio
    sys.path.insert(0, str(dk.ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"))
    from _threshold_common import polygonize
    with rasterio.open(prob_path) as d:
        dk.ek.assert_crs(d, crs)
        p = d.read(1).astype("float32")
        if d.nodata is not None:
            p[p == d.nodata] = np.nan
        tf = d.transform
    c = polygonize(np.nan_to_num(p, nan=0.0), tf, crs, thr, min_area)
    c["area"] = c.area
    return c.reset_index(drop=True)


def match(cands, sites, iou_thr: float, point_r: float) -> list:
    """Per candidate, the site_id it matches or None. Greedy one to one, best pair first."""
    pairs = []
    pts = sites.geometry.geom_type.eq("Point").all()
    for i, cg in enumerate(cands.geometry):
        for j, sg in enumerate(sites.geometry):
            if pts:
                d = cg.distance(sg)
                if d <= point_r:
                    pairs.append((-d, i, j))
            elif cg.intersects(sg):
                iou = cg.intersection(sg).area / cg.union(sg).area
                if iou >= iou_thr:
                    pairs.append((iou, i, j))
    out, used_c, used_s = [None] * len(cands), set(), set()
    for _, i, j in sorted(pairs, reverse=True):
        if i not in used_c and j not in used_s:
            used_c.add(i), used_s.add(j)
            out[i] = sites.site_id.iloc[j]
    return out


def site_hits(cands, matched, area_km2: float, k_per_km2: float, site_ids) -> tuple[np.ndarray, int]:
    """Boolean per site: matched by a candidate inside the top K. Ties by larger area then id (fw_00 section 4)."""
    df = pd.DataFrame({"s": cands.score.to_numpy() if len(cands) else [], "a": cands.area.to_numpy() if len(cands) else [],
                       "t": matched, "i": np.arange(len(cands))})
    k = int(round(k_per_km2 * area_km2))
    top = df.sort_values(["s", "a", "i"], ascending=[False, False, True]).head(k)
    hit = set(top.t.dropna())
    return np.array([s in hit for s in site_ids]), k


def crossing(dens: np.ndarray, rel: np.ndarray, share: float) -> float:
    """Density where rel first falls below share going down the ladder (log-linear). nan if never."""
    o = np.argsort(-dens)
    d, r = dens[o], rel[o]
    for k in range(1, len(d)):
        if r[k] < share <= r[k - 1]:
            t = (r[k - 1] - share) / (r[k - 1] - r[k])
            return float(10 ** (np.log10(d[k - 1]) + t * (np.log10(d[k]) - np.log10(d[k - 1]))))
    return float("nan")


def curve(hits: dict, dens: dict, strata: np.ndarray, B: int, seed: int, shares) -> tuple[pd.DataFrame, dict]:
    """hits[(rate, seed_idx)] = bool per site. dens[(rate, seed_idx)] = measured ground ppsm."""
    rates = sorted({r for r, _ in hits}, reverse=True)
    groups = [np.flatnonzero(strata == h) for h in np.unique(strata)]
    rng = np.random.default_rng(seed)
    draws = [np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups]) for _ in range(B)]

    def rec(keys, idx):
        return np.mean([hits[k][idx].mean() for k in keys])
    allidx = np.arange(len(strata))
    rows, boot = [], {}
    for r in rates:
        keys = [k for k in hits if k[0] == r]
        per_seed = [hits[k].mean() for k in keys]
        boot[r] = np.array([rec(keys, ix) for ix in draws])
        lo, hi = np.percentile(boot[r], [2.5, 97.5])
        rows.append({"rate": r, "ground_ppsm": float(np.mean([dens[k] for k in keys])), "n_seeds": len(keys),
                     "recall": rec(keys, allidx), "seed_min": min(per_seed), "seed_max": max(per_seed), "lo": lo, "hi": hi})
    df = pd.DataFrame(rows)
    nat = df.recall.iloc[0]
    df["share_of_native"] = df.recall / nat if nat else np.nan
    out = {}
    for s in shares:
        pt = crossing(df.ground_ppsm.to_numpy(), df.share_of_native.to_numpy(), s)
        bd = []
        for b in range(B):
            nb = boot[rates[0]][b]
            if nb > 0:
                bd.append(crossing(df.ground_ppsm.to_numpy(), np.array([boot[r][b] for r in rates]) / nb, s))
        bd = np.array(bd, float)
        fin = bd[np.isfinite(bd)]
        out[f"ppsm_at_{s:.2f}_of_native"] = {"point": pt, "lo": float(np.percentile(fin, 2.5)) if len(fin) else None,
                                              "hi": float(np.percentile(fin, 97.5)) if len(fin) else None,
                                              "share_of_draws_crossing": float(len(fin) / max(len(bd), 1))}
    return df, out


def figure(df: pd.DataFrame, anchor: float, path: Path, conditional: bool) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    P = dk.ek.PALETTE   # lost/found palette, worst pair dE 21.1 deutan (dataviz validator --pairs all, CLAUDE.md)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.fill_between(df.ground_ppsm, df.seed_min, df.seed_max, color=P["grey"], alpha=0.35, lw=0)
    ax.errorbar(df.ground_ppsm, df.recall, yerr=[df.recall - df.lo, df.hi - df.recall], color=P["blue"], marker="o", capsize=3)
    ax.axvline(anchor, color=P["orange"], ls="--")
    ax.text(anchor, 0.02, f" 9t airborne {anchor:.2f} ground pts/m²", color=P["orange"], rotation=90, va="bottom")
    ax.text(df.ground_ppsm.iloc[-1], df.seed_max.iloc[-1], " seed range", color=P["charcoal"], va="bottom")
    ax.set_xscale("log")
    ax.set_ylim(0, 1)
    ax.set_xlabel("retained ground returns per m² (measured)")
    ax.set_ylabel("recall at K = 40 per km²")
    ax.set_title("Recall by retained ground density" + (", conditional on lidar-visible sites" if conditional else ""), fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    import geopandas as gpd
    cfg = dk.load_cfg()
    S, L = cfg["score"], cfg["ladder"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rungs", required=True)
    ap.add_argument("--density-json", required=True)
    ap.add_argument("--sites", default=None)
    ap.add_argument("--B", type=int, default=S["B"])
    ap.add_argument("--k-per-km2", type=float, default=S["k_per_km2"], help="40 is primary. 30 is the sensitivity")
    ap.add_argument("--not-conditional", action="store_true", help="only when S1 shows selection was independent of lidar")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    rungs = pd.read_csv(dk.need(Path(a.rungs), "S4 rung table"))
    if "prob" not in rungs:
        raise ValueError("rung table has no prob column. Run S4 in full mode (not --dem-only) first")
    fp_km2 = json.loads(dk.need(Path(a.density_json), "S2 density JSON").read_text())["footprint_m2"] / 1e6
    sp = dk.need(Path(a.sites) if a.sites else dk.resolve(cfg["inputs"]["sites"]), "NETL site layer", cfg["inputs"]["sites"])
    sites = gpd.read_file(sp)
    dk.ek.assert_crs(sites, cfg["crs"])
    dk.ek.assert_unique(sites, "site_id")
    dk.ek.assert_no_nan(sites.hillside, "hillside")
    hits, dens, rows = {}, {}, []
    for r in rungs.itertuples():
        c = candidates(dk.need(Path(r.prob), f"probability raster of {r.sfx}"), cfg["crs"], S["prob_threshold"], S["min_blob_m2"])
        m = match(c, sites, S["iou_match"], S["point_match_m"])
        h, k = site_hits(c, m, fp_km2, a.k_per_km2, sites.site_id.tolist())
        hits[(r.rate, r.seed_idx)], dens[(r.rate, r.seed_idx)] = h, r.ground_ppsm
        rows.append({"sfx": r.sfx, "rate": r.rate, "seed_idx": r.seed_idx, "ground_ppsm": r.ground_ppsm,
                     "n_candidates": len(c), "k": k, "hits": int(h.sum()), "n_sites": len(h), "recall": float(h.mean())})
    by = pd.DataFrame(rows)
    df, thr = curve(hits, dens, sites.hillside.to_numpy(), a.B, L["master_seed"], S["share_of_native"])
    n_h = sites.hillside.nunique()
    meta = {"thresholds": thr, "footprint_km2": fp_km2, "k_per_km2": a.k_per_km2, "n_sites": len(sites), "n_hillsides": int(n_h),
            "resampling": "sites with replacement within hillside, paired across rungs", "B": a.B,
            "conditional_on_lidar_visible_sites": not a.not_conditional,
            "note": "No universal threshold and no cross-platform equivalence (review revision 2, 2026-11-04)",
            "unreliable_bootstrap": bool(len(sites) < 15)}
    out = Path(a.out) if a.out else dk.resolve(cfg["outputs"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    by.to_csv(out / "drone_recall_by_rung_oc.csv", index=False)
    df.to_csv(out / "drone_density_curve_oc.csv", index=False)
    (out / "drone_density_curve_oc.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    figure(df, L["anchor_ground_ppsm"], out / "drone_density_curve_oc.png", not a.not_conditional)
    dk.prov(out, "drone_density_curve", inputs=[Path(a.rungs), sp], outputs=sorted(out.glob("drone_*_oc.*")), params=meta,
            seeds={"bootstrap": L["master_seed"]})
    print(df.to_string(index=False))
    print(json.dumps(thr, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""3.3 S4. Seam and realism checks for the S3 terrain edits.

Purpose
    Flag edits whose texture does not match the ground around them, and render ten edits as
    hillshade before and after. The S3 run already holds three texture statistics per variant.
        ratio_inside_outside    var(Laplacian) inside the footprint over the ring outside it
                                (fw_3_3 S4 text, tolerance 20%)
        ratio_seam_band         edited over background in the feather band
        ratio_highpass_texture  var(Laplacian) of the 3-cell high-pass, edited over background,
                                inside the footprint
    The rule applied comes from --rule (default inside_outside, the framework text). A two
    location dry run (2026-11-05) gave pit ratios of 4.2 to 6.7 under that rule, because a real
    pit has more curvature than flat ground. The rule as written would drop almost every pit
    edit. That is reported in the summary, not hidden. Flagged edits are dropped from the paired
    analysis only when --drop is passed, and the count is always written.

Inputs
    S3 run folder: slope_edit_locations_9t.csv (and slope_edit_paired_scores_9t.csv if scored)
    expansions/3_geography/3_3_low_relief_slope/data/interim/slope_edit_windows_9t/loc*.npz

Outputs (in the S3 run folder)
    slope_edit_seam_flags_9t.csv      one row per location and variant, statistic, pass flag
    slope_edit_seam_summary_9t.json   pass counts per variant and rule
    slope_edit_seam_renders_9t.png    up to ten edits, hillshade before and after, footprint outline

Run
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_edit_seam_check_9t.py
    python expansions/3_geography/3_3_low_relief_slope/src/_slope_edit_seam_check_9t.py --rule highpass_texture --tol 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

EDITS = ("pit", "bump", "ramp", "flat_cut")
RULES = {"inside_outside": "ratio_inside_outside", "seam_band": "ratio_seam_band",
         "highpass_texture": "ratio_highpass_texture"}


def hillshade(z, res=0.5, az=315.0, alt=45.0):
    gy, gx = np.gradient(z, res)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, e = np.radians(az), np.radians(alt)
    return np.clip(np.sin(e) * np.cos(slope) + np.cos(e) * np.sin(slope) * np.cos(a - aspect), 0, 1)


def seam_flags(locs: pd.DataFrame, rule: str, tol: float) -> pd.DataFrame:
    col = RULES[rule]
    rows = []
    for _, r in locs.iterrows():
        for v in EDITS:
            x = r.get(f"{v}_{col}", np.nan)
            rows.append({"loc_id": int(r.loc_id), "variant": v, "rule": rule, "ratio": x,
                         "pass": bool(np.isfinite(x) and abs(x - 1.0) <= tol)})
    return pd.DataFrame(rows)


def render(npz_files, path, res=0.5, n=10):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    files = npz_files[:n]
    if not files:
        return None
    fig, axes = plt.subplots(len(files), 2, figsize=(5.2, 2.6 * len(files)), squeeze=False)
    for i, f in enumerate(files):
        z = np.load(f)
        H = z["background"].shape[0]
        c = slice(H // 2 - 60, H // 2 + 60)
        for j, v in enumerate(("background", "pit")):
            ax = axes[i, j]
            ax.imshow(hillshade(z[v][c, c], res), cmap="gray", vmin=0, vmax=1)
            ax.contour(z["foot"][c, c].astype(float), levels=[0.5], colors=[ek.PALETTE["orange"]], linewidths=1)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"{f.stem} {'before' if j == 0 else 'after pit edit'}", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default=None, help="S3 run folder (default newest *_slope_edit_*)")
    ap.add_argument("--rule", choices=sorted(RULES), default="inside_outside")
    ap.add_argument("--tol", type=float, default=0.20)
    ap.add_argument("--drop", action="store_true", help="write a filtered paired-score table")
    a = ap.parse_args(argv)
    runs = sorted(ek.sub("3.3", "results").glob("*_slope_edit_*"))
    run = Path(a.run) if a.run else (runs[-1] if runs else None)
    if run is None or not (run / "slope_edit_locations_9t.csv").exists():
        raise FileNotFoundError("MISSING INPUT: S3 run folder with slope_edit_locations_9t.csv. Run _slope_terrain_edit_9t.py.")
    locs = pd.read_csv(run / "slope_edit_locations_9t.csv")
    fl = seam_flags(locs, a.rule, a.tol)
    o1 = run / "slope_edit_seam_flags_9t.csv"
    fl.to_csv(o1, index=False)
    summ = {"rule": a.rule, "tol": a.tol, "n_locations": int(len(locs)),
            "pass_by_variant": fl.groupby("variant")["pass"].sum().astype(int).to_dict(),
            "median_ratio_by_variant": fl.groupby("variant")["ratio"].median().to_dict(),
            "outside_diff_fail": int((~locs.outside_diff_ok.astype(bool)).sum())}
    sc_p = run / "slope_edit_paired_scores_9t.csv"
    if a.drop and sc_p.exists():
        bad = set(fl.loc[(fl.variant == "pit") & ~fl["pass"], "loc_id"])
        sc = pd.read_csv(sc_p)
        sc[~sc.loc_id.isin(bad)].to_csv(run / "slope_edit_paired_scores_seamok_9t.csv", index=False)
        summ["dropped_locations"] = len(bad)
    o2 = run / "slope_edit_seam_summary_9t.json"
    o2.write_text(json.dumps(summ, indent=2, default=float), encoding="utf-8")
    npz = sorted((ek.sub("3.3", "data/interim") / "slope_edit_windows_9t").glob("loc*.npz"))
    o3 = render(npz, run / "slope_edit_seam_renders_9t.png")
    print(json.dumps(summ, indent=2, default=float))
    print(f"wrote {o1}\n      {o2}\n      {o3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

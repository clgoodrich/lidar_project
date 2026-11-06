"""6.3 S2. Neutral contact sheets and the blind label-entry file.

Purpose
    One PNG per sampled candidate with hillshade, slope, local relief and an aerial chip when one exists. Fixed
    chip size (60 m), north up, the same stretch for every sheet, a crosshair at the centroid and a scale bar.
    No model score, no DEP record, no band, no other reviewer's label. Sheets carry a random sheet id. The key
    linking sheet id to candidate id is written to a separate file that reviewers must not open.
    The label-entry file has one row per reviewer per sheet (sheet_id, reviewer, class, confidence, minutes, notes).
Inputs
    confuser_sample_9t.csv (S1), hillshade_9t_05.tif, slope_9t_05.tif, local_relief_10_9t_05.tif (held),
    aerial orthoimage (assumed, optional; the panel says "no aerial chip" when absent)
Outputs
    data/9t/results/confusers/sheets/<sheet_id>.png
    data/9t/results/confusers/confuser_labels_9t.csv          (blank entry rows, two reviewers)
    data/9t/results/confusers/confuser_sheet_key_9t.csv       (sheet_id -> uid, kept from reviewers)
Run
    python expansions/6_adjacent/6_3_confuser_classes/src/_confuser_sheets_9t.py [--sample FILE] [--reviewers A,B] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _confuser_common_9t as C
from _confuser_common_9t import ek

STRETCH = {"hillshade": (0, 255, "gray"), "slope": (0, 45, "cividis"), "relief": (-1.0, 1.0, "PuOr_r")}


def read_chip(path: Path, cx: float, cy: float, half_m: float):
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open(path) as r:
        win = from_bounds(cx - half_m, cy - half_m, cx + half_m, cy + half_m, transform=r.transform)
        a = r.read(window=win, boundless=True, fill_value=r.nodata if r.nodata is not None else 0).astype(np.float32)
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
    return a[0] if a.shape[0] == 1 else np.moveaxis(a[:3], 0, -1)


def render_sheet(chips: dict, out_png: Path, sheet_id: str, chip_m: float, dpi: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(chips)
    fig, axes = plt.subplots(1, len(names), figsize=(3.0 * len(names), 3.4))
    for ax, nm in zip(np.atleast_1d(axes), names):
        a = chips[nm]
        ext = (-chip_m / 2, chip_m / 2, -chip_m / 2, chip_m / 2)
        if a is None:
            ax.text(0.5, 0.5, "no aerial chip", ha="center", va="center", transform=ax.transAxes)
        elif a.ndim == 3:
            v = a[np.isfinite(a)]
            ax.imshow(np.clip(a / (np.percentile(v, 99) if v.size else 1), 0, 1), extent=ext)
        else:
            lo, hi, cmap = STRETCH.get(nm, (np.nanmin(a), np.nanmax(a), "gray"))
            ax.imshow(a, vmin=lo, vmax=hi, cmap=cmap, extent=ext)
        ax.plot([0], [0], marker="+", color=ek.PALETTE["orange"], markersize=14, mew=1.5)
        ax.plot([-chip_m / 2 + 3, -chip_m / 2 + 13], [-chip_m / 2 + 3] * 2, color="white", lw=3)
        ax.plot([-chip_m / 2 + 3, -chip_m / 2 + 13], [-chip_m / 2 + 3] * 2, color="black", lw=1)
        ax.set_title(nm, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"sheet {sheet_id}   north up   bar 10 m", fontsize=9)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def build(cfg: dict, out_dir: Path, sample_csv: Path, reviewers: list[str], overrides: dict | None = None,
          limit: int | None = None):
    o = overrides or {}
    sh = cfg["sheets"]
    s = pd.read_csv(sample_csv)
    ek.assert_unique(s, "uid")
    rng = np.random.default_rng(ek.child_seed(cfg["sample"]["master_seed"], 0, 7))
    s["sheet_id"] = [f"S{v:05d}" for v in rng.choice(100000, len(s), replace=False)]
    rasters = {nm: C.input_path(cfg, nm, o.get(nm), required=(nm != "aerial")) for nm in sh["panels"]}
    sdir = out_dir / "sheets"
    sdir.mkdir(parents=True, exist_ok=True)
    pngs = []
    for r in s.head(limit).itertuples() if limit else s.itertuples():
        chips = {nm: (read_chip(p, r.cx, r.cy, sh["chip_m"] / 2) if p is not None else None) for nm, p in rasters.items()}
        png = sdir / f"{r.sheet_id}.png"
        render_sheet(chips, png, r.sheet_id, sh["chip_m"], sh["dpi"])
        pngs.append(png)
    key = out_dir / f"confuser_sheet_key_{cfg['area']}.csv"
    s[["sheet_id", "uid", "relabel"]].to_csv(key, index=False)
    lab = pd.DataFrame([{"sheet_id": sid, "reviewer": rv, "class": "", "confidence": "", "minutes": "", "notes": ""}
                        for rv in reviewers for sid in s.sheet_id.sample(frac=1, random_state=int(rng.integers(1e9)))])
    lab_csv = out_dir / f"confuser_labels_{cfg['area']}.csv"
    if lab_csv.exists():
        raise FileExistsError(f"{lab_csv} exists and may hold reviewer labels. Move it before regenerating.")
    lab.to_csv(lab_csv, index=False)
    C.provenance(cfg, out_dir, "confsheets", inputs=[sample_csv] + [p for p in rasters.values() if p],
                 outputs=[key, lab_csv] + pngs[:5], params=sh)
    return {"sheets": pngs, "key": key, "labels": lab_csv}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--sample", default=None, help="default <out>/confuser_sample_9t.csv")
    ap.add_argument("--reviewers", default="reviewer_a,reviewer_b")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None, help="render only the first N sheets (pilot check)")
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    out = C.results_dir(cfg, a.out)
    sample = Path(a.sample) if a.sample else out / f"confuser_sample_{cfg['area']}.csv"
    if not sample.exists():
        raise C.MissingInput(f"{sample} missing. Run _confuser_sample_9t.py first.")
    r = build(cfg, out, sample, a.reviewers.split(","), limit=a.limit)
    print(f"wrote {len(r['sheets'])} sheets in {out / 'sheets'}\nwrote {r['labels']}\nwrote {r['key']} (keep from reviewers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

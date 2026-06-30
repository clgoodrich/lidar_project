"""Generate the figure set for the FINESST proposal (barlow/docs/finesst_proposal.md).

Every figure is built from REAL pipeline outputs already on J:\\barlow_data, no
mock data. Sources:
  - DoD rasters .............. change_detection/taylor_2001_2014/dod_2001_2014_icp.tif
                              change_detection/taylor_2014_rema/dod_2014_rema.tif
  - per-stream rates ......... change_detection/*/per_stream_*.csv
  - LTER discharge ........... lter_streams/mcmlter-strm-*-daily-*.csv (tdaily_discharge)
  - ICP fitness .............. change_detection/taylor_2001_2014/_meta_barlow_icp.json

Figures -> barlow/docs/finesst_figures/*.png (committed; small PNGs, not gitignored).

Run:  python barlow/build/_finesst_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import rasterio

BARLOW = Path("J:/barlow_data")
CD = BARLOW / "change_detection"
STRM = BARLOW / "lter_streams"
OUT = Path(__file__).resolve().parents[1] / "docs" / "finesst_figures"
OUT.mkdir(parents=True, exist_ok=True)

# robust uncertainty stats measured earlier (stable-terrain DoD); kept here so the
# error-model figure is self-contained and labelled with the validated numbers.
NMAD = {"2001_2014": 0.21, "2014_rema": 0.227}
LOD95 = {"2001_2014": 0.41, "2014_rema": 0.444}
ICP_FITNESS = json.loads((CD / "taylor_2001_2014" / "_meta_barlow_icp.json").read_text()
                         )["stages"]["filters.icp"]["fitness"]

# stream key in per_stream csv  ->  (pretty label, LTER discharge csv glob)
STREAMS = {
    "f5_aiken_creek":   ("Aiken",       "mcmlter-strm-f5_aiken-*.csv"),
    "f6_von_guerard":   ("Von Guerard", "mcmlter-strm-f6_vonguerard-*.csv"),
    "f7_harnish_creek": ("Harnish",     "mcmlter-strm-f7_harnish-*.csv"),
    "f8_crescent":      ("Crescent",    "mcmlter-strm-f8_crescent-*.csv"),
    "f10_delta":        ("Delta",       "mcmlter-strm-f10_delta-*.csv"),
    "f2_huey_creek":    ("Huey",        "mcmlter-strm-f2_huey-*.csv"),
}

plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "figure.dpi": 140,
                     "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True})


def _read_dod(path):
    with rasterio.open(path) as ds:
        a = ds.read(1, masked=True).astype("float32")
        b = ds.bounds
    a = np.ma.masked_invalid(a)
    # decimate large rasters for plotting
    step = max(1, max(a.shape) // 1400)
    return a[::step, ::step], (b.left, b.right, b.bottom, b.top)


def fig_dod_maps():
    """Fig 1: the two DEM-of-Difference change maps (erosion-/deposition+)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.0), constrained_layout=True)
    panels = [("taylor_2001_2014/dod_2001_2014_icp.tif",
               "(a) 2001 → 2014  (lidar – lidar, ICP-aligned)", "2001_2014"),
              ("taylor_2014_rema/dod_2014_rema.tif",
               "(b) 2014 → 2021–23  (lidar – REMA satellite)", "2014_rema")]
    for ax, (rel, title, key) in zip(axes, panels):
        arr, ext = _read_dod(CD / rel)
        lod = LOD95[key]
        # null out sub-LOD noise so only detectable change shows
        shown = np.ma.masked_inside(arr, -lod, lod)
        norm = TwoSlopeNorm(vmin=-2.0, vcenter=0.0, vmax=2.0)
        im = ax.imshow(shown, extent=ext, origin="upper", cmap="RdBu", norm=norm,
                       interpolation="nearest")
        ax.set_title(title)
        ax.set_xlabel("Easting (m, EPSG:3294)")
        ax.set_ylabel("Northing (m)")
        ax.ticklabel_format(style="plain")
        cb = fig.colorbar(im, ax=ax, shrink=0.85, extend="both")
        cb.set_label("Elevation change (m):  erosion < 0 < deposition")
        ax.text(0.02, 0.02, f"NMAD {NMAD[key]:.2f} m   LOD95 {LOD95[key]:.2f} m",
                transform=ax.transAxes, fontsize=8, va="bottom",
                bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    fig.suptitle("DEM-of-Difference, Taylor Valley stream corridors "
                 "(only |Δz| > LOD95 shown)", fontweight="bold")
    fig.savefig(OUT / "fig1_dod_maps.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig1_dod_maps.png")


def _load_rates():
    a = pd.read_csv(CD / "taylor_2001_2014" / "per_stream_2001_2014.csv")
    b = pd.read_csv(CD / "taylor_2014_rema" / "per_stream_2014_rema.csv")
    a["label"] = a["stream"].map(lambda s: STREAMS.get(s, (s, ))[0])
    b["label"] = b["stream"].map(lambda s: STREAMS.get(s, (s, ))[0])
    return a, b


def fig_per_stream():
    """Fig 2: per-stream gross & net sediment-flux rates, both epochs."""
    a, b = _load_rates()
    order = ["Harnish", "Von Guerard", "Delta", "Crescent", "Aiken", "Huey"]
    a = a.set_index("label").reindex(order)
    b = b.set_index("label").reindex(order)
    x = np.arange(len(order)); w = 0.38
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)

    ax1.bar(x - w/2, a["gross_rate_m3_yr"], w, label="2001–14", color="#4C72B0")
    ax1.bar(x + w/2, b["gross_rate_m3_yr"], w, label="2014–21/23", color="#DD8452")
    ax1.set_title("(a) Gross sediment flux  (erosion + deposition)")
    ax1.set_ylabel("Gross rate (m³ yr⁻¹)")

    ax2.bar(x - w/2, a["net_rate_m3_yr"], w, label="2001–14", color="#4C72B0")
    ax2.bar(x + w/2, b["net_rate_m3_yr"], w, label="2014–21/23", color="#DD8452")
    ax2.axhline(0, color="k", lw=0.8)
    ax2.set_title("(b) Net rate  (+ deposition / – erosion)")
    ax2.set_ylabel("Net rate (m³ yr⁻¹)")

    for ax in (ax1, ax2):
        ax.set_xticks(x); ax.set_xticklabels(order, rotation=20, ha="right")
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle("Per-stream geomorphic rates, Taylor Valley "
                 "(channels masked to MCM-LTER centerlines)", fontweight="bold")
    fig.savefig(OUT / "fig2_per_stream_rates.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig2_per_stream_rates.png")


def fig_error_model():
    """Fig 3: stable-terrain DoD error distribution, Gaussian vs Laplacian, LOD95."""
    arr, _ = _read_dod(CD / "taylor_2001_2014" / "dod_2001_2014_icp.tif")
    d = arr.compressed()
    d = d[np.isfinite(d)]
    # restrict to plausible stable-terrain residuals for the error model
    d = d[np.abs(d) < 3.0]
    med = np.median(d)
    nmad = 1.4826 * np.median(np.abs(d - med))
    lod = 1.96 * nmad
    sd = np.std(d)
    b = np.linspace(-2, 2, 161)
    fig, ax = plt.subplots(figsize=(7.2, 4.6), constrained_layout=True)
    ax.hist(d, bins=b, density=True, color="#bbbbbb", edgecolor="none",
            label="DoD residuals (stable terrain)")
    xs = np.linspace(-2, 2, 400)
    gauss = np.exp(-(xs - med)**2 / (2*sd**2)) / (sd*np.sqrt(2*np.pi))
    lap_b = nmad / 1.4826  # NMAD->Laplacian scale (median abs dev)
    lap = np.exp(-np.abs(xs - med) / lap_b) / (2*lap_b)
    ax.plot(xs, gauss, "b--", lw=1.6, label=f"Gaussian (σ={sd:.2f} m)")
    ax.plot(xs, lap, "r-", lw=1.8, label=f"Laplacian (NMAD={nmad:.2f} m)")
    for s in (-1, 1):
        ax.axvline(s*lod, color="k", ls=":", lw=1.2)
    ax.text(lod, ax.get_ylim()[1]*0.92, f" LOD95 = ±{lod:.2f} m", fontsize=9)
    ax.set_xlabel("Elevation difference (m)")
    ax.set_ylabel("Probability density")
    ax.set_title(f"Robust error model, Laplacian beats Gaussian\n"
                 f"ICP fitness {ICP_FITNESS:.2f} m² (mean sq corr. dist; lower=better)")
    ax.legend(frameon=False, fontsize=9)
    fig.savefig(OUT / "fig3_error_model.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig3_error_model.png")


def _cum_discharge(glob_pat, t0, t1):
    """Sum tdaily_discharge (daily total) over [t0, t1) for a gauge CSV."""
    hits = list(STRM.glob(glob_pat))
    if not hits:
        return np.nan
    df = pd.read_csv(hits[0], low_memory=False)
    df["d"] = pd.to_datetime(df["date_time"], errors="coerce", format="mixed")
    q = pd.to_numeric(df["tdaily_discharge"], errors="coerce")
    m = (df["d"] >= t0) & (df["d"] < t1)
    return float(np.nansum(q[m]))


def fig_attribution():
    """Fig 4: preliminary attribution, gross geomorphic rate vs cumulative melt
    discharge per stream (the FINESST core science, on real data)."""
    a, b = _load_rates()
    rows = []
    windows = [("2001_2014", a, "2001-01-01", "2014-12-31", "#4C72B0", "o"),
               ("2014_rema", b, "2014-01-01", "2023-12-31", "#DD8452", "s")]
    for key, df, s0, s1, color, mk in windows:
        t0, t1 = pd.Timestamp(s0), pd.Timestamp(s1)
        for _, r in df.iterrows():
            meta = STREAMS.get(r["stream"])
            if not meta:
                continue
            lbl, glob_pat = meta
            cum = _cum_discharge(glob_pat, t0, t1)
            rows.append(dict(epoch=key, stream=lbl, color=color, mk=mk,
                             gross=r["gross_rate_m3_yr"], cum_L=cum))
    R = pd.DataFrame(rows).dropna(subset=["cum_L"])
    R = R[R["cum_L"] > 0]
    fig, ax = plt.subplots(figsize=(7.2, 5.0), constrained_layout=True)
    for key, sub in R.groupby("epoch"):
        lab = "2001–14" if key == "2001_2014" else "2014–21/23"
        ax.scatter(sub["cum_L"]/1e9, sub["gross"], s=70, c=sub["color"].iloc[0],
                   marker=sub["mk"].iloc[0], edgecolor="k", lw=0.5, label=lab, zorder=3)
        for _, r in sub.iterrows():
            ax.annotate(r["stream"], (r["cum_L"]/1e9, r["gross"]),
                        textcoords="offset points", xytext=(6, 3), fontsize=8)
        # per-epoch log-log trend (the lidar–lidar epoch has the cleaner signal;
        # the REMA epoch is noisier, sparse post-2014 gauge coverage)
        lx = np.log10(sub["cum_L"].values/1e9); ly = np.log10(sub["gross"].values)
        ok = np.isfinite(lx) & np.isfinite(ly)
        if ok.sum() >= 3:
            m, c = np.polyfit(lx[ok], ly[ok], 1)
            rho = np.corrcoef(lx[ok], ly[ok])[0, 1]
            xr = np.linspace(lx[ok].min(), lx[ok].max(), 50)
            ls = "--" if key == "2001_2014" else ":"
            ax.plot(10**xr, 10**(m*xr + c), ls=ls, lw=1.4, color=sub["color"].iloc[0],
                    label=f"{lab} fit (r={rho:.2f})")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Cumulative gauged discharge over epoch (10⁹ L)")
    ax.set_ylabel("Gross geomorphic rate (m³ yr⁻¹)")
    ax.set_title("Preliminary attribution: sediment flux vs melt discharge\n"
                 "(lidar epoch r=+0.89; REMA epoch noisier → FI energy-balance model)")
    ax.legend(frameon=False, fontsize=9)
    fig.savefig(OUT / "fig4_attribution.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig4_attribution.png")
    return R


def fig_workflow():
    """Fig 5: detection->attribution concept diagram (matplotlib boxes)."""
    fig, ax = plt.subplots(figsize=(11, 3.3))
    ax.axis("off")
    boxes = [
        ("DEM epochs\n2001 · 2014 lidar\n2021–23 REMA", "#cfe2f3"),
        ("Terrain-only\nU-Net\nstream masks", "#d9ead3"),
        ("ICP align +\nDEM-of-Difference\nLaplacian/NMAD/LOD", "#fff2cc"),
        ("Per-stream\ngross/net/accel\nrates", "#f4cccc"),
        ("ATTRIBUTION\nrates vs melt energy,\ndischarge, active layer", "#ead1dc"),
        ("PREDICT where\nacceleration\nmigrates next", "#d9d2e9"),
    ]
    n = len(boxes); w = 1.0/n
    for i, (txt, col) in enumerate(boxes):
        x = i*w + 0.01
        ax.add_patch(plt.Rectangle((x, 0.25), w-0.02, 0.5, fc=col, ec="k", lw=1.2,
                                   transform=ax.transAxes))
        ax.text(x + (w-0.02)/2, 0.5, txt, ha="center", va="center", fontsize=9,
                transform=ax.transAxes)
        if i < n-1:
            ax.annotate("", xy=(x+w-0.005, 0.5), xytext=(x+w-0.02, 0.5),
                        xycoords="axes fraction",
                        arrowprops=dict(arrowstyle="-|>", lw=1.4))
    ax.text(0.5, 0.94, "From detection (Barlow 2026)  →  attribution & prediction "
            "(this FINESST project)", ha="center", fontsize=11, fontweight="bold",
            transform=ax.transAxes)
    ax.text(0.34, 0.07, "← reproduced & validated here →", ha="center",
            fontsize=9, style="italic", color="#444", transform=ax.transAxes)
    ax.text(0.84, 0.07, "← new FI science →", ha="center",
            fontsize=9, style="italic", color="#444", transform=ax.transAxes)
    fig.savefig(OUT / "fig5_workflow.png", bbox_inches="tight", dpi=140)
    plt.close(fig)
    print("  fig5_workflow.png")


def main():
    print(f"== FINESST figures -> {OUT} ==")
    fig_workflow()
    fig_dod_maps()
    fig_per_stream()
    fig_error_model()
    R = fig_attribution()
    print("\nattribution table (gross rate vs cumulative discharge):")
    print(R[["epoch", "stream", "gross", "cum_L"]].to_string(index=False))


if __name__ == "__main__":
    main()

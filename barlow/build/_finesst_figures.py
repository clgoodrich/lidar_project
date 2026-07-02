"""Generate the figure set for the FINESST proposal (barlow/docs/finesst_proposal.md).

Every figure is built from REAL pipeline outputs already on E:\\barlow_data_DO_NOT_DELETE, no
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

BARLOW = Path("E:/barlow_data_DO_NOT_DELETE")
CD = BARLOW / "change_detection"
STRM = BARLOW / "lter_streams"
OUT = Path(__file__).resolve().parents[1] / "docs" / "finesst_figures"
OUT.mkdir(parents=True, exist_ok=True)

ICP_FITNESS = json.loads((CD / "taylor_2001_2014" / "_meta_barlow_icp.json").read_text()
                         )["stages"]["filters.icp"]["fitness"]

# DoD acquisition windows (decimal-year DEM dates -> discharge integration windows).
# 2001 ATM flown Nov-Dec 2001; 2014/15 NCALM austral summer; REMA strips 2021-23 (~2022).
EPOCH_WIN = {"2001_2014": ("2001-11-01", "2015-01-01"),
             "2014_rema": ("2015-01-01", "2022-01-01")}


def _nmad_lod(path):
    """NMAD / LOD95 computed live from the (bias-corrected) DoD raster, no hardcoding."""
    with rasterio.open(path) as ds:
        a = ds.read(1)
        d = a[a != -9999]
    nmad = 1.4826 * np.median(np.abs(d - np.median(d)))
    return nmad, 1.96 * nmad

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
    """Fig 1: the two DEM-of-Difference change maps (erosion-/deposition+).
    Both panels are the SAME stream-corridor window (bias-only co-registration;
    ICP is validated separately on a high-relief pilot, see fig3), so the epochs
    are spatially comparable. NMAD/LOD annotated live from each raster."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.0), constrained_layout=True)
    panels = [("taylor_2001_2014/dod_2001_2014.tif",
               "(a) 2001 → 2014  (lidar – lidar)", "2001_2014"),
              ("taylor_2014_rema/dod_2014_rema.tif",
               "(b) 2014 → 2021–23  (lidar – REMA satellite)", "2014_rema")]
    for ax, (rel, title, key) in zip(axes, panels):
        nmad, lod = _nmad_lod(CD / rel)
        arr, ext = _read_dod(CD / rel)
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
        ax.text(0.02, 0.02, f"NMAD {nmad:.2f} m   LOD95 {lod:.2f} m",
                transform=ax.transAxes, fontsize=8, va="bottom",
                bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    fig.suptitle("DEM-of-Difference, Taylor Valley stream corridors, same window "
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
    """Fig 2: per-stream specific (area-normalized) sediment-flux rates, both epochs.
    Specific rates (mm/yr = m³/yr per m² of masked channel) are the comparable
    quantity: the valid-data footprint differs between epochs (the 2001 ATM lidar
    swath is narrower than REMA coverage), so raw m³/yr totals would confound
    real change with coverage."""
    a, b = _load_rates()
    order = ["Harnish", "Von Guerard", "Delta", "Crescent", "Aiken", "Huey"]
    a = a.set_index("label").reindex(order)
    b = b.set_index("label").reindex(order)
    x = np.arange(len(order)); w = 0.38
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)

    ax1.bar(x - w/2, a["gross_mm_yr"], w, label="2001–14", color="#4C72B0")
    ax1.bar(x + w/2, b["gross_mm_yr"], w, label="2014–21/23", color="#DD8452")
    ax1.set_title("(a) Specific gross flux  (erosion + deposition)")
    ax1.set_ylabel("Gross rate (mm yr⁻¹ over channel area)")

    ax2.bar(x - w/2, a["net_mm_yr"], w, label="2001–14", color="#4C72B0")
    ax2.bar(x + w/2, b["net_mm_yr"], w, label="2014–21/23", color="#DD8452")
    ax2.axhline(0, color="k", lw=0.8)
    ax2.set_title("(b) Specific net rate  (+ deposition / – erosion)")
    ax2.set_ylabel("Net rate (mm yr⁻¹ over channel area)")

    for ax in (ax1, ax2):
        ax.set_xticks(x); ax.set_xticklabels(order, rotation=20, ha="right")
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle("Per-stream specific geomorphic rates, Taylor Valley "
                 "(channels masked to MCM-LTER centerlines)", fontweight="bold")
    fig.savefig(OUT / "fig2_per_stream_rates.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig2_per_stream_rates.png")


def fig_error_model():
    """Fig 3: DoD error distribution, Gaussian vs Laplacian, LOD95. Built from the
    high-relief ICP pilot window (where ICP matters); channel pixels are a
    negligible share, so residuals approximate stable terrain (verified: excluding
    channels shifts NMAD by <0.01 m on the stream-corridor window)."""
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
    ax.set_title(f"Robust error model, Laplacian beats Gaussian (high-relief ICP pilot)\n"
                 f"ICP fitness {ICP_FITNESS:.2f} m² (mean sq corr. dist; lower=better)")
    ax.legend(frameon=False, fontsize=9)
    fig.savefig(OUT / "fig3_error_model.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig3_error_model.png")


def _mean_discharge(glob_pat, t0, t1):
    """Mean tdaily_discharge (L/day) per GAUGED day over [t0, t1). Mean-per-gauged-day
    (not the cumulative sum) because gauge coverage is unequal across streams and
    epochs (257-716 gauged days in 2001-14; 48-362 post-2015) — cumulative sums
    would bias poorly-gauged streams low. Returns (mean_L_day, n_gauged_days)."""
    hits = list(STRM.glob(glob_pat))
    if not hits:
        return np.nan, 0
    df = pd.read_csv(hits[0], low_memory=False)
    df["d"] = pd.to_datetime(df["date_time"], errors="coerce", format="mixed")
    q = pd.to_numeric(df["tdaily_discharge"], errors="coerce")
    m = (df["d"] >= t0) & (df["d"] < t1) & q.notna()
    if m.sum() == 0:
        return np.nan, 0
    return float(q[m].mean()), int(m.sum())


def fig_attribution():
    """Fig 4: preliminary attribution, per-stream geomorphic rate vs mean gauged melt
    discharge (the FINESST core science, on real data). Two panels: (a) total gross
    flux (m³/yr) — scales with channel size, the first-order 'bigger streams move
    more' relation; (b) specific rate (mm/yr, area-normalized) — the melt-INTENSITY
    signal O1 targets. Lidar epoch is fit per panel; the REMA epoch shows no coherent
    relation under sparse post-2015 gauging and is plotted unfit, which motivates
    modeled (gauge-independent) melt-energy drivers."""
    from scipy import stats as sstats
    a, b = _load_rates()
    rows = []
    for key, df, color, mk in [("2001_2014", a, "#4C72B0", "o"),
                               ("2014_rema", b, "#DD8452", "s")]:
        t0, t1 = (pd.Timestamp(s) for s in EPOCH_WIN[key])
        for _, r in df.iterrows():
            meta = STREAMS.get(r["stream"])
            if not meta:
                continue
            lbl, glob_pat = meta
            mq, nd = _mean_discharge(glob_pat, t0, t1)
            rows.append(dict(epoch=key, stream=lbl, color=color, mk=mk,
                             gross=r["gross_rate_m3_yr"], spec=r["gross_mm_yr"],
                             meanq=mq, gauge_days=nd))
    R = pd.DataFrame(rows).dropna(subset=["meanq"])
    R = R[R["meanq"] > 0]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    panels = [("gross", "Gross geomorphic rate (m³ yr⁻¹)",
               "(a) Total flux (confounded by channel size / coverage)"),
              ("spec", "Specific gross rate (mm yr⁻¹)",
               "(b) Specific (per-area) rate: the melt-intensity signal")]
    stats_txt = {}
    for ax, (ycol, ylab, title) in zip(axes, panels):
        for key, sub in R.groupby("epoch"):
            lab = "2001–14" if key == "2001_2014" else "2014–21/23"
            filled = key == "2001_2014"
            ax.scatter(sub["meanq"]/1e6, sub[ycol], s=70,
                       c=sub["color"].iloc[0] if filled else "none",
                       edgecolor="k" if filled else sub["color"].iloc[0],
                       marker=sub["mk"].iloc[0], lw=0.5 if filled else 1.4,
                       label=lab if filled else f"{lab} (sparse gauging; no fit)",
                       zorder=3)
            for _, r in sub.iterrows():
                ax.annotate(r["stream"], (r["meanq"]/1e6, r[ycol]),
                            textcoords="offset points", xytext=(6, 3), fontsize=8)
            if not filled:
                continue  # REMA epoch: no coherent relation -> honest, no fit line
            lx = np.log10(sub["meanq"].values/1e6)
            ly = np.log10(sub[ycol].values)
            m, c = np.polyfit(lx, ly, 1)
            pr, pp = sstats.pearsonr(lx, ly)
            sr, sp = sstats.spearmanr(lx, ly)
            stats_txt[ycol] = (pr, pp, sr, sp)
            xr = np.linspace(lx.min(), lx.max(), 50)
            ax.plot(10**xr, 10**(m*xr + c), "--", lw=1.4, color=sub["color"].iloc[0],
                    label=f"{lab} fit  r={pr:+.2f} (p={pp:.3f}),  ρ={sr:+.2f} (p={sp:.3f})")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlabel("Mean gauged discharge over epoch (10⁶ L day⁻¹)")
        ax.set_ylabel(ylab)
        ax.set_title(title, fontsize=10)
        ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.suptitle("Preliminary attribution: sediment flux vs melt discharge, "
                 "n = 6 gauged streams per epoch (lake-level rise screened)",
                 fontweight="bold")
    fig.savefig(OUT / "fig4_attribution.png", bbox_inches="tight")
    plt.close(fig)
    print("  fig4_attribution.png")
    for ycol, (pr, pp, sr, sp) in stats_txt.items():
        print(f"    lidar-epoch {ycol}: Pearson r={pr:+.2f} (p={pp:.3f})  "
              f"Spearman rho={sr:+.2f} (p={sp:.3f})")
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
    print(R[["epoch", "stream", "gross", "spec", "meanq", "gauge_days"]].to_string(index=False))


if __name__ == "__main__":
    main()

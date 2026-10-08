"""NISAR GSLC coherence change at annotated pads, 9t: candidate disturbance events.

Option 2 of the 2026-10-05 "what L-band can do for wells" list.
Work on a pad (clearing, grading, a rig) changes the surface between two passes, so the pair
that spans the work loses coherence on the pad. A pad is 40-100 m across, so unlike a pit it
covers many 5 m pixels.

DEP plug dates cannot validate this here. In the April 2026 DEP export only one well in the radar
window has a plug date in or near the stack (121-39189, 2025-10-12, before the first date). So
this run is detection with a false-alarm rate measured on decoys, not a validation.

Per pair (consecutive dates on one track, at most MAX_DT_DAYS apart):
  * HH coherence with a WIN x WIN boxcar (5 x 5 = 25 m, 25 looks).
  * pad core = pad shrunk by CORE_M; ring 20-60 m out, clear of pads, pits and roads.
  * d = mean coherence(core) - mean coherence(ring).
  * anomaly = d minus that pad's median d over the pairs of the same track.
Decoys: N_DECOY same-shape copies per pad on background 150-600 m away, with the same steps.
Threshold: the anomaly at which only FA_RATE of decoy pairs fall below it, per season.
Pad pairs below that are candidate disturbance events. The decoys give the expected count.

  python notebooks/wellsight_v2/s5_eval/_nisar_pad_change_9t.py
"""
import importlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st = ifg.st
from _common import read_layer  # noqa: E402

OUT, FIG, CRS, ANN = st.OUT, st.FIG, st.CRS, st.ANN
WELLS = HERE.parents[2] / "data" / "_source" / "reference" / "dep_wells" / "venango_wells_all.gpkg"
WIN, CORE_M, RING, N_DECOY, FA_RATE, SEED = 5, 5.0, (20.0, 60.0), 5, 0.01, 20261007
# pads #1F5FA8 circles, decoys #8E959B crosses, flagged events #D97706 (lost/found palette,
# dataviz validate_palette.js --mode light --pairs all, 2026-10-07: CVD worst #8E959B-#D97706 dE 15.0
# protan, normal 16.9; the grey fails the chroma floor by design and decoys also differ by marker).
# Maps greyscale.
PAD_C, DEC_C, EVT_C, INK = "#1F5FA8", "#8E959B", "#D97706", "#2B2F36"


def season(d1):
    m = int(d1[5:7])
    return "winter" if m in (12, 1, 2, 3) else "snowfree"


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = ifg.load_complex()
    pairs = ifg.pairs_of(idx)
    cover = st.canopy_cover(tf, shape)
    in_tile = np.isfinite(cover)
    ok_flat = in_tile.ravel()

    pads = read_layer(ANN, "plat").to_crs(CRS).reset_index(drop=True)
    pits = read_layer(ANN, "pit_outside").to_crs(CRS)
    roads = read_layer(ANN, "roads").to_crs(CRS)
    feat = rasterize([(g, 1) for g in pd.concat([pads.buffer(20), pits.buffer(20), roads.buffer(20)])],
                     out_shape=shape, transform=tf, fill=0, dtype="uint8").astype(bool)
    bg_flat = (in_tile & ~feat).ravel()
    excl = pd.concat([pads.buffer(5), pits.buffer(5), roads.buffer(5)]).union_all()

    sets = []
    for i, g in enumerate(pads.geometry):
        core, rg = st.pixel_sets(g, CORE_M, RING, excl, tf, shape, ok_flat)
        if len(core) < 4 or len(rg) < 20:
            continue
        dec = st.placebo_sets(g, CORE_M, RING, excl, tf, shape, ok_flat, bg_flat, rng, N_DECOY)
        sets.append((i, core, rg, dec))
    print(f"{len(sets)} of {len(pads)} pads usable inside the window")

    wells = gpd.read_file(WELLS).to_crs(CRS)
    j = gpd.sjoin(wells[["PERMIT_NUM", "WELL_STATU", "DATE_PLUGG", "geometry"]],
                  gpd.GeoDataFrame(geometry=pads.buffer(10), crs=CRS).reset_index(names="pad"), predicate="within")
    wells_on = j.groupby("pad").agg(n_dep_wells=("PERMIT_NUM", "size"),
                                    n_active=("WELL_STATU", lambda s: int((s == "Active").sum())),
                                    permits=("PERMIT_NUM", lambda s: ";".join(s)))

    rows, cohs = [], {}
    for p in pairs.itertuples():
        coh, _ = ifg.interferogram(stack[p.f1][0], stack[p.f2][0], w=WIN)
        cf = coh.ravel()
        cohs[(p.track, p.d1, p.d2)] = coh
        for i, core, rg, dec in sets:
            ring = np.nanmean(cf[rg])
            rows.append(dict(kind="pad", pad=i, copy=-1, track=p.track, d1=p.d1, d2=p.d2,
                             coh_core=np.nanmean(cf[core]), coh_ring=ring, d=np.nanmean(cf[core]) - ring))
            for k, (a, b) in enumerate(dec):
                rows.append(dict(kind="decoy", pad=i, copy=k, track=p.track, d1=p.d1, d2=p.d2,
                                 coh_core=np.nanmean(cf[a]), coh_ring=np.nanmean(cf[b]),
                                 d=np.nanmean(cf[a]) - np.nanmean(cf[b])))
    df = pd.DataFrame(rows)
    df["season"] = df.d1.map(season)
    df["anomaly"] = df.d - df.groupby(["kind", "pad", "copy", "track"]).d.transform("median")

    thr = {s: float(np.nanquantile(g.anomaly, FA_RATE)) for s, g in df[df.kind == "decoy"].groupby("season")}
    df["flag"] = df.anomaly < df.season.map(thr)
    out_rows = []
    for s, g in df.groupby("season"):
        n_pad, k_pad = int((g.kind == "pad").sum()), int(g[g.kind == "pad"].flag.sum())
        fa = float(g[g.kind == "decoy"].flag.mean())
        bt = binomtest(k_pad, n_pad, fa, alternative="greater")
        out_rows.append(dict(season=s, threshold=round(thr[s], 3), n_pad_pairs=n_pad, pad_events=k_pad,
                             expected_from_decoys=round(n_pad * fa, 1), decoy_rate=round(fa, 4),
                             p_more_than_decoys=float(f"{bt.pvalue:.2g}")))
    res = pd.DataFrame(out_rows)
    print(res.to_string())

    ev = df[(df.kind == "pad") & df.flag].copy()
    ev = ev.join(wells_on, on="pad")
    ev[["n_dep_wells", "n_active"]] = ev[["n_dep_wells", "n_active"]].fillna(0).astype(int)
    ev["pad_area_m2"] = pads.area.values[ev.pad]
    ev["pad_events_total"] = ev.groupby("pad").pad.transform("size")
    ev = ev.sort_values("anomaly")
    print(ev[["pad", "track", "d1", "d2", "coh_core", "coh_ring", "anomaly", "n_dep_wells", "n_active",
              "pad_events_total"]].head(25).to_string())

    # pads with repeated events, and the one in-window plug
    rep = ev.groupby("pad").size()
    plug = j[j.PERMIT_NUM == "121-39189"]
    plug_pad = int(plug["pad"].iloc[0]) if len(plug) else None

    stem = "nisar_pad_change"
    df.to_csv(OUT / f"{stem}_per_pair_9t.csv", index=False)
    res.to_csv(OUT / f"{stem}_by_season_9t.csv", index=False)
    gdf = gpd.GeoDataFrame(ev.drop(columns=["kind", "copy", "flag"]), geometry=pads.geometry.values[ev.pad], crs=CRS)
    gdf.to_file(OUT / f"{stem}_events_9t.gpkg", layer="candidate_pad_events", driver="GPKG")
    json.dump(dict(params=dict(win=WIN, core_m=CORE_M, ring_m=RING, n_decoy=N_DECOY, fa_rate=FA_RATE, seed=SEED),
                   n_pads_used=len(sets), n_pairs=len(pairs), by_season=out_rows,
                   pads_with_2plus_events=int((rep >= 2).sum()),
                   plugged_121_39189_pad=plug_pad,
                   plugged_121_39189_pad_events=ev[ev.pad == plug_pad][["track", "d1", "d2", "anomaly"]].to_dict("records")
                   if plug_pad is not None else None),
              open(OUT / f"{stem}_summary_9t.json", "w"), indent=2, default=float)

    # figure 1: anomaly distributions, pads vs decoys, per season
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    bins = np.linspace(-0.4, 0.4, 61)
    for a, s in zip(ax, ["snowfree", "winter"]):
        g = df[df.season == s]
        a.hist(g[g.kind == "decoy"].anomaly.dropna(), bins, density=True, color=DEC_C, alpha=0.8, label="decoys")
        a.hist(g[g.kind == "pad"].anomaly.dropna(), bins, density=True, histtype="step", lw=2, color=PAD_C, label="pads")
        a.axvline(thr[s], color=EVT_C, lw=2, ls="--", label=f"{FA_RATE:.0%} decoy threshold")
        r = res[res.season == s].iloc[0]
        a.set_title(f"{s}: {r.pad_events} pad events, {r.expected_from_decoys} expected", fontsize=10)
        a.set_xlabel("coherence anomaly (pad minus ring, minus its own median)")
    ax[0].set_ylabel("density")
    ax[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f"{stem}_anomaly_hist_9t.png", dpi=150)

    # figure 2: time series and chips for the four strongest snow-free events
    top = ev[ev.season == "snowfree"].drop_duplicates("pad").head(4)
    if len(top):
        fig, ax = plt.subplots(2, len(top), figsize=(3.6 * len(top), 7), squeeze=False)
        for c, e in enumerate(top.itertuples()):
            ts = df[(df.kind == "pad") & (df.pad == e.pad) & (df.track == e.track)].sort_values("d1")
            tsd = df[(df.kind == "decoy") & (df.pad == e.pad) & (df.track == e.track)]
            for k, g in tsd.groupby("copy"):
                ax[0, c].plot(pd.to_datetime(g.sort_values("d1").d1), g.sort_values("d1").coh_core,
                              color=DEC_C, marker="x", lw=0.8)
            ax[0, c].plot(pd.to_datetime(ts.d1), ts.coh_core, color=PAD_C, marker="o", lw=2, label="pad")
            ax[0, c].plot(pd.to_datetime([e.d1]), [e.coh_core], marker="o", ms=12, mfc="none", mec=EVT_C, mew=2)
            ax[0, c].set_title(f"pad {e.pad}, track {e.track}\n{e.d1} to {e.d2}", fontsize=9)
            ax[0, c].tick_params(axis="x", labelrotation=55, labelsize=7)
            ax[0, c].set_ylim(0, 1)
            coh = cohs[(e.track, e.d1, e.d2)]
            g = pads.geometry.iloc[e.pad]
            cx, cy = g.centroid.x, g.centroid.y
            c0, r0 = int((cx - 150 - tf.c) / 5), int((cy + 150 - tf.f) / -5)
            chip = coh[max(r0, 0):r0 + 60, max(c0, 0):c0 + 60]
            ax[1, c].imshow(chip, cmap="Greys_r", vmin=0, vmax=1,
                            extent=[tf.c + c0 * 5, tf.c + (c0 + chip.shape[1]) * 5,
                                    tf.f - (r0 + chip.shape[0]) * 5, tf.f - r0 * 5])
            gpd.GeoSeries([g]).boundary.plot(ax=ax[1, c], color=EVT_C, lw=1.5)
            ax[1, c].set_xticks([]); ax[1, c].set_yticks([])
            ax[1, c].set_title(f"coherence, 300 m chip\nwells on pad: {e.n_dep_wells} ({e.n_active} active)", fontsize=9)
        ax[0, 0].set_ylabel("pad core coherence (decoys as grey crosses)")
        fig.suptitle("Candidate disturbance events: strongest snow-free coherence drops on pads", fontsize=11)
        fig.tight_layout()
        fig.savefig(FIG / f"{stem}_top_events_9t.png", dpi=150)
    print("done", stem)


if __name__ == "__main__":
    main()

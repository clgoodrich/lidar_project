"""Stage 0 of docs/iterations/nisar_regeocode_plan_9t.md: how far off is NASA's GSLC placement over 9t?

Builds a fake radar brightness image from the 1 m lidar bare earth, then slides it over the real
mean HH image to find the shift that lines them up best.

Simulated brightness (area projection, Small 2011):
  * Each 1 m lidar cell is a facet with normal n. l is the unit vector from ground to satellite.
  * Its weight is the facet area seen by the radar: max(n.l, 0) / n_z (n_z turns map area into
    true facet area). A flat cell weighs l_z = cos(incidence).
  * Facets are binned into radar cells: slant range s = -P.l and along-track a = P.v, where v is
    the horizontal unit vector at right angles to the horizontal look. Bin size 3.1 m slant range
    by 4.4 m along track (the RSLC sample spacing).
  * Each bin's summed weight over the flat value is the simulated brightness. Each 1 m cell takes
    its bin's value. Facing slopes come out bright, back slopes dark, layover very bright.
  * Shadow: n.l <= 0. Layover: the slope facing the satellite is steeper than the incidence angle.
    Terrain blocking further away is not traced. At 38-47 degrees incidence it is rare on 9t.

Match: both images go to dB, minus their 250 m running mean, on the 5 m GSLC grid. The 1 m simulation is
shifted at 1 m steps (25 sub-pixel offsets, each block-averaged to 5 m) and every 5 m lag up to
+-30 m is scored by normalized cross-correlation. Done on the whole tile and on 4 x 4 blocks.

Shift sign: (dx, dy) is how far features sit in the radar image from where the lidar says they
are, in metres east and north. "away_m" is that shift along the horizontal direction pointing
away from the satellite. A DEM that is too high under trees pushes features away from it.

Gate (plan): every block within +-2.5 m means NASA's placement is good enough. The DEM is NAD83(2011)
and the GSLC is WGS84. They differ by about 1-1.5 m here, so shifts under that are not resolvable.

Run (about 20 minutes, mostly the remote cube read for the first run):
  python notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py
  python notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py --figure   # figure only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import uniform_filter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "s1_build"))
from _common import path_for  # noqa: E402

D9 = path_for("data") / "9t"
DEM = D9 / "derived" / "1m" / "dem_9t_1m.tif"
CHM = D9 / "derived" / "1m" / "chm_9t_1m.tif"
GS = D9 / "derived" / "nisar_gslc_5m"
OUT = D9 / "results" / "nisar"
FIG = OUT / "figures"
LOS_JSON = OUT / "nisar_los_by_track_9t.json"
TRACKS = (26, 90, 162)
DS_RANGE, DS_AZ = 3.1, 4.4   # RSLC sample spacing, slant range and along track (m)
MAX_LAG = 30                 # m
BG_M = 250
NBLK = 4
GATE_M = 2.5


def read_los():
    """Look vector and incidence per track at the 9t centre, from one GSLC's radarGrid cubes."""
    out = {int(k): v for k, v in json.load(open(LOS_JSON)).items()} if LOS_JSON.exists() else {}
    if all(t in out for t in TRACKS):
        return out
    import h5py, fsspec  # noqa: E401
    from scipy.interpolate import RegularGridInterpolator
    import _fetch_nisar_gslc_window_9t as fetch
    idx = pd.read_csv(GS / "nisar_gslc_window_index_9t_5m.csv")
    q = fetch.query().set_index("granule")
    xc, yc, hc = 621750.0, 4595250.0, 380.0   # 9t centre, a typical ellipsoid height
    for t in [t for t in TRACKS if t not in out]:
        g = idx[idx.track == t].iloc[-1].granule
        f = fsspec.filesystem("http").open(fetch.signed_url(q.loc[g, "url"]), block_size=8 * 2**20,
                                           cache_type="blockcache")
        with h5py.File(f, "r") as h:
            rg = h["science/LSAR/GSLC/metadata/radarGrid"]
            x, y, z = rg["xCoordinates"][:], rg["yCoordinates"][:], rg["heightAboveEllipsoid"][:]
            # read only the 2 x 2 cube cells around the 9t centre (a full cube takes minutes remotely)
            i0 = int(np.clip(np.searchsorted(x, xc) - 1, 0, len(x) - 2))
            yi = np.argsort(y)
            j = int(np.clip(np.searchsorted(y[yi], yc) - 1, 0, len(y) - 2))
            j0, j1 = sorted((yi[j], yi[j + 1]))
            v = {}
            for k in ("losUnitVectorX", "losUnitVectorY", "alongTrackUnitVectorX",
                      "alongTrackUnitVectorY", "incidenceAngle"):
                a = rg[k][:, j0:j1 + 1, i0:i0 + 2]          # (height, y, x)
                ys = y[j0:j1 + 1]
                if ys[0] > ys[-1]:
                    ys, a = ys[::-1], a[:, ::-1, :]
                v[k] = float(RegularGridInterpolator((z, ys, x[i0:i0 + 2]), a)((hc, yc, xc)))
        e, n = v["losUnitVectorX"], v["losUnitVectorY"]
        out[t] = dict(granule=g, east=e, north=n, up=float(np.sqrt(1 - e * e - n * n)),
                      incidence_deg=v["incidenceAngle"],
                      along_east=v["alongTrackUnitVectorX"], along_north=v["alongTrackUnitVectorY"])
        print(t, out[t])
        json.dump(out, open(LOS_JSON, "w"), indent=2)
    return out


def simulate(dem, l):
    """Area-projection brightness (ratio to flat ground) per 1 m cell, plus shadow/layover masks."""
    gy, gx = np.gradient(np.where(np.isfinite(dem), dem, np.nan))   # rows run south: gy is -dz/dnorth
    dzdx, dzdn = gx, -gy
    nz = 1 / np.sqrt(1 + dzdx ** 2 + dzdn ** 2)
    n = np.stack([-dzdx * nz, -dzdn * nz, nz])
    lv = np.array([l["east"], l["north"], l["up"]])
    cos_loc = np.tensordot(lv, n, 1)
    w = np.clip(cos_loc, 0, None) / nz
    shadow = cos_loc <= 0
    lh = np.hypot(lv[0], lv[1])
    away = -lv[:2] / lh                                   # horizontal, away from the satellite
    foreslope = -(dzdx * away[0] + dzdn * away[1])        # rise toward the satellite
    layover = foreslope > np.tan(np.radians(l["incidence_deg"]))
    rr, cc = np.mgrid[0:dem.shape[0], 0:dem.shape[1]]
    e, nn = cc + 0.5, -(rr + 0.5)
    s = -(e * lv[0] + nn * lv[1] + np.nan_to_num(dem) * lv[2])
    vdir = np.array([l["along_east"], l["along_north"]])
    vdir = vdir / np.hypot(*vdir)
    a = e * vdir[0] + nn * vdir[1]
    si = np.floor((s - np.nanmin(s)) / DS_RANGE).astype(np.int64)
    ai = np.floor((a - a.min()) / DS_AZ).astype(np.int64)
    key = si * (ai.max() + 1) + ai
    ok = np.isfinite(dem) & np.isfinite(w)
    tot = np.bincount(key[ok], weights=w[ok], minlength=key.max() + 1)
    # flat ground: a bin covers DS_RANGE / sin(inc) of ground range, each m2 weighing l_z
    flat = DS_RANGE / lh * DS_AZ * lv[2]
    sim = tot[key] / flat
    sim[~ok] = np.nan
    return sim.astype(np.float32), shadow & ok, layover & ok


def to_db_hp(a, px):
    """dB minus the 250 m running mean (NaN-aware)."""
    db = 10 * np.log10(np.clip(a, 1e-6, None)) if px != "db" else a
    m = np.isfinite(db)
    k = BG_M // 5 + 1
    bg = uniform_filter(np.where(m, db, 0), k) / np.maximum(uniform_filter(m.astype(float), k), 1e-6)
    return np.where(m, db - bg, np.nan)


def block5(a):
    h, w = a.shape[0] // 5, a.shape[1] // 5
    return np.nanmean(a[:h * 5, :w * 5].reshape(h, 5, w, 5), axis=(1, 3))


def ncc(A, B, lag5, n5):
    """Normalized cross-correlation of A against B shifted by every 5 m lag.

    A and B are padded by lag5. Sums are taken once per lag over the core, then split into
    NBLK x NBLK blocks by reshaping; the tile score adds the block sums."""
    bs = n5 // NBLK
    core = (slice(lag5, lag5 + bs * NBLK),) * 2
    Ac = A[core]
    out = {}
    def bsum(x):
        return x.reshape(NBLK, bs, NBLK, bs).sum(axis=(1, 3))
    for dy in range(-lag5, lag5 + 1):
        for dx in range(-lag5, lag5 + 1):
            Bc = np.roll(B, (dy, dx), axis=(0, 1))[core]
            m = np.isfinite(Ac) & np.isfinite(Bc)
            a, b = np.where(m, Ac, 0), np.where(m, Bc, 0)
            S = [bsum(v) for v in (m.astype(float), a, b, a * b, a * a, b * b)]
            for name, idx in [("tile", (slice(None), slice(None)))] +                     [(f"b{i}{j}", (i, j)) for i in range(NBLK) for j in range(NBLK)]:
                N, sa, sb, sab, saa, sbb = (np.sum(v[idx]) for v in S)
                if N < 500:
                    continue
                cov = sab - sa * sb / N
                den = np.sqrt((saa - sa * sa / N) * (sbb - sb * sb / N))
                out.setdefault(name, {})[(dy, dx)] = float(cov / den)
    return out


# lost/found palette reused (CLAUDE.md): dataviz validator --pairs all, worst pair dE 21.1 deutan,
# 22.6 normal, all >= 3:1 on white. Tracks also differ by marker shape.
TRACK_STYLE = {26: ("#1F5FA8", "o", "track 026 (descending, looks east)"),
               90: ("#D97706", "s", "track 090 (ascending, looks west)"),
               162: ("#A31515", "^", "track 162 (ascending, looks west)")}
ARROW_X = 25   # arrows drawn 25 times longer than the shift


def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    df = pd.read_csv(OUT / "nisar_lidar_sim_match_shifts_9t.csv")
    blk = df[df.block != "tile"]
    with rasterio.open(D9 / "derived" / "1m" / "hillshade_9t_1m.tif") as s:
        hs = s.read(1, out_shape=(900, 900)).astype(float)
        b = s.bounds
    bs = (b.right - b.left) / NBLK
    fig, ax = plt.subplots(1, 4, figsize=(17, 4.6), gridspec_kw=dict(width_ratios=[1, 1, 1, 1.15]))
    for k, t in enumerate(TRACKS):
        a = ax[k]
        a.imshow(hs, cmap="gray", extent=(b.left, b.right, b.bottom, b.top), alpha=0.8)
        col, mk, lab = TRACK_STYLE[t]
        for _, r in blk[blk.track == t].iterrows():
            i, j = int(r.block[1]), int(r.block[2])
            xc, yc = b.left + (j + 0.5) * bs, b.top - (i + 0.5) * bs
            a.annotate("", xy=(xc + ARROW_X * r.dx_east_m, yc + ARROW_X * r.dy_north_m), xytext=(xc, yc),
                       arrowprops=dict(arrowstyle="-|>", color=col, lw=2))
            a.plot(xc, yc, mk, color=col, ms=5)
            a.text(xc, yc - 0.32 * bs, f"{np.hypot(r.dx_east_m, r.dy_north_m):.0f} m", ha="center",
                   fontsize=7, color="black", bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.5))
        a.set_title(lab, fontsize=9)
        a.set_xticks([]); a.set_yticks([])
    ax[0].text(0.02, 0.02, f"arrow = where the radar puts features\nrelative to the lidar ground (x{ARROW_X})",
               transform=ax[0].transAxes, fontsize=7, bbox=dict(fc="white", ec="none"))
    a = ax[3]
    for t in TRACKS:
        col, mk, lab = TRACK_STYLE[t]
        g = blk[blk.track == t]
        a.scatter(g.canopy_h_mean_m, g.away_m, color=col, marker=mk, s=36, label=lab.split(" (")[0],
                  edgecolor="white", linewidth=0.8)
    a.axhspan(-GATE_M, GATE_M, color="#8E959B", alpha=0.25, lw=0)
    a.text(6.2, 0.6, "gate: within 2.5 m", fontsize=7)
    a.set_xlabel("mean canopy height in block (m, lidar)")
    a.set_ylabel("shift away from the satellite (m)")
    a.set_title("Shift grows with canopy height", fontsize=9)
    a.legend(fontsize=7, frameon=False)
    a.grid(alpha=0.3)
    fig.suptitle("NISAR GSLC over 9t against a lidar bare-earth radar simulation, 4 x 4 blocks of 1.1 km",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    FIG.mkdir(exist_ok=True)
    path = FIG / "nisar_lidar_sim_match_9t.png"
    fig.savefig(path, dpi=150)
    print("wrote", path)


def main():
    los = read_los()
    with rasterio.open(DEM) as s:
        dem = s.read(1).astype(np.float64)
        dem[dem == s.nodata] = np.nan
        dtf = s.transform
    with rasterio.open(CHM) as s:
        chm = s.read(1).astype(np.float32)
        chm[(chm == s.nodata) | (chm < 0)] = np.nan
    # the 5 m GSLC grid: DEM cell (0,0) is at 619500, 4597500; GSLC edge at 619295, 4597705
    with rasterio.open(GS / "nisar_bright_targets_layers_t162_9t.tif") as s:
        gtf, gshape = s.transform, s.shape
    c0 = int(round((dtf.c - gtf.c) / 5))
    r0 = int(round((gtf.f - dtf.f) / 5))
    n5 = dem.shape[0] // 5
    lag5 = MAX_LAG // 5
    rows, sims = [], {}
    chm5 = block5(np.where(np.isfinite(chm), chm, np.nan))
    for t in TRACKS:
        l = los[t]
        sim, shadow, layover = simulate(dem, l)
        sims[t] = (sim, shadow, layover)
        with rasterio.open(GS / f"nisar_bright_targets_layers_t{t:03d}_9t.tif") as s:
            hh = s.read(1)
        # radar image cut to the lidar footprint, with a lag margin
        R = to_db_hp(hh, "db")
        Rc = R[r0 - lag5:r0 + n5 + lag5, c0 - lag5:c0 + n5 + lag5]
        away = -np.array([l["east"], l["north"]]) / np.hypot(l["east"], l["north"])
        bs = n5 // NBLK
        blocks = [("tile", slice(lag5, lag5 + bs * NBLK), slice(lag5, lag5 + bs * NBLK))]
        for i in range(NBLK):
            for j in range(NBLK):
                blocks.append((f"b{i}{j}", slice(lag5 + i * bs, lag5 + (i + 1) * bs),
                               slice(lag5 + j * bs, lag5 + (j + 1) * bs)))
        scores = {b[0]: {} for b in blocks}
        for oy in range(5):
            for ox in range(5):
                # shift the 1 m sim by (ox east, oy south) m, then block to 5 m
                sh = np.full_like(sim, np.nan)
                sh[oy:, ox:] = sim[:sim.shape[0] - oy, :sim.shape[1] - ox]
                S = to_db_hp(block5(sh), "lin")
                Sp = np.full_like(Rc, np.nan)
                Sp[lag5:lag5 + n5, lag5:lag5 + n5] = S[:n5, :n5]
                for name, sc in ncc(Rc, Sp, lag5, n5).items():
                    for (dy, dx), v in sc.items():
                        # total shift of sim content: east = 5*dx + ox, south = 5*dy + oy
                        scores[name][(5 * dx + ox, -(5 * dy + oy))] = v
        for name, ry, rx in blocks:
            sc = scores[name]
            (dx_m, dy_m), best = max(sc.items(), key=lambda kv: kv[1])
            zero = sc.get((0, 0), np.nan)
            sub = (slice(ry.start - lag5, ry.stop - lag5), slice(rx.start - lag5, rx.stop - lag5))
            rows.append(dict(track=t, block=name, dx_east_m=dx_m, dy_north_m=dy_m,
                             away_m=round(dx_m * away[0] + dy_m * away[1], 1),
                             along_m=round(-dx_m * away[1] + dy_m * away[0], 1),
                             ncc_best=round(best, 3), ncc_zero_shift=round(zero, 3),
                             canopy_h_mean_m=round(float(np.nanmean(chm5[sub])), 1),
                             canopy_cover=round(float(np.nanmean(chm5[sub] > 2)), 2),
                             at_lag_edge=bool(max(abs(dx_m), abs(dy_m)) >= MAX_LAG)))
        print(pd.DataFrame([r for r in rows if r["track"] == t]).to_string())

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "nisar_lidar_sim_match_shifts_9t.csv", index=False)

    # sim rasters on the 5 m GSLC grid (gitignored folder; small)
    for t, (sim, shadow, layover) in sims.items():
        bands = {"sim_brightness_db": 10 * np.log10(np.clip(block5(sim), 1e-6, None)),
                 "shadow_fraction": block5(shadow.astype(np.float32)),
                 "layover_fraction": block5(layover.astype(np.float32))}
        path = GS / f"nisar_lidar_sim_t{t:03d}_9t.tif"
        with rasterio.open(path, "w", driver="GTiff", height=gshape[0], width=gshape[1], count=3,
                           dtype="float32", crs="EPSG:32617", transform=gtf, nodata=np.nan,
                           compress="deflate") as dst:
            for i, (k, a) in enumerate(bands.items(), 1):
                full = np.full(gshape, np.nan, np.float32)
                full[r0:r0 + n5, c0:c0 + n5] = a[:n5, :n5]
                dst.write(full, i)
                dst.set_band_description(i, k)
        print("wrote", path)

    blk = df[df.block != "tile"]
    summ = dict(params=dict(range_bin_m=DS_RANGE, az_bin_m=DS_AZ, max_lag_m=MAX_LAG, bg_m=BG_M,
                            blocks=f"{NBLK}x{NBLK}", gate_m=GATE_M, radar_image="mean HH dB, all dates"),
                los=los,
                tile=df[df.block == "tile"].set_index("track")[["dx_east_m", "dy_north_m", "away_m",
                                                                 "ncc_best", "ncc_zero_shift"]].to_dict("index"),
                blocks_within_gate=int((np.hypot(blk.dx_east_m, blk.dy_north_m) <= GATE_M).sum()),
                blocks_total=int(len(blk)),
                corr_away_vs_canopy_by_track={int(t): round(float(np.corrcoef(g.away_m, g.canopy_h_mean_m)[0, 1]), 2)
                                              for t, g in blk.groupby("track")})
    json.dump(summ, open(OUT / "nisar_lidar_sim_match_summary_9t.json", "w"), indent=2, default=int)
    print(json.dumps(summ, indent=2, default=int))
    figure()


if __name__ == "__main__":
    figure() if "--figure" in sys.argv else main()

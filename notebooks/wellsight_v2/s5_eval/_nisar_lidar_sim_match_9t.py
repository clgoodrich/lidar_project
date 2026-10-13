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
"along_m" is the shift at right angles to that, pointing back against the flight direction.

Gate (plan): every block within +-2.5 m means NASA's placement is good enough.

Datum (fixed 2026-10-13): the simulation sits on the lidar's NAD83(2011) grid and the radar on
WGS84 (ITRF2014). On 9t the same point is 0.80 m west and 1.01 m north in the radar grid. Shifts
are reported in the radar's frame: that datum offset, taken at the stack's mean date, is removed.
The best shift is refined below 1 m with a parabola through the peak and its neighbours.

Canopy (--kappa k, added 2026-10-13): forest echo comes partly from inside the canopy. With k > 0
each facet's echo is binned at the slant range of a point k x canopy height (25 m mean) above the ground,
then mapped back to the map the way our ground-height placement does it. Elevated echo then
lands toward the satellite in the simulation as it does in the radar. k = 0 is bare earth.

Dates: NASA granules in _nisar_area.BAD_DATES are left out. --dates provisional or beta keeps
one processing generation only (beta dates sit 3.2 m closer in slant range, see the plan doc).

Run (about 20 minutes, mostly the remote cube read for the first run):
  python notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py                  # NASA's GSLC
  python notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py --stack lidar    # our stack
  python notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py --stack lidar --dates beta
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
import _nisar_area as A  # noqa: E402  (--area picks 9t, 613590 or mkf)

DEM = A.lidar("dem")
CHM = A.lidar("chm")
GS = A.GSLC
OUT = A.RESULTS
FIG = OUT / "figures"
LOS_JSON = OUT / f"nisar_los_by_track_{A.TAG}.json"
# --stack lidar: match our lidar-height re-placement (Stage 3) instead of NASA's GSLC (check V3)
STACK = "lidar" if "--stack" in sys.argv and sys.argv[sys.argv.index("--stack") + 1] == "lidar" else "gslc"
DATES = sys.argv[sys.argv.index("--dates") + 1] if "--dates" in sys.argv else "all"   # all, provisional, beta
KAPPA = float(sys.argv[sys.argv.index("--kappa") + 1]) if "--kappa" in sys.argv else 0.0
SLC_LIDAR = A.DATA / "derived" / "nisar_slc_lidar_5m"
_IDX = pd.read_csv(GS / f"nisar_gslc_window_index_{A.TAG}_5m.csv")
# tracks with at least one usable window (all of track 090's McKean windows are empty)
TRACKS = tuple(int(t) for t in sorted(A.usable(_IDX).track.unique()))


def stack_index():
    """Usable dates of the chosen stack and the folder holding them."""
    if STACK == "gslc":
        idx, folder = _IDX, GS
    else:
        idx, folder = pd.read_csv(SLC_LIDAR / f"nisar_slc_lidar_index_{A.TAG}.csv"), SLC_LIDAR
    idx = A.usable(idx)
    return (idx if DATES == "all" else idx[idx.collection == DATES]), folder


def _suffix():
    if STACK == "gslc":
        s = ""
    else:
        idx, _ = stack_index()
        s = ("_coregabs" if "absolute" in idx and idx.absolute.any() else "_coreg")             if "coreg" in idx and idx.coreg.any() else "_lidarslc"
    return s + {"all": "", "provisional": "_prov", "beta": "_beta"}[DATES] + (f"_k{round(KAPPA * 100):03d}" if KAPPA else "")


# --figure --suffix _coreg_k010 redraws a saved run (its suffix says stack, dates and kappa)
SUF = sys.argv[sys.argv.index("--suffix") + 1] if "--suffix" in sys.argv else _suffix()
DS_RANGE, DS_AZ = 3.1, 4.4   # RSLC sample spacing, slant range and along track (m)
MAX_LAG = 30                 # m
BG_M = 250
NBLK = 4 if A.TAG == "9t" else None   # set from the area size in main(): blocks of about 1.1 km
GATE_M = 2.5


def grid_point(xc, yc, epsg):
    """(x, y) of a UTM 17 point in the granule's zone, and the turn from that zone's grid to UTM 17's."""
    if epsg == 32617:
        return xc, yc, 0.0
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:32617", f"EPSG:{epsg}", always_xy=True)
    px, py = tr.transform(xc, yc)
    qx, qy = tr.transform(xc, yc + 1000.0)       # UTM 17 grid north, seen in the other zone
    return px, py, float(np.arctan2(qx - px, qy - py))


def rotate(e, n, rot):
    """East/north components in the granule zone -> UTM 17 grid components."""
    c, s_ = np.cos(rot), np.sin(rot)
    return float(e * c - n * s_), float(e * s_ + n * c)


def read_los():
    """Look vector and incidence per track at the area centre, from one GSLC's radarGrid cubes."""
    try:
        out = {int(k): v for k, v in json.load(open(LOS_JSON)).items()} if LOS_JSON.exists() else {}
    except json.JSONDecodeError:   # a run that died mid-write; read the cubes again
        out = {}
    if all(t in out for t in TRACKS):
        return out
    import h5py, fsspec  # noqa: E401
    from scipy.interpolate import RegularGridInterpolator
    import _fetch_nisar_gslc_window_9t as fetch
    idx = pd.read_csv(GS / f"nisar_gslc_window_index_{A.TAG}_5m.csv")
    q = fetch.query().set_index("granule")
    if A.TAG == "9t":
        xc, yc, hc = 621750.0, 4595250.0, 380.0   # 9t centre, a typical ellipsoid height
    else:
        x0, y0, x1, y1 = A.bounds("EPSG:32617")
        with rasterio.open(DEM) as s:
            z = s.read(1, out_shape=(200, 200), masked=True)
        # DEM heights are NAVD88; the geoid is about 34 m below the ellipsoid here
        xc, yc, hc = (x0 + x1) / 2, (y0 + y1) / 2, float(np.ma.median(z)) - 34.0
    for t in [t for t in TRACKS if t not in out]:
        g = idx[idx.track == t].iloc[-1].granule
        f = fsspec.filesystem("http").open(fetch.signed_url(q.loc[g, "url"]), block_size=8 * 2**20,
                                           cache_type="blockcache")
        with h5py.File(f, "r") as h:
            rg = h["science/LSAR/GSLC/metadata/radarGrid"]
            x, y, z = rg["xCoordinates"][:], rg["yCoordinates"][:], rg["heightAboveEllipsoid"][:]
            epsg = int(h["science/LSAR/GSLC/grids/frequencyA/projection"][()])
            # McKean track 098 comes in UTM 18: look up the centre in that zone, then turn its
            # vectors by the angle between the two zones' grid north (about 4 deg there)
            px, py, rot = grid_point(xc, yc, epsg)
            # read only the 2 x 2 cube cells around the 9t centre (a full cube takes minutes remotely)
            i0 = int(np.clip(np.searchsorted(x, px) - 1, 0, len(x) - 2))
            yi = np.argsort(y)
            j = int(np.clip(np.searchsorted(y[yi], py) - 1, 0, len(y) - 2))
            j0, j1 = sorted((yi[j], yi[j + 1]))
            v = {}
            for k in ("losUnitVectorX", "losUnitVectorY", "alongTrackUnitVectorX",
                      "alongTrackUnitVectorY", "incidenceAngle"):
                a = rg[k][:, j0:j1 + 1, i0:i0 + 2]          # (height, y, x)
                ys = y[j0:j1 + 1]
                if ys[0] > ys[-1]:
                    ys, a = ys[::-1], a[:, ::-1, :]
                v[k] = float(RegularGridInterpolator((z, ys, x[i0:i0 + 2]), a)((hc, py, px)))
        e, n = rotate(v["losUnitVectorX"], v["losUnitVectorY"], rot)
        v["alongTrackUnitVectorX"], v["alongTrackUnitVectorY"] = rotate(
            v["alongTrackUnitVectorX"], v["alongTrackUnitVectorY"], rot)
        out[t] = dict(granule=g, east=e, north=n, up=float(np.sqrt(1 - e * e - n * n)),
                      incidence_deg=v["incidenceAngle"],
                      along_east=v["alongTrackUnitVectorX"], along_north=v["alongTrackUnitVectorY"])
        print(t, out[t])
        json.dump(out, open(LOS_JSON, "w"), indent=2)
    return out


def simulate(dem, l, chm=None, kappa=0.0):
    """Area-projection brightness (ratio to flat ground) per 1 m cell, plus shadow/layover masks.
    kappa > 0: each facet's echo sits kappa x canopy height above the ground (see the docstring)."""
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
    s = -(e * lv[0] + nn * lv[1] + np.nan_to_num(dem) * lv[2])            # ground, as we place pixels
    if kappa:   # a stand echoes as a whole: canopy height averaged over 25 m, not crown by crown
        c = np.where(np.isfinite(chm), chm, 0.0)
        c = uniform_filter(c, 25) / np.maximum(uniform_filter(np.isfinite(chm).astype(float), 25), 1e-6)
    s_echo = s - kappa * c * lv[2] if kappa else s                        # where the echo really is
    vdir = np.array([l["along_east"], l["along_north"]])
    vdir = vdir / np.hypot(*vdir)
    a = e * vdir[0] + nn * vdir[1]
    s0 = min(np.nanmin(s), np.nanmin(s_echo))
    si = np.floor((s - s0) / DS_RANGE).astype(np.int64)
    se = np.floor((s_echo - s0) / DS_RANGE).astype(np.int64)
    ai = np.floor((a - a.min()) / DS_AZ).astype(np.int64)
    key = si * (ai.max() + 1) + ai
    key_echo = se * (ai.max() + 1) + ai
    ok = np.isfinite(dem) & np.isfinite(w)
    tot = np.bincount(key_echo[ok], weights=w[ok], minlength=max(key.max(), key_echo.max()) + 1)
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
# Track 098 (McKean only) adds teal #00909A: dataviz validate_palette.js --mode light --pairs all
# on all four (2026-10-12), ALL CHECKS PASS, worst pair #00909A-#1F5FA8 dE 15.1 deutan, 15.2 normal.
TRACK98_C = "#00909A"
TRACK_STYLE = {26: ("#1F5FA8", "o", "track 026 (descending, looks east)"),
               90: ("#D97706", "s", "track 090 (ascending, looks west)"),
               162: ("#A31515", "^", "track 162 (ascending, looks west)"),
               98: (TRACK98_C, "D", "track 098 (descending, looks east)")}
ARROW_X = 25   # arrows drawn 25 times longer than the shift


def mean_hh_db(t):
    """Mean HH power in dB over the chosen dates of track t, from NASA's stack or from ours.
    (Before 2026-10-13 NASA's stack used the bright-target layer: all dates, bad ones too.)"""
    idx, folder = stack_index()
    idx = idx[idx.track == t]
    acc = None
    for f in idx.file:
        with rasterio.open(folder / f) as s:
            p = np.abs(s.read(1)).astype(np.float64) ** 2
        acc = p if acc is None else acc + p
    with np.errstate(divide="ignore", invalid="ignore"):
        return (10 * np.log10(acc / len(idx))).astype(np.float32)


def datum_offset():
    """Where the radar grid (WGS84 = ITRF2014) puts the area centre minus where the lidar grid
    (NAD83(2011)) puts it, east and north metres, at the mean date of the stack."""
    from pyproj import Transformer
    idx, _ = stack_index()
    d = pd.to_datetime(idx.date)
    epoch = float(np.mean(d.dt.year + (d.dt.dayofyear - 0.5) / 365.25))
    with rasterio.open(DEM) as s:
        crs, b = s.crs, s.bounds
    xc, yc = (b.left + b.right) / 2, (b.bottom + b.top) / 2
    lon, lat = Transformer.from_crs(crs, "EPSG:6318", always_xy=True).transform(xc, yc)
    # PROJ's NAD83(2011) -> "WGS 84" is a null transform; ITRF2014 (EPSG:7912) stands in
    lo, la, _, _ = Transformer.from_crs("EPSG:6319", "EPSG:7912", always_xy=True).transform(lon, lat, 0.0, epoch)
    xi, yi = Transformer.from_crs("EPSG:4326", "EPSG:32617", always_xy=True).transform(lo, la)
    return float(xi - xc), float(yi - yc), round(epoch, 2)


def refine(sc, dx, dy):
    """Sub-metre peak: a parabola through the best 1 m shift and its two neighbours, per axis."""
    def vertex(m, c, p):
        den = m - 2 * c + p
        return 0.5 * (m - p) / den if np.isfinite(den) and den < 0 else 0.0
    c = sc[(dx, dy)]
    ox = vertex(sc.get((dx - 1, dy), np.nan), c, sc.get((dx + 1, dy), np.nan))
    oy = vertex(sc.get((dx, dy - 1), np.nan), c, sc.get((dx, dy + 1), np.nan))
    return dx + float(np.clip(ox, -0.5, 0.5)), dy + float(np.clip(oy, -0.5, 0.5))


def figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    df = pd.read_csv(OUT / f"nisar_lidar_sim_match_shifts{SUF}_{A.TAG}.csv")
    nblk = int(df.block[df.block != "tile"].str[1].astype(int).max()) + 1
    blk = df[df.block != "tile"]
    with rasterio.open(A.lidar("hillshade")) as s:
        hs = s.read(1, out_shape=(900, 900)).astype(float)
        b = s.bounds
    bs = (b.right - b.left) / nblk
    nt = len(TRACKS)
    fig, ax = plt.subplots(1, nt + 1, figsize=(4.25 * (nt + 1), 4.6), gridspec_kw=dict(width_ratios=[1] * nt + [1.15]))
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
    fig.text(0.01, 0.012, f"Arrow = where the radar puts features relative to the lidar ground, drawn {ARROW_X} "
             "times longer. Label = length of the shift.", fontsize=7)
    a = ax[nt]
    for t in TRACKS:
        col, mk, lab = TRACK_STYLE[t]
        g = blk[blk.track == t]
        a.scatter(g.canopy_h_mean_m, g.away_m, color=col, marker=mk, s=36, label=lab.split(" (")[0],
                  edgecolor="white", linewidth=0.8)
    a.axhspan(-GATE_M, GATE_M, color="#8E959B", alpha=0.25, lw=0)
    a.text(0.02, GATE_M - 0.15, "gate: within 2.5 m", fontsize=7, va="top", transform=a.get_yaxis_transform())
    a.set_xlabel("mean canopy height in block (m, lidar)")
    a.set_ylabel("shift away from the satellite (m)")
    a.set_title("Shift against canopy height", fontsize=9)
    a.legend(fontsize=7, frameon=False)
    a.grid(alpha=0.3)
    import re
    stack = {"": "NASA's GSLC", "_lidarslc": "our lidar-height placement",
             "_coreg": "our placement, dates lined up",
             "_coregabs": "our placement, dates lined up and each track tied to the lidar"}[
        re.sub(r"_prov|_beta|_k\d{3}", "", SUF)]
    k = re.search(r"_k(\d{3})", SUF)
    sim = f"forest echo at {int(k.group(1))}% of stand height" if k else "bare earth"
    dates = ", provisional dates only" if "_prov" in SUF else ", beta dates only" if "_beta" in SUF else ""
    fig.suptitle(f"NISAR over {A.TAG}: {stack}{dates}, against a lidar radar simulation ({sim}). {nblk} x {nblk} blocks of about 1.1 km",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    FIG.mkdir(exist_ok=True)
    path = FIG / f"nisar_lidar_sim_match{SUF}_{A.TAG}.png"
    fig.savefig(path, dpi=150)
    print("wrote", path)


def main():
    global NBLK
    los = read_los()
    de, dn, epoch = datum_offset()
    print(f"datum: radar grid minus lidar grid = {de:+.2f} m east, {dn:+.2f} m north at {epoch}")
    with rasterio.open(DEM) as s:
        dem = s.read(1).astype(np.float64)
        dem[dem == s.nodata] = np.nan
        dtf = s.transform
    with rasterio.open(CHM) as s:
        chm = s.read(1).astype(np.float32)
        chm[(chm == s.nodata) | (chm < 0)] = np.nan
    # the 5 m GSLC grid: DEM cell (0,0) is at 619500, 4597500; GSLC edge at 619295, 4597705
    with rasterio.open(GS / f"nisar_bright_targets_layers_t{TRACKS[-1]:03d}_{A.TAG}.tif") as s:
        gtf, gshape = s.transform, s.shape
    assert dem.shape[0] == dem.shape[1], "the block layout assumes a square lidar area"
    c0 = int(round((dtf.c - gtf.c) / 5))
    r0 = int(round((gtf.f - dtf.f) / 5))
    n5 = dem.shape[0] // 5
    if NBLK is None:
        NBLK = max(1, round(n5 * 5 / 1125))
    lag5 = MAX_LAG // 5
    rows, sims = [], {}
    chm5 = block5(np.where(np.isfinite(chm), chm, np.nan))
    for t in TRACKS:
        l = los[t]
        sim, shadow, layover = simulate(dem, l, chm, KAPPA)
        sims[t] = (sim, shadow, layover)
        hh = mean_hh_db(t)
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
            if not sc:   # block outside the lidar (42% of the McKean box has none)
                continue
            (ix, iy), best = max(sc.items(), key=lambda kv: kv[1])
            fx, fy = refine(sc, ix, iy)
            # in the radar's frame: take off the NAD83 -> ITRF offset of the simulation's grid
            dx_m, dy_m = round(fx - de, 1), round(fy - dn, 1)
            zero = sc.get((0, 0), np.nan)
            sub = (slice(ry.start - lag5, ry.stop - lag5), slice(rx.start - lag5, rx.stop - lag5))
            rows.append(dict(track=t, block=name, dx_east_m=dx_m, dy_north_m=dy_m,
                             away_m=round(dx_m * away[0] + dy_m * away[1], 1),
                             along_m=round(-dx_m * away[1] + dy_m * away[0], 1),
                             ncc_best=round(best, 3), ncc_zero_shift=round(zero, 3),
                             canopy_h_mean_m=round(float(np.nanmean(chm5[sub])), 1),
                             canopy_cover=round(float(np.nanmean(chm5[sub] > 2)), 2),
                             at_lag_edge=bool(max(abs(ix), abs(iy)) >= MAX_LAG)))
        print(pd.DataFrame([r for r in rows if r["track"] == t]).to_string())

    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"nisar_lidar_sim_match_shifts{SUF}_{A.TAG}.csv", index=False)

    # sim rasters on the 5 m GSLC grid (gitignored folder; small). They do not depend on the
    # stack, so only the NASA all-dates run writes them (parallel runs would collide).
    for t, (sim, shadow, layover) in (sims.items() if STACK == "gslc" and DATES == "all" else []):
        bands = {"sim_brightness_db": 10 * np.log10(np.clip(block5(sim), 1e-6, None)),
                 "shadow_fraction": block5(shadow.astype(np.float32)),
                 "layover_fraction": block5(layover.astype(np.float32))}
        path = GS / f"nisar_lidar_sim_t{t:03d}_{A.TAG}.tif"
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
    idx, _ = stack_index()
    summ = dict(params=dict(range_bin_m=DS_RANGE, az_bin_m=DS_AZ, max_lag_m=MAX_LAG, bg_m=BG_M,
                            blocks=f"{NBLK}x{NBLK}", gate_m=GATE_M, radar_image="mean HH power in dB",
                            stack=STACK + SUF.replace("_prov", "").replace("_beta", ""), dates=DATES,
                            dates_per_track={int(k): int(v) for k, v in idx.groupby("track").size().items()},
                            left_out=sorted(f"{d} t{t:03d}" for d, t in A.BAD_DATES),
                            datum_offset_removed_east_north_m=[round(de, 2), round(dn, 2)], datum_epoch=epoch,
                            peak="1 m search, parabola refined", kappa=KAPPA),
                los=los,
                block_median_m={int(t): dict(away=round(float(g.away_m.median()), 2), along=round(float(g.along_m.median()), 2),
                                             total=round(float(np.hypot(g.dx_east_m, g.dy_north_m).median()), 2))
                                for t, g in df[df.block != "tile"].groupby("track")},
                tile=df[df.block == "tile"].set_index("track")[["dx_east_m", "dy_north_m", "away_m",
                                                                 "ncc_best", "ncc_zero_shift"]].to_dict("index"),
                blocks_within_gate=int((np.hypot(blk.dx_east_m, blk.dy_north_m) <= GATE_M).sum()),
                blocks_total=int(len(blk)),
                corr_away_vs_canopy_by_track={int(t): round(float(np.corrcoef(g.away_m, g.canopy_h_mean_m)[0, 1]), 2)
                                              for t, g in blk.groupby("track")})
    json.dump(summ, open(OUT / f"nisar_lidar_sim_match_summary{SUF}_{A.TAG}.json", "w"), indent=2, default=int)
    print(json.dumps(summ, indent=2, default=int))
    figure()


if __name__ == "__main__":
    figure() if "--figure" in sys.argv else main()

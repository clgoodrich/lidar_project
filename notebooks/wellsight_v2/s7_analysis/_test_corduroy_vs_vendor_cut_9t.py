"""Are the corn rows the same problem as the vendor's scan-angle cut? No.

THE QUESTION
------------
Two separate data-quality findings are in the deck and they keep getting
conflated, because both are described as "missing data" and both make stripes.

  THE VENDOR CUT (the Data QA slides). Venango 2020-03 stopped calling returns
  ground past 18 degrees of scan angle, while the scanner kept recording out to
  19.8. 190.9 million returns across the block were delivered UNCLASSIFIED that
  should have been ground. They are in the file. Reclassifying them is what the
  recovered-ground DEM does.

  THE CORN ROWS (the CHM slide). Parallel NoData stripes in the DSM and so in
  the CHM, 3.00 m apart on a 79 degree bearing, which
  _test_corduroy_is_scan_geometry_9t.py showed is the across-track direction of
  a 348.2 degree flight line at 112.2 m/s -- one mirror sweep at 37.4 Hz.

This asks whether they are the same thing, and answers it five ways: by scan
angle in the window, by whether the void cells hold anything recoverable, by
rebuilding the CHM on both DEMs, by correlating the two patterns over the whole
tile, and by profiling the void rate across the swath.

The swath profile is the part that explains the geometry. Dropout climbs from
0.38% at nadir to 5.35% at 12-14 degrees, then collapses to 0.89%. It collapses
because that is where the next flight line starts to overlap -- 0% of cells
inside 14 degrees see a second line, 98.3% of cells beyond it do -- and a second
pass fills what the first one missed. The vendor cut at 18 degrees sits inside
that overlap. So the two problems are not merely uncorrelated, they occupy
different parts of the swath by construction.

WHY THEY CANNOT BE THE SAME, IN ONE LINE
----------------------------------------
The cut is about what a return was LABELLED. The corn rows are about whether a
return EXISTS. You cannot reclassify a pulse that never came back.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_corduroy_vs_vendor_cut_9t.py
Writes:
    data/9t/results/nonground_classification/corduroy_vs_vendor_cut_9t.json
    data/9t/results/nonground_classification/cut_returns_and_voids_9t_5m.npz
    docs/presentation/figures_30to45min/v6/corduroy_vs_vendor_cut_9t.png
    docs/presentation/figures_30to45min/v6/void_rate_vs_scan_angle_9t.png
"""
from __future__ import annotations

import json
from pathlib import Path

import laspy
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
RG = ROOT / "data/9t/results/recovered_ground_9t"
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUTJ = (ROOT / "data/9t/results/nonground_classification"
        / "corduroy_vs_vendor_cut_9t.json")
FIG = ROOT / "docs/presentation/figures_30to45min/v6"

#: The CHM panel's window, from _build_derivative_panel.py.
CX, CY, SIDE, RES = 621359.6, 4594467.4, 300.0, 0.5

#: Venango 2020-03, from scan_angle_cliff_by_acquisition_all_tiles.csv. The
#: vendor stopped calling ground here; the scanner recorded to about 19.8.
CUT_DEG = 18.0

#: LAS 1.4 point formats 6+ store scan angle in 0.006 degree units. Reading the
#: raw field as degrees gives -1234 for what is actually -7.4, which looks like
#: a corrupt file rather than a unit.
SCALE = 0.006


def read(path, b):
    with rasterio.open(path) as r:
        a = r.read(1, window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=np.nan).astype("float32")
    a[a < -1000.0] = np.nan
    return a


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)
    out = {"window_en": [CX, CY], "side_m": SIDE, "res_m": RES,
           "cut_deg": CUT_DEG}

    dsm = read(D05 / "dsm_9t_05.tif", b)
    void = ~np.isfinite(dsm)
    ny, nx = dsm.shape
    print(f"window {SIDE:.0f} m at {CX} E {CY} N")
    print(f"  DSM void {int(void.sum()):,} cells = {100*void.mean():.2f}%")

    # ---- 1. is this window anywhere near the cut? -----------------------
    X, Y, A, CL = [], [], [], []
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= b[0]) & (x < b[2]) & (y >= b[1]) & (y < b[3])
        if not m.any():
            continue
        X.append(x[m]); Y.append(y[m])
        A.append(np.asarray(las.scan_angle)[m].astype("float32") * SCALE)
        CL.append(np.asarray(las.classification)[m])
    x = np.concatenate(X); y = np.concatenate(Y)
    ang = np.abs(np.concatenate(A)); cl = np.concatenate(CL)

    q = np.percentile(ang, [0, 50, 95, 99, 100])
    n_past = int((ang >= CUT_DEG).sum())
    print("\n1. SCAN ANGLE IN THIS WINDOW")
    print(f"  |angle| min {q[0]:.2f}  median {q[1]:.2f}  p95 {q[2]:.2f}  "
          f"p99 {q[3]:.2f}  max {q[4]:.2f} deg")
    print(f"  returns at or past the {CUT_DEG:.0f} deg cut: {n_past:,} of "
          f"{len(ang):,}  ({100*n_past/len(ang):.3f}%)")
    print(f"  headroom to the cut: {CUT_DEG - q[4]:.1f} deg")
    out["angle"] = dict(min=float(q[0]), median=float(q[1]), p95=float(q[2]),
                        p99=float(q[3]), max=float(q[4]),
                        n_returns=int(len(ang)), n_past_cut=n_past)

    # ---- 2. is there anything in a void cell to recover? ----------------
    c = np.clip(((x - b[0]) / RES).astype(int), 0, nx - 1)
    r = np.clip(((b[3] - y) / RES).astype(int), 0, ny - 1)
    idx = r * nx + c
    n_all = np.bincount(idx, minlength=nx * ny).reshape(ny, nx)
    # class 1 = unclassified, which is where the cut returns were dumped
    n_un = np.bincount(idx[cl == 1], minlength=nx * ny).reshape(ny, nx)
    n_cut = np.bincount(idx[(cl == 1) & (ang >= CUT_DEG)],
                        minlength=nx * ny).reshape(ny, nx)
    print("\n2. WHAT IS IN A VOID CELL, BY CLASS")
    print(f"  void cells with any return at all      : "
          f"{int((n_all[void] > 0).sum()):,} of {int(void.sum()):,}  "
          f"({100*(n_all[void] > 0).mean():.2f}%)")
    print(f"  void cells with an unclassified return : "
          f"{int((n_un[void] > 0).sum()):,}  "
          f"({100*(n_un[void] > 0).mean():.2f}%)")
    print(f"  void cells holding a CUT return        : "
          f"{int((n_cut[void] > 0).sum()):,}  "
          f"({100*(n_cut[void] > 0).mean():.2f}%)  <- what recovery could fix")
    out["void_cells"] = dict(
        n=int(void.sum()),
        with_any_return=int((n_all[void] > 0).sum()),
        with_unclassified=int((n_un[void] > 0).sum()),
        with_cut_return=int((n_cut[void] > 0).sum()))

    # ---- 3. rebuild the CHM on both DEMs --------------------------------
    dem_v = read(RG / "dem_vendorground_9t_0p5m.tif", b)
    dem_r = read(RG / "dem_vendorplusrecovered_slope0p35_9t_0p5m.tif", b)
    chm_v, chm_r = dsm - dem_v, dsm - dem_r
    nv, nr_ = ~np.isfinite(chm_v), ~np.isfinite(chm_r)
    same = int((nv == nr_).sum())
    d = (chm_r - chm_v)[np.isfinite(chm_v) & np.isfinite(chm_r)]
    print("\n3. CHM ON THE VENDOR DEM vs THE RECOVERED DEM")
    print(f"  CHM NoData, vendor    {int(nv.sum()):,} cells "
          f"({100*nv.mean():.2f}%)")
    print(f"  CHM NoData, recovered {int(nr_.sum()):,} cells "
          f"({100*nr_.mean():.2f}%)")
    print(f"  masks identical in {100*same/nv.size:.2f}% of cells   "
          f"holes closed by recovery: {int(nv.sum()) - int(nr_.sum())}")
    if d.size:
        print(f"  where both exist, canopy height moves: median "
              f"{np.median(d):+.4f} m, p95 |{np.percentile(np.abs(d), 95):.3f}| m")
    out["chm"] = dict(
        nodata_vendor=int(nv.sum()), nodata_recovered=int(nr_.sum()),
        masks_identical_pct=float(100 * same / nv.size),
        holes_closed=int(nv.sum()) - int(nr_.sum()),
        dz_median=float(np.median(d)) if d.size else None,
        dz_p95_abs=float(np.percentile(np.abs(d), 95)) if d.size else None)

    OUTJ.parent.mkdir(parents=True, exist_ok=True)
    OUTJ.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---- 4. and at tile scale, do the two patterns overlap? -------------
    tile = tile_grids()
    ok = tile["n_all"] > 20
    frac = np.where(ok, tile["n_cut"] / np.maximum(tile["n_all"], 1), np.nan)
    vf = tile["void"]
    z, pz = ok & (tile["n_cut"] == 0), ok & (tile["n_cut"] > 0)
    r = float(np.corrcoef(frac[ok], vf[ok])[0, 1])
    print("\n4. THE WHOLE 4.5 km TILE, 5 m cells")
    print(f"  mean void fraction where NO return was cut  : {vf[z].mean():.4f}"
          f"   ({int(z.sum()):,} cells)")
    print(f"  mean void fraction where returns WERE cut   : {vf[pz].mean():.4f}"
          f"   ({int(pz.sum()):,} cells)")
    print(f"  correlation between cut fraction and void fraction: r = {r:+.3f}")
    print("  -> the corn rows are if anything LESS common where the cut bites")
    out["tile"] = dict(
        grid_m=float(tile["grid"]),
        void_where_none_cut=float(vf[z].mean()),
        void_where_cut=float(vf[pz].mean()),
        n_cells_none_cut=int(z.sum()), n_cells_cut=int(pz.sum()),
        pearson_r=r)

    # ---- 5. how the void rate runs with scan angle ----------------------
    prof = angle_profile(tile)
    print("\n5. VOID RATE ACROSS THE SWATH")
    for a0, a1, pct, n in prof:
        print(f"  {a0:2.0f}-{a1:2.0f} deg  void {pct:5.2f}%   ({n:,} cells)")
    # Why it collapses: check it, do not assert it. Overlap is the only thing
    # that can fill a gap one pass left, so count distinct flight lines.
    nl, vf2, mg = tile["n_lines"], tile["void"], tile["mang"]
    one = np.isfinite(mg) & (nl == 1)
    two = np.isfinite(mg) & (nl >= 2)
    print(f"  seen by ONE flight line : {int(one.sum()):>7,} cells  "
          f"void {100*vf2[one].mean():.2f}%  mean |angle| {np.nanmean(mg[one]):.1f} deg")
    print(f"  seen by TWO or more     : {int(two.sum()):>7,} cells  "
          f"void {100*vf2[two].mean():.2f}%  mean |angle| {np.nanmean(mg[two]):.1f} deg")
    for a0, a1 in ((0, 8), (8, 14), (14, 18), (18, 25)):
        k = np.isfinite(mg) & (mg >= a0) & (mg < a1)
        if int(k.sum()) < 500:
            continue
        print(f"    {a0:2d}-{a1:2d} deg: {100*(nl[k] >= 2).mean():5.1f}% of "
              f"cells see 2+ lines, void {100*vf2[k].mean():.2f}%")
    print("  -> overlap switches on at 14 deg and the dropout collapses there.")
    print("     The vendor's 18 deg cut sits inside that overlap, which is why")
    print("     the two problems never touch the same ground.")
    out["overlap"] = dict(
        void_one_line=float(vf2[one].mean()), n_one_line=int(one.sum()),
        void_two_plus=float(vf2[two].mean()), n_two_plus=int(two.sum()))
    out["angle_profile"] = [dict(lo=a0, hi=a1, void_pct=pct, n_cells=n)
                            for a0, a1, pct, n in prof]
    OUTJ.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---- 6. the figures ---------------------------------------------------
    figure(b, void, ang, x, y, dsm, out, tile, frac)
    figure_profile(prof, out)

    print("\nVERDICT")
    print(f"  the cut bites at {CUT_DEG:.0f} deg; this window never exceeds "
          f"{q[4]:.1f} deg, so not one return here was cut")
    print(f"  {100*(n_cut[void] > 0).mean():.2f}% of void cells hold a cut "
          f"return, so there is nothing for recovery to put back")
    print(f"  recovery closes {int(nv.sum()) - int(nr_.sum())} of the CHM's "
          f"{int(nv.sum()):,} holes")
    print(f"\n  {OUTJ}")
    return 0


#: Full 9t extent, and the cell size the tile-scale panels are binned at. 5 m
#: is deliberate: the corn rows are 3 m apart, so a 5 m cell cannot resolve an
#: individual stripe and the panel shows WHERE the dropout field is rather than
#: redrawing the stripes at a size nobody can see.
TILE_B = (619500.0, 4593000.0, 624000.0, 4597500.0)
TILE_G = 5.0
TILE_NPZ = (ROOT / "data/9t/results/nonground_classification"
            / "cut_returns_and_voids_9t_5m.npz")


def tile_grids():
    """Cut-return density and DSM void fraction over the whole tile.

    Cached, because it decompresses nine LAZ files -- about 85 million returns
    -- and nothing in it changes unless the delivery does.
    """
    if TILE_NPZ.exists():
        # `with`, because np.load on an .npz keeps the zip handle open and
        # Windows will not let the stale cache be unlinked while it is.
        with np.load(TILE_NPZ) as d:
            if "n_lines" in d:
                return dict(n_all=d["n_all"], n_cut=d["n_cut"],
                            void=d["void"], mang=d["mang"],
                            n_lines=d["n_lines"],
                            bounds=tuple(d["bounds"]), grid=float(d["grid"]))
        # an older cache, written before these fields existed
        TILE_NPZ.unlink()

    nx = int((TILE_B[2] - TILE_B[0]) / TILE_G)
    ny = int((TILE_B[3] - TILE_B[1]) / TILE_G)
    n_all = np.zeros(ny * nx, np.int64)
    n_cut = np.zeros(ny * nx, np.int64)
    a_sum = np.zeros(ny * nx)
    pairs = []          # unique (cell, point_source_id), for the overlap count

    # The same tile can sit in westernpa/ and in westernpa/OTHER_DATA/. Key by
    # filename so it is counted once; a doubled tile would halve every fraction
    # in the panel without changing anything that looks wrong.
    seen, files = set(), []
    for d_ in ("data/_source/lidar/westernpa",
               "data/_source/lidar/westernpa/OTHER_DATA"):
        for f in sorted((ROOT / d_).glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            seen.add(f.name)
            files.append(f)

    for f in files:
        with laspy.open(f) as rd:
            lo, hi = rd.header.mins, rd.header.maxs
        if (lo[0] > TILE_B[2] or hi[0] < TILE_B[0]
                or lo[1] > TILE_B[3] or hi[1] < TILE_B[1]):
            continue
        las = laspy.read(f)
        px, py = np.asarray(las.x), np.asarray(las.y)
        m = ((px >= TILE_B[0]) & (px < TILE_B[2])
             & (py >= TILE_B[1]) & (py < TILE_B[3]))
        if not m.any():
            continue
        px, py = px[m], py[m]
        a = np.abs(np.asarray(las.scan_angle)[m].astype("float32") * SCALE)
        c = np.clip(((px - TILE_B[0]) / TILE_G).astype(int), 0, nx - 1)
        r = np.clip(((TILE_B[3] - py) / TILE_G).astype(int), 0, ny - 1)
        i = r * nx + c
        n_all += np.bincount(i, minlength=nx * ny)
        n_cut += np.bincount(i[a >= CUT_DEG], minlength=nx * ny)
        a_sum += np.bincount(i, weights=a, minlength=nx * ny)
        ps = np.asarray(las.point_source_id)[m].astype(np.int64)
        pairs.append(np.unique(i.astype(np.int64) * 100000 + ps))
        print(f"    {f.name}: {int(m.sum()):,} pts, "
              f"{int((a >= CUT_DEG).sum()):,} past the cut")

    with rasterio.open(D05 / "dsm_9t_05.tif") as rr:
        dsm = rr.read(1, window=from_bounds(*TILE_B, transform=rr.transform),
                      boundless=True, fill_value=np.nan).astype("float32")
    dsm[dsm < -1000.0] = np.nan
    v = (~np.isfinite(dsm)).astype("float32")
    k = int(TILE_G / 0.5)
    vy, vx = v.shape
    v = v[:vy // k * k, :vx // k * k].reshape(vy // k, k, vx // k, k).mean((1, 3))

    n_all = n_all.reshape(ny, nx)
    n_cut = n_cut.reshape(ny, nx)
    mang = np.where(n_all > 20, a_sum.reshape(ny, nx) / np.maximum(n_all, 1),
                    np.nan)
    # How many distinct flight lines see each cell. Two lines overlapping is
    # the only thing that can fill a gap the other one left.
    u = np.unique(np.concatenate(pairs))
    n_lines = np.bincount(u // 100000, minlength=nx * ny).reshape(ny, nx)
    np.savez_compressed(TILE_NPZ, n_all=n_all, n_cut=n_cut, void=v, mang=mang,
                        n_lines=n_lines, bounds=np.array(TILE_B),
                        grid=TILE_G, cut=CUT_DEG)
    return dict(n_all=n_all, n_cut=n_cut, void=v, mang=mang, n_lines=n_lines,
                bounds=TILE_B, grid=TILE_G)


def angle_profile(tile, edges=(0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 25)):
    """Void rate against mean |scan angle| per 5 m cell."""
    m_, v = tile["mang"], tile["void"]
    rows = []
    for a0, a1 in zip(edges[:-1], edges[1:]):
        k = np.isfinite(m_) & (m_ >= a0) & (m_ < a1)
        if int(k.sum()) < 200:
            continue
        rows.append((float(a0), float(a1), float(100 * v[k].mean()),
                     int(k.sum())))
    return rows


def figure_profile(prof, out):
    """One idea per figure: where across the swath the dropout actually is."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    C_VOID, C_CUT = "#D97706", "#1F5FA8"
    INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"

    mid = [(a0 + a1) / 2 for a0, a1, _, _ in prof]
    pct = [p for _, _, p, _ in prof]
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    ax.axvspan(CUT_DEG, 25, color=C_CUT, alpha=0.10, zorder=1)
    ax.text(CUT_DEG + 0.25, max(pct) * 0.94,
            f"past {CUT_DEG:.0f}\u00b0 the vendor\nstopped calling ground",
            fontsize=12, color=C_CUT, fontweight="bold", va="top")
    ax.axvline(CUT_DEG, color=C_CUT, lw=2, zorder=2)

    ax.plot(mid, pct, "-o", color=C_VOID, lw=2.6, ms=7, zorder=4)
    top = int(np.argmax(pct))
    ax.annotate(f"worst here — {pct[top]:.1f}% of cells empty",
                xy=(mid[top], pct[top]), xytext=(mid[top] - 5.4, pct[top] + 0.5),
                fontsize=12.5, fontweight="bold", color=C_VOID,
                arrowprops=dict(arrowstyle="->", color=C_VOID, lw=1.6))
    ax.annotate("from 14° out, the next flight line\noverlaps and fills the gaps",
                xy=(mid[-3], pct[-3]), xytext=(mid[-3] - 7.2, pct[top] * 0.45),
                fontsize=12, color=MUTED, ha="center",
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.4))

    ax.set_xlabel("mean scan angle off nadir, degrees", fontsize=12.5,
                  color=INK)
    ax.set_ylabel("cells with no return at all, %", fontsize=12.5, color=INK)
    ax.set_title("The dropout is worst two thirds of the way out, "
                 "and gone by the cut",
                 loc="left", fontsize=16, fontweight="bold", color=INK)
    ax.set_xlim(0, 25)
    ax.set_ylim(0, max(pct) * 1.25)
    ax.grid(axis="y", color="#dcdcd6", lw=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_edgecolor("#c8c8c0")
    fig.tight_layout()
    p = FIG / "void_rate_vs_scan_angle_9t.png"
    fig.savefig(p, dpi=170, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")


def figure(b, void, ang, x, y, dsm, out, tile, frac):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle

    #: From the project's validated lost/found palette. There is no green in
    #: this figure, so the red/green prohibition is not the binding constraint;
    #: the binding one is that the two stripe patterns must stay separable, and
    #: #1F5FA8 against #D97706 is the pair already validated at dE 21.1 deutan,
    #: 22.6 normal. Each also carries a second encoding -- they never appear in
    #: the same panel, and each panel says in words what it holds.
    C_VOID = "#D97706"      # the corn rows -- no return at all
    C_CUT = "#1F5FA8"       # returns past the vendor's cut
    INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"

    ny, nx = void.shape
    fig, axes = plt.subplots(2, 2, figsize=(13.8, 12.4))
    fig.patch.set_facecolor(PAPER)

    # NaN must not be left to the axes facecolor. On a black-to-white ramp that
    # is brighter than vmax, so a hole renders as the tallest thing in the
    # panel -- the exact bug that made the corn rows look like canopy in the
    # first place. Paint it a mid neutral and let the overlay do the talking.
    base = plt.get_cmap("gray").with_extremes(bad="#9aa0a6")
    vlo, vhi = np.nanpercentile(dsm, 2), np.nanpercentile(dsm, 98)
    ext = (b[0], b[2], b[1], b[3])

    # --- top left: the window, corn rows ---------------------------------
    ax = axes[0][0]
    ax.imshow(np.ma.masked_invalid(dsm), extent=ext, origin="upper",
              cmap=base, vmin=vlo, vmax=vhi, interpolation="nearest")
    ov = np.zeros((ny, nx, 4))
    ov[void] = matplotlib.colors.to_rgba(C_VOID)
    ax.imshow(ov, extent=ext, origin="upper", interpolation="nearest")
    ax.set_title("300 m window — cells with no return at all",
                 loc="left", fontsize=14, fontweight="bold", color=INK)
    ax.set_xlabel(f"{out['void_cells']['n']:,} cells, 3.00 m apart, "
                  "running across-track", fontsize=11.5, color=MUTED)

    # --- top right: the window, cut returns ------------------------------
    ax = axes[0][1]
    ax.imshow(np.ma.masked_invalid(dsm), extent=ext, origin="upper",
              cmap=base, vmin=vlo, vmax=vhi, interpolation="nearest")
    past = ang >= CUT_DEG
    if past.any():
        ax.scatter(x[past], y[past], s=1, c=C_CUT, linewidths=0)
        sub = f"{int(past.sum()):,} returns past the cut"
    else:
        # An empty overlay and a forgotten overlay look identical. Say which.
        ax.text(0.5, 0.5, f"not one return in this window\nreaches the "
                          f"{CUT_DEG:.0f}\u00b0 cut\n\nthe steepest here is "
                          f"{out['angle']['max']:.1f}\u00b0",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=15, fontweight="bold", color=C_CUT,
                bbox=dict(boxstyle="round,pad=0.7", facecolor="#ffffff",
                          edgecolor=C_CUT, linewidth=1.5))
        sub = "nothing to draw, which is the finding"
    ax.set_title(f"300 m window — returns past the {CUT_DEG:.0f}° cut",
                 loc="left", fontsize=14, fontweight="bold", color=INK)
    ax.set_xlabel(sub, fontsize=11.5, color=MUTED)

    # --- bottom row: the whole tile --------------------------------------
    tb = tile["bounds"]
    text = (tb[0], tb[2], tb[1], tb[3])
    win = Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                    fill=False, edgecolor=INK, linewidth=2.0, zorder=6)

    ax = axes[1][0]
    ax.set_facecolor("#ffffff")
    ax.imshow(np.where(tile["n_all"] > 20, frac, np.nan), extent=text,
              origin="upper", cmap=_ramp(C_CUT), vmin=0, vmax=0.6,
              interpolation="nearest")
    ax.add_patch(win)
    ax.set_title("Whole tile — share of returns past the cut",
                 loc="left", fontsize=14, fontweight="bold", color=INK)
    ax.set_xlabel("bands parallel to the flight lines, at the swath edges "
                  "— black box is the window above",
                  fontsize=11.5, color=MUTED)

    ax = axes[1][1]
    ax.set_facecolor("#ffffff")
    ax.imshow(np.where(tile["void"] > 0, tile["void"], np.nan), extent=text,
              origin="upper", cmap=_ramp(C_VOID), vmin=0, vmax=0.25,
              interpolation="nearest")
    ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                           fill=False, edgecolor=INK, linewidth=2.0, zorder=6))
    ax.set_title("Whole tile — share of cells with no return",
                 loc="left", fontsize=14, fontweight="bold", color=INK)
    t = out["tile"]
    ax.set_xlabel(
        f"{t['void_where_cut']:.3f} where returns were cut, "
        f"{t['void_where_none_cut']:.3f} where none were  —  r = "
        f"{t['pearson_r']:+.3f}", fontsize=11.5, color=MUTED)

    for row in axes:
        for ax in row:
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_edgecolor("#c8c8c0")

    fig.legend(handles=[
        Patch(facecolor=C_VOID, edgecolor="none",
              label="no return of any kind  —  nothing to recover"),
        Patch(facecolor=C_CUT, edgecolor="none",
              label="return exists, was mislabelled  —  recoverable")],
        loc="lower center", ncol=2, frameon=False, fontsize=13)
    fig.suptitle("Two different problems that both make stripes, and they do "
                 "not overlap",
                 x=0.012, ha="left", fontsize=18, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.045, 1, 0.965))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "corduroy_vs_vendor_cut_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")


def _ramp(hexcol):
    """White-to-colour ramp, so zero reads as paper rather than as a value."""
    import matplotlib
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        "r", ["#ffffff", hexcol]).with_extremes(bad="#ffffff")


if __name__ == "__main__":
    raise SystemExit(main())

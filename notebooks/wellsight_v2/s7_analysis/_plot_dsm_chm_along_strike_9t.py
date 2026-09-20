"""DSM and DEM on one axis, CHM below. Along the dropout row.

Row is found by sweeping across the 79 deg strike and taking the emptiest line.
Buffer 1 m, and a position is left blank when more than half the buffer has no
value, so gaps read as gaps instead of being averaged away.

Run:
    python notebooks/wellsight_v2/s7_analysis/_plot_dsm_chm_along_strike_9t.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
FIG = ROOT / "docs/presentation/figures_30to45min/2_terrain_derivatives"


def read_window(path, b):
    with rasterio.open(path) as r:
        w = from_bounds(*b, transform=r.transform)
        a = r.read(1, window=w, boundless=True,
                   fill_value=np.nan).astype("float32")
    a[a < -1000.0] = np.nan
    return a


def band(arrays, b, res, x0, y0, bearing, half_m, buf):
    th = np.radians(bearing)
    ux, uy = np.sin(th), np.cos(th)
    bx, by = -uy, ux
    offs = np.arange(-buf / 2, buf / 2 + res, res)
    s = np.arange(-half_m, half_m, res)
    st = [np.full((len(offs), len(s)), np.nan, np.float32) for _ in arrays]
    for i, o in enumerate(offs):
        X, Y = x0 + o * bx + s * ux, y0 + o * by + s * uy
        c = np.round((X - b[0]) / res - 0.5)
        r = np.round((b[3] - Y) / res - 0.5)
        for a, k in zip(arrays, st):
            ny, nx = a.shape
            ok = (c >= 0) & (c < nx) & (r >= 0) & (r < ny)
            ci = np.clip(c, 0, nx - 1).astype(int)
            ri = np.clip(r, 0, ny - 1).astype(int)
            v = a[ri, ci].astype(np.float32)
            v[~ok] = np.nan
            k[i] = v
    out, miss = [], np.isnan(st[0]).mean(axis=0)
    for k in st:
        f = np.isnan(k).mean(axis=0)
        with np.errstate(invalid="ignore"):
            m = np.nanmean(k, axis=0)
        m[f > 0.5] = np.nan
        out.append(m)
    return s, out, miss


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float,
                    default=[41.49264, -79.546127])
    ap.add_argument("--side", type=float, default=300.0)
    ap.add_argument("--res", type=float, default=0.5)
    ap.add_argument("--strike", type=float, default=79.0)
    ap.add_argument("--buffer-m", type=float, default=1.0)
    ap.add_argument("--half-m", type=float, default=55.0)
    ap.add_argument("--search-m", type=float, default=40.0)
    a = ap.parse_args()

    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    cx, cy = tr.transform(a.centre[1], a.centre[0])
    h = a.side / 2.0
    b = (cx - h, cy - h, cx + h, cy + h)

    chm = read_window(D05 / "chm_9t_05.tif", b)
    dem = read_window(D05 / "dem_9t_05.tif", b)
    dsm = read_window(D05 / "dsm_9t_05.tif", b)
    nod = ~np.isfinite(chm)
    rows, cols = np.where(nod)
    x0 = b[0] + (cols.mean() + 0.5) * a.res
    y0 = b[3] - (rows.mean() + 0.5) * a.res
    th = np.radians(a.strike)
    vx, vy = np.cos(th), -np.sin(th)

    best = None
    for off in np.arange(-a.search_m, a.search_m + 0.01, 0.25):
        _, _, miss = band([chm], b, a.res, x0 + off * vx, y0 + off * vy,
                          a.strike, a.half_m, a.buffer_m)
        sc = float(np.mean(miss > 0.5))
        if best is None or sc > best[0]:
            best = (sc, float(off))
    sc, off = best
    rx, ry = x0 + off * vx, y0 + off * vy
    s, (v_dem, v_dsm, v_chm), miss = band([dem, dsm, chm], b, a.res, rx, ry,
                                          a.strike, a.half_m, a.buffer_m)
    print(f"row at {rx:.1f} E {ry:.1f} N, strike {a.strike} deg, "
          f"{100*sc:.0f}% of the length empty")

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
    a1.plot(s, v_dsm, color="#2a78d6", linewidth=1.8, label="DSM")
    a1.plot(s, v_dem, color="#eb6834", linewidth=1.8, label="DEM")
    a1.set_ylabel("elevation, m")
    a1.grid(color="#d9dbd6", linewidth=0.7)
    a1.legend(loc="upper right")
    a2.plot(s, v_chm, color="#4a3aa7", linewidth=1.8)
    a2.set_ylabel("CHM, m")
    a2.set_xlabel("distance along the strike, m")
    a2.grid(color="#d9dbd6", linewidth=0.7)
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / (f"dsm_dem_chm_along_strike_b{a.strike:.0f}"
                f"_buf{a.buffer_m/2:.1f}mside_300m_9t.png".replace(".", "p", 1)
               if False else
               f"dsm_dem_chm_along_strike_b{a.strike:.0f}_"
               f"buf{str(a.buffer_m/2).replace('.','p')}mside_300m_9t.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

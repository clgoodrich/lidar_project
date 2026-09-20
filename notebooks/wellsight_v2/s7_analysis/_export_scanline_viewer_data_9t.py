"""Export a small 3D scene -- returns, DSM and DEM -- for the HTML viewer.

Covers the CHM scan-line dropout area on 9t, so the gaps can be inspected from
any angle instead of through one profile at a time.

The DSM and DEM go out as Float32 grids with NaN preserved, because the NaN IS
the subject: the bright corduroy in `chm_300m_9t.png` is missing data, not tall
canopy, and a viewer that silently fills the holes would hide exactly what it is
meant to show.

Returns carry return_number / number_of_returns so the cloud can be coloured by
whether a pulse came back once or several times.

Everything is written as base64 Float32 / Uint8 into one .js file the page loads
as a plain script, since the Artifact CSP blocks fetch() to any host.

Run:
    python notebooks/wellsight_v2/s7_analysis/_export_scanline_viewer_data_9t.py
    ... --side 120 --max-points 400000
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUT = ROOT / "docs/presentation/viewers"

#: Centre of the dropout field, from _build_chm_nodata_cross_section_9t.py.
CX, CY = 621392.0, 4594510.0


def b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre-en", nargs=2, type=float, default=[CX, CY])
    ap.add_argument("--side", type=float, default=120.0)
    ap.add_argument("--res", type=float, default=0.5)
    ap.add_argument("--max-points", type=int, default=400000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    cx, cy = a.centre_en
    h = a.side / 2.0
    b = (cx - h, cy - h, cx + h, cy + h)
    print(f"window {a.side:.0f} m at {cx:.1f} E {cy:.1f} N")

    grids = {}
    for name, fn in (("dem", "dem_9t_05.tif"), ("dsm", "dsm_9t_05.tif"),
                     ("chm", "chm_9t_05.tif")):
        with rasterio.open(D05 / fn) as r:
            w = from_bounds(*b, transform=r.transform)
            g = r.read(1, window=w, boundless=True,
                       fill_value=np.nan).astype("float32")
        g[g < -1000.0] = np.nan
        grids[name] = g
        print(f"  {name}: {g.shape}  nan {100*np.isnan(g).mean():.2f}%")
    ny, nx = grids["dem"].shape

    import laspy
    X, Y, Z, RN, NR = [], [], [], [], []
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
        m = (x >= b[0]) & (x < b[2]) & (y >= b[1]) & (y < b[3])
        if not m.any():
            continue
        X.append(x[m]); Y.append(y[m]); Z.append(z[m])
        RN.append(np.asarray(las.return_number)[m].astype(np.uint8))
        NR.append(np.asarray(las.number_of_returns)[m].astype(np.uint8))
        print(f"  {f.name}: {int(m.sum()):,} returns")
    x = np.concatenate(X); y = np.concatenate(Y); z = np.concatenate(Z)
    rn = np.concatenate(RN); nr = np.concatenate(NR)

    if len(x) > a.max_points:
        rng = np.random.default_rng(a.seed)
        k = rng.choice(len(x), size=a.max_points, replace=False)
        k.sort()
        x, y, z, rn, nr = x[k], y[k], z[k], rn[k], nr[k]
        print(f"  subsampled to {len(x):,}")

    # local metres, origin at the window's SW corner, so float32 keeps precision
    px = (x - b[0]).astype("float32")
    py = (y - b[1]).astype("float32")
    zmin = float(np.nanmin(grids["dem"]))
    pz = (z - zmin).astype("float32")

    meta = dict(
        origin_en=[b[0], b[1]], side_m=a.side, res_m=a.res,
        nx=int(nx), ny=int(ny), z_base=zmin,
        n_points=int(len(px)),
        dem_nan_pct=float(100 * np.isnan(grids["dem"]).mean()),
        dsm_nan_pct=float(100 * np.isnan(grids["dsm"]).mean()),
        chm_nan_pct=float(100 * np.isnan(grids["chm"]).mean()),
        z_min=float(np.nanmin(pz)), z_max=float(np.nanmax(pz)),
        multi_return_pct=float(100 * np.mean(nr > 1)),
    )
    print("  " + json.dumps({k: (round(v, 2) if isinstance(v, float) else v)
                             for k, v in meta.items() if k != "origin_en"}))

    OUT.mkdir(parents=True, exist_ok=True)
    js = OUT / "scanline_scene_data.js"
    parts = [
        "window.SCENE = " + json.dumps(meta) + ";",
        'window.SCENE.px = "' + b64(px) + '";',
        'window.SCENE.py = "' + b64(py) + '";',
        'window.SCENE.pz = "' + b64(pz) + '";',
        'window.SCENE.rn = "' + b64(rn) + '";',
        'window.SCENE.nr = "' + b64(nr) + '";',
        'window.SCENE.dem = "' + b64((grids["dem"] - zmin).astype("float32")) + '";',
        'window.SCENE.dsm = "' + b64((grids["dsm"] - zmin).astype("float32")) + '";',
        'window.SCENE.chm = "' + b64(grids["chm"].astype("float32")) + '";',
    ]
    js.write_text("\n".join(parts), encoding="utf-8")
    print(f"\n  {js}  ({js.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

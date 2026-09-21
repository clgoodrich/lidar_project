"""Which derivative layers carry the scan-line stripes, and how strongly.

WHY
---
The corn rows are visible on the RRIM. The RRIM is built from slope and the two
openness rasters, which are built from the DEM -- and the DEM has NO voids at
all, because a Delaunay TIN spans every gap. So the stripes cannot be arriving
as missing data. They must be arriving as SHAPE: the TIN bridges a gap between
two scan lines with a flat triangle, and a flat triangle among curved ground is
a real, measurable feature that slope and openness will happily report.

That predicts the artefact survives into every DEM derivative, and that it is
not fixed by anything that only fills holes.

HOW IT IS MEASURED
------------------
Directional power at the scan-line bearing. For a candidate bearing, project
every cell onto the perpendicular and take the profile mean; ruled structure at
that bearing makes the profile oscillate, and the variance of its high-passed
form is the score. Comparing the score AT the scan-line bearing against the
median over all bearings gives a unitless ratio: 1.0 is no preferred direction,
higher means striping along that bearing.

Reported for each layer at 0.5 m and at 1 m, so the question "does coarsening
fix it" gets a number instead of an opinion.

DO NOT read a high ratio as "this layer is broken". Real terrain has grain too.
The comparison that matters is the SAME layer at two resolutions, and the
scan-line bearing against the median bearing in the same raster.

Run:
    python notebooks/wellsight_v2/s7_analysis/_stripe_strength_by_layer_9t.py
Writes:
    data/9t/results/nonground_classification/stripe_strength_by_layer_9t.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
OUT = (ROOT / "data/9t/results/nonground_classification"
       / "stripe_strength_by_layer_9t.json")

#: The corduroy window, from _build_derivative_panel.py.
CX, CY, SIDE = 621359.6, 4594467.4, 300.0
#: Scan-line bearing, measured off the ground point pattern in
#: _measure_scanner_geometry_9t.py. The corn rows lie along it.
SCAN_BRG = 78.0

LAYERS = {
    "0.5 m": (ROOT / "data/9t/derived/05", "05",
              ["dem", "dsm", "chm", "slope", "openness_pos", "openness_neg",
               "lrm_5", "tpi_05", "hillshade"]),
    "1 m": (ROOT / "data/9t/derived/1m", "1m",
            ["dem", "slope", "openness_pos", "openness_neg", "lrm_5",
             "tpi_05", "hillshade"]),
}


def read(path, b):
    with rasterio.open(path) as r:
        a = r.read(1, window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=np.nan).astype("float32")
        nod = r.nodata
    if nod is not None:
        a[a == nod] = np.nan
    a[a < -1e6] = np.nan
    return a


def directional_power(a, brg_deg, res):
    """Variance of the high-passed profile taken perpendicular to `brg_deg`."""
    ny, nx = a.shape
    yy, xx = np.mgrid[0:ny, 0:nx].astype("float32")
    # image row increases southward, so north is -row
    r = np.radians(brg_deg)
    perp = (xx * np.cos(r) + yy * np.sin(r)) * res
    fin = np.isfinite(a)
    if fin.sum() < 1000:
        return np.nan
    v = a[fin] - np.nanmean(a[fin])
    p = perp[fin]
    step = res
    bins = np.arange(p.min(), p.max() + step, step)
    idx = np.clip(((p - bins[0]) / step).astype(int), 0, len(bins) - 2)
    cnt = np.bincount(idx, minlength=len(bins) - 1)
    tot = np.bincount(idx, weights=v, minlength=len(bins) - 1)
    ok = cnt > 20
    if ok.sum() < 40:
        return np.nan
    prof = np.where(ok, tot / np.maximum(cnt, 1), np.nan)
    prof = prof[ok]
    # high-pass at about 8 m, well above the ~1 m line spacing and well below
    # any hillside the window contains
    w = max(3, int(round(8.0 / step)) | 1)
    hp = prof - np.convolve(prof, np.ones(w) / w, mode="same")
    edge = w
    hp = hp[edge:-edge] if len(hp) > 2 * edge + 10 else hp
    return float(np.var(hp))


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)
    brgs = np.arange(0, 180, 6.0)
    res_out = {"window": list(b), "scan_bearing": SCAN_BRG, "layers": {}}

    print(f"window {SIDE:.0f} m at {CX} E {CY} N, scan bearing {SCAN_BRG}°")
    print("\n  layer              res    ratio at the scan bearing")
    for label, (d, sfx, names) in LAYERS.items():
        for nm in names:
            p = d / f"{nm}_9t_{sfx}.tif"
            if not p.exists():
                continue
            with rasterio.open(p) as r:
                res = abs(r.transform.a)
            a = read(p, b)
            if not np.isfinite(a).any():
                continue
            scores = np.array([directional_power(a, bg, res) for bg in brgs])
            at = directional_power(a, SCAN_BRG, res)
            med = float(np.nanmedian(scores))
            ratio = float(at / med) if med > 0 else float("nan")
            res_out["layers"].setdefault(nm, {})[label] = dict(
                ratio=ratio, power_at_scan=at, power_median=med,
                void_pct=float(100 * np.mean(~np.isfinite(a))))
            flag = "  <-- striped" if ratio > 2.0 else ""
            print(f"  {nm:<18} {label:<6} {ratio:6.2f}{flag}")

    print("\n  ratio 1.0 means no preferred direction; higher means the layer")
    print("  oscillates along the scan-line bearing more than along others.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res_out, indent=2), encoding="utf-8")
    print(f"\n  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

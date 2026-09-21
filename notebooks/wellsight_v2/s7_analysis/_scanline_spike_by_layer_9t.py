"""How strong is the scan-line spike in each layer, and does 1 m remove it?

THE CORRECTION THIS EXISTS TO MAKE
----------------------------------
`_stripe_strength_by_layer_9t.py` reported the corn rows as a DSM-only problem
that never reaches the RRIM. That was wrong, and the way it was wrong is worth
keeping.

It scored each layer by ARGMAX over bearing. The RRIM's argmax sits at 117 to
147 degrees, so the answer came back "no corn rows here". Plot the whole curve
and there is a second feature the argmax never sees: a NARROW SPIKE at 78 to 80
degrees, exactly the corn-row bearing, reaching about 3x the baseline. It is
real, it was visible to the eye all along, and reporting only the largest peak
hid it.

NARROW AND BROAD MEAN DIFFERENT THINGS
--------------------------------------
The 128-degree feature is a broad hump tens of degrees wide. That is terrain
fabric -- the hillside and its drainage running north-west to south-east -- and
it is supposed to be there.

The 78-degree feature is a spike a few degrees wide. Regular ruled structure at
one exact bearing is what a scanner leaves behind, not what a landscape does.
Width, not height, is what separates the artefact from the ground.

So this measures PROMINENCE AT THE SCAN BEARING rather than the global peak:
the highest power within a few degrees of 78, divided by the local baseline 15
to 45 degrees away on either side. A layer with no scan-line artefact scores
about 1.

Run:
    python notebooks/wellsight_v2/s7_analysis/_scanline_spike_by_layer_9t.py
Writes:
    data/9t/results/nonground_classification/scanline_spike_by_layer_9t.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
OUT = (ROOT / "data/9t/results/nonground_classification"
       / "scanline_spike_by_layer_9t.json")

SCAN_BRG = 78.0
HALF = 6.0          # deg, how far off 78 the spike may sit
BASE_LO, BASE_HI = 15.0, 45.0   # deg, where the local baseline is taken
HP_M = 8.0

#: Windows: the user's spot, the corn-row panel, and the worst DSM void.
WINDOWS = {
    "user spot": (623822.4 - 45, 4594948.6 - 45, 623822.4 + 45, 4594948.6 + 45),
    "corn-row panel": (621209.6, 4594317.4, 621509.6, 4594617.4),
    "worst DSM void": (621520.0, 4593725.0, 621820.0, 4594025.0),
}

LAYERS = [
    ("dsm", "05", "data/9t/derived/05/dsm_9t_05.tif", False),
    ("chm", "05", "data/9t/derived/05/chm_9t_05.tif", False),
    ("dem", "05", "data/9t/derived/05/dem_9t_05.tif", False),
    ("dem", "1m", "data/9t/derived/1m/dem_9t_1m.tif", False),
    ("slope", "05", "data/9t/derived/05/slope_9t_05.tif", False),
    ("slope", "1m", "data/9t/derived/1m/slope_9t_1m.tif", False),
    ("openness_neg", "05", "data/9t/derived/05/openness_neg_9t_05.tif", False),
    ("openness_neg", "1m", "data/9t/derived/1m/openness_neg_9t_1m.tif", False),
    ("lrm_5", "05", "data/9t/derived/05/lrm_5_9t_05.tif", False),
    ("lrm_5", "1m", "data/9t/derived/1m/lrm_5_9t_1m.tif", False),
    ("hillshade", "05", "data/9t/derived/05/hillshade_9t_05.tif", False),
    ("hillshade", "1m", "data/9t/derived/1m/hillshade_9t_1m.tif", False),
    ("rrim", "05", "data/9t/derived/05/rrim_openness_9t_05.tif", True),
    ("rrim", "1m", "data/9t/derived/1m/rrim_openness_9t_1m.tif", True),
]


def read(path, b, rgb):
    with rasterio.open(path) as r:
        a = r.read(window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=np.nan).astype("float32")
        res = abs(r.transform.a)
        nod = r.nodata
    if rgb:
        g = (0.299 * a[0] + 0.587 * a[1] + 0.114 * a[2]).astype("float32")
        return g, res
    g = a[0]
    if nod is not None:
        g[g == nod] = np.nan
    g[g < -1e6] = np.nan
    return g, res


def power(a, brg, res):
    ny, nx = a.shape
    yy, xx = np.mgrid[0:ny, 0:nx].astype("float32")
    r = np.radians(brg)
    perp = (xx * np.cos(r) + yy * np.sin(r)) * res
    fin = np.isfinite(a)
    if fin.sum() < 1500:
        return np.nan
    v = a[fin] - np.nanmean(a[fin])
    p = perp[fin]
    bins = np.arange(p.min(), p.max() + res, res)
    idx = np.clip(((p - bins[0]) / res).astype(int), 0, len(bins) - 2)
    cnt = np.bincount(idx, minlength=len(bins) - 1)
    tot = np.bincount(idx, weights=v, minlength=len(bins) - 1)
    ok = cnt > 15
    if ok.sum() < 40:
        return np.nan
    prof = (tot / np.maximum(cnt, 1))[ok]
    w = max(3, int(round(HP_M / res)) | 1)
    hp = prof - np.convolve(prof, np.ones(w) / w, mode="same")
    if len(hp) > 2 * w + 10:
        hp = hp[w:-w]
    return float(np.var(hp))


def spike(a, res):
    """Prominence of the scan-bearing spike over its own local baseline."""
    brgs = np.arange(0.0, 180.0, 1.0)
    sc = np.array([power(a, b, res) for b in brgs])
    if not np.isfinite(sc).any():
        return np.nan, np.nan
    d = np.minimum(np.abs(brgs - SCAN_BRG), 180 - np.abs(brgs - SCAN_BRG))
    near = d <= HALF
    base = (d >= BASE_LO) & (d <= BASE_HI)
    if not near.any() or not base.any():
        return np.nan, np.nan
    b_ = np.nanmedian(sc[base])
    if not np.isfinite(b_) or b_ <= 0:
        return np.nan, np.nan
    return float(np.nanmax(sc[near]) / b_), float(brgs[near][
        int(np.nanargmax(sc[near]))])


def main() -> int:
    res = {"scan_bearing": SCAN_BRG, "half_deg": HALF,
           "baseline_deg": [BASE_LO, BASE_HI], "windows": {}}
    for wname, b in WINDOWS.items():
        print(f"\n{wname}")
        print("  layer            0.5 m      1 m      change")
        rows = {}
        for nm, sfx, rel, rgb in LAYERS:
            p = ROOT / rel
            if not p.exists():
                continue
            a, r_ = read(p, b, rgb)
            if not np.isfinite(a).any():
                continue
            s, at = spike(a, r_)
            rows.setdefault(nm, {})[sfx] = dict(prominence=s, peak_at=at)
        for nm, d in rows.items():
            a5 = d.get("05", {}).get("prominence", float("nan"))
            a1 = d.get("1m", {}).get("prominence", float("nan"))
            if np.isfinite(a5) and np.isfinite(a1):
                ch = f"{a1 - a5:+.2f}"
            else:
                ch = "--"
            f1 = f"{a1:6.2f}" if np.isfinite(a1) else "    --"
            flag = "  <-- striped" if max(
                [v for v in (a5, a1) if np.isfinite(v)] or [0]) > 1.8 else ""
            print(f"  {nm:<15} {a5:6.2f}   {f1}   {ch}{flag}")
        res["windows"][wname] = rows

    print("\n  prominence 1.0 means no spike at the scan bearing at all.")
    print("  This is measured against the LOCAL baseline 15-45 deg away, so a")
    print("  broad terrain hump somewhere else in the curve cannot inflate it.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\n  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

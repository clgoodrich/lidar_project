"""Which way does the RRIM's grain actually run? Measured, and drawn on top.

THE DISAGREEMENT THIS SETTLES
-----------------------------
Looking at the RRIM, the streaks read as running the same way as the corn rows,
slanted ENE or WNW. A coarse bearing sweep put the grain at 120 to 168 degrees
instead, which is a different family of lines entirely -- the corn rows are at
78. Those two readings cannot both be right, and the earlier sweep is the weaker
evidence: three hand-picked windows at 3 or 6 degree steps, with the peak taken
from a single noisy curve.

So this does three things the earlier test did not.

1. SWEEPS AT 1 DEGREE over MANY windows tiled across the whole 9t square, and
   reports the distribution of peak bearings rather than one number. A direction
   that is real shows up in most windows; one that is noise moves around.

2. REPORTS THE TOP TWO PEAKS per window, separated by at least 20 degrees. If
   there are two families of lines -- and a dual-channel scanner is a reason to
   expect two -- one number per window can only ever find one of them.

3. DRAWS THE CANDIDATE BEARINGS ON THE IMAGE. A crop at native resolution with
   reference lines at each candidate laid over it, so the question "which of
   these do the streaks follow" can be answered by eye instead of by argument.

BEARING CONVENTION, CHECKED RATHER THAN ASSUMED
-----------------------------------------------
Bearings are degrees clockwise from north, and a bearing names the direction the
LINES run, not the direction across them. Image rows increase southward, so a
line of map bearing b runs along (sin b, -cos b) in (col, row) and the
perpendicular this projects onto is (cos b, sin b). The convention is verified
against the DSM, whose corn rows an independent method put at 79 degrees on the
NoData mask: the sweep must return 78 for the DSM or it is measuring the wrong
axis and nothing else here can be trusted.

Run:
    python notebooks/wellsight_v2/s7_analysis/_rrim_grain_bearing_9t.py
Writes:
    data/9t/results/nonground_classification/rrim_grain_bearing_9t.json
    docs/presentation/figures_30to45min/v6/rrim_grain_bearing_9t.png
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "docs/presentation/figures_30to45min/v6"
OUT = (ROOT / "data/9t/results/nonground_classification"
       / "rrim_grain_bearing_9t.json")

RRIM = ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif"
DSM = ROOT / "data/9t/derived/05/dsm_9t_05.tif"
TILE = (619500.0, 4593000.0, 624000.0, 4597500.0)

WIN = 250.0        # m, each sample window
STRIDE = 450.0     # m between window centres
HP_M = 8.0         # high-pass wavelength, well above the ~1 m line spacing

#: Candidates to draw on the crop. Corn rows from the NoData mask; across-track
#: and the two cross-fire channels from the flight geometry and the datasheet.
CANDIDATES = [
    (78.0, "#D97706", "scan lines / corn rows"),
    (85.8, "#8E959B", "across-track"),
    (120.0, "#1F5FA8", "what the sweep found"),
]
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read(path, b, rgb=False):
    with rasterio.open(path) as r:
        a = r.read(window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=np.nan).astype("float32")
        res = abs(r.transform.a)
        nod = r.nodata
    if rgb:
        return np.moveaxis(np.nan_to_num(a[:3], nan=255).astype("uint8"),
                           0, -1), res
    a = a[0]
    if nod is not None:
        a[a == nod] = np.nan
    a[a < -1e6] = np.nan
    return a, res


def power(a, brg, res):
    ny, nx = a.shape
    yy, xx = np.mgrid[0:ny, 0:nx].astype("float32")
    r = np.radians(brg)
    perp = (xx * np.cos(r) + yy * np.sin(r)) * res
    fin = np.isfinite(a)
    if fin.sum() < 2000:
        return np.nan
    v = a[fin] - np.nanmean(a[fin])
    p = perp[fin]
    bins = np.arange(p.min(), p.max() + res, res)
    idx = np.clip(((p - bins[0]) / res).astype(int), 0, len(bins) - 2)
    cnt = np.bincount(idx, minlength=len(bins) - 1)
    tot = np.bincount(idx, weights=v, minlength=len(bins) - 1)
    ok = cnt > 20
    if ok.sum() < 40:
        return np.nan
    prof = (tot / np.maximum(cnt, 1))[ok]
    w = max(3, int(round(HP_M / res)) | 1)
    hp = prof - np.convolve(prof, np.ones(w) / w, mode="same")
    if len(hp) > 2 * w + 10:
        hp = hp[w:-w]
    return float(np.var(hp))


def two_peaks(scores, brgs, sep=20.0):
    out = []
    for i in np.argsort(scores)[::-1]:
        if not np.isfinite(scores[i]):
            continue
        b = brgs[i]
        if all(min(abs(b - q), 180 - abs(b - q)) > sep for q, _ in out):
            out.append((float(b), float(scores[i])))
        if len(out) == 2:
            break
    return out


def sweep(path, rgb=False):
    brgs = np.arange(0.0, 180.0, 1.0)
    cx = np.arange(TILE[0] + WIN, TILE[2] - WIN, STRIDE)
    cy = np.arange(TILE[1] + WIN, TILE[3] - WIN, STRIDE)
    rows = []
    for x in cx:
        for y in cy:
            b = (x - WIN / 2, y - WIN / 2, x + WIN / 2, y + WIN / 2)
            a, res = read(path, b, rgb=rgb)
            if rgb:
                a = (0.299 * a[..., 0] + 0.587 * a[..., 1]
                     + 0.114 * a[..., 2]).astype("float32")
            if not np.isfinite(a).any():
                continue
            sc = np.array([power(a, bg, res) for bg in brgs])
            med = np.nanmedian(sc)
            if not np.isfinite(med) or med <= 0:
                continue
            pk = two_peaks(sc, brgs)
            if not pk:
                continue
            rows.append(dict(cx=float(x), cy=float(y),
                             peak1=pk[0][0], ratio1=pk[0][1] / med,
                             peak2=pk[1][0] if len(pk) > 1 else None,
                             ratio2=(pk[1][1] / med) if len(pk) > 1 else None))
    return rows


def circ_summary(vals, weights=None):
    """Mean and spread of axial (mod 180) bearings. A plain mean is wrong here:
    179 and 1 degree are two degrees apart, not 178."""
    a = np.radians(np.asarray(vals) * 2.0)
    w = np.ones_like(a) if weights is None else np.asarray(weights)
    s, c = np.sum(w * np.sin(a)), np.sum(w * np.cos(a))
    mean = (np.degrees(np.arctan2(s, c)) / 2.0) % 180.0
    R = np.hypot(s, c) / max(np.sum(w), 1e-9)
    return float(mean), float(R)


def main() -> int:
    res = {"window_m": WIN, "stride_m": STRIDE, "layers": {}}
    for name, path, rgb in (("DSM (control)", DSM, False),
                            ("RRIM", RRIM, True)):
        rows = sweep(path, rgb=rgb)
        p1 = [r["peak1"] for r in rows]
        w1 = [r["ratio1"] for r in rows]
        m, R = circ_summary(p1, w1)
        p2 = [r["peak2"] for r in rows if r["peak2"] is not None]
        m2, R2 = circ_summary(p2) if p2 else (float("nan"), 0.0)
        res["layers"][name] = dict(
            n_windows=len(rows), mean_peak1=m, concentration1=R,
            mean_peak2=m2, concentration2=R2,
            median_ratio1=float(np.median(w1)) if w1 else None)
        print(f"\n{name}: {len(rows)} windows")
        print(f"  dominant bearing  {m:6.1f} deg   concentration {R:.2f}   "
              f"median ratio {np.median(w1):.2f}")
        print(f"  second bearing    {m2:6.1f} deg   concentration {R2:.2f}")
        h, e = np.histogram(p1, bins=np.arange(0, 190, 10))
        print("  where the strongest peak lands, per 10 deg bin:")
        for i in range(len(h)):
            if h[i]:
                print(f"    {e[i]:3.0f}-{e[i+1]:3.0f}  " + "#" * h[i]
                      + f" {h[i]}")

    ctrl = res["layers"]["DSM (control)"]["mean_peak1"]
    ok = min(abs(ctrl - 78.0), 180 - abs(ctrl - 78.0)) < 12.0
    print(f"\n  CONVENTION CHECK: the DSM control lands at {ctrl:.1f} deg "
          f"against 78 expected -- {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("  Everything above is measuring the wrong axis. Stop here.")
    res["convention_check_pass"] = bool(ok)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    figure(res)
    print(f"\n  {OUT}")
    return 0


def figure(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    #: A tight crop, so individual streaks are resolvable rather than a texture.
    CROP = 120.0
    cx, cy = 621700.0, 4595150.0
    b = (cx - CROP / 2, cy - CROP / 2, cx + CROP / 2, cy + CROP / 2)
    img, r05 = read(RRIM, b, rgb=True)

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 7.2))
    fig.patch.set_facecolor(PAPER)

    for ax, overlay in zip(axes, (False, True)):
        ax.imshow(img, interpolation="nearest")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")
        if not overlay:
            ax.set_title("RRIM, 120 m at 0.5 m", loc="left", fontsize=14,
                         fontweight="bold", color=INK)
            continue
        ax.set_title("the same, with each candidate bearing drawn on it",
                     loc="left", fontsize=14, fontweight="bold", color=INK)
        n = img.shape[0]
        # one family of parallel guides per candidate, drawn right across so
        # they can be laid against the streaks rather than guessed at
        for k, (brg, col, lab) in enumerate(CANDIDATES):
            t = np.radians(brg)
            dx, dy = np.sin(t), -np.cos(t)          # (col, row) for bearing
            for off in np.arange(-n, 2 * n, n / 4.5):
                x0 = off - dx * n * 2
                y0 = (n * (0.12 + 0.3 * k)) - dy * n * 2
                ax.plot([x0, x0 + dx * n * 4], [y0, y0 + dy * n * 4],
                        color=col, lw=1.8, alpha=0.9, zorder=5)
            ax.set_xlim(0, n); ax.set_ylim(n, 0)
        ax.legend(handles=[Line2D([], [], color=c, lw=2.6,
                                  label=f"{b_:.0f}°  {l}")
                           for b_, c, l in CANDIDATES],
                  loc="lower right", fontsize=11, framealpha=0.95)

    d = res["layers"]["RRIM"]
    fig.suptitle("Which way does the RRIM's grain run?",
                 x=0.012, y=0.985, ha="left", va="top", fontsize=17,
                 fontweight="bold", color=INK)
    fig.text(0.012, 0.942,
             f"{d['n_windows']} windows across the tile, 1° sweep  ·  "
             f"dominant {d['mean_peak1']:.0f}° "
             f"(concentration {d['concentration1']:.2f})  ·  "
             f"second {d['mean_peak2']:.0f}°",
             fontsize=12, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "rrim_grain_bearing_9t.png"
    fig.savefig(p, dpi=155, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")


if __name__ == "__main__":
    raise SystemExit(main())

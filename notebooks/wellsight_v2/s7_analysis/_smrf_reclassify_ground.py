"""Classify ground ourselves, with no 18-degree cut, and see what changes.

WHY
---
The PA WesternPA 2019 D20 March-2020 block discards every at-ground return
beyond 18 degrees off nadir -- about a million per tile, measuring 0.065-0.067 m
RMSE against neighbouring flight lines, inside the QL2 spec of 0.10 m. 17.81% of
0.5 m DEM cells hold no ground return at all, and a quarter of those have one of
the discarded returns sitting in them.

Patching the vendor's flags does not work: the reference surface is built FROM
class 2, so promoting points moves the surface and re-opens the question. The
only clean answer is to classify ground from scratch and compare like for like.

THE FILTER
----------
PDAL `filters.smrf` -- Pingel, Clarke & McBride (2013), the Simple Morphological
Filter. Progressive morphological opening on a raster of minimum elevations,
with a slope-dependent threshold. It is not the Axelsson TIN family the vendor
used, which is deliberate: an independent method is a real check, not a rerun.

PARAMETERS COME FROM THE TERRAIN, NOT FROM ME
---------------------------------------------
SMRF's default slope is 0.15. The 9t slope raster measures p50 0.13, p90 0.34,
p99 0.67 -- Appalachian Plateau, and the default would reject genuinely steep
ground. So `--sweep` runs a range of slopes and picks by an OBJECTIVE error
metric, fixed before looking at any result:

    A ground point must be a terminal return.

If a pulse produced a return after this one, something was below this point and
it is not the ground. That is geometry, not opinion. The vendor's class 2 is
100.0% terminal returns. Any SMRF setting that pushes non-terminal returns into
ground is manufacturing ground, and the rate is measurable without reference to
pits, DEMs, or anything we want the answer to be.

The chosen slope is the one that recovers the most withheld returns while
holding that error rate at the vendor's level. Tuning on pit depth would be
fitting to the answer and is not done anywhere in this script.

WHAT IS MEASURED
----------------
    point level   ground recovered, where it came from in the swath, and the
                  non-terminal error rate
    DEM level     void cells closed, and how far the surface actually moved
    target level  depth of every annotated pit, both ways

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md). The vendor's classification is ferried
into a spare dimension before SMRF overwrites it, so both live in one file and
no point can be mismatched between them. DEMs are Delaunay TIN + faceraster,
which is what `phase_1_derivative_generation.ipynb` builds.

Run:
    python notebooks/wellsight_v2/s7_analysis/_smrf_reclassify_ground.py --sweep
    python notebooks/wellsight_v2/s7_analysis/_smrf_reclassify_ground.py --slope 0.35
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# --- v6 bare mode -----------------------------------------------------------
import os as _os

BARE = _os.environ.get("WELLSIGHT_BARE") == "1"


def _chrome(_fn, *a, **k):
    """Draw slide chrome only when the figure has to stand on its own."""
    if not BARE:
        return _fn(*a, **k)
    return None


def _out(p):
    from pathlib import Path as _P
    p = _P(p)
    if BARE:
        p = p / "v6"
        p.mkdir(parents=True, exist_ok=True)
    return p
# ----------------------------------------------------------------------------


warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = _out(ROOT / "data" / "9t" / "results" / "smrf_ground")
#: Never under v6/ -- the classification does not depend on how it is drawn.
_CACHE = ROOT / "data" / "9t" / "results" / "smrf_ground" / "_cache"
_CACHE.mkdir(parents=True, exist_ok=True)
#: BARE builds must never overwrite the shipped figures.
FIG = _out(ROOT / "docs" / "presentation" / "figures_30to45min" / "1_data_qa")
PDAL = "pdal"

RES = 0.5            # DEM cell size, matching the project's 0.5 m products
NEAR = 0.15
RING_IN, RING_OUT = 2.0, 8.0
SWEEP = [0.15, 0.25, 0.35, 0.50, 0.70]

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"
#: Colourblind rule: a red/green pair is the one a deuteranope or
#: protanope cannot read, so no figure here contains both. Checked with
#: the dataviz validator over ALL pairs, not just adjacent ones.
#:   blue #1F5FA8  amber #D97706  deep red #A31515
#:   worst pair dE 21.1 deutan / 21.5 protan / 22.6 normal, all >= 3:1
GREY, BLUE, VERM, GREEN = "#8E959B", "#1F5FA8", "#A31515", "#D97706"


def run_pipeline(stages, label, timeout=7200):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    t0 = time.time()
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True,
                       timeout=timeout)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-1500:]); print(r.stderr[-1500:])
        raise RuntimeError(f"{label} failed, exit {r.returncode}")
    return time.time() - t0


def find_tile(code):
    hits = [f for f in sorted(SRC.rglob("*.laz"))
            if not f.name.startswith("_merged")
            and re.search(rf"17T..{code}(\.copc)?\.laz$", f.name)]
    if not hits:
        raise SystemExit(f"no source file for tile {code}")
    return hits[0]


def smrf(laz, out_las, slope, cell=1.0, window=18.0, threshold=0.5,
         scalar=1.25):
    """Reclassify ground with SMRF, keeping the vendor's labels alongside."""
    return run_pipeline([
        str(laz),
        # Park the vendor's classification somewhere SMRF will not overwrite it,
        # so both labels ride on the same point and nothing can be mismatched.
        {"type": "filters.ferry", "dimensions": "Classification=>VendorClass"},
        # Height above the VENDOR surface, computed before we touch anything --
        # it is how the recovered points get described later.
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        # Standard practice: drop gross outliers before the morphological pass,
        # then tell SMRF to ignore what was flagged.
        {"type": "filters.outlier", "method": "statistical", "mean_k": 8,
         "multiplier": 3.0},
        {"type": "filters.smrf", "cell": cell, "slope": slope,
         "window": window, "threshold": threshold, "scalar": scalar,
         "ignore": "Classification[7:7]"},
        {"type": "writers.las", "filename": str(out_las),
         "extra_dims": "VendorClass=uint8,HeightAboveGround=float32",
         "compression": "false"},
    ], f"smrf slope={slope}")


def read_las(p):
    import laspy
    las = laspy.read(str(p))
    d = {"x": np.asarray(las.x), "y": np.asarray(las.y), "z": np.asarray(las.z),
         "smrf": np.asarray(las.classification).astype("int16"),
         "vendor": np.asarray(las.VendorClass).astype("int16"),
         "hag": np.asarray(las.HeightAboveGround, dtype="float32"),
         "rn": np.asarray(las.return_number).astype("int16"),
         "nr": np.asarray(las.number_of_returns).astype("int16")}
    for a in ("scan_angle", "scan_angle_rank"):
        if hasattr(las, a):
            v = np.asarray(getattr(las, a), dtype="float32")
            d["ang"] = np.abs(v * 0.006 if a == "scan_angle" else v)
            break
    return d


def point_metrics(d, slope):
    """Everything measurable without building a raster."""
    vg = d["vendor"] == 2
    sg = d["smrf"] == 2
    term = d["rn"] == d["nr"]
    inter = (d["rn"] > 1) & (d["rn"] < d["nr"])
    rec = sg & ~vg                       # SMRF says ground, vendor did not
    drop = vg & ~sg                      # vendor said ground, SMRF does not
    return dict(
        slope=slope, points=int(d["z"].size),
        vendor_ground=int(vg.sum()), smrf_ground=int(sg.sum()),
        recovered=int(rec.sum()), dropped=int(drop.sum()),
        agree_pct=100 * float((vg == sg).mean()),
        # the objective error metric, fixed before any result was seen
        vendor_nonterminal_pct=100 * float((~term[vg]).mean()) if vg.any() else np.nan,
        smrf_nonterminal_pct=100 * float((~term[sg]).mean()) if sg.any() else np.nan,
        vendor_intermediate=int((inter & vg).sum()),
        smrf_intermediate=int((inter & sg).sum()),
        rec_beyond18_pct=100 * float((d["ang"][rec] >= 18.0).mean())
            if rec.any() else np.nan,
        rec_med_ang=float(np.median(d["ang"][rec])) if rec.any() else np.nan,
        rec_med_hag=float(np.median(d["hag"][rec])) if rec.any() else np.nan,
        rec_above_half_m_pct=100 * float((d["hag"][rec] > 0.5).mean())
            if rec.any() else np.nan,
    )


def dem(las, out_tif, class_field, bounds):
    """Delaunay TIN + faceraster at RES -- phase 1's method, not a proxy."""
    x0, y0, x1, y1 = bounds
    w = int(round((x1 - x0) / RES))
    h = int(round((y1 - y0) / RES))
    return run_pipeline([
        str(las),
        {"type": "filters.range", "limits": f"{class_field}[2:2]"},
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster", "resolution": RES,
         "origin_x": x0, "origin_y": y0, "width": w, "height": h},
        {"type": "writers.raster", "filename": str(out_tif),
         "data_type": "float32"},
    ], f"dem {class_field}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", nargs="+", default=["616591", "621594"])
    ap.add_argument("--slope", type=float, default=0.35)
    ap.add_argument("--force", action="store_true",
                    help="re-run SMRF even when the cached LAS exists")
    ap.add_argument("--sweep", action="store_true",
                    help="try a range of slopes on the first tile and stop")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    if args.sweep:
        code = args.tiles[0]
        laz = find_tile(code)
        print(f"SWEEP on {code}\n")
        rows = []
        for s in SWEEP:
            tmp = Path(tempfile.gettempdir()) / f"_smrf_{code}_{s}.las"
            try:
                dt = smrf(laz, tmp, s)
            except Exception as e:
                print(f"  slope {s:.2f}  FAILED {e}"); continue
            d = read_las(tmp)
            m = point_metrics(d, s)
            m["tile"] = code
            m["seconds"] = round(dt)
            rows.append(m)
            print(f"  slope {s:.2f}  {dt:5.0f}s  ground {m['smrf_ground']:>9,} "
                  f"(vendor {m['vendor_ground']:,})  recovered "
                  f"{m['recovered']:>9,}  dropped {m['dropped']:>8,}  "
                  f"non-terminal {m['smrf_nonterminal_pct']:5.2f}% "
                  f"(vendor {m['vendor_nonterminal_pct']:.2f}%)")
            tmp.unlink(missing_ok=True)
            del d
        df = pd.DataFrame(rows)
        df.to_csv(OUT / f"smrf_slope_sweep_{code}.csv", index=False)
        print(f"\nwrote {OUT / f'smrf_slope_sweep_{code}.csv'}")
        print("\n  Choose the slope that recovers the most withheld returns "
              "while holding the\n  non-terminal error rate at the vendor's "
              "level. Do NOT choose on pit depth.")
        return 0

    for code in args.tiles:
        _full(code, args.slope, args.force)
    return 0


def _full(code, slope, force=False):
    import rasterio
    laz = find_tile(code)
    print(f"\n=== tile {code}, SMRF slope {slope}")
    # SMRF over a full map square is minutes of PDAL. The result is a pure
    # function of (tile, slope), so it is cached beside the outputs instead of
    # written to a temp file and deleted -- redrawing the figure used to pay
    # for the classification again every single time.
    cache = _CACHE / f"smrf_{code}_slope{str(slope).replace('.', 'p')}.las"
    if cache.exists() and not force:
        print(f"    reusing cached SMRF {cache.name} "
              f"({cache.stat().st_size/1e6:.0f} MB; --force to redo)")
    else:
        dt = smrf(laz, cache, slope)
        print(f"    smrf {dt:.0f}s  -> {cache.name}")
    las = cache
    d = read_las(las)
    m = point_metrics(d, slope)
    m["tile"] = code
    print(f"    vendor ground {m['vendor_ground']:,}  ->  smrf "
          f"{m['smrf_ground']:,}   recovered {m['recovered']:,}  "
          f"dropped {m['dropped']:,}")
    print(f"    non-terminal in ground: vendor "
          f"{m['vendor_nonterminal_pct']:.3f}%  smrf "
          f"{m['smrf_nonterminal_pct']:.3f}%")
    print(f"    recovered points: {m['rec_beyond18_pct']:.1f}% lie beyond 18 "
          f"deg, median angle {m['rec_med_ang']:.1f} deg, median height above "
          f"the vendor surface {m['rec_med_hag']:+.3f} m")

    bx0 = np.floor(d["x"].min() / RES) * RES
    by0 = np.floor(d["y"].min() / RES) * RES
    bx1 = np.ceil(d["x"].max() / RES) * RES
    by1 = np.ceil(d["y"].max() / RES) * RES
    bounds = (bx0, by0, bx1, by1)

    dv = OUT / f"dem_vendorground_{code}_{str(RES).replace('.','p')}m.tif"
    ds = OUT / f"dem_smrfground_slope{str(slope).replace('.','p')}_{code}_" \
               f"{str(RES).replace('.','p')}m.tif"
    dem(las, dv, "VendorClass", bounds)
    dem(las, ds, "Classification", bounds)
    print(f"    wrote {dv.name}\n    wrote {ds.name}")

    with rasterio.open(dv) as r:
        A = r.read(1).astype("float32")
        prof, tf = r.profile, r.transform
        if r.nodata is not None:
            A[A == r.nodata] = np.nan
    with rasterio.open(ds) as r:
        B = r.read(1).astype("float32")
        if r.nodata is not None:
            B[B == r.nodata] = np.nan

    # voids measured on the points, not the interpolated raster: a TIN fills
    # every cell inside its hull, so "no data" in the raster is not the same
    # question as "no ground return in this cell"
    nx = int(round((bx1 - bx0) / RES)); ny = int(round((by1 - by0) / RES))
    col = np.clip(((d["x"] - bx0) / RES).astype(np.int64), 0, nx - 1)
    row = np.clip(((by1 - d["y"]) / RES).astype(np.int64), 0, ny - 1)
    flat = row * nx + col
    n = nx * ny
    c_all = np.bincount(flat, minlength=n)
    c_v = np.bincount(flat[d["vendor"] == 2], minlength=n)
    c_s = np.bincount(flat[d["smrf"] == 2], minlength=n)
    cov = c_all > 0
    void_v = int((cov & (c_v == 0)).sum())
    void_s = int((cov & (c_s == 0)).sum())
    closed = int((cov & (c_v == 0) & (c_s > 0)).sum())
    m.update(cells_covered=int(cov.sum()), void_vendor=void_v,
             void_smrf=void_s, voids_closed=closed,
             void_vendor_pct=100 * void_v / cov.sum(),
             void_smrf_pct=100 * void_s / cov.sum())
    print(f"    voids {void_v:,} ({m['void_vendor_pct']:.2f}%)  ->  "
          f"{void_s:,} ({m['void_smrf_pct']:.2f}%)   closed {closed:,} "
          f"({100*closed/max(void_v,1):.1f}% of them)")

    dz = B - A
    fin = np.isfinite(dz)
    m.update(dz_median=float(np.nanmedian(dz[fin])),
             dz_p95=float(np.nanpercentile(np.abs(dz[fin]), 95)),
             dz_over_10cm_pct=100 * float((np.abs(dz[fin]) > 0.10).mean()))
    print(f"    surface moved: median {m['dz_median']:+.3f} m, p95 |dz| "
          f"{m['dz_p95']:.3f} m, {m['dz_over_10cm_pct']:.1f}% of cells by "
          f"more than 10 cm")

    # The obvious objection: did we fix the holes, or repaint the whole DEM?
    # Split the movement by whether the cell had a ground measurement before.
    # Movement should concentrate where the surface was previously guessed.
    status = np.full(cov.shape, 3, dtype="uint8")       # 3 = outside coverage
    status[cov & (c_v > 0)] = 0                          # had ground already
    status[cov & (c_v == 0) & (c_s > 0)] = 1             # void closed by SMRF
    status[cov & (c_v == 0) & (c_s == 0)] = 2            # still void
    status = status.reshape(ny, nx)
    print(f"    {'where':22s} {'cells':>10s} {'median dz':>11s} "
          f"{'p95 |dz|':>10s} {'> 10 cm':>9s}")
    for code_, lab in ((0, "had ground already"), (1, "void closed by SMRF"),
                       (2, "still no ground")):
        k = (status == code_) & fin
        if k.sum() < 50:
            continue
        v = dz[k]
        m[f"dz_p95_status{code_}"] = float(np.percentile(np.abs(v), 95))
        m[f"dz_over10_status{code_}"] = 100 * float((np.abs(v) > 0.10).mean())
        print(f"    {lab:22s} {int(k.sum()):>10,} {np.median(v):>+11.3f} "
              f"{np.percentile(np.abs(v), 95):>10.3f} "
              f"{100*(np.abs(v) > 0.10).mean():>8.1f}%")

    sp = OUT / f"ground_cell_status_{code}_{str(RES).replace('.','p')}m.tif"
    prof2 = dict(prof)
    prof2.update(dtype="uint8", nodata=3, count=1, compress="deflate")
    with rasterio.open(sp, "w", **prof2) as ds_:
        ds_.write(status, 1)
    print(f"    wrote {sp.name}  (0 had ground, 1 closed by SMRF, 2 still void)")

    pits = _pit_depths(code, A, B, tf, (ny, nx))
    if pits is not None and len(pits):
        m.update(pits=len(pits),
                 depth_vendor=float(pits.depth_A.median()),
                 depth_smrf=float(pits.depth_B.median()),
                 depth_delta=float(pits.d_depth.median()),
                 pits_deeper_10cm=int((pits.d_depth >= 0.10).sum()))
        print(f"    {len(pits)} annotated pits: median depth "
              f"{m['depth_vendor']:.2f} -> {m['depth_smrf']:.2f} m "
              f"(delta {m['depth_delta']:+.3f}); "
              f"{m['pits_deeper_10cm']} deepened by >= 0.10 m")
        pits.to_csv(OUT / f"pit_depth_vendor_vs_smrf_{code}.csv", index=False)

    pd.DataFrame([m]).to_csv(OUT / f"smrf_vs_vendor_{code}.csv", index=False)
    _figure(code, slope, A, B, dz, cov.reshape(ny, nx),
            (c_v == 0).reshape(ny, nx), (c_s == 0).reshape(ny, nx), bounds, m)
    # Deliberately NOT deleted. This used to be a temp file; it is the SMRF
    # cache now, and removing it here cost a full reclassification on every
    # redraw. `--force` overwrites it when the classification must change.
    del d


def _pit_depths(code, A, B, tf, shape):
    import geopandas as gpd
    from rasterio.features import rasterize
    from shapely.geometry import box
    try:
        pits = gpd.read_file(ANN, layer="pit_inside")
    except Exception:
        return None
    l = tf.c; t = tf.f
    bb = box(l, t + shape[0] * tf.e, l + shape[1] * tf.a, t)
    sel = pits[pits.centroid.within(bb)]
    rows = []
    for _, p in sel.iterrows():
        fm = rasterize([(p.geometry, 1)], out_shape=shape, transform=tf,
                       dtype="uint8").astype(bool)
        rg = p.geometry.buffer(RING_OUT).difference(p.geometry.buffer(RING_IN))
        rm = rasterize([(rg, 1)], out_shape=shape, transform=tf,
                       dtype="uint8").astype(bool)
        if fm.sum() < 4 or rm.sum() < 4:
            continue
        if not (np.isfinite(A[fm]).any() and np.isfinite(B[fm]).any()):
            continue
        dA = np.nanmedian(A[rm]) - np.nanpercentile(A[fm], 5)
        dB = np.nanmedian(B[rm]) - np.nanpercentile(B[fm], 5)
        rows.append(dict(tile=code, area_m2=p.geometry.area,
                         depth_A=dA, depth_B=dB, d_depth=dB - dA))
    return pd.DataFrame(rows)


def _figure(code, slope, A, B, dz, cov, vv, vs, bounds, m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource, TwoSlopeNorm, ListedColormap

    ext = [bounds[0], bounds[2], bounds[1], bounds[3]]
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(1, 3, figsize=(19.2, 7.4))
    ls = LightSource(315, 45)

    for a, arr, t in ((ax[0], A, "DEM from the vendor's ground"),
                      (ax[1], B, f"DEM from SMRF ground, slope {slope}")):
        f = np.nan_to_num(arr, nan=float(np.nanmedian(arr)))
        a.imshow(ls.hillshade(f, vert_exag=2.0, dx=RES, dy=RES), extent=ext,
                 cmap="gray", origin="upper")
        a.set_title(t, fontsize=13.5, fontweight="bold", loc="left", pad=8)

    # which cells gained a ground return
    cat = np.full(cov.shape, np.nan)
    cat[cov & ~vv] = 0                      # already had ground
    cat[cov & vv & ~vs] = 1                 # void closed by SMRF
    cat[cov & vv & vs] = 2                  # still void
    cm = ListedColormap(["#eceae4", GREEN, VERM])
    ax[2].imshow(cat, extent=ext, origin="upper", cmap=cm, vmin=0, vmax=2,
                 interpolation="nearest")
    ax[2].set_title("Cells with no ground return", fontsize=13.5,
                    fontweight="bold", loc="left", pad=8)
    import matplotlib.patches as mp
    ax[2].legend(handles=[
        mp.Patch(color="#eceae4", label="had ground already"),
        mp.Patch(color=GREEN, label=f"void closed by SMRF "
                                    f"({m['voids_closed']:,})"),
        mp.Patch(color=VERM, label=f"still no ground ({m['void_smrf']:,})")],
        frameon=False, fontsize=10, loc="lower left")

    for a in ax:
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3])
        a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
        for sp in a.spines.values():
            sp.set_color(RULE)
    _chrome(fig.suptitle, f"Ground reclassified with SMRF   ·   tile {code}   "
                 f"·   {m['recovered']:,} returns recovered, "
                 f"{m['void_vendor_pct']:.1f}% → "
                 f"{m['void_smrf_pct']:.1f}% of cells without ground",
                 fontsize=16, fontweight="bold", x=0.010, ha="left", y=0.975)
    fig.subplots_adjust(left=0.010, right=0.99, top=0.88, bottom=0.02,
                        wspace=0.05)
    p = FIG / f"smrf_vs_vendor_{code}.png"
    fig.savefig(p, dpi=185)
    plt.close(fig)
    print(f"    wrote {p}")


if __name__ == "__main__":
    sys.exit(main())

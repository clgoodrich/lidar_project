"""
Session summary figure — end-to-end Phase 0-2 results on the calibration subarea.

Shows:
  1. Subarea DEM with hillshade + well locations
  2. Feature A (pads) candidates over hillshade with wells
  3. Feature B (roads) candidates over hillshade with wells
  4. Nearest-candidate distance CDFs (wells vs null) for A
  5. Nearest-candidate distance CDFs (wells vs null) for B
  6. Enrichment vs radius for A and B
"""
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import rasterio
import geopandas as gpd
from shapely.geometry import Point, box
from shapely.strtree import STRtree

ROOT = Path(r"C:/Users/colto/Documents/GitHub/lidar_project")
DATA = ROOT / "data"
SUB = DATA / "derivatives" / "subarea"
TARGET_CRS = "EPSG:26917"
SUB_BBOX = (619500.0, 4594000.0, 624500.0, 4599000.0)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Load data ─────────────────────────────────────────────────────────────
with rasterio.open(SUB / "hillshade.tif") as s:
    HS = s.read(1).astype("float32")
    TRANSFORM = s.transform

wells_all = gpd.read_file(DATA / "wells_with_features.shp").to_crs(TARGET_CRS)
wells = wells_all[wells_all.geometry.within(box(*SUB_BBOX))].copy().reset_index(drop=True)

pads = gpd.read_file(SUB / "features_A_pads.gpkg", layer="pads")
roads = gpd.read_file(SUB / "features_B_roads.gpkg", layer="roads")

inv = ~TRANSFORM
def to_px(x, y):
    c, r = inv * (x, y)
    return c, r


# ── Panels 1-3: subarea with features + wells ────────────────────────────
wells_px = np.array([to_px(p.x, p.y) for p in wells.geometry])

fig = plt.figure(figsize=(22, 14))
gs = fig.add_gridspec(2, 3, height_ratios=[1.3, 1])

ax = fig.add_subplot(gs[0, 0])
ax.imshow(HS, cmap="gray")
ax.scatter(wells_px[:, 0], wells_px[:, 1], s=3, c="cyan", alpha=0.6,
           label=f"{len(wells)} wells")
ax.set_title(f"Calibration subarea — 5×5 km, {len(wells)} wells", fontsize=11)
ax.legend(loc="upper right", fontsize=9)
ax.axis("off")

ax = fig.add_subplot(gs[0, 1])
ax.imshow(HS, cmap="gray")
ax.scatter(wells_px[:, 0], wells_px[:, 1], s=3, c="cyan", alpha=0.35)
for _, row in pads.iterrows():
    if row.geometry is None or row.geometry.is_empty:
        continue
    xs, ys = row.geometry.exterior.xy
    pxs = []; pys = []
    for x, y in zip(xs, ys):
        c, r = to_px(x, y); pxs.append(c); pys.append(r)
    ax.plot(pxs, pys, color="orange", linewidth=1.2)
ax.set_title(f"Feature A (pads) — {len(pads)} candidates\nKS p=0.003, enrichment 1.73× at 50 m",
             fontsize=11)
ax.axis("off")

ax = fig.add_subplot(gs[0, 2])
ax.imshow(HS, cmap="gray")
ax.scatter(wells_px[:, 0], wells_px[:, 1], s=3, c="cyan", alpha=0.35)
for _, row in roads.iterrows():
    if row.geometry is None or row.geometry.is_empty:
        continue
    if row.geometry.geom_type == "Polygon":
        xs, ys = row.geometry.exterior.xy
        pxs = []; pys = []
        for x, y in zip(xs, ys):
            c, r = to_px(x, y); pxs.append(c); pys.append(r)
        ax.plot(pxs, pys, color="magenta", linewidth=1.2)
ax.set_title(f"Feature B (roads) — {len(roads)} candidates\nKS p=0.43, enrichment 1.14× at 100 m (null)",
             fontsize=11)
ax.axis("off")


# ── Recompute nearest-distances for CDF + enrichment curves ──────────────
def nearest_distances(points, features):
    tree = STRtree(features.geometry.values)
    out = np.empty(len(points))
    for i, pt in enumerate(points.geometry.values):
        idx = tree.nearest(pt)
        out[i] = pt.distance(features.geometry.values[idx])
    return out


def draw_null(n, seed=42):
    rng = np.random.default_rng(seed)
    xs = rng.uniform(SUB_BBOX[0], SUB_BBOX[2], n * 3)
    ys = rng.uniform(SUB_BBOX[1], SUB_BBOX[3], n * 3)
    # Sample wells' slope + HAND distribution as in validation
    with rasterio.open(SUB / "slope.tif") as s:
        slope_arr = s.read(1).astype("float32")
        nd = s.nodata
        t = s.transform
    slope_arr[slope_arr == nd] = np.nan
    with rasterio.open(SUB / "hand.tif") as s:
        hand_arr = s.read(1).astype("float32")
        nd_h = s.nodata
    hand_arr[hand_arr == nd_h] = np.nan
    def sample(arr, x, y):
        c, r = (~t) * (x, y)
        r = np.round(r).astype(int); c = np.round(c).astype(int)
        out = np.full(len(x), np.nan)
        valid = (r >= 0) & (r < arr.shape[0]) & (c >= 0) & (c < arr.shape[1])
        out[valid] = arr[r[valid], c[valid]]
        return out
    s_vals = sample(slope_arr, xs, ys)
    h_vals = sample(hand_arr, xs, ys)
    keep = ~(np.isnan(s_vals) | np.isnan(h_vals))
    xs, ys = xs[keep], ys[keep]
    idx = rng.choice(len(xs), min(len(xs), n), replace=False)
    xs, ys = xs[idx], ys[idx]
    return gpd.GeoDataFrame(geometry=[Point(a, b) for a, b in zip(xs, ys)], crs=TARGET_CRS)


null_pts = draw_null(len(wells))

log("Computing nearest distances for CDF plots...")
well_d_A = nearest_distances(wells, pads)
null_d_A = nearest_distances(null_pts, pads)
well_d_B = nearest_distances(wells, roads)
null_d_B = nearest_distances(null_pts, roads)


# ── Panel 4: CDF for Feature A ───────────────────────────────────────────
ax = fig.add_subplot(gs[1, 0])
xsA = np.sort(well_d_A); yA = np.arange(1, len(xsA) + 1) / len(xsA)
xsA_n = np.sort(null_d_A); yA_n = np.arange(1, len(xsA_n) + 1) / len(xsA_n)
ax.plot(xsA, yA, label="Wells", color="tab:blue", lw=2)
ax.plot(xsA_n, yA_n, label="Null (covariate-matched)", color="grey", lw=2, linestyle="--")
ax.set_xlabel("Distance to nearest pad candidate (m)")
ax.set_ylabel("CDF")
ax.set_xlim(0, 1500)
ax.legend(loc="lower right", fontsize=9)
ax.set_title("Feature A — nearest distance CDF (wells shifted left of null = association)")
ax.grid(alpha=0.3)

# ── Panel 5: CDF for Feature B ───────────────────────────────────────────
ax = fig.add_subplot(gs[1, 1])
xsB = np.sort(well_d_B); yB = np.arange(1, len(xsB) + 1) / len(xsB)
xsB_n = np.sort(null_d_B); yB_n = np.arange(1, len(xsB_n) + 1) / len(xsB_n)
ax.plot(xsB, yB, label="Wells", color="tab:red", lw=2)
ax.plot(xsB_n, yB_n, label="Null", color="grey", lw=2, linestyle="--")
ax.set_xlabel("Distance to nearest road candidate (m)")
ax.set_ylabel("CDF")
ax.set_xlim(0, 1500)
ax.legend(loc="lower right", fontsize=9)
ax.set_title("Feature B — nearest distance CDF (wells ≈ null = no association)")
ax.grid(alpha=0.3)

# ── Panel 6: Enrichment vs radius ────────────────────────────────────────
ax = fig.add_subplot(gs[1, 2])
radii = [50, 100, 150, 200]
# Values from validation_results.csv
enrich_A = [1.73, 1.51, 1.35, 1.30]
enrich_B = [1.29, 1.14, 1.14, 1.10]
ax.plot(radii, enrich_A, "o-", label="Feature A (pads)", color="tab:blue", lw=2, markersize=8)
ax.plot(radii, enrich_B, "s-", label="Feature B (roads)", color="tab:red", lw=2, markersize=8)
ax.axhline(1.0, color="grey", linestyle=":", label="Null expectation")
ax.set_xlabel("Search radius (m)")
ax.set_ylabel("Enrichment (well-mean / null-mean)")
ax.set_title("Enrichment vs radius — A decays from 1.73× (real), B hovers near 1× (null)")
ax.legend(fontsize=9)
ax.grid(alpha=0.3)
ax.set_ylim(0.9, 2.0)

plt.suptitle(
    "Session summary — Phase 0 foundation + Feature A & B detectors + Phase 2 validation\n"
    "Calibration subarea (E 619500–624500, N 4594000–4599000)  •  803 historic wells",
    fontsize=13, y=0.99,
)
plt.tight_layout()

out_png = SUB / "session_summary.png"
plt.savefig(out_png, dpi=110, bbox_inches="tight")
plt.close()
log(f"Saved: {out_png}")

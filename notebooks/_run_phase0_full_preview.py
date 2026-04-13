"""
Phase 0.6 — Full sanity preview including both DEM-only and point-cloud
derivatives. Renders every base layer on a hillshade and prints diagnostic
percentiles.
"""
import time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import rasterio

SUB = Path(r"C:/Users/colto/Documents/GitHub/lidar_project/data/derivatives/subarea")

PANELS = [
    (SUB / "dem.tif",                          "DEM (m)",             "cividis",    None, None),
    (SUB / "hillshade.tif",                    "Hillshade",           "gray",       None, None),
    (SUB / "openness_positive.tif",            "Openness (pos °)",    "cividis",    80,   90),
    (SUB / "openness_negative.tif",            "Openness (neg °)",    "cividis",    80,   90),
    (SUB / "slope.tif",                        "Slope (°)",           "cividis",    0,    35),
    (SUB / "plan_curvature.tif",               "Plan curvature",      "coolwarm_r", -0.5, 0.5),
    (SUB / "local_relief.tif",                 "Local relief (m)",    "cividis",    0,    8),
    (SUB / "roughness.tif",                    "Roughness",           "cividis",    0,    5),
    (SUB / "tpi_15m.tif",                      "TPI 15m",             "coolwarm_r", -0.5, 0.5),
    (SUB / "tpi_15m_gradient_magnitude.tif",   "TPI15 grad mag",      "cividis",    0,    0.3),
    (SUB / "hand.tif",                         "HAND (m)",            "cividis",    0,    30),
    (SUB / "streams.tif",                      "Streams",             "Blues",      0,    1),
    (SUB / "chm.tif",                          "CHM (m)",             "cividis",    0,    30),
    (SUB / "chm_anomaly.tif",                  "CHM anomaly (z)",     "coolwarm_r", -2,   2),
    (SUB / "intensity.tif",                    "Intensity",           "cividis",    None, None),
    (SUB / "intensity_anomaly.tif",            "Intensity anomaly",   "coolwarm_r", -2,   2),
    (SUB / "first_return_fraction.tif",        "First return frac",   "cividis",    0,    1),
    (SUB / "point_density_ground.tif",         "Ground pt density",   "cividis",    0,    10),
    (SUB / "point_density_mask.tif",           "Quality mask",        "Greys_r",    0,    1),
    (SUB / "dsm.tif",                          "DSM (m)",             "cividis",    None, None),
]

with rasterio.open(SUB / "hillshade.tif") as s:
    hs = s.read(1).astype("float32")

cols = 4
rows = (len(PANELS) + cols - 1) // cols
fig, axes = plt.subplots(rows, cols, figsize=(22, 4.5 * rows))
for ax, (path, title, cmap, vmn, vmx) in zip(axes.flat, PANELS):
    if not path.exists():
        ax.set_title(f"{title} (missing)", fontsize=10); ax.axis("off"); continue
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nd = src.nodata
    if nd is not None:
        arr[arr == nd] = np.nan
    if vmn is None or vmx is None:
        vmn, vmx = np.nanpercentile(arr, [2, 98])
    # Only overlay hillshade on panels where it adds value
    use_hs = title not in ("Hillshade", "Streams", "Quality mask", "DEM (m)", "DSM (m)", "CHM (m)", "Intensity")
    if use_hs:
        ax.imshow(hs, cmap="gray", alpha=0.55)
    im = ax.imshow(arr, cmap=cmap, vmin=vmn, vmax=vmx, alpha=0.80 if use_hs else 1.0)
    ax.set_title(title, fontsize=10)
    ax.axis("off")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

# Hide any unused subplots
for ax in axes.flat[len(PANELS):]:
    ax.axis("off")

fig.suptitle("Phase 0 — All derivatives, calibration subarea (5 × 5 km)",
             fontsize=14, y=1.00)
plt.tight_layout()
out = SUB / "derivatives_preview_full.png"
plt.savefig(out, dpi=110, bbox_inches="tight")
plt.close()
print(f"Saved: {out}")

# Final diagnostic table
print("\nAll-derivatives diagnostic:")
for path, title, *_ in PANELS:
    if not path.exists():
        continue
    with rasterio.open(path) as src:
        a = src.read(1).astype("float32")
        nd = src.nodata
    if nd is not None:
        a[a == nd] = np.nan
    finite = np.isfinite(a).sum()
    total = a.size
    if finite == 0:
        print(f"  {title:22s}  ALL NAN")
        continue
    p2, p50, p98 = np.nanpercentile(a, [2, 50, 98])
    print(f"  {title:22s}  valid={finite/total*100:5.1f}%  p2={p2:12.3f}  p50={p50:12.3f}  p98={p98:12.3f}")

"""Build the interactive SAR side-looking-geometry simulator from a 613590 lidar chunk.

What it makes
-------------
1. A real 800 m x 800 m DEM clip from the steepest part of block 613590
   (166 m relief, 99th-percentile slope ~37 deg). This is the real layer.
2. The same clip with a SYNTHETIC Matterhorn-style peak added on top
   (62 deg summit faces, 22 deg apron, 260 m tall). The peak is made up.
   Real PA terrain is not steep enough for radar shadow at mid incidence
   angles: shadow needs back-slopes steeper than 90 - theta (50 deg at
   theta = 40 deg) and less than 0.1% of the chunk is that steep. The
   62 deg faces guarantee layover, foreshortening and shadow all appear
   at once for any look direction when 28 deg < theta < 62 deg.
3. A self-contained HTML tool that embeds both scenes at 2 m and simulates
   layover, foreshortening and shadow for any incidence angle, flight
   heading and look side.

Geometry model (far-field / plane-wave, flat Earth over 800 m):
    slant range      r = u sin(theta) - z cos(theta)
    layover          dz/du > tan(theta)                 (dr/du < 0)
    shadow           z below max_{q<p}(z_q - (u_p - u_q) cot(theta))
    range compression K = sin(theta - a) / (sin(theta) cos(a))
where u is horizontal distance along the look direction and a is the
terrain slope in the range direction. Standard SAR geometry; see
literature/CITATIONS.md (Richards 2009; Small 2011).

Reproduce:
    python notebooks/wellsight_v2/s7_analysis/_build_sar_geometry_simulator_613590.py
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import path_for  # noqa: E402

AREA = "613590"
DEM = path_for("derived") / AREA / "derived" / "1m" / f"dem_{AREA}_1m.tif"
# Steepest 600 m window found by a relief scan (row 3840, col 560); widened
# to 800 m so the synthetic peak's apron fits inside the scene.
ROW0, COL0, SIZE = 3700, 400, 800
DISPLAY_RES = 2  # metres per cell in the HTML

# Synthetic peak parameters
PEAK_H = 260.0          # summit height above the real surface, m
FACE_DEG = 62.0         # summit face slope
APRON_DEG = 22.0        # lower apron slope
FACE_RUN = 100.0        # horizontal run of the steep faces, m
PEAK_ROT_DEG = 20.0     # pyramid rotation so faces are not grid-aligned

CLIP_DIR = path_for("derived") / AREA / "derived" / "1m" / "clips"
OUT_DIR = path_for("results_613590") / "sar_geometry"
TEMPLATE = Path(__file__).with_name("_sar_geometry_simulator_template.html")

REAL_TIF = CLIP_DIR / f"dem_real_sargeom_scene_800m_{AREA}_1m.tif"
SYNTH_TIF = CLIP_DIR / (
    f"dem_synthetic_peak260m_face62deg_on_real_sargeom_scene_800m_{AREA}_1m.tif")
OUT_HTML = OUT_DIR / (
    f"sar_geometry_simulator_layover_foreshortening_shadow_800m_{AREA}_2m.html")


def synthetic_peak(n: int, res: float) -> np.ndarray:
    """Faceted pyramid peak (heights in m) on an n x n grid, centred."""
    c = (np.arange(n) + 0.5) * res - n * res / 2
    x, y = np.meshgrid(c, -c)
    t = np.radians(PEAK_ROT_DEG)
    a = x * np.cos(t) + y * np.sin(t)
    b = -x * np.sin(t) + y * np.cos(t)
    # Mostly L-inf (flat faces, sharp ridges) with a little L2 to round edges.
    d = 0.8 * np.maximum(np.abs(a), np.abs(b)) + 0.2 * np.hypot(a, b)
    tf, ta = np.tan(np.radians(FACE_DEG)), np.tan(np.radians(APRON_DEG))
    z_knee = PEAK_H - FACE_RUN * tf
    z = np.where(d < FACE_RUN, PEAK_H - d * tf, z_knee - (d - FACE_RUN) * ta)
    return np.clip(z, 0, None)


def encode(z: np.ndarray) -> dict:
    """uint16 centimetres above the scene minimum, base64."""
    zmin = float(z.min())
    q = np.round((z - zmin) * 100).astype("<u2")
    assert (z - zmin).max() * 100 < 65535
    return {"n": int(z.shape[0]), "res": DISPLAY_RES, "zmin": zmin,
            "b64": base64.b64encode(q.tobytes()).decode("ascii")}


def main() -> None:
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(DEM) as src:
        win = Window(COL0, ROW0, SIZE, SIZE)
        real = src.read(1, window=win).astype(np.float32)
        prof = src.profile.copy()
        prof.update(width=SIZE, height=SIZE, transform=src.window_transform(win),
                    dtype="float32", compress="deflate", tiled=True,
                    blockxsize=256, blockysize=256)
        crs = src.crs.to_string() if src.crs else "unknown"
        bounds = rasterio.windows.bounds(win, src.transform)
        if src.nodata is not None:
            assert not (real == src.nodata).any(), "nodata inside scene window"

    synth = real + synthetic_peak(SIZE, 1.0).astype(np.float32)
    for path, arr in ((REAL_TIF, real), (SYNTH_TIF, synth)):
        with rasterio.open(path, "w", **prof) as dst:
            dst.write(arr, 1)
        print("wrote", path)

    def block(a: np.ndarray) -> np.ndarray:
        k = DISPLAY_RES
        return a.reshape(SIZE // k, k, SIZE // k, k).mean(axis=(1, 3))

    meta = {"crs": crs, "bounds": [round(v, 1) for v in bounds],
            "source": str(DEM.relative_to(path_for("data").parent)).replace("\\", "/"),
            "window_rowcol": [ROW0, COL0], "size_m": SIZE}
    scenes = {
        "synthetic": {"label": "Synthetic peak on real 613590 terrain",
                      "note": (f"Made-up {PEAK_H:.0f} m peak, {FACE_DEG:.0f}° faces, "
                               f"{APRON_DEG:.0f}° apron, added to the real lidar DEM."),
                      **encode(block(synth)), **meta},
        "real": {"label": "Real 613590 terrain only",
                 "note": "Bare-earth lidar DEM, western PA. 167 m relief.",
                 **encode(block(real)), **meta},
    }
    html = TEMPLATE.read_text(encoding="utf8").replace(
        "/*__SCENES__*/null", json.dumps(scenes))
    OUT_HTML.write_text(html, encoding="utf8")
    print("wrote", OUT_HTML, f"({OUT_HTML.stat().st_size / 1e6:.2f} MB)")

    gy, gx = np.gradient(synth, 1.0)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    print(f"synthetic scene: relief {synth.max() - synth.min():.1f} m, "
          f"slope p99 {np.percentile(s, 99):.1f}, frac>55deg {(s > 55).mean():.4f}")


if __name__ == "__main__":
    main()

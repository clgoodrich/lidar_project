"""Two area figures for the 4-slide Pennsylvania deck: where, and what the records hold.

WHAT
----
1. `pa_counties_venango_mckean_drake_well_locator.png`
   Pennsylvania's 67 counties, with Venango (the modelled tiles) and McKean
   (lidar in hand) filled, the 9t tile marked, and the Drake Well site.
2. `dep_wells_by_status_on_hillshade_9t.png`
   Every DEP well record inside the 9t tile over the 1 m hillshade, grouped as
   orphan or abandoned / plugged / active or other.

DATA
----
  * County outlines: US Census Bureau cartographic boundary file
    cb_2023_us_county_5m (public domain), fetched 2026-09-27 from
    https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_5m.zip
    to data/_source/reference/census_boundaries/ (the .zip is gitignored).
  * Wells: PA DEP oil and gas well export, 2026-04,
    data/_source/reference/dep_wells/venango_wells_all.gpkg (20,108 records).
  * Hillshade: data/9t/derived/1m/hillshade_9t_1m.tif.
  * Drake Well: 41.6106 N, 79.6575 W, the Drake Well Museum and Park site in
    Cherrytree Township, Venango County.

COLOUR
------
validate_palette.py --mode light --pairs all "#D97706,#1F5FA8,#5FB4E0":
all checks pass, worst CVD pair #5FB4E0/#D97706 dE 23.3 deutan, worst normal
pair 25.4. No red or green. Each well group also has its own marker shape
(circle / square / triangle), so colour is never the only encoding.

Run:
  python docs/presentation/pa_trip_4slide/_build_pa_area_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from shapely.geometry import Point, box

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
from _common import path_for  # noqa: E402

COUNTIES = path_for("data") / "_source" / "reference" / "census_boundaries" / "cb_2023_us_county_5m.zip"
WELLS = path_for("data") / "_source" / "reference" / "dep_wells" / "venango_wells_all.gpkg"
HILL = path_for("data") / "9t" / "derived" / "1m" / "hillshade_9t_1m.tif"
OUT = Path(__file__).resolve().parent / "figures"

DRAKE_LONLAT = (-79.6575, 41.6106)
PA_CRS = "EPSG:6346"

ORPHAN_C, PLUGGED_C, ACTIVE_C = "#D97706", "#1F5FA8", "#5FB4E0"
INK, MUTED, PAPER = "#17222B", "#56626D", "#F5F2EC"
VENANGO_FILL, MCKEAN_FILL, OTHER_FILL = "#1F5FA8", "#5FB4E0", "#E4DFD5"


def locator() -> Path:
    c = gpd.read_file(f"zip://{COUNTIES}")
    pa = c[c.STATEFP == "42"].to_crs(PA_CRS)
    with rasterio.open(HILL) as r:
        tile = gpd.GeoSeries([box(*r.bounds)], crs=r.crs).to_crs(PA_CRS)
    drake = gpd.GeoSeries([Point(*DRAKE_LONLAT)], crs="EPSG:4326").to_crs(PA_CRS)

    fig, ax = plt.subplots(figsize=(12, 7.2), facecolor=PAPER)
    ax.set_facecolor(PAPER)
    pa.plot(ax=ax, color=OTHER_FILL, edgecolor="#FFFFFF", lw=0.8)
    pa[pa.NAME == "Venango"].plot(ax=ax, color=VENANGO_FILL, edgecolor="#FFFFFF", lw=0.8)
    pa[pa.NAME == "McKean"].plot(ax=ax, color=MCKEAN_FILL, edgecolor="#FFFFFF", lw=0.8)
    pa.dissolve().boundary.plot(ax=ax, color=INK, lw=1.2)
    tile.boundary.plot(ax=ax, color=PAPER, lw=1.6)
    drake.plot(ax=ax, marker="*", color=ORPHAN_C, markersize=420, edgecolor=INK, lw=0.8, zorder=5)

    def label(name, dx, dy, text):
        p = pa[pa.NAME == name].geometry.iloc[0].representative_point()
        ax.annotate(text, (p.x, p.y), (p.x + dx, p.y + dy), fontsize=17, color=INK,
                    fontweight="bold", ha="center",
                    arrowprops=dict(arrowstyle="-", color=INK, lw=1))
    label("Venango", -30000, -95000, "Venango County\nour study tiles")
    label("McKean", 30000, 55000, "McKean County\nlidar in hand")
    ax.annotate("Drake Well, 1859", (drake.x.iloc[0], drake.y.iloc[0]),
                (drake.x.iloc[0] + 150000, drake.y.iloc[0] - 70000), fontsize=17, fontweight="bold", color=INK,
                arrowprops=dict(arrowstyle="-", color=INK, lw=1))
    ax.set_axis_off()
    ax.set_aspect("equal")
    fig.tight_layout()
    p = OUT / "pa_counties_venango_mckean_drake_well_locator.png"
    fig.savefig(p, dpi=170, facecolor=PAPER)
    plt.close(fig)
    return p


def wells_on_tile() -> tuple[Path, dict]:
    with rasterio.open(HILL) as r:
        f = 3
        img = r.read(1, out_shape=(r.height // f, r.width // f)).astype(np.float32)
        b = r.bounds
        crs = r.crs
    w = gpd.read_file(WELLS).to_crs(crs)
    w = w[w.within(box(*b))]
    s = w.WELL_STATU
    groups = {
        "Orphan or abandoned": (s.isin(["DEP Orphan List", "DEP Abandoned List", "Abandoned"]),
                                ORPHAN_C, "o"),
        "Plugged": (s.isin(["Plugged OG Well", "DEP Plugged", "Plugged Unverified"]), PLUGGED_C, "s"),
        "Active": (s.eq("Active"), ACTIVE_C, "^"),
    }
    # Records for wells never drilled are left off the map.
    counts = {k: int(m.sum()) for k, (m, _, _) in groups.items()}
    counts["never drilled or not located (not shown)"] = int(
        s.isin(["Operator Reported Not Drilled", "Proposed But Never Materialized",
                "Cannot Be Located"]).sum())

    fig, ax = plt.subplots(figsize=(9, 9), facecolor=PAPER)
    lo, hi = np.nanpercentile(img, [1, 99])
    ax.imshow(img, cmap="gray", vmin=lo, vmax=hi, extent=(b.left, b.right, b.bottom, b.top))
    handles = []
    for k, (m, col, mk) in groups.items():
        g = w[m]
        ax.scatter(g.geometry.x, g.geometry.y, s=26, c=col, marker=mk, edgecolors="#FFFFFF",
                   linewidths=0.5, zorder=3)
        handles.append(Line2D([], [], ls="", marker=mk, color=col, markeredgecolor="#FFFFFF",
                              markersize=11, label=f"{k}  ({counts[k]:,})"))
    ax.plot([b.left + 250, b.left + 1250], [b.bottom + 250] * 2, color="#FFFFFF", lw=4)
    ax.text(b.left + 750, b.bottom + 330, "1 km", color="#FFFFFF", ha="center", fontsize=16,
            fontweight="bold")
    ax.set_xlim(b.left, b.right); ax.set_ylim(b.bottom, b.top)
    ax.set_axis_off()
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=3,
              frameon=False, fontsize=13, handletextpad=0.3, columnspacing=1.2)
    fig.tight_layout()
    p = OUT / "dep_wells_by_status_on_hillshade_9t.png"
    fig.savefig(p, dpi=170, facecolor=PAPER)
    plt.close(fig)
    return p, counts


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("wrote", locator())
    p, counts = wells_on_tile()
    print("wrote", p)
    print(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())

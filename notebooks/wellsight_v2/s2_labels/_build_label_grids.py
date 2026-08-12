"""Build 2x2 derivative grids over the most well-dense areas, for annotation.

Creates label_grids/<region>_NN/ folders, each a contiguous 2x2 tile mosaic with
the 1 m DEM + hillshade + WellSight analytical derivative stack, plus EMPTY
annotation geopackages to draw labels on:
  westernpa_*: pit_inside.gpkg (MultiPolygon), pit_outside.gpkg (Polygon)
  permian_*  : pads.gpkg (Polygon)

Grids are selected to MAXIMIZE known orphan-well count inside the footprint
(orphan wells are the detection targets). WPA wells come from the PA orphan CSV;
Permian wells from the RRC orphan layer.

WPA builds from local LAZ (data/source_laz/westernpa). Permian has no local point
clouds yet -> this script only *selects + reports* the densest Permian 2x2 areas
(by well cluster) so QL1 LAZ can be fetched for them; pass --build-permian once
the LAZ are downloaded into data/source_laz/permian/.

CLI:
  python notebooks/wellsight_v2/s2_labels/_build_label_grids.py --region westernpa --dry-run
  python notebooks/wellsight_v2/s2_labels/_build_label_grids.py --region westernpa
  python notebooks/wellsight_v2/s2_labels/_build_label_grids.py --region permian  --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
# _build_derivatives and _build_3x3_hillshades used to sit in the same folder as
# this file. The 2026-08-12 stage refactor put them in s1_build and this script
# in s2_labels, so the same-directory import no longer resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s1_build"))
from _common import DERIV, DST_CRS, ROOT, run_pdal          # noqa: E402
from _build_derivatives import build as build_derivatives    # type: ignore  # noqa: E402
from _build_3x3_hillshades import (                           # type: ignore  # noqa: E402
    TILE_M, discover_tiles, build_indices, axis_origins,
)

LABEL_GRIDS = ROOT / "label_grids"
PA_WELLS = ROOT / "data" / "external" / "legacy_data" / "US_Documented_Orphan_Wells.csv"
PERMIAN_WELLS = (DERIV / "experiments" / "permian_sample" / "rrc_orphan_wells_permian.gpkg")
RES = 1.0
N_GRIDS = 4
# 9t training core (EPSG:6346) -- exclude so WPA label grids are fresh, non-redundant
EXCLUDE_9T = {"x0": 619500.0, "y0": 4593000.0, "x1": 624000.0, "y1": 4597500.0}


# ===========================================================================
# wells
# ===========================================================================
def load_pa_wells() -> gpd.GeoDataFrame:
    df = pd.read_csv(PA_WELLS)
    df = df.dropna(subset=["Longitude", "Latitude"])
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude),
                         crs="EPSG:4326").to_crs(DST_CRS)
    return g


def load_permian_wells() -> gpd.GeoDataFrame:
    return gpd.read_file(PERMIAN_WELLS).to_crs("EPSG:32613")  # UTM 13N metric for clustering


# ===========================================================================
# WPA: enumerate 2x2 blocks, score by well count, pick non-overlapping
# ===========================================================================
def enumerate_2x2_wpa() -> list[dict]:
    tiles = discover_tiles()
    e_idx, n_idx = build_indices(tiles)
    e_origin, n_origin = axis_origins(e_idx, n_idx)
    grid = {(e_idx[e], n_idx[(b, n)]): p for (b, e, n), p in tiles.items()}
    max_ei = max(k[0] for k in grid); max_ni = max(k[1] for k in grid)
    blocks = []
    for ei0 in range(max_ei):
        for ni0 in range(max_ni):
            cells = [(ei0 + de, ni0 + dn) for de in (0, 1) for dn in (0, 1)]
            members = [grid.get(c) for c in cells]
            if any(m is None for m in members):
                continue
            x0 = e_origin + ei0 * TILE_M
            y0 = n_origin + ni0 * TILE_M
            blocks.append({"ei0": ei0, "ni0": ni0, "members": members,
                           "x0": x0, "y0": y0, "x1": x0 + 2 * TILE_M, "y1": y0 + 2 * TILE_M})
    return blocks


def _overlaps(a, b) -> bool:
    return not (a["x1"] <= b["x0"] or b["x1"] <= a["x0"]
                or a["y1"] <= b["y0"] or b["y1"] <= a["y0"])


def pick_dense(blocks, wells, n) -> list[dict]:
    wx = wells.geometry.x.to_numpy(); wy = wells.geometry.y.to_numpy()
    for b in blocks:
        m = (wx >= b["x0"]) & (wx < b["x1"]) & (wy >= b["y0"]) & (wy < b["y1"])
        b["n_wells"] = int(m.sum())
    blocks.sort(key=lambda b: -b["n_wells"])
    picked: list[dict] = []
    for b in blocks:
        if b["n_wells"] == 0:
            break
        if any(_overlaps(b, p) for p in picked):
            continue
        picked.append(b)
        if len(picked) == n:
            break
    return picked


# ===========================================================================
# build one WPA grid (DEM + hillshade + analytical stack) + empty gpkgs
# ===========================================================================
def build_dem_hillshade(members, x0, y0, x1, y1, sfx, out_dir):
    import whitebox
    out_dir.mkdir(parents=True, exist_ok=True)
    dem_name = f"dem_{sfx}.tif"; hs_name = f"hillshade_{sfx}.tif"
    dem_tif = out_dir / dem_name
    W = int(round((x1 - x0) / RES)); H = int(round((y1 - y0) / RES))
    if dem_tif.exists():
        print(f"  DEM exists, skipping rebuild -> {dem_name}")
    else:
        _build_dem(members, x0, y0, W, H, sfx, dem_tif, out_dir)
    import whitebox
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(out_dir.resolve())); wbt.set_verbose_mode(False)
    rc = wbt.hillshade(dem=dem_name, output=hs_name, azimuth=315.0, altitude=45.0)
    print(f"  hillshade {'ok' if rc == 0 else 'FAILED rc=%d' % rc} -> {hs_name}")
    return dem_tif


def _build_dem(members, x0, y0, W, H, sfx, dem_tif, out_dir):
    stages = [
        *[str(p) for p in members],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster", "resolution": RES,
         "origin_x": x0, "origin_y": y0, "width": W, "height": H},
        {"type": "writers.raster", "filename": str(dem_tif), "data_type": "float32"},
    ]
    print(f"  DEM ({W}x{H}) from {len(members)} tiles ...")
    run_pdal(stages, label=f"dem_{sfx}", tmp_dir=out_dir, timeout=3600)


def stamp_crs(out_dir: Path, crs):
    """Ensure every .tif in out_dir has a CRS (3DEP tiles can lack one)."""
    import rasterio
    from rasterio.crs import CRS
    target = CRS.from_user_input(crs)
    for tif in out_dir.glob("*.tif"):
        with rasterio.open(tif) as r:
            has = r.crs is not None
        if not has:
            with rasterio.open(tif, "r+") as r:
                r.crs = target
            print(f"  stamped CRS on {tif.name}")


def write_empty(path: Path, geom_type: str, cols: dict, crs):
    # an empty gpkg has no geometry -> it is location-independent; never clobber an
    # existing one (the user may have it open in QGIS, which locks the file on Windows)
    if path.exists():
        print(f"  gpkg exists, keeping -> {path.name}")
        return
    import pyogrio
    data = {c: gpd.pd.Series([], dtype=t) for c, t in cols.items()}
    gdf = gpd.GeoDataFrame(data, geometry=gpd.GeoSeries([], crs=crs))
    pyogrio.write_dataframe(gdf, path, layer=path.stem, geometry_type=geom_type)


def build_wpa(args):
    wells = load_pa_wells()
    blocks = enumerate_2x2_wpa()
    n_all = len(blocks)
    blocks = [b for b in blocks if not _overlaps(b, EXCLUDE_9T)]
    print(f"WPA: {len(blocks)} candidate 2x2 blocks ({n_all-len(blocks)} dropped for 9t-core "
          f"overlap), {len(wells)} PA orphan wells")
    picked = pick_dense(blocks, wells, args.n)
    print(f"\n== selected {len(picked)} well-dense WPA 2x2 grids ==")
    for i, b in enumerate(picked, 1):
        print(f"  westernpa_{i:02d}: {b['n_wells']:4d} wells  "
              f"x={b['x0']:.0f}..{b['x1']:.0f} y={b['y0']:.0f}..{b['y1']:.0f}  "
              f"tiles={[p.name.split('D20_')[1][:9] for p in b['members']]}")
    if args.dry_run:
        return
    for i, b in enumerate(picked, 1):
        name = f"westernpa_{i:02d}"; sfx = f"{name}_1m"
        out_dir = LABEL_GRIDS / name
        print(f"\n========== {name}  ({b['n_wells']} wells) ==========")
        t0 = time.time()
        merge = ROOT / "data" / "source_laz" / "westernpa" / f"_merged_{sfx}.las"
        try:
            build_dem_hillshade(b["members"], b["x0"], b["y0"], b["x1"], b["y1"], sfx, out_dir)
            build_derivatives(b["members"], x0=b["x0"], y0=b["y0"], x1=b["x1"], y1=b["y1"],
                              res=RES, sfx=sfx, dst_crs=DST_CRS, merge_path=merge,
                              skip_existing=True, out_dir=out_dir)
        except Exception as e:  # noqa: BLE001
            print(f"  [{name}] FAILED: {e}"); continue
        finally:
            if merge.exists():
                try: merge.unlink()
                except OSError: pass
        write_empty(out_dir / f"{name}_pit_inside.gpkg", "MultiPolygon",
                    {"pit_id": "int64", "plat_id": "int64"}, DST_CRS)
        write_empty(out_dir / f"{name}_pit_outside.gpkg", "Polygon",
                    {"pit_id": "int64", "plat_id": "int64"}, DST_CRS)
        print(f"  [{name}] done in {time.time()-t0:.0f}s "
              f"(+ empty {name}_pit_inside/{name}_pit_outside gpkgs)")
    print(f"\nWPA grids in {LABEL_GRIDS}")


# ===========================================================================
# WPA manual placement: explicit 2x2 sub-block of a named 3x3 section
# ===========================================================================
# corner -> (de set, dn set) of the 2x2 within the section's 3x3 (de=E, dn=N)
_CORNER = {"NE": ((1, 2), (1, 2)), "NW": ((0, 1), (1, 2)),
           "SE": ((1, 2), (0, 1)), "SW": ((0, 1), (0, 1))}
MANUAL_WPA = {
    "westernpa_03": ("613590", "NE"),  # NE 2x2 of 613590 section
    "westernpa_04": ("622599", "NW"),  # NW 2x2 of 622599 section
}


def _resolve_2x2(section_key: str, corner: str):
    """Return (members[4], x0, y0, x1, y1) for a 2x2 corner of a 3x3 section."""
    tiles = discover_tiles()
    e_idx, n_idx = build_indices(tiles)
    e_org, n_org = axis_origins(e_idx, n_idx)
    grid = {(e_idx[e], n_idx[(b, n)]): p for (b, e, n), p in tiles.items()}
    ec, nc = section_key[:3], section_key[3:]
    sw = next(((b, e, n) for (b, e, n) in tiles if e == ec and n == nc), None)
    if sw is None:
        raise SystemExit(f"section {section_key} SW tile not found")
    ei0, ni0 = e_idx[sw[1]], n_idx[(sw[0], sw[2])]
    des, dns = _CORNER[corner]
    cells = [(ei0 + de, ni0 + dn) for de in des for dn in dns]
    members = [grid.get(c) for c in cells]
    if any(m is None for m in members):
        miss = [c for c, m in zip(cells, members) if m is None]
        raise SystemExit(f"section {section_key} {corner} 2x2 missing tiles at idx {miss}")
    ei_sw, ni_sw = min(des), min(dns)
    x0 = e_org + (ei0 + ei_sw) * TILE_M
    y0 = n_org + (ni0 + ni_sw) * TILE_M
    return members, x0, y0, x0 + 2 * TILE_M, y0 + 2 * TILE_M


def build_wpa_manual(args):
    names = args.only.split(",") if args.only else list(MANUAL_WPA)
    for name in names:
        section, corner = MANUAL_WPA[name]
        members, x0, y0, x1, y1 = _resolve_2x2(section, corner)
        sfx = f"{name}_1m"; out_dir = LABEL_GRIDS / name
        print(f"\n========== {name}  ({corner} 2x2 of {section}) ==========")
        print(f"  x={x0:.0f}..{x1:.0f} y={y0:.0f}..{y1:.0f}  "
              f"tiles={[p.name.split('D20_')[1][:9] for p in members]}")
        if args.dry_run:
            continue
        # remove stale derivatives from the old density-picked location
        for old in out_dir.glob("*.tif"):
            old.unlink()
        for old in out_dir.glob("*.tif.aux.xml"):
            old.unlink()
        t0 = time.time()
        merge = ROOT / "data" / "source_laz" / "westernpa" / f"_merged_{sfx}.las"
        try:
            build_dem_hillshade(members, x0, y0, x1, y1, sfx, out_dir)
            build_derivatives(members, x0=x0, y0=y0, x1=x1, y1=y1, res=RES, sfx=sfx,
                              dst_crs=DST_CRS, merge_path=merge, skip_existing=False,
                              out_dir=out_dir)
        except Exception as e:  # noqa: BLE001
            print(f"  [{name}] FAILED: {e}"); continue
        finally:
            if merge.exists():
                try: merge.unlink()
                except OSError: pass
        write_empty(out_dir / f"{name}_pit_inside.gpkg", "MultiPolygon",
                    {"pit_id": "int64", "plat_id": "int64"}, DST_CRS)
        write_empty(out_dir / f"{name}_pit_outside.gpkg", "Polygon",
                    {"pit_id": "int64", "plat_id": "int64"}, DST_CRS)
        print(f"  [{name}] done in {time.time()-t0:.0f}s")
    print(f"\nWPA manual grids in {LABEL_GRIDS}")


# ===========================================================================
# Permian: select densest well clusters (no local LAZ -> report for download)
# ===========================================================================
def select_permian(args):
    wells = load_permian_wells()
    wx = wells.geometry.x.to_numpy(); wy = wells.geometry.y.to_numpy()
    grid_m = 3000.0  # 2x2 of 1.5km tiles
    # bin wells into a 3km grid, find densest non-adjacent cells
    gi = np.floor(wx / grid_m).astype(int); gj = np.floor(wy / grid_m).astype(int)
    from collections import Counter
    cnt = Counter(zip(gi.tolist(), gj.tolist()))
    cells = sorted(cnt.items(), key=lambda kv: -kv[1])
    picked = []
    for (ci, cj), c in cells:
        if any(abs(ci - pi) <= 1 and abs(cj - pj) <= 1 for (pi, pj), _ in picked):
            continue
        picked.append(((ci, cj), c))
        if len(picked) == args.n:
            break
    print(f"PERMIAN: {len(wells)} RRC orphan wells; densest {args.n} 3km cells "
          f"(EPSG:32613 UTM13N):")
    for k, ((ci, cj), c) in enumerate(picked, 1):
        x0, y0 = ci * grid_m, cj * grid_m
        cx, cy = x0 + grid_m / 2, y0 + grid_m / 2
        lon, lat = gpd.GeoSeries([gpd.points_from_xy([cx], [cy])[0]], crs=32613
                                 ).to_crs(4326).geometry.iloc[0].coords[0]
        print(f"  permian_{k:02d}: {c:4d} wells  x={x0:.0f}..{x0+grid_m:.0f} "
              f"y={y0:.0f}..{y0+grid_m:.0f}  center=({lat:.4f},{lon:.4f})")
    print("\nNote: no local Permian LAZ. Next step = fetch USGS 3DEP QL1 tiles "
          "covering these centers, then re-run with --build-permian.")


def build_permian(args):
    """Mosaic each downloaded grid (native UTM) -> DEM+hillshade+stack + empty pads gpkg.

    Tile count per grid is whatever was downloaded (now 3x3 = 9 tiles); this globs
    *.laz so it is agnostic to grid size."""
    import json
    import laspy
    src = ROOT / "data" / "source_laz" / "permian"
    manifest = json.loads((src / "permian_grids_manifest.json").read_text())
    for name, info in manifest.items():
        if args.only and name not in args.only.split(","):
            continue
        gdir = src / name
        laz = sorted(gdir.glob("*.laz"))
        if len(laz) < 1:
            print(f"[{name}] no LAZ downloaded yet -> skip"); continue
        # union bbox + native EPSG from headers
        mins = np.array([np.inf, np.inf]); maxs = np.array([-np.inf, -np.inf]); epsg = None
        for p in laz:
            with laspy.open(p) as f:
                h = f.header
                mins = np.minimum(mins, h.mins[:2]); maxs = np.maximum(maxs, h.maxs[:2])
                if epsg is None:
                    try: epsg = h.parse_crs().to_epsg()
                    except Exception: epsg = None
        if epsg is None:
            epsg = {"13": 6342, "14": 6343}.get(info.get("utm_zone"), 6343)
        dst = f"EPSG:{epsg}"
        x0, y0 = float(np.floor(mins[0])), float(np.floor(mins[1]))
        x1, y1 = float(np.ceil(maxs[0])), float(np.ceil(maxs[1]))
        sfx = f"{name}_1m"; out_dir = LABEL_GRIDS / name
        print(f"\n========== {name}  ({len(laz)} tiles, {dst}) ==========")
        print(f"  bbox {x0:.0f},{y0:.0f}..{x1:.0f},{y1:.0f}")
        t0 = time.time(); merge = gdir / f"_merged_{sfx}.las"
        # clear stale derivatives from any prior (different-location) build
        for old in out_dir.glob("*.tif"):
            old.unlink()
        for old in out_dir.glob("*.tif.aux.xml"):
            old.unlink()
        # build_derivatives owns dem+hillshade+slope+stack; it builds the DEM from
        # the merged LAS (tagged a_srs=dst), so the DEM gets a CRS even though the
        # raw 3DEP tiles carry none. skip_existing=False to overwrite stale outputs.
        # dem_method="gdal": dense QL1 3x3 mosaics OOM the delaunay TIN -> use IDW.
        try:
            build_derivatives(laz, x0=x0, y0=y0, x1=x1, y1=y1, res=RES, sfx=sfx,
                              dst_crs=dst, merge_path=merge, skip_existing=False,
                              out_dir=out_dir, dem_method="gdal",
                              openness_only=args.openness_only)
        except Exception as e:  # noqa: BLE001
            print(f"  [{name}] FAILED: {e}"); continue
        finally:
            if merge.exists():
                try: merge.unlink()
                except OSError: pass
        stamp_crs(out_dir, dst)
        write_empty(out_dir / f"{name}_pads.gpkg", "Polygon",
                    {"pad_id": "int64", "note": "object"}, dst)
        print(f"  [{name}] done in {time.time()-t0:.0f}s (+ empty {name}_pads gpkg)")
    print(f"\nPermian grids in {LABEL_GRIDS}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", choices=["westernpa", "permian"], required=True)
    ap.add_argument("--n", type=int, default=N_GRIDS)
    ap.add_argument("--dry-run", action="store_true", help="select + report, do not build")
    ap.add_argument("--build-permian", action="store_true",
                    help="build from downloaded data/source_laz/permian/<grid>/ tiles")
    ap.add_argument("--manual", action="store_true",
                    help="WPA: build explicit MANUAL_WPA 2x2 placements instead of density pick")
    ap.add_argument("--openness-only", action="store_true",
                    help="permian: emit only DEM + openness_pos/neg (skip full stack)")
    ap.add_argument("--only", help="comma-separated grid names")
    args = ap.parse_args()
    LABEL_GRIDS.mkdir(exist_ok=True)
    if args.region == "westernpa" and args.manual:
        build_wpa_manual(args)
    elif args.region == "westernpa":
        build_wpa(args)
    elif args.build_permian:
        build_permian(args)
    else:
        select_permian(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

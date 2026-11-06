"""3.1 S3. Rebuild the 0.5 m model stack on native target points with the 9t builder.

Purpose
    The frozen models read seven 0.5 m channels (features_pit_9t_05.tif). Warren and McKean
    derivatives on disk are 1 m from another pipeline, so they are not used. This stage calls
    notebooks/wellsight_v2/s1_build/_build_derivatives.py with --res 0.5 on the native tiles
    (reprojecting McKean from EPSG:6350), then adds roughness_11 (11-cell std at 0.5 m, the
    builder formula with win = 11), stacks the seven channels in checkpoint order with band
    descriptions, writes a void raster (no ground return in the cell), and asserts the band
    order equals features_pit_9t_05.tif. Thinning to 9t density is a separate sensitivity arm
    (3.2 _appal_thin_density_arm.py), never this stage.
    --check-9t rebuilds the channels on a 9t crop from dem_9t_05.tif and compares them with
    the stored 9t stack band by band (cheap QC of the recompute path).

Bootstrap rule
    Default is a dry run that prints the builder command. --block-id builds one block plus a
    128 m margin first, to time it. --execute runs the builder. Full-area builds are expensive.

Inputs
    S0 inventory, S1 roles gpkg, tiles (config areas.<area>.tiles), the 9t stack for the order check

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/data/processed/<area>/05/   (gitignored, heavy)
        dem_<sfx>.tif ... openness_neg_<sfx>.tif (builder outputs), roughness_11_<sfx>.tif,
        features_pit_<sfx>.tif (7 bands), void_<sfx>.tif (uint8, 1 = no ground return)
    .../results/tables/<area>/xfer_build_derivs_<sfx>.json   (command, timing, channel check)
    .../results/tables/<area>/xfer_recompute_check_9t.json   (--check-9t only)
    <sfx> is <area>_05, or <area>_b<block>_05 for a one-block timing build.

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_build_derivs_wfm.py --area warren --check-9t
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_build_derivs_wfm.py --area warren --block-id 40 --execute
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_build_derivs_wfm.py --area mckean --execute
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
from _xfer_tile_inventory_wfm import footprint_6346  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"
BUILDER = xl.NB / "s1_build" / "_build_derivatives.py"
MARGIN_M = 128.0


def stack_channels(d: Path, sfx: str, channels, out: Path) -> Path:
    import rasterio
    from _common import make_profile
    paths = [d / f"{c}_{sfx}.tif" for c in channels]
    for p in paths:
        xl.need(p, f"channel raster {p.name}", "builder output missing")
    with rasterio.open(paths[0]) as r0:
        ek.assert_crs(r0)
        prof = make_profile(width=r0.width, height=r0.height, transform=r0.transform, crs=r0.crs,
                            dtype="float32", nodata=np.nan, count=len(paths), bigtiff=True)
    with rasterio.open(out, "w", **prof) as dst:
        for i, (c, p) in enumerate(zip(channels, paths), start=1):
            with rasterio.open(p) as r:
                a = r.read(1).astype(np.float32)
                if r.nodata is not None:
                    a = np.where(a == r.nodata, np.nan, a)
            dst.write(a, i)
            dst.set_band_description(i, c)
    return out


def post_build(d: Path, sfx: str, channels, ref_features: Path) -> dict:
    """roughness_11, 7-band stack, void raster, order assertion."""
    import rasterio
    from _common import write_tif
    with rasterio.open(d / f"dem_{sfx}.tif") as r:
        dem = r.read(1).astype(np.float32)
        if r.nodata is not None:
            dem[dem == r.nodata] = np.nan
        tf, crs = r.transform, r.crs
    write_tif(d / f"roughness_11_{sfx}.tif", xl.roughness_std(dem, 11), transform=tf, crs=crs)
    feats = stack_channels(d, sfx, channels, d / f"features_pit_{sfx}.tif")
    with rasterio.open(d / f"ground_density_{sfx}.tif") as r:
        void = (r.read(1) == 0).astype(np.uint8)
    write_tif(d / f"void_{sfx}.tif", void, transform=tf, crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(ref_features) as a, rasterio.open(feats) as b:
        if tuple(a.descriptions) != tuple(b.descriptions):
            raise AssertionError(f"channel order {b.descriptions} != 9t {a.descriptions}")
        if a.res != b.res:
            raise AssertionError(f"resolution {b.res} != 9t {a.res}")
    return {"features": str(feats), "void_frac": float(void.mean()), "channels": list(channels),
            "dem_nan_frac": float(np.isnan(dem).mean())}


def check_9t(cfg, out_json: Path, size: int = 600) -> dict:
    """Recompute the seven channels on a 9t crop and compare with the stored 9t stack."""
    import rasterio
    from rasterio.windows import Window
    channels_from_dem = xl.channels_from_dem
    feats = xl.need(xl.resolve_path(cfg["reference"]["features_9t"]), "9t feature stack")
    dem_p = feats.parent / "dem_9t_05.tif"
    w = Window(4000, 4000, size, size)
    with rasterio.open(dem_p) as r:
        dem = r.read(1, window=w).astype(np.float32)
    with rasterio.open(feats) as r:
        ref = r.read(window=w).astype(np.float32)
        names = r.descriptions
    ch = channels_from_dem(dem, 0.5)
    m = (slice(60, -60), slice(60, -60))   # drop window-edge effects
    rows = {}
    for i, n in enumerate(names):
        a, b = ch[i][m].ravel(), ref[i][m].ravel()
        ok = np.isfinite(a) & np.isfinite(b)
        rows[n] = {"r": float(np.corrcoef(a[ok], b[ok])[0, 1]), "max_abs_diff": float(np.abs(a[ok] - b[ok]).max()),
                   "median_abs_diff": float(np.median(np.abs(a[ok] - b[ok])))}
    out_json.write_text(json.dumps({"crop": [4000, 4000, size, size], "bands": rows}, indent=2), encoding="utf-8")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--block-id", type=int, default=None, help="build one block plus margin (timing)")
    ap.add_argument("--bbox", default=None, help="override x0,y0,x1,y1 (EPSG:6346)")
    ap.add_argument("--execute", action="store_true", help="run the builder (expensive)")
    ap.add_argument("--post-only", action="store_true", help="skip the builder, redo stack and checks")
    ap.add_argument("--check-9t", action="store_true", help="QC of the channel recompute on 9t, then exit")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    if a.check_9t:
        o = ctx["tables"] / "xfer_recompute_check_9t.json"
        print(json.dumps(check_9t(cfg, o), indent=2))
        print(f"wrote {o}")
        return 0
    inv = pd.read_csv(xl.need(ctx["tables"] / f"xfer_tile_inventory_{a.area}.csv", "S0 inventory"))
    if a.bbox:
        bbox = tuple(float(v) for v in a.bbox.split(","))
        sfx = f"{a.area}_bbox_05"
    else:
        import geopandas as gpd
        b = gpd.read_file(xl.need(ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg", "S1 roles"), layer="blocks")
        if a.block_id is not None:
            sel = b[b.block_id == a.block_id]
            if not len(sel):
                raise KeyError(f"block {a.block_id} not in S1 roles")
            sfx = f"{a.area}_b{a.block_id}_05"
        else:
            sel = b[b.role != "ineligible"]
            sfx = f"{a.area}_05"
        x0, y0, x1, y1 = sel.total_bounds
        bbox = (x0 - MARGIN_M, y0 - MARGIN_M, x1 + MARGIN_M, y1 + MARGIN_M)
    bbox = tuple(float(np.round(v / 0.5) * 0.5) for v in bbox)
    from shapely.geometry import box
    q = box(*bbox)
    use = [r["file"] for r in inv.to_dict("records")
           if footprint_6346(r, None if pd.isna(r["crs_epsg"]) else int(r["crs_epsg"])).intersects(q)]
    tiles = [t for t in ctx["tiles"] if t.name in set(use)]
    out_dir = ctx["heavy"]
    cmd = [sys.executable, str(BUILDER), "--tiles", ",".join(str(t) for t in tiles),
           "--bbox", ",".join(f"{v:.1f}" for v in bbox), "--suffix", sfx, "--res", "0.5",
           "--out-dir", str(out_dir), "--merge-path", str(out_dir / f"_merged_{sfx}.las")]
    if ctx["src_crs"]:
        cmd += ["--src-crs", ctx["src_crs"]]
    rec = {"area": a.area, "sfx": sfx, "bbox": bbox, "n_tiles": len(tiles), "cmd": cmd,
           "area_km2": (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) / 1e6}
    print(f"{len(tiles)} tiles, bbox {bbox} ({rec['area_km2']:.2f} km2)\n  " + " ".join(cmd[:2] + ["..."] + cmd[4:]))
    if not (a.execute or a.post_only):
        print("dry run (pass --execute to build; time one block first with --block-id)")
        return 0
    t0 = time.time()
    if a.execute and not a.post_only:
        r = subprocess.run(cmd, cwd=str(ek.REPO))
        if r.returncode:
            raise RuntimeError(f"builder failed rc={r.returncode}")
    rec["builder_sec"] = round(time.time() - t0, 1)
    rec.update(post_build(out_dir, sfx, cfg["builders"]["channels"], xl.resolve_path(cfg["reference"]["features_9t"])))
    rec["total_sec"] = round(time.time() - t0, 1)
    js = ctx["tables"] / f"xfer_build_derivs_{sfx}.json"
    js.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in rec.items() if k != "cmd"}, indent=2, default=str))
    print(f"wrote {out_dir}\n      {js}\nRun the >100 MB audit (CLAUDE.md Large-file rule) now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build the full-code + full-metadata appendix for the NISAR 9t pipeline. Set 2026-11-26.

Why: nisar/docs/nisar_pipeline_spec_9t.md is the terse spec. This dumps everything behind it, machine
generated so nothing is retyped: per-granule metadata (index + RSLC HDF5 identification/parameters/orbit),
raster profiles, vector schemas, DEP status counts, every current result file, and the full source of
every pipeline script. Always the lidar-placed stack (NISAR_STACK=slc).
Out: nisar/docs/nisar_pipeline_appendix_9t.md
Run: python nisar/code/s7_analysis/_nisar_pipeline_appendix_9t.py
"""
import os
import sys
from pathlib import Path

import geopandas as gpd
import h5py
import numpy as np
import pandas as pd
import rasterio

os.environ["NISAR_STACK"] = "slc"
ROOT = Path(__file__).resolve().parents[3]
N = ROOT / "nisar"
sys.path.insert(0, str(N / "code"))
import _nisar_area as A  # noqa: E402
from _common import path_for  # noqa: E402

OUT = N / "docs" / "nisar_pipeline_appendix_9t.md"
SCRIPTS = [
    "nisar/code/_nisar_area.py", "nisar/code/s5_eval/_nisar_processor_step_9t.py", "nisar/code/_nisar_fig_style.py", "notebooks/wellsight_v2/_common.py",
    "nisar/code/s1_build/_fetch_nisar_gslc_window_9t.py", "nisar/code/s1_build/_fetch_nisar_rslc_window_9t.py",
    "nisar/code/s1_build/_nisar_geometry.py", "nisar/code/s1_build/_nisar_regeocode_lidar_9t.py",
    "nisar/code/s5_eval/_nisar_lidar_sim_match_9t.py", "nisar/code/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py",
    "nisar/code/s5_eval/_nisar_gslc_interferogram_pits_9t.py", "nisar/code/s5_eval/_nisar_steel_9t.py",
    "nisar/code/s5_eval/_nisar_steel_pads_9t.py", "nisar/code/s5_eval/_nisar_bright_targets_9t.py",
    "nisar/code/s5_eval/_nisar_pad_change_9t.py", "nisar/code/s5_eval/_nisar_pit_pool_9t.py",
    "nisar/code/s5_eval/_nisar_slope_motion_9t.py", "nisar/code/s7_analysis/_nisar_naip_chips_9t.py",
    "nisar/code/s7_analysis/_nisar_steel_pads_fig_9t.py", "nisar/code/s7_analysis/_nisar_pipeline_appendix_9t.py",
]
RESULTS = [
    "nisar_processor_step_summary_9t_slc.json", "nisar_lidar_sim_match_summary_coregabs_k010_9t.json", "nisar_steel_summary_9t_slc.json",
    "nisar_steel_pads_summary_9t_slc.json", "nisar_bright_targets_summary_9t_slc.json",
    "nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_9t_slc_5m.json", "nisar_pad_change_summary_9t_slc.json",
    "nisar_gslc_interferogram_pits_vs_decoys_win3_9t_slc_5m_summary.json", "nisar_slope_motion_summary_9t_slc.json",
]
CSVS = ["nisar_steel_by_canopy_9t_slc.csv", "nisar_pad_change_by_season_9t_slc.csv", "nisar_pit_pool_radar_9t.csv",
        "nisar_top_targets_naip_classes_9t.csv", "nisar_slc_date_offsets_9t.csv", "nisar_slc_track_offsets_9t.csv"]
RUN = [
    "python nisar/code/s1_build/_fetch_nisar_gslc_window_9t.py",
    "python nisar/code/s1_build/_fetch_nisar_rslc_window_9t.py",
    "python nisar/code/s1_build/_nisar_regeocode_lidar_9t.py --v1 <pairs>          # reproduce NASA GSLC first",
    "python nisar/code/s1_build/_nisar_regeocode_lidar_9t.py --heights lidar --write",
    "python nisar/code/s1_build/_nisar_regeocode_lidar_9t.py --estimate-offsets",
    "python nisar/code/s1_build/_nisar_regeocode_lidar_9t.py --heights lidar --write --coreg",
    "python nisar/code/s5_eval/_nisar_lidar_sim_match_9t.py --stack lidar --kappa 0.1",
    "python nisar/code/s1_build/_nisar_regeocode_lidar_9t.py --track-offsets _coreg_k010",
    "python nisar/code/s1_build/_nisar_regeocode_lidar_9t.py --heights lidar --write --coreg --absolute",
    "python nisar/code/s5_eval/_nisar_lidar_sim_match_9t.py --stack lidar --kappa 0.1   # check -> coregabs_k010",
    "python nisar/code/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_gslc_interferogram_pits_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_steel_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_steel_pads_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_bright_targets_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_pad_change_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_processor_step_9t.py --slc",
    "python nisar/code/s5_eval/_nisar_pit_pool_9t.py",
    "python nisar/code/s5_eval/_nisar_slope_motion_9t.py --slc",
    "python nisar/code/s7_analysis/_nisar_naip_chips_9t.py",
    "python nisar/code/s7_analysis/_nisar_steel_pads_fig_9t.py",
    "python nisar/code/s7_analysis/_nisar_pipeline_appendix_9t.py",
]


def val(d):
    v = d[()]
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    if isinstance(v, np.ndarray):
        if v.dtype.kind == "S":
            v = [x.decode(errors="replace") for x in v.ravel()]
            return v if len(v) > 1 else v[0]
        return v.tolist()
    return v.item() if hasattr(v, "item") else v


def attrs(o):
    out = {}
    for k, v in o.attrs.items():
        out[k] = v.decode(errors="replace") if isinstance(v, bytes) else (v.tolist() if hasattr(v, "tolist") else v)
    return out


def h5dump(path, w, full_runconfig):
    with h5py.File(path, "r") as h:
        def visit(name, o):
            if not isinstance(o, h5py.Dataset):
                return
            if name.endswith("runConfigurationContents"):
                if full_runconfig:
                    w(f"- `{name}` (processor run configuration, verbatim):\n```yaml\n{val(o)}\n```")
                return
            if o.size > 12 and o.dtype.kind in "fciu":
                s = f"{o.dtype} {o.shape}"
                if o.size < 5e6 and o.dtype.kind != "c":
                    a = o[()]
                    s += f" min={np.nanmin(a):.6g} max={np.nanmax(a):.6g}"
            else:
                s = repr(val(o))
            at = attrs(o)
            w(f"- `{name}`: {s}" + (f" | attrs {at}" if at else ""))
        h.visititems(visit)


def main():
    L = []
    w = L.append
    w("# NISAR 9t pipeline appendix: full metadata, processes and code\n")
    w("Machine generated by `nisar/code/s7_analysis/_nisar_pipeline_appendix_9t.py`. Read with "
      "`nisar/docs/nisar_pipeline_spec_9t.md` (spec) and `nisar/docs/nisar_technical_writeup_9t.md` (narrative). "
      "Findings use only post-2026-06-01 9t data on the lidar-placed stack. No credentials included.\n")
    w("Contents: 1 granule index | 2 RSLC HDF5 metadata per granule | 3 GSLC + SLC raster metadata | "
      "4 lidar raster metadata | 5 vector schemas | 6 run order | 7 result files verbatim | 8 full source code\n")

    idx = A.usable(pd.read_csv(A.INDEX))
    w(f"## 1. Granule index (lidar-placed stack, used rows)\nSource `{A.INDEX.relative_to(ROOT).as_posix()}`. {len(idx)} rows.\n")
    w(idx.to_markdown(index=False))
    g = pd.read_csv(N / "derived/9t/nisar_gslc_5m/nisar_gslc_window_index_9t_5m.csv")
    w(f"\nAll GSLC windows held, including excluded: {len(g)} rows. By collection and track:\n")
    w(g.groupby(["collection", "track"]).size().rename("n").reset_index().to_markdown(index=False))
    ex = g[~g.index.isin(A.usable(g).index)]
    cols = [c for c in ["file", "date", "collection", "track", "frame", "valid_fraction"] if c in ex]
    w("\nExcluded GSLC windows (before DATE_FLOOR, <50% valid, or BAD_DATES):\n")
    w(ex[cols].to_markdown(index=False))

    w("\n## 2. RSLC HDF5 metadata, per used granule\nWindow files hold NASA groups copied whole: identification, orbit, "
      "attitude, parameters (processingInformation/parameters), plus geolocationGrid and gslcTimingCorrections cut to the "
      "window. Large arrays summarised as dtype, shape, min, max. Processor run configuration printed once.\n")
    first = True
    for _, r in idx.iterrows():
        p = A.RSLC / str(r.rslc)
        if not p.exists():
            w(f"### {r.rslc}\nmissing on disk\n")
            continue
        w(f"### {r.date} track {r.track}{r.direction} `{p.relative_to(ROOT).as_posix()}`\n")
        h5dump(p, w, first)
        first = False
        w("")

    w("## 3. Raster metadata: GSLC window and lidar-placed SLC (one each; every date shares the grid)\n")
    used_g = A.usable(g)
    for p in [N / "derived/9t/nisar_gslc_5m" / used_g.file.iloc[-1], A.GSLC / idx.file.iloc[0]]:
        with rasterio.open(p) as s:
            pr = {k: str(v) for k, v in s.profile.items()}
            w(f"- `{p.relative_to(ROOT).as_posix()}`\n  - profile {pr}\n  - bounds {tuple(s.bounds)}\n"
              f"  - tags {s.tags()}\n  - band descriptions {s.descriptions}\n")

    w("## 4. Lidar, DEM and imagery rasters\n")
    for nm in ["dem", "chm", "slope", "hillshade"]:
        p = A.lidar(nm)
        if p.exists():
            with rasterio.open(p) as s:
                w(f"- `{nm}` `{p}`: crs {s.crs.to_string()}, res {s.res}, size {s.width}x{s.height}, "
                  f"dtype {s.dtypes[0]}, nodata {s.nodata}, bounds {tuple(round(b, 2) for b in s.bounds)}")
    rr = path_for("derived") / "9t" / "derived" / "05" / "rrim_openness_9t_05.tif"
    if rr.exists():
        with rasterio.open(rr) as s:
            w(f"- `rrim 0.5 m` `{rr}`: crs {s.crs.to_string()}, res {s.res}, size {s.width}x{s.height}, "
              f"bands {s.count} {s.dtypes[0]}")
    dem = N / "derived/9t/nisar_dem/DEM_N41_00_W080_00_C01.tif"
    if dem.exists():
        with rasterio.open(dem) as s:
            w(f"- `NISAR DEM v1.2` `{dem.relative_to(ROOT).as_posix()}`: crs {s.crs.to_string()}, res {s.res}, "
              f"size {s.width}x{s.height}, dtype {s.dtypes[0]}")
    w("- NAIP: Planetary Computer STAC collection `naip`, 2022-06-19 over the 9t bbox, 0.6 m, 4-band uint8, "
      "NAD83 UTM 17N, read live through /vsicurl with an anonymous SAS token.\n")

    w("## 5. Vector data schemas and counts\n")
    ann = path_for("truth") / "annotations_proj.gpkg"
    for lay in ["plat", "pit_outside", "roads"]:
        try:
            d = gpd.read_file(ann, layer=lay)
            w(f"- `{ann.name}` layer `{lay}`: {len(d)} features, crs {d.crs}, geom {sorted(d.geom_type.unique())}, "
              f"columns {list(d.columns)}")
        except Exception as e:  # noqa: BLE001
            w(f"- layer {lay}: unreadable ({e})")
    wl = gpd.read_file(A.WELLS)
    b = A.bounds()
    w9 = wl.to_crs("EPSG:32617").cx[b[0]:b[2], b[1]:b[3]]
    w(f"- DEP wells `{A.WELLS.name}` (data/_source/reference/dep_wells/): {len(wl)} rows in export, {len(w9)} inside "
      f"9t lidar bounds, crs {wl.crs}, columns {list(wl.columns)}\n")
    w("WELL_STATU counts inside 9t lidar bounds:\n")
    w(w9.WELL_STATU.value_counts().rename_axis("WELL_STATU").reset_index().to_markdown(index=False))
    for f in ["nisar_steel_pads_sites_9t_slc.gpkg", "nisar_bright_targets_points_9t_slc.gpkg",
              "nisar_dep_well_pad_distance_9t.gpkg"]:
        p = A.RESULTS / f
        if p.exists():
            d = gpd.read_file(p)
            w(f"\n- `nisar/results/9t/{f}`: {len(d)} rows, columns {list(d.columns)}")

    w("\n## 6. Run order (reproduce from scratch)\n```")
    for c in RUN:
        w(c)
    w("```\nEnvironment: Python 3.13; h5py, fsspec + aiohttp, requests, rasterio/GDAL, geopandas, shapely, scipy, numpy, "
      "pandas, matplotlib. Earthdata login in ~/_netrc.\n")

    w("## 7. Result files (verbatim)\n")
    for f in RESULTS:
        p = A.RESULTS / f
        if p.exists():
            w(f"### nisar/results/9t/{f}\n```json\n{p.read_text(encoding='utf-8')}\n```")
    for f in CSVS:
        p = A.RESULTS / f
        if p.exists():
            w(f"### nisar/results/9t/{f}\n```csv\n{p.read_text(encoding='utf-8')}\n```")

    w("## 8. Full source code\n")
    for s in SCRIPTS:
        p = ROOT / s
        w(f"### {s}\n```python\n{p.read_text(encoding='utf-8')}\n```" if p.exists() else f"### {s}\nnot found")
    OUT.write_text("\n".join(str(x) for x in L), encoding="utf-8")
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

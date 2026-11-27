"""Build the full-metadata + full-code appendix for the lidar pit / pad / road pipeline. Set 2026-11-26.

Why: docs/lidar_methodology_brief.md is the terse methodology. This dumps everything behind it, machine
generated so nothing is retyped: source tile index, raster profiles, checkpoint contents, annotation
schemas and counts, fold tables, result files verbatim, run order and the full source of every
script in the chain. The raw LAZ tiles are not on disk (offloaded), so source-lidar metadata comes from
data/_source/lidar/laz_tile_index.csv, not from LAS headers.
Out: docs/lidar_methodology_appendix.md
Run: python notebooks/wellsight_v2/s7_analysis/_lidar_methodology_appendix.py
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lidar_methodology_appendix.md"
B9T = (619500, 4593000, 624000, 4597500)
B613 = (613500, 4590000, 618000, 4594500)
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"

SCRIPTS = [
    "notebooks/wellsight_v2/_common.py", "notebooks/wellsight_v2/_dl.py",
    "notebooks/wellsight_v2/s1_build/_build_derivatives.py", "notebooks/wellsight_v2/s1_build/_make_rrim.py",
    "notebooks/wellsight_v2/s1_build/_build_extra_channels.py",
    "notebooks/wellsight_v2/s2_labels/_build_label_grids.py", "notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py",
    "notebooks/wellsight_v2/s2_labels/_build_pad_road_dataset.py", "notebooks/wellsight_v2/s2_labels/_build_unified_split.py",
    "notebooks/wellsight_v2/s2_labels/_prep_road_1m.py",
    "notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py", "notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py",
    "notebooks/wellsight_v2/s3_train/_road_unet_1m_recall.py", "notebooks/wellsight_v2/s3_train/_drainage_unet_1m.py",
    "notebooks/wellsight_v2/s4_infer/_infer_pit_pad_613590_05.py",
    "notebooks/wellsight_v2/s5_eval/_threshold_common.py", "notebooks/wellsight_v2/s5_eval/_match_rules_pit_pad_9t.py",
    "notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py",
    "notebooks/wellsight_v2/s5_eval/_cv5_pr_calibration_pit_pad_9t.py",
    "notebooks/wellsight_v2/s5_eval/_pad_cv5_tau_scale.py",
    "notebooks/wellsight_v2/s5_eval/_transfer_pit_cv5_to_613590_05.py",
    "notebooks/wellsight_v2/s5_eval/_is_613590_fully_annotated.py",
    "notebooks/wellsight_v2/s5_eval/_score_road_pred_vs_roads_shp_613590.py",
    "agu_poster/_make_poster_figures.py", "agu_poster/_make_agu_poster.py",
    "notebooks/wellsight_v2/s7_analysis/_lidar_methodology_appendix.py",
]
RASTERS = [
    "data/9t/derived/05/dem_9t_05.tif", "data/9t/derived/05/chm_9t_05.tif", "data/9t/derived/05/hillshade_9t_05.tif",
    "data/9t/derived/05/rrim_openness_9t_05.tif", "data/9t/derived/05/features_pit_9t_05.tif",
    "data/9t/derived/05/labels_pit_9t_05.tif", "data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif",
    "data/9t/models/pad/unet_cv5/fold0/pad_prob_cvfold0_9t_05.tif",
    "data/613590/derived/05/dem_613590_05.tif", "data/613590/derived/05/rrim_openness_613590_05.tif",
    "data/613590/derived/inference_05/features_613590_05.tif", "data/613590/derived/inference_05/pit_prob_floor_613590_05.tif",
    "data/613590/derived/inference_05/pad_prob_613590_05.tif", "data/613590/derived/inference_05/pit_argmax_613590_05.tif",
    "data/9t/derived/1m/dem_9t_1m.tif",
]
CKPTS = ([f"data/9t/models/pit/unet_cv5/fold{k}/best.pt" for k in range(5)]
         + [f"data/9t/models/pad/unet_cv5/fold{k}/best.pt" for k in range(5)]
         + ["data/9t/models/pit/unet_v2/best.pt", "data/9t/models/pad/unet/best.pt",
            "data/9t/models/road/unet_1m_recall/best.pt"])
VERBATIM = [
    "data/9t/derived/05/feature_stats.json",
    "data/9t/models/pit/unet_cv5/pit_cv5_per_fold_9t.csv", "data/9t/models/pad/unet_cv5/pad_cv5_per_fold_9t.csv",
    "data/9t/models/pit/unet_cv5/pit_cv5_recovery_curve_9t.csv",
    "data/613590/results/annotation_coverage_613590_vs_9t.json",
    "data/_comparisons/pit_heldout_and_transfer_2026-09-20/613590_transfer_from_9t_cv5_05/pit_transfer_recall_summary_613590_05.json",
    "data/9t/models/pit/unet_v2/test_metrics.json", "data/9t/models/pad/unet/test_metrics.json",
]
RUN = [
    "# 1 derivatives (PDAL merge -> DEM -> channels), 0.5 m, per tile",
    "python notebooks/wellsight_v2/s1_build/_build_derivatives.py --suffix 9t_05 --res 0.5 --dem-method delaunay --bbox 619500,4593000,624000,4597500 --tiles <glob>",
    "python notebooks/wellsight_v2/s1_build/_build_derivatives.py --suffix 613590_05 --res 0.5 --crs EPSG:6346 --dem-method delaunay --bbox 613500,4590000,618000,4594500 --tiles <glob>",
    "python notebooks/wellsight_v2/s1_build/_make_rrim.py            # RRIM from openness + slope",
    "# 2 labels and split (hand annotation in QGIS -> rasters, blocks, manifests). --force re-assigns folds: do not",
    "python notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py",
    "python notebooks/wellsight_v2/s2_labels/_build_pad_road_dataset.py",
    "# 3 train 5-fold block CV (40 epochs, F1 and F2 thresholds on inner validation)",
    "python notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py --folds 5 --epochs 40",
    "python notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py --folds 5 --epochs 40",
    "python notebooks/wellsight_v2/s3_train/_road_unet_1m_recall.py --epochs 40",
    "# 4 scoring",
    "python notebooks/wellsight_v2/s5_eval/_pad_cv5_tau_scale.py",
    "python notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py",
    "python notebooks/wellsight_v2/s5_eval/_cv5_pr_calibration_pit_pad_9t.py",
    "# 5 transfer to 613590",
    "python notebooks/wellsight_v2/s4_infer/_infer_pit_pad_613590_05.py",
    "python notebooks/wellsight_v2/s5_eval/_transfer_pit_cv5_to_613590_05.py",
    "# 6 poster",
    "python agu_poster/_make_poster_figures.py",
    "python agu_poster/_make_agu_poster.py --mockup",
    "python notebooks/wellsight_v2/s7_analysis/_lidar_methodology_appendix.py",
]


def prof(p):
    with rasterio.open(p) as s:
        return (f"crs {s.crs.to_string() if s.crs else None}, res {s.res}, size {s.width}x{s.height}, bands {s.count}, "
                f"dtype {s.dtypes[0]}, nodata {s.nodata}, bounds {tuple(round(b, 2) for b in s.bounds)}, "
                f"descriptions {s.descriptions}, tags {s.tags()}")


def main():
    L = []
    w = L.append
    w("# Lidar pit / pad / road pipeline appendix: full metadata and code\n")
    w("Machine generated by `notebooks/wellsight_v2/s7_analysis/_lidar_methodology_appendix.py`. Read with "
      "`docs/lidar_methodology_brief.md`. Paths are repo-relative.\n")
    w("Contents: 1 source tile index | 2 raster profiles | 3 checkpoints | 4 annotations | "
      "5 wells | 6 fold assignment | 7 result files verbatim | 8 run order | 9 full source code\n")

    idx = pd.read_csv(ROOT / "data/_source/lidar/laz_tile_index.csv")
    w("## 1. Source lidar tile index\nSource `data/_source/lidar/laz_tile_index.csv` "
      f"({len(idx)} rows, WesternPA D20 holdings). Raw LAZ is offloaded, not on this disk. Tiles overlapping each study tile:\n")
    for nm, b in (("9t", B9T), ("613590", B613)):
        m = idx[(idx.min_x < b[2]) & (idx.max_x > b[0]) & (idx.min_y < b[3]) & (idx.max_y > b[1])]
        w(f"### {nm}, bounds {b}, {len(m)} tiles\n")
        w(m.to_markdown(index=False))
        w("")

    w("## 2. Raster profiles\n")
    for r in RASTERS:
        p = ROOT / r
        try:
            w(f"- `{r}`: {prof(p)}" if p.exists() else f"- `{r}`: not on disk")
        except Exception as e:  # noqa: BLE001
            w(f"- `{r}`: unreadable ({e})")

    w("\n## 3. Checkpoints (contents)\nmu and sd travel inside each checkpoint and are used at inference.\n")
    try:
        import torch
        for c in CKPTS:
            p = ROOT / c
            if not p.exists():
                w(f"- `{c}`: not on disk")
                continue
            ck = torch.load(p, map_location="cpu", weights_only=False)
            nparam = sum(v.numel() for v in ck["state_dict"].values()) if "state_dict" in ck else None
            small = {k: (v if np.size(v) < 20 else f"array{np.shape(v)}") for k, v in ck.items() if k != "state_dict"}
            w(f"- `{c}`: params {nparam}, keys {list(ck.keys())}\n  - {small}")
    except Exception as e:  # noqa: BLE001
        w(f"checkpoint read failed: {e}")

    w("\n## 4. Annotations (`qgis/annotations/annotations_proj.gpkg`)\n")
    for lay in ["pit_inside", "pit_outside", "pit_wall", "plat", "roads", "not_roads", "drainage"]:
        d = gpd.read_file(ANN, layer=lay)
        line = d.geom_type.iloc[0] == "LineString"
        a = d.geometry.length if line else d.geometry.area
        c9 = len(d.cx[B9T[0]:B9T[2], B9T[1]:B9T[3]])
        c6 = len(d.cx[B613[0]:B613[2], B613[1]:B613[3]])
        w(f"- `{lay}`: {len(d)} features, crs {d.crs.to_epsg()}, geom {sorted(d.geom_type.unique())}, columns {list(d.columns)}, "
          f"bounds {[round(x) for x in d.total_bounds]}, in 9t {c9}, in 613590 {c6}, "
          f"{'m length' if line else 'm2'} median {a.median():.1f} (p10 {a.quantile(.1):.1f}, p90 {a.quantile(.9):.1f})")

    w("\n## 5. Well records\n")
    for f in ["venango_wells_all.gpkg", "wells_in_tile.gpkg", "dep_wells_snapped_9tile.gpkg"]:
        p = ROOT / "data/_source/reference/dep_wells" / f
        if p.exists():
            d = gpd.read_file(p)
            w(f"- `data/_source/reference/dep_wells/{f}`: {len(d)} rows, crs {d.crs}, columns {list(d.columns)}")

    w("\n## 6. Fold assignment (block-wise 5-fold)\n")
    for nm, f in (("pit", "data/9t/models/pit/unet_cv5/pit_cv5_fold_assignment_9t.csv"),
                  ("pad", "data/9t/models/pad/unet_cv5/pad_cv5_fold_assignment_9t.csv")):
        p = ROOT / f
        if p.exists():
            d = pd.read_csv(p)
            w(f"### {nm}, `{f}`, columns {list(d.columns)}, {len(d)} rows\n")
            bc = "block_id" if "block_id" in d else d.columns[1]
            w(d.groupby("fold").agg(n=(d.columns[0], "size"), blocks=(bc, "nunique")).reset_index().to_markdown(index=False))
            w("")

    w("## 7. Result files (verbatim)\n")
    for f in VERBATIM:
        p = ROOT / f
        if p.exists():
            w(f"### {f}\n```{p.suffix.lstrip('.')}\n{p.read_text(encoding='utf-8')}\n```")
        else:
            w(f"### {f}\nnot found")

    w("## 8. Run order\n```")
    L.extend(RUN)
    w("```\nEnvironment: Python 3.13, PyTorch (CUDA, AMP), rasterio/GDAL, geopandas, shapely, scipy, numpy, pandas, "
      "matplotlib, PDAL 2.10 CLI (subprocess), WhiteboxTools, python-pptx, PowerPoint COM (render check).\n")

    w("## 9. Full source code\n")
    for s in SCRIPTS:
        p = ROOT / s
        w(f"### {s}\n```python\n{p.read_text(encoding='utf-8')}\n```" if p.exists() else f"### {s}\nnot found")
    OUT.write_text("\n".join(str(x) for x in L), encoding="utf-8")
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

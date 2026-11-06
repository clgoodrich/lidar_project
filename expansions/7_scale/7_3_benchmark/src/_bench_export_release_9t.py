"""Export a versioned terrain-feature benchmark release (7.3 S1).

Purpose
    Write a frozen release folder with block-aligned tiles, labels per split, split lists,
    a manifest of SHA-256 hashes, the official scorer as evaluate.py, a README and a licence stub.
    Hidden-test and buffer blocks ship tiles and block geometry, never labels.
    Labels are drawn terrain features (evidence level a). They are never wells.

Inputs (config_7_3.json, resolved with ek.path_for)
    feature stack   path_for("nine_t") / features_pit_9t_05.tif   (7 bands, held)
    DEM             path_for("nine_t") / dem_9t_05.tif            (held)
    blocks          path_for("nine_t") / blocks_unified_9t.gpkg    (held)
    annotations     path_for("truth") / annotations_proj.gpkg      (held)
    future split    path_for("results_9t") / splits/cv_splits_future_9t_v1.json   (from P1, assumed)
    audit blocks    path_for("results_9t") / splits/audit_blocks_9t_v1.csv        (from P2, assumed)
    --provisional-historical uses the held historical held-out lists instead and stamps the
    release PROVISIONAL. A provisional release has no hidden test and must not be published.
Outputs
    <release_root>/terrain_v1/ (default expansions/7_scale/7_3_benchmark/data/processed/terrain_v1/, gitignored)
        tiles/blk<id>.tif            8 bands (7 channels + DEM), float32, EPSG:6346, nodata NaN
        labels/labels_<role>.gpkg    layers pit_floor, pit_full, pad (public roles only)
        blocks/blocks_<role>.gpkg    block polygons per role
        splits/splits_terrain_v1.json
        evaluate.py, README.md, LICENCE_SOURCES.md, manifest.csv
    --verify re-hashes every file against manifest.csv and exits 1 on any mismatch.

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_export_release_9t.py --provisional-historical --max-tiles 4
    python expansions/7_scale/7_3_benchmark/src/_bench_export_release_9t.py --verify
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

HERE = Path(__file__).resolve().parent
CFG = HERE / "config_7_3.json"
PUBLIC_ROLES = ("train", "val", "devtest")
HIDDEN_ROLES = ("test", "buffer")


def load_cfg(path: Path = CFG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cfg_path(entry: dict) -> Path:
    return ek.path_for(entry["key"]) / entry["rel"]


def need(path: Path, what: str) -> Path:
    if not Path(path).exists():
        raise FileNotFoundError(f"missing input for 7.3 ({what}): {path}. See config_7_3.json")
    return Path(path)


# ----------------------------------------------------------------------------- roles
def roles_from_future(split_json: Path, audit_csv: Path, devtest_fold: int) -> tuple[dict, list]:
    """Block roles from the P1 future split and the P2 audit list.

    Returns ({block_id: role}, folds) where folds is the public CV list shipped to users.
    """
    sp = json.loads(need(split_json, "P1 future split").read_text())
    au = pd.read_csv(need(audit_csv, "P2 audit blocks"))
    roles: dict[int, str] = {}
    for _, r in au.iterrows():
        roles[int(r["block_id"])] = "test" if str(r["role"]).startswith("comparative") or r["role"] == "test" else "buffer"
    for b in sp.get("buffer_blocks", []):
        roles.setdefault(int(b), "buffer")
    folds = []
    for f in sp["folds"]:
        held = [int(b) for b in f["heldout"] if int(b) not in roles]
        folds.append({"fold": int(f["fold"]), "heldout": sorted(held)})
        for b in held:
            roles[b] = "devtest" if int(f["fold"]) == devtest_fold else "train"
    return roles, folds


def roles_from_historical(hist_csv: Path, devtest_fold: int) -> tuple[dict, list]:
    """PROVISIONAL roles from the historical held-out lists (protocol section 3 says only those are valid)."""
    h = pd.read_csv(need(hist_csv, "historical split"))
    h = h[h["role"].astype(str).str.startswith("held")].dropna(subset=["block_id"])
    roles, folds = {}, []
    for k, g in h.groupby("fold"):
        ids = sorted(int(b) for b in g["block_id"])
        folds.append({"fold": int(k), "heldout": ids})
        for b in ids:
            roles[b] = "devtest" if int(k) == devtest_fold else "train"
    return roles, folds


# ----------------------------------------------------------------------------- labels
def split_labels(feat, blocks, roles: dict, block_col: str = "block_id"):
    """Assign each feature a role by centroid. Drop from public files any feature touching a hidden block."""
    import geopandas as gpd
    feat = feat.to_crs(blocks.crs).reset_index(drop=True)
    feat = feat[feat.geometry.notna() & ~feat.geometry.is_empty].copy()
    b = blocks[[block_col, "geometry"]].copy()
    b["role"] = [roles.get(int(x)) for x in b[block_col]]
    cent = gpd.GeoDataFrame({"fid": feat.index}, geometry=feat.geometry.centroid.values, crs=blocks.crs)
    j = gpd.sjoin(cent, b, how="left", predicate="within").drop_duplicates("fid").set_index("fid")
    feat["block_id"] = j[block_col].reindex(feat.index).to_numpy()
    feat["role"] = j["role"].reindex(feat.index).to_numpy()
    hidden = b[b["role"].isin(HIDDEN_ROLES)]
    if len(hidden):
        touch = gpd.sjoin(feat[["geometry"]], hidden[["geometry"]], how="inner", predicate="intersects").index.unique()
        feat.loc[feat.index.isin(touch), "role"] = "hidden_touch"
    return feat


def near_duplicates_across_splits(feat, tol_m: float = 5.0) -> int:
    from scipy.spatial import cKDTree
    f = feat[feat["role"].isin(PUBLIC_ROLES)]
    if len(f) < 2:
        return 0
    xy = np.c_[f.geometry.centroid.x, f.geometry.centroid.y]
    r = f["role"].to_numpy()
    pairs = cKDTree(xy).query_pairs(tol_m, output_type="ndarray")
    return int(sum(r[i] != r[j] for i, j in pairs))


# ----------------------------------------------------------------------------- tiles
def write_tile(stack_path: Path, dem_path: Path, bounds, out: Path) -> None:
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open(stack_path) as s, rasterio.open(dem_path) as d:
        ek.assert_crs(s, "EPSG:6346"); ek.assert_crs(d, "EPSG:6346")
        w = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        a = s.read(window=w, boundless=True, fill_value=np.nan).astype(np.float32)
        wd = from_bounds(*bounds, transform=d.transform).round_offsets().round_lengths()
        dem = d.read(1, window=wd, boundless=True, fill_value=np.nan).astype(np.float32)
        if d.nodata is not None and np.isfinite(d.nodata):
            dem[dem == d.nodata] = np.nan
        tf = s.window_transform(w)
        names = list(s.descriptions) if any(s.descriptions) else [f"band{i+1}" for i in range(s.count)]
        crs = s.crs
    prof = dict(driver="GTiff", width=a.shape[2], height=a.shape[1], count=a.shape[0] + 1, dtype="float32",
                crs=crs, transform=tf, nodata=np.nan, tiled=True, blockxsize=256, blockysize=256,
                compress="deflate", predictor=3)
    with rasterio.open(out, "w", **prof) as o:
        o.write(a, list(range(1, a.shape[0] + 1)))
        o.write(dem[: a.shape[1], : a.shape[2]], a.shape[0] + 1)
        for i, n in enumerate(names + ["dem"], start=1):
            o.set_band_description(i, n or f"band{i}")
        o.update_tags(units="metres", crs="EPSG:6346", vertical_datum="NAVD88", evidence_level="a")


# ----------------------------------------------------------------------------- manifest
def write_manifest(root: Path) -> Path:
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.csv":
            rows.append({"path": p.relative_to(root).as_posix(), "sha256": ek.sha256(p), "bytes": p.stat().st_size})
    out = root / "manifest.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    return out


def verify_manifest(root: Path) -> list[str]:
    bad = []
    m = pd.read_csv(root / "manifest.csv")
    for _, r in m.iterrows():
        p = root / r["path"]
        if not p.exists():
            bad.append(f"missing {r['path']}")
        elif ek.sha256(p) != r["sha256"]:
            bad.append(f"hash {r['path']}")
    listed = set(m["path"])
    for p in root.rglob("*"):
        if p.is_file() and p.name != "manifest.csv" and p.relative_to(root).as_posix() not in listed:
            bad.append(f"unlisted {p.relative_to(root).as_posix()}")
    return bad


README = """# {name}

Version {name}. Status {status}.

This release holds lidar derivative tiles, drawn terrain-feature polygons, split lists and an
official scorer. Every label is a drawn terrain feature (evidence level a). A label is not a well.
On the source area, 27 of 424 drawn pits (6.4%) have a catalogued well within 25 m.

## Out of scope
Locating wells for entry or plugging. Regulatory, legal or safety decisions. Counting wells.
Claims about another state or lidar vintage. Any claim that a detected feature is a well.

## Contents
- `tiles/` one tile per 375 m block. Eight bands. Seven derivative channels and the DEM.
- `labels/` public labels by split. Hidden-test and buffer blocks have no labels here.
- `blocks/` block polygons by role.
- `splits/splits_{name}.json` block roles and public folds.
- `evaluate.py` the official scorer. K is 40 candidates per km2.
- `manifest.csv` SHA-256 of every file.

## Score a prediction
`python evaluate.py --pred <raster> --labels labels/labels_devtest.gpkg --layer pit_floor --blocks blocks/blocks_devtest.gpkg --out score.json`
"""

LICENCE = """# Source licences ({name})

Every row is VERIFY until the terms text is saved here with a date.

| Source | Terms | Checked on |
|---|---|---|
| Lidar | {lidar} | not yet |
| Labels | {labels} | not yet |
| Well context | {well_context} | not yet |
"""


def export(cfg: dict, out_root: Path, provisional: bool, max_tiles: int | None, devtest_fold: int,
           skip_tiles: bool = False) -> dict:
    import geopandas as gpd
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import read_layer
    inp = cfg["inputs"]
    blocks = gpd.read_file(need(cfg_path(inp["blocks"]), "blocks"))
    ek.assert_crs(blocks, cfg["crs"])
    ek.assert_unique(blocks, "block_id")
    blocks["block_id"] = blocks["block_id"].astype(int)
    if provisional:
        roles, folds = roles_from_historical(cfg_path(inp["split_historical"]), devtest_fold)
    else:
        roles, folds = roles_from_future(cfg_path(inp["split_future"]), cfg_path(inp["audit_blocks"]), devtest_fold)
    ek.assert_no_nan(list(roles), "block ids in roles")
    root = out_root / cfg["release_name"]
    if root.exists():
        shutil.rmtree(root)
    for d in ("tiles", "labels", "blocks", "splits"):
        (root / d).mkdir(parents=True, exist_ok=True)

    ann = need(cfg_path(inp["annotations"]), "annotations")
    counts = {}
    feats = {}
    for task, layer in inp["annotations"]["layers"].items():
        f = split_labels(read_layer(ann, layer), blocks, roles)
        feats[task] = f
        counts[task] = f["role"].fillna("off_tile").value_counts().to_dict()
        for role in PUBLIC_ROLES:
            sub = f[f["role"] == role][["block_id", "geometry"]].reset_index(drop=True)
            sub["feature_id"] = [f"{task}_{role}_{i:05d}" for i in range(len(sub))]
            if len(sub):
                sub.to_file(root / "labels" / f"labels_{role}.gpkg", layer=task, driver="GPKG")
    # leakage check 1: no hidden label anywhere in shipped files
    for p in (root / "labels").glob("*.gpkg"):
        for task in feats:
            try:
                g = gpd.read_file(p, layer=task)
            except Exception:  # noqa: BLE001 - layer absent in that role
                continue
            hid = set(g["block_id"].dropna().astype(int)) & {b for b, r in roles.items() if r in HIDDEN_ROLES}
            if hid:
                raise AssertionError(f"hidden block labels in {p.name}: {sorted(hid)[:5]}")
    ndup = sum(near_duplicates_across_splits(f) for f in feats.values())

    blocks["role"] = [roles.get(int(b), "unassigned") for b in blocks["block_id"]]
    for role, g in blocks.groupby("role"):
        g[["block_id", "role", "geometry"]].to_file(root / "blocks" / f"blocks_{role}.gpkg", driver="GPKG")
    split_obj = {"release": cfg["release_name"], "provisional": provisional, "devtest_fold": devtest_fold,
                 "roles": {str(b): r for b, r in sorted(roles.items())}, "public_folds": folds,
                 "note": "Hidden-test labels are withheld by the maintainers."}
    (root / "splits" / f"splits_{cfg['release_name']}.json").write_text(json.dumps(split_obj, indent=2), encoding="utf-8")

    n_tiles = 0
    if not skip_tiles:
        stack, dem = need(cfg_path(inp["feature_stack"]), "feature stack"), need(cfg_path(inp["dem"]), "DEM")
        for _, r in blocks[blocks["role"] != "unassigned"].sort_values("block_id").iterrows():
            if max_tiles is not None and n_tiles >= max_tiles:
                break
            write_tile(stack, dem, r.geometry.bounds, root / "tiles" / f"blk{int(r['block_id']):04d}.tif")
            n_tiles += 1
    shutil.copyfile(HERE / "_bench_evaluate_recall_k.py", root / "evaluate.py")
    status = "PROVISIONAL, not for release" if provisional else "candidate release"
    (root / "README.md").write_text(README.format(name=cfg["release_name"], status=status), encoding="utf-8")
    (root / "LICENCE_SOURCES.md").write_text(LICENCE.format(name=cfg["release_name"], **cfg["licences"]), encoding="utf-8")
    write_manifest(root)
    summary = {"release": str(root), "provisional": provisional, "n_tiles": n_tiles,
               "roles": pd.Series(roles).value_counts().to_dict(), "label_counts": counts,
               "near_duplicates_across_splits": ndup}
    (root / "_export_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_manifest(root)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Export the terrain-feature benchmark release (7.3 S1).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--out-root", default=None, help="default: config release_root")
    ap.add_argument("--provisional-historical", action="store_true")
    ap.add_argument("--devtest-fold", type=int, default=4)
    ap.add_argument("--max-tiles", type=int, default=None)
    ap.add_argument("--skip-tiles", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    out_root = Path(a.out_root) if a.out_root else cfg_path(cfg["release_root"])
    if a.verify:
        bad = verify_manifest(out_root / cfg["release_name"])
        print("manifest OK" if not bad else "\n".join(bad))
        return 1 if bad else 0
    try:
        s = export(cfg, out_root, a.provisional_historical, a.max_tiles, a.devtest_fold, a.skip_tiles)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    print(json.dumps(s, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

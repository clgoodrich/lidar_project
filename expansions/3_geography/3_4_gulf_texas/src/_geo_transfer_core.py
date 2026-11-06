"""Shared regional-transfer machinery for expansions 3.4 to 3.8 (Gulf/Texas, OK/KS, California, Canada, Alaska).

Purpose
    One implementation of the steps every regional transfer framework repeats, so the five
    regions differ only in registry schema, CRS and region-specific confusers.
      config      load src/config_<id>.json, resolve path specs without data path literals
      inputs      require_input(): fail with a message that names the missing input and its schema
      registry    normalise any well registry to one schema (WELL_COLS), paged ArcGIS query ledger
      windows     window boxes, UTM CRS choice, union cover from tile boxes, lexicographic ranking
      blocks      375 m block grid, edge flags, seeded role draw with a buffer
      density     ground density, void fraction and class shares per block from LAS/LAZ (laspy)
      observe     minimum detectable depth, 9t pit depth distribution, observable share
      candidates  probability raster -> blobs (thr 0.10, >= 4 m2, mean prob score), greedy IoU 0.3 match
      scoring     pooled recall at K per km2 over complete blocks, block bootstrap, area difference,
                  paired arm difference, permutation null band (< 15 blocks), density-scaled K, ceiling
      agreement   two-annotator pad/pit F1 at IoU 0.3 and Cohen kappa on classes
      inference   frozen checkpoint inference through notebooks/wellsight_v2/s4_infer/_predict_on_tile.py
      prereg      write a preregistration skeleton from the config
    Statistics come from expansions/_shared/src/expkit.py (fw_00 section 4). Nothing here retunes on a target.

Inputs
    Per-expansion config  expansions/3_geography/<id>_<slug>/src/config_<id>.json
    Lidar catalogue       ek.path_for("reference") / lidar_catalogue / lidar_win_*.csv  (held, discovery only)

Outputs (CLI subcommands, all under the expansion folder or data/<area>/results/transfer/)
    density   data/<area>/results/transfer/xfer_density_void_<area>.csv
    blocks    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg
    cover     expansions/3_geography/<id>_*/results/tables/xfer_window_cover_<id>.csv
    infer     data/<area>/results/transfer/<run_id>/<task>_prob_<suffix>.tif
    score     data/<area>/results/transfer/<run_id>/xfer_score_k40_<area>.json
    width     expansions/3_geography/<id>_*/results/tables/xfer_projected_width_<id>.json
    agree     data/<area>/results/transfer/xfer_label_agreement_<area>.json
    prereg    expansions/3_geography/<id>_*/docs/prereg_draft_<id>.md

Run
    python expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py cover --exp 3.4
    python expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py density --exp 3.4 --area la_caddo
    (subcommands: cover density blocks derive infer score width agree prereg)

Import from a sibling expansion
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
    import _geo_transfer_core as gt
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

REPO = ek.REPO
WSV2 = REPO / "notebooks" / "wellsight_v2"
BLOCK_M = 375.0            # 9t block size, so the projected-width tool applies unchanged
K_PER_KM2 = 40.0           # user decision 2026-11-04 (protocol section 2 rule 7)
CAND_THR = 0.10            # lowest cutoff in the sweep (fw_00 section 4)
MIN_BLOB_M2 = 4.0
IOU_MATCH = 0.3
REF_9T = {"ground_density_ppm2": 2.70, "void_frac_05": 0.452}   # protocol section 3 rule 5, fw 3.4 S2

# Lost/found palette from CLAUDE.md, dataviz validator --pairs all, worst pair dE 21.1 deutan / 22.6 normal.
# Arms and strata also get a marker shape so colour is never the only encoding.
MARKERS = {"A0": "o", "A1": "s", "A2": "^", "C0": "D", "ref": "x", "L0": "o", "L1": "s", "O1": "^",
           "F1": "D", "L2": "v", "model": "o", "rule": "s", "union": "^"}


# ============================================================================ errors / config
class MissingInputError(FileNotFoundError):
    """An assumed (VERIFY) input is not on disk. The message names it and its expected schema."""


def exp_src(exp_id: str) -> Path:
    return ek.exp_dir(exp_id) / "src"


def load_config(exp_id: str, path: Path | None = None) -> dict:
    p = path or exp_src(exp_id) / f"config_{exp_id.replace('.', '_')}.json"
    if not p.exists():
        raise MissingInputError(f"config for {exp_id} not found at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def resolve(spec, exp_id: str | None = None, **fmt) -> Path:
    """Path spec -> Path, without spelling a data path in code.

    spec forms: {"key": "<paths.toml key>", "rel": "a/b.csv"} | {"area": "la_caddo", "rel": "..."}
                | {"exp": "3.4", "rel": "data/raw/x.csv"} | a plain string relative to the expansion folder.
    Strings may hold {placeholders} filled from fmt (e.g. area="ca1").
    """
    f = (lambda v: v.format(**fmt) if isinstance(v, str) and fmt else v)
    if isinstance(spec, (str, Path)):
        if exp_id is None:
            raise ValueError("plain-string path spec needs exp_id")
        return ek.exp_dir(exp_id) / f(str(spec))
    rel = f(spec.get("rel", ""))
    if "key" in spec:
        return ek.path_for(spec["key"]) / rel
    if "area" in spec:
        return ek.area_dir(f(spec["area"])) / rel
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / rel
    raise ValueError(f"bad path spec {spec}")


def require_input(path: Path, what: str, schema: str | dict | list | None = None, verify: str = "") -> Path:
    """Raise MissingInputError naming the input, the expected schema and the VERIFY step."""
    path = Path(path)
    if path.exists():
        return path
    msg = [f"MISSING INPUT: {what}", f"  expected at: {path}"]
    if schema:
        msg.append(f"  assumed schema: {json.dumps(schema) if not isinstance(schema, str) else schema}")
    if verify:
        msg.append(f"  VERIFY: {verify}")
    msg.append("  This input is assumed (framework section 'Assumed data'). Obtain it, or edit the config path.")
    raise MissingInputError("\n".join(msg))


class DecisionMissingError(ValueError):
    """A preregistration value that only the user can set (margin, delta_gain, caps) is still null."""


def need_decision(cfg: dict, key: str, what: str = "") -> float:
    v = cfg.get("prereg", {}).get(key)
    if v is None or v == "TBD":
        raise DecisionMissingError(f"USER DECISION MISSING: prereg.{key} ({what or 'see framework section 5/6'}) "
                                   f"is null in the config. Set it in the prereg before scoring.")
    return v


def config_input(cfg: dict, name: str, exp_id: str, **fmt) -> Path:
    """Resolve cfg['inputs'][name] (placeholders filled from fmt) and require it."""
    item = cfg["inputs"][name]
    return require_input(resolve(item["path"], exp_id, **fmt), f"{exp_id} input '{name}'",
                         item.get("schema"), item.get("verify", ""))


def area_transfer_dir(area: str) -> Path:
    d = ek.area_dir(area) / "results" / "transfer"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================================ registry
WELL_COLS = ["well_id", "source", "state_prov", "county", "status_raw", "status_norm", "well_type",
             "lat", "lon", "coord_method", "coord_reliability", "spud_date", "plug_date", "snapshot_date"]


def normalise_registry(df: pd.DataFrame, colmap: dict, source: str, status_map: dict | None = None,
                       snapshot_date: str = "", lonlat_crs: str = "EPSG:4269"):
    """Any registry -> GeoDataFrame with WELL_COLS in EPSG:4326.

    colmap maps WELL_COLS names to source column names (missing ones become NA). status_map maps
    raw status strings (case-insensitive) to a normalised vocabulary. Unmapped statuses stay
    'unmapped', never guessed. Rows with missing or out-of-range coordinates are kept with
    coord_ok = False so counts reconcile (fw_00 section 5 rule 1).
    """
    import geopandas as gpd
    out = pd.DataFrame(index=df.index)
    for c in WELL_COLS:
        src = colmap.get(c)
        out[c] = df[src] if src in df.columns else pd.NA
    out["source"] = source
    out["snapshot_date"] = snapshot_date or out["snapshot_date"]
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    sm = {str(k).strip().lower(): v for k, v in (status_map or {}).items()}
    out["status_norm"] = [sm.get(str(s).strip().lower(), "unmapped") if pd.notna(s) else "missing"
                          for s in out["status_raw"]]
    out["coord_ok"] = out["lat"].between(-90, 90) & out["lon"].between(-180, 180) & \
        ~((out["lat"] == 0) & (out["lon"] == 0))
    out["coord_reliability"] = out["coord_reliability"].fillna("unknown")
    out["well_id"] = out["well_id"].astype("string")
    g = gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(out["lon"].where(out["coord_ok"]),
                                                          out["lat"].where(out["coord_ok"])),
                         crs=lonlat_crs)
    if lonlat_crs != "EPSG:4326":
        g = g.to_crs("EPSG:4326")
    ek.assert_rows(g, len(df), f"normalise {source}")
    return g


def registry_summary(g) -> dict:
    return {"rows": int(len(g)), "coord_ok": int(g["coord_ok"].sum()),
            "status_norm": g["status_norm"].value_counts(dropna=False).to_dict(),
            "coord_reliability": g["coord_reliability"].astype(str).value_counts(dropna=False).to_dict(),
            "duplicate_ids": int(g["well_id"].dropna().duplicated().sum())}


def load_usgs_orphans(states: list[str], year: int = 2026):
    """USGS documented orphan list (held) for the given states, normalised. The 2022 and 2026 files differ in schema."""
    if year == 2026:
        rel, idcol = ("wells_us_orphan_2026", "US_orphaned_wells_2026.csv"), "primary_identifier"
        cmap = {"well_id": idcol, "state_prov": "state", "county": "county", "status_raw": "status",
                "well_type": "type", "lat": "latitude", "lon": "longitude", "coord_method": "location_notes"}
        st = "state"
    elif year == 2022:
        rel, idcol = ("wells_us_orphan_2022", "US_orphaned_wells.csv"), "Well identifier"
        cmap = {"well_id": idcol, "state_prov": "State", "county": "County", "status_raw": "Status",
                "well_type": "Type", "lat": "Latitude", "lon": "Longitude", "coord_method": "Location notes"}
        st = "State"
    else:
        raise ValueError(year)
    p = require_input(ek.path_for("reference") / rel[0] / rel[1], f"USGS orphan list {year}")
    df = pd.read_csv(p, encoding="utf-8-sig", low_memory=False, dtype={idcol: str})
    df = df[df[st].isin(states)].reset_index(drop=True)
    return normalise_registry(df, cmap, f"usgs_orphan_{year}",
                              status_map={"orphan": "orphan", "abandoned": "abandoned",
                                          "potentially deserted": "deserted_potential",
                                          "deserted": "deserted"},
                              lonlat_crs="EPSG:4269")


@dataclass
class PageResult:
    offset: int
    status: str          # ok | empty | failed | incomplete
    n: int
    rows: list


def reconcile_pages(pages: list[PageResult], expected_total: int | None) -> dict:
    """fw_00 revision 2 QC. Keep successful-empty, failed and incomplete pages apart and compare totals."""
    by = {s: [p.offset for p in pages if p.status == s] for s in ("ok", "empty", "failed", "incomplete")}
    retrieved = sum(p.n for p in pages if p.status in ("ok", "incomplete"))
    complete = (not by["failed"] and not by["incomplete"] and
                (expected_total is None or retrieved == expected_total))
    return {"expected_total": expected_total, "retrieved": retrieved, "complete": bool(complete),
            "pages": {k: len(v) for k, v in by.items()}, "failed_offsets": by["failed"],
            "incomplete_offsets": by["incomplete"]}


def arcgis_paged_query(layer_url: str, page: int = 1000, where: str = "1=1", max_tries: int = 3,
                       fetch=None) -> tuple[pd.DataFrame, dict]:
    """Page an ArcGIS REST layer (returnCountOnly first, then resultOffset pages).

    fetch(url, params) -> dict is injectable for tests. The default uses urllib (network). Only the
    gated fetch scripts call this with the default, and only with --execute.
    """
    if fetch is None:
        import urllib.parse
        import urllib.request

        def fetch(url, params):
            q = url + "/query?" + urllib.parse.urlencode({**params, "f": "json"})
            req = urllib.request.Request(q, headers={"User-Agent": "lidar-well-research/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
    total = None
    try:
        total = int(fetch(layer_url, {"where": where, "returnCountOnly": "true"}).get("count"))
    except Exception:  # noqa: BLE001
        total = None
    pages, off = [], 0
    while True:
        res = None
        for _ in range(max_tries):
            try:
                res = fetch(layer_url, {"where": where, "outFields": "*", "returnGeometry": "true",
                                        "outSR": 4326, "resultOffset": off, "resultRecordCount": page,
                                        "orderByFields": "OBJECTID"})
                break
            except Exception:  # noqa: BLE001
                res = None
        if res is None or "error" in (res or {}):
            pages.append(PageResult(off, "failed", 0, []))
            if total is None or off >= total:
                break
            off += page
            continue
        feats = res.get("features", [])
        rows = [{**f.get("attributes", {}), "lon": (f.get("geometry") or {}).get("x"),
                 "lat": (f.get("geometry") or {}).get("y")} for f in feats]
        status = "empty" if not rows else ("incomplete" if res.get("exceededTransferLimit") and
                                           len(rows) < page else "ok")
        pages.append(PageResult(off, status, len(rows), rows))
        if not rows or (total is not None and off + len(rows) >= total):
            break
        off += len(rows)
    df = pd.DataFrame([r for p in pages for r in p.rows])
    return df, reconcile_pages(pages, total)


# ============================================================================ windows / CRS
def utm_epsg_nad83_2011(lon: float) -> int:
    """NAD83(2011) UTM zone N EPSG code (zone 17 -> 6346, 15 -> 6344, 13 -> 6342). Zones 1 to 19."""
    z = int((lon + 180) // 6) + 1
    if not 1 <= z <= 19:
        raise ValueError(f"lon {lon} outside NAD83(2011) UTM zones 1 to 19")
    return 6329 + z


_CSRS_UTM = {7: 3154, 8: 3155, 9: 3156, 10: 3157, 11: 2955, 12: 2956, 13: 2957, 14: 3158, 15: 3159, 16: 3160,
             17: 2958, 18: 2959}


def utm_epsg_csrs(lon: float) -> int:
    """NAD83(CSRS) UTM zone N EPSG code for Canada (zones 7 to 18, checked with pyproj 2026-11-05)."""
    z = int((lon + 180) // 6) + 1
    if z not in _CSRS_UTM:
        raise ValueError(f"lon {lon} outside NAD83(CSRS) UTM zones 7 to 18")
    return _CSRS_UTM[z]


def window_box(lon: float, lat: float, crs: str, side_km: float = 5.0):
    """25 km2 square (default) centred on lon, lat in a projected CRS. Returns shapely box."""
    from pyproj import Transformer
    from shapely.geometry import box
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    h = side_km * 500.0
    return box(x - h, y - h, x + h, y + h)


def load_catalogue(name: str) -> pd.DataFrame:
    p = require_input(ek.path_for("reference") / "lidar_catalogue" / name, f"lidar catalogue {name}")
    return pd.read_csv(p)


def union_cover(tile_boxes_ll: list[tuple], window_ll: tuple) -> float:
    """Share of a window (minx, miny, maxx, maxy lon/lat) covered by the union of tile boxes.

    Tile boxes from the catalogue are bounding boxes, so this is an upper bound on true cover
    (protocol section 13). Computed in an equal-area CRS.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union
    import geopandas as gpd
    w = gpd.GeoSeries([box(*window_ll)], crs="EPSG:4326").to_crs("EPSG:5070").iloc[0]
    if not tile_boxes_ll:
        return 0.0
    u = gpd.GeoSeries([box(*b) for b in tile_boxes_ll], crs="EPSG:4326").to_crs("EPSG:5070")
    return float(unary_union(list(u)).intersection(w).area / w.area)


def window_cover_table(windows: list[str]) -> pd.DataFrame:
    """Per window and project, union cover from tile bounding boxes (catalogue, held)."""
    win = load_catalogue("lidar_win_windows_us.csv").set_index("window")
    tw = load_catalogue("lidar_win_tile_window_us.csv")
    tiles = load_catalogue("lidar_win_tiles_unique_us.csv")
    rows = []
    for w in windows:
        if w not in win.index:
            rows.append({"window": w, "project": None, "status": "window not in catalogue"})
            continue
        r = win.loc[w]
        wbox = (r.minx, r.miny, r.maxx, r.maxy)
        sub_tw = tw[tw["window"] == w]
        for proj, g in sub_tw.groupby("project"):
            t = tiles[tiles["url"].isin(g["url"])]
            boxes = list(zip(t.bb_minx, t.bb_miny, t.bb_maxx, t.bb_maxy))
            rows.append({"window": w, "project": proj, "tiles": len(t), "mb": float(t["mb"].sum()),
                         "published": t["published"].max(), "cover_bbox_upper": union_cover(boxes, wbox),
                         "wells_in_window": int(r.wells_in_window), "status": "ok"})
    return pd.DataFrame(rows)


def lexicographic_rank(df: pd.DataFrame, keys: list[tuple[str, bool]]) -> pd.DataFrame:
    """Rank rows lexicographically. keys = [(column, descending), ...]. Gates (bool columns) first."""
    cols = [k for k, _ in keys]
    asc = [not d for _, d in keys]
    out = df.sort_values(cols, ascending=asc, kind="mergesort").reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


# ============================================================================ blocks / roles
def make_blocks(bounds: tuple, crs: str, size: float = BLOCK_M, footprint=None):
    """Square block grid over bounds (projected). edge = block not wholly inside footprint (or bounds)."""
    import geopandas as gpd
    from shapely.geometry import box
    x0, y0, x1, y1 = bounds
    nx, ny = int(math.floor((x1 - x0) / size)), int(math.floor((y1 - y0) / size))
    geoms, ids = [], []
    for j in range(ny):
        for i in range(nx):
            geoms.append(box(x0 + i * size, y0 + j * size, x0 + (i + 1) * size, y0 + (j + 1) * size))
            ids.append(f"b{j:03d}_{i:03d}")
    g = gpd.GeoDataFrame({"block_id": ids}, geometry=geoms, crs=crs)
    fp = footprint if footprint is not None else box(*bounds)
    g["edge"] = ~g.geometry.within(fp.buffer(1e-6))
    g["area_km2"] = g.geometry.area / 1e6
    ek.assert_unique(g, "block_id")
    return g


def assign_roles(blocks, fractions: dict, seed: int, buffer_m: float, protect=("test", "audit"),
                 strata_col: str | None = None):
    """Seeded role draw. Blocks within buffer_m of a protected-role block that drew a training-type
    role are relabelled 'buffer' (never trained on, never scored). Edge blocks get 'edge'.

    buffer_m comes from the derived P1 correlogram range in the config, never a fixed guess.
    """
    rng = np.random.default_rng(seed)
    g = blocks.copy()
    g["role"] = "edge"
    inner = g.index[~g["edge"]]
    names = list(fractions)
    p = np.array([fractions[n] for n in names], float)
    p = p / p.sum()
    groups = [inner] if strata_col is None else [g.index[(~g["edge"]) & (g[strata_col] == s)]
                                                for s in sorted(g.loc[inner, strata_col].unique())]
    for idx in groups:
        idx = np.array(idx)
        rng.shuffle(idx)
        counts = np.floor(p * len(idx)).astype(int)
        counts[0] += len(idx) - counts.sum()
        pos = 0
        for n, c in zip(names, counts):
            g.loc[idx[pos:pos + c], "role"] = n
            pos += c
    prot = g[g["role"].isin(protect)]
    if len(prot) and buffer_m > 0:
        zone = prot.geometry.buffer(buffer_m).union_all()
        near = (~g["role"].isin(list(protect) + ["edge"])) & g.geometry.intersects(zone)
        g.loc[near, "role"] = "buffer"
    return g


# ============================================================================ density / void
def las_block_density(las_paths: list[Path], blocks, cell: float = 0.5, chunk: int = 5_000_000,
                      ground_class: int = 2, water_class: int = 9) -> pd.DataFrame:
    """Per block: ground points per m2, 0.5 m void fraction (cells with no ground return), class shares.

    Reads LAS/LAZ in chunks with laspy. The CRS of the points must equal the blocks' CRS
    (asserted from the header WKT when present). Measures, never infers from file size.
    """
    import laspy
    from rasterio.transform import from_origin
    x0, y0, x1, y1 = blocks.total_bounds
    W, H = int(round((x1 - x0) / cell)), int(round((y1 - y0) / cell))
    occ = np.zeros((H, W), dtype=bool)
    counts = {"ground": np.zeros((H, W), np.uint32)}
    cls_tot: dict[int, int] = {}
    water = np.zeros((H, W), np.uint32)
    allpts = np.zeros((H, W), np.uint32)
    for lp in las_paths:
        with laspy.open(lp) as fh:
            crs = fh.header.parse_crs()
            if crs is not None:
                ek.assert_crs(crs, blocks.crs)
            for pts in fh.chunk_iterator(chunk):
                x, y, c = np.asarray(pts.x), np.asarray(pts.y), np.asarray(pts.classification)
                col = np.floor((x - x0) / cell).astype(np.int64)
                row = np.floor((y1 - y) / cell).astype(np.int64)
                ok = (col >= 0) & (col < W) & (row >= 0) & (row < H)
                col, row, c = col[ok], row[ok], c[ok]
                for k, v in zip(*np.unique(c, return_counts=True)):
                    cls_tot[int(k)] = cls_tot.get(int(k), 0) + int(v)
                np.add.at(allpts, (row, col), 1)
                gm = c == ground_class
                np.add.at(counts["ground"], (row[gm], col[gm]), 1)
                occ[row[gm], col[gm]] = True
                wm = c == water_class
                np.add.at(water, (row[wm], col[wm]), 1)
    tf = from_origin(x0, y1, cell, cell)
    return block_stats_from_grids(blocks, tf, cell, counts["ground"], occ, water, allpts, cls_tot)


def block_stats_from_grids(blocks, transform, cell, ground, occ, water, allpts, cls_tot=None) -> pd.DataFrame:
    """Aggregate per-cell grids into per-block rows (split out so tests need no LAS file)."""
    rows = []
    x0, y1 = transform.c, transform.f
    for _, b in blocks.iterrows():
        bx0, by0, bx1, by1 = b.geometry.bounds
        c0, c1 = int(round((bx0 - x0) / cell)), int(round((bx1 - x0) / cell))
        r0, r1 = int(round((y1 - by1) / cell)), int(round((y1 - by0) / cell))
        sl = (slice(max(r0, 0), r1), slice(max(c0, 0), c1))
        n_cells = max((r1 - r0) * (c1 - c0), 1)
        area = n_cells * cell * cell
        g = int(ground[sl].sum())
        a = int(allpts[sl].sum())
        rows.append({"block_id": b.block_id, "ground_pts": g, "ground_ppm2": g / area,
                     "void_frac_05": 1.0 - float(occ[sl].sum()) / n_cells,
                     "water_share_pts": float(water[sl].sum()) / a if a else float("nan"),
                     "all_ppm2": a / area})
    df = pd.DataFrame(rows)
    df.attrs["class_totals"] = cls_tot or {}
    ek.assert_rows(df, len(blocks), "density per block")
    return df


# ============================================================================ observability
def robust_sd(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def detrend_local(dem: np.ndarray, win_cells: int = 21) -> np.ndarray:
    """DEM minus a local median (removes slope and long-wavelength relief). NaN kept as NaN."""
    from scipy.ndimage import median_filter
    fill = np.where(np.isfinite(dem), dem, np.nanmedian(dem))
    resid = dem - median_filter(fill, size=win_cells, mode="nearest")
    return np.where(np.isfinite(dem), resid, np.nan)


def min_detectable_depth(dem: np.ndarray, stable_mask: np.ndarray, k: float = 3.0, win_cells: int = 21) -> float:
    """fw 3.4 definition. k times the robust SD of detrended DEM on stable ground (pasture or crop)."""
    r = detrend_local(dem, win_cells)
    return k * robust_sd(r[stable_mask & np.isfinite(r)])


def feature_depths(dem: np.ndarray, transform, floors, ring_m: float = 5.0) -> np.ndarray:
    """Depth per floor polygon: median DEM in a ring_m ring outside the polygon minus the floor minimum."""
    from rasterio.features import geometry_mask
    out = []
    for geom in floors:
        inside = ~geometry_mask([geom], dem.shape, transform, invert=False)
        ring = ~geometry_mask([geom.buffer(ring_m).difference(geom)], dem.shape, transform, invert=False)
        f, r = dem[inside & np.isfinite(dem)], dem[ring & np.isfinite(dem)]
        out.append(float(np.median(r) - np.min(f)) if f.size and r.size else float("nan"))
    return np.array(out)


def feature_depths_from_raster(dem_path: Path, floors, ring_m: float = 5.0) -> np.ndarray:
    """Windowed version of feature_depths for large DEMs (reads one small window per polygon)."""
    import rasterio
    from rasterio.windows import from_bounds
    out = []
    with rasterio.open(dem_path) as r:
        for geom in floors:
            x0, y0, x1, y1 = geom.buffer(ring_m + 2 * r.res[0]).bounds
            win = from_bounds(x0, y0, x1, y1, r.transform).round_offsets().round_lengths()
            a = r.read(1, window=win, boundless=True, fill_value=np.nan).astype(np.float32)
            if r.nodata is not None:
                a[a == r.nodata] = np.nan
            out.append(feature_depths(a, r.window_transform(win), [geom], ring_m)[0])
    return np.array(out)


def observable_share(depths: np.ndarray, mdd: float) -> dict:
    d = depths[np.isfinite(depths)]
    k = int((d >= mdd).sum())
    p, lo, hi = ek.clopper_pearson(k, len(d)) if len(d) else (float("nan"),) * 3
    return {"mdd_m": mdd, "n": int(len(d)), "observable": k, "share": p, "ci95": [lo, hi]}


# ============================================================================ candidates / matching
def extract_candidates(prob: np.ndarray, cell: float, thr: float = CAND_THR, min_m2: float = MIN_BLOB_M2,
                       valid: np.ndarray | None = None):
    """Connected blobs above thr (8-connected), area >= min_m2, score = mean probability.

    Returns (labels int32 raster with 0 = none, DataFrame blob_id, score, area_m2, row, col).
    Nodata (non-finite or negative) never forms a blob. valid masks ineligible ground (water, edge).
    """
    from scipy import ndimage
    p = np.where(np.isfinite(prob) & (prob >= 0), prob, 0.0)
    m = p >= thr
    if valid is not None:
        m &= valid
    lab, n = ndimage.label(m, structure=np.ones((3, 3), int))
    if n == 0:
        return lab.astype(np.int32), pd.DataFrame(columns=["blob_id", "score", "area_m2", "row", "col"])
    idx = np.arange(1, n + 1)
    npx = ndimage.sum(np.ones_like(p), lab, idx)
    mean = ndimage.mean(p, lab, idx)
    com = ndimage.center_of_mass(np.ones_like(p), lab, idx)
    df = pd.DataFrame({"blob_id": idx, "score": mean, "area_m2": npx * cell * cell,
                       "row": [c[0] for c in com], "col": [c[1] for c in com]})
    keep = df["area_m2"] >= min_m2
    drop = df.loc[~keep, "blob_id"].to_numpy()
    if len(drop):
        lab[np.isin(lab, drop)] = 0
    return lab.astype(np.int32), df[keep].reset_index(drop=True)


def greedy_iou_match(cand_lab: np.ndarray, truth_lab: np.ndarray, iou_thr: float = IOU_MATCH) -> dict:
    """Greedy by IoU, one candidate to one truth (fw_00 section 4). Returns {blob_id: truth_id}.

    A second blob inside an already matched truth is a duplicate and stays unmatched.
    """
    m = (cand_lab > 0) & (truth_lab > 0)
    if not m.any():
        return {}
    pairs = pd.DataFrame({"c": cand_lab[m], "t": truth_lab[m]}).value_counts().rename("inter").reset_index()
    ca = pd.Series(np.bincount(cand_lab.ravel()))
    ta = pd.Series(np.bincount(truth_lab.ravel()))
    pairs["iou"] = pairs["inter"] / (ca[pairs["c"]].to_numpy() + ta[pairs["t"]].to_numpy() - pairs["inter"])
    pairs = pairs[pairs["iou"] >= iou_thr].sort_values(["iou", "c"], ascending=[False, True])
    used_c, used_t, out = set(), set(), {}
    for c, t in zip(pairs["c"], pairs["t"]):
        if c in used_c or t in used_t:
            continue
        used_c.add(c)
        used_t.add(t)
        out[int(c)] = int(t)
    return out


def block_of_pixels(rows, cols, transform, blocks) -> list:
    """Block id for each pixel centre (None outside all blocks)."""
    import geopandas as gpd
    xs = transform.c + (np.asarray(cols) + 0.5) * transform.a
    ys = transform.f + (np.asarray(rows) + 0.5) * transform.e
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs, ys), crs=blocks.crs)
    j = gpd.sjoin(pts, blocks[["block_id", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    return [None if pd.isna(v) else v for v in j["block_id"].reindex(pts.index)]


def build_block_tables(cands: pd.DataFrame, truth_block: dict, eligible_blocks: pd.DataFrame) -> dict:
    """Per-block tables for resampling.

    cands           blob_id, score, area_m2, block_id, truth_id (NaN if unmatched)
    truth_block     {truth_id: block_id} for every truth feature (by its centroid)
    eligible_blocks block_id, area_km2 for every COMPLETE eligible block (empty ones included)
    """
    tables = {}
    nt = pd.Series(truth_block).value_counts()
    for b, a in zip(eligible_blocks["block_id"], eligible_blocks["area_km2"]):
        c = cands[cands["block_id"] == b][["blob_id", "score", "area_m2", "truth_id"]]
        tables[b] = {"c": c.reset_index(drop=True), "n_truth": int(nt.get(b, 0)), "km2": float(a)}
    return tables


def pooled_recall_at_k(tables: dict, block_list: list, k_per_km2: float = K_PER_KM2) -> float:
    """Pooled recall at K per km2 over the listed blocks (duplicates from resampling allowed).

    Each copy of a block gets its own truth namespace so a duplicated block counts its hits twice,
    as the pooled-count bootstrap requires (fw_00 section 4).
    """
    if not block_list:
        return float("nan")
    parts, n_truth, km2 = [], 0, 0.0
    for j, b in enumerate(block_list):
        t = tables[b]
        n_truth += t["n_truth"]
        km2 += t["km2"]
        if len(t["c"]):
            c = t["c"].copy()
            c["truth_id"] = [f"{j}:{v}" if pd.notna(v) else None for v in c["truth_id"]]
            c["blob_id"] = [f"{j}:{v}" for v in c["blob_id"]]
            parts.append(c)
    if n_truth == 0:
        return float("nan")
    if not parts:
        return 0.0
    c = pd.concat(parts, ignore_index=True)
    r = ek.recall_at_k(c["score"], c["truth_id"], [None] * len(c), {"all": n_truth}, km2,
                       k_per_km2=k_per_km2, areas=c["area_m2"], cand_ids=c["blob_id"])
    return r["recall"]


def density_per_km2(tables: dict, blocks: list | None = None) -> float:
    bl = blocks or list(tables)
    km2 = sum(tables[b]["km2"] for b in bl)
    return sum(tables[b]["n_truth"] for b in bl) / km2 if km2 else float("nan")


def ceiling_per_block(tables: dict, k_per_km2: float = K_PER_KM2) -> pd.DataFrame:
    """Highest possible recall at K per block, min(1, K / density)."""
    rows = []
    for b, t in tables.items():
        d = t["n_truth"] / t["km2"] if t["km2"] else float("nan")
        rows.append({"block_id": b, "density_per_km2": d,
                     "ceiling": 1.0 if d == 0 else min(1.0, k_per_km2 / d)})
    return pd.DataFrame(rows)


def permutation_null_band(tab_a: dict, tab_b: dict, k_per_km2: float, B: int = 2000, seed: int = 0) -> dict:
    """Null band of recall(a) - recall(b) under exchange of area labels across blocks (< 15 blocks).

    Report beside the bootstrap interval with a warning. Not a confidence interval for the effect.
    """
    rng = np.random.default_rng(seed)
    merged = {("a", k): v for k, v in tab_a.items()} | {("b", k): v for k, v in tab_b.items()}
    keys = list(merged)
    na = len(tab_a)
    obs = pooled_recall_at_k(merged, keys[:na], k_per_km2) - pooled_recall_at_k(merged, keys[na:], k_per_km2)
    d = []
    for _ in range(B):
        perm = [keys[i] for i in rng.permutation(len(keys))]
        d.append(pooled_recall_at_k(merged, perm[:na], k_per_km2) - pooled_recall_at_k(merged, perm[na:], k_per_km2))
    d = np.array(d)
    lo, hi = np.nanpercentile(d, [2.5, 97.5])
    return {"observed": float(obs), "null_lo": float(lo), "null_hi": float(hi),
            "p_two_sided": float(np.nanmean(np.abs(d) >= abs(obs)))}


def transfer_difference(tab_t: dict, tab_ref: dict, margin: float, k_per_km2: float = K_PER_KM2,
                        B: int = 2000, seed: int = 0) -> dict:
    """Primary transfer estimand. Target minus reference recall at K, independent block bootstraps."""
    fa = lambda bl: pooled_recall_at_k(tab_t, bl, k_per_km2)    # noqa: E731
    fb = lambda bl: pooled_recall_at_k(tab_ref, bl, k_per_km2)  # noqa: E731
    d, lo, hi = ek.bootstrap_diff(fa, list(tab_t), fb, list(tab_ref), B=B, seed=seed)
    pt, tlo, thi, _ = ek.block_bootstrap(fa, list(tab_t), B=B, seed=seed + 1)
    out = {"k_per_km2": k_per_km2, "n_blocks_target": len(tab_t), "n_blocks_ref": len(tab_ref),
           "recall_target": pt, "recall_target_ci": [tlo, thi], "recall_ref": fb(list(tab_ref)),
           "diff": d, "diff_ci": [lo, hi], "margin": margin,
           "decision": ek.decide(lo, hi, margin, "noninferiority"),
           "density_target": density_per_km2(tab_t), "density_ref": density_per_km2(tab_ref)}
    if len(tab_t) < 15:
        out["warning"] = "fewer than 15 target blocks, bootstrap unreliable, see permutation band"
        out["permutation"] = permutation_null_band(tab_t, tab_ref, k_per_km2, B=min(B, 500), seed=seed + 2)
    return out


def paired_arm_difference(tab_arm: dict, tab_base: dict, delta_gain: float, k_per_km2: float = K_PER_KM2,
                          B: int = 2000, seed: int = 0) -> dict:
    """Paired arms on the same blocks (same resampled blocks for both). Superiority against delta_gain."""
    if set(tab_arm) != set(tab_base):
        raise AssertionError("paired arms must be scored on identical blocks")
    bl = sorted(tab_arm)
    fa = lambda b: pooled_recall_at_k(tab_arm, b, k_per_km2)   # noqa: E731
    fb = lambda b: pooled_recall_at_k(tab_base, b, k_per_km2)  # noqa: E731
    d, lo, hi = ek.bootstrap_diff(fa, bl, fb, bl, B=B, seed=seed, paired=True)
    return {"gain": d, "gain_ci": [lo, hi], "delta_gain": delta_gain, "n_blocks": len(bl),
            "decision": ek.decide(lo, hi, delta_gain, "superiority")}


def density_scaled_k(density_target: float, density_9t: float, k_9t: float = K_PER_KM2) -> float:
    """Secondary K = c * density, c = K_9t / density_9t fixed from 9t before scoring."""
    return (k_9t / density_9t) * density_target


def score_raster(prob_path: Path, truth, blocks, eligible_mask_fn=None, thr: float = CAND_THR) -> tuple:
    """Read a probability raster, extract candidates, match to truth polygons, build block tables.

    truth  GeoDataFrame of truth polygons (same CRS) with a 'truth_id' column
    blocks GeoDataFrame with block_id, area_km2 and an 'eligible' bool column (complete blocks only)
    Returns (tables, cand DataFrame).
    """
    import rasterio
    from rasterio.features import rasterize
    with rasterio.open(prob_path) as r:
        ek.assert_crs(r, blocks.crs)
        prob = r.read(1).astype(np.float32)
        if r.nodata is not None:
            prob[prob == r.nodata] = np.nan
        if r.dtypes[0] == "uint8":           # mosaic convention, DN / 254, 255 nodata (protocol s2)
            prob = np.where(prob == 255, np.nan, prob / 254.0)
        tf, cell = r.transform, r.res[0]
    ek.assert_crs(truth, blocks.crs)
    elig = blocks[blocks["eligible"]]
    valid = rasterize([(g, 1) for g in elig.geometry], out_shape=prob.shape, transform=tf, fill=0).astype(bool)
    if eligible_mask_fn is not None:
        valid &= eligible_mask_fn(prob.shape, tf)
    lab, cands = extract_candidates(prob, cell, thr, valid=valid)
    tl = rasterize([(g, int(i)) for g, i in zip(truth.geometry, truth["truth_id"])], out_shape=prob.shape,
                   transform=tf, fill=0, dtype="int32")
    match = greedy_iou_match(lab, tl)
    cands["truth_id"] = cands["blob_id"].map(match)
    cands["block_id"] = block_of_pixels(cands["row"], cands["col"], tf, blocks) if len(cands) else []
    cents = truth.geometry.centroid
    tj = __import__("geopandas").sjoin(__import__("geopandas").GeoDataFrame(
        {"truth_id": truth["truth_id"].to_numpy()}, geometry=cents.to_numpy(), crs=truth.crs),
        elig[["block_id", "geometry"]], how="inner", predicate="within")
    truth_block = dict(zip(tj["truth_id"], tj["block_id"]))
    cands = cands[cands["block_id"].isin(elig["block_id"])]
    return build_block_tables(cands, truth_block, elig), cands


# ============================================================================ agreement
def polygon_f1(a, b, iou_thr: float = IOU_MATCH) -> dict:
    """Pad- or pit-existence agreement between two annotators. Greedy IoU match on polygons."""
    pairs = []
    for i, ga in enumerate(a.geometry):
        for j in b.sindex.query(ga, predicate="intersects"):
            gb = b.geometry.iloc[j]
            inter = ga.intersection(gb).area
            iou = inter / (ga.area + gb.area - inter) if inter else 0.0
            if iou >= iou_thr:
                pairs.append((iou, i, int(j)))
    pairs.sort(key=lambda t: (-t[0], t[1], t[2]))
    ua, ub, matched = set(), set(), []
    for iou, i, j in pairs:
        if i not in ua and j not in ub:
            ua.add(i)
            ub.add(j)
            matched.append((i, j))
    tp = len(matched)
    prec = tp / len(b) if len(b) else float("nan")
    rec = tp / len(a) if len(a) else float("nan")
    f1 = 2 * tp / (len(a) + len(b)) if (len(a) + len(b)) else float("nan")
    return {"n_a": len(a), "n_b": len(b), "matched": tp, "precision_b_vs_a": prec, "recall_b_vs_a": rec,
            "f1": f1, "pairs": matched}


def cohen_kappa(x, y) -> float:
    x, y = np.asarray(x), np.asarray(y)
    if len(x) == 0:
        return float("nan")
    cats = sorted(set(x) | set(y))
    po = float(np.mean(x == y))
    pe = sum(float(np.mean(x == c)) * float(np.mean(y == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


# ============================================================================ inference / derivatives
def check_checkpoint(ckpt: Path, expected_sha: str | None) -> str:
    require_input(ckpt, "frozen checkpoint", "torch best.pt with state_dict, mu, sd, channels, epoch")
    sha = ek.sha256(ckpt)
    if expected_sha and sha != expected_sha:
        raise AssertionError(f"checkpoint hash {sha[:12]} != expected {expected_sha[:12]} ({ckpt})")
    return sha


def frozen_infer(features: Path, ckpt: Path, task: str, out_dir: Path, suffix: str,
                 expected_sha: str | None = None) -> Path:
    """Run one frozen checkpoint with the repo's infer_one (mu and sd come from the checkpoint).

    GPU if available. Asserts the stack band count equals the checkpoint channel count.
    """
    import rasterio
    sys.path.insert(0, str(WSV2 / "s4_infer"))
    sys.path.insert(0, str(WSV2))
    import torch
    from _predict_on_tile import TASKS, infer_one  # noqa: E402
    check_checkpoint(ckpt, expected_sha)
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    with rasterio.open(require_input(features, "feature stack (0.5 m, 7 bands, 9t order)")) as r:
        if r.count != len(ck["channels"]):
            raise AssertionError(f"stack has {r.count} bands, checkpoint wants {ck['channels']}")
    _, _, ncls, patch, ov = {t[0]: t for t in TASKS}[task]
    out_dir.mkdir(parents=True, exist_ok=True)
    infer_one(task, ckpt, ncls, patch, ov, features, out_dir, suffix)
    return out_dir / (f"pit_prob_floor_{suffix}.tif" if task == "pit" else f"{task}_prob_{suffix}.tif")


def mean_rasters(paths: list[Path], out: Path) -> Path:
    """Arm policy. Pixel mean of seed probability rasters on one grid (NaN where any seed is nodata)."""
    import rasterio
    acc = None
    for p in paths:
        with rasterio.open(p) as r:
            a = r.read(1).astype(np.float32)
            if r.nodata is not None:
                a[a == r.nodata] = np.nan
            prof = r.profile.copy()
            acc = a if acc is None else acc + a
    prof.update(dtype="float32", nodata=-1.0)
    m = acc / len(paths)
    with rasterio.open(out, "w", **prof) as d:
        d.write(np.where(np.isfinite(m), m, -1.0).astype(np.float32), 1)
    return out


def build_derivatives_cmd(tiles_glob: str, bbox: tuple, suffix: str, crs: str, src_crs: str | None,
                          out_dir: Path, res: float = 0.5) -> list[str]:
    """Command line for the 9t derivative builder (frozen 0.5 m pipeline, protocol section 3 rule 5)."""
    cmd = [sys.executable, str(WSV2 / "s1_build" / "_build_derivatives.py"), "--tiles", tiles_glob,
           "--bbox", ",".join(f"{v:.2f}" for v in bbox), "--suffix", suffix, "--res", str(res),
           "--crs", crs, "--out-dir", str(out_dir)]
    if src_crs:
        cmd += ["--src-crs", src_crs]
    return cmd


# ============================================================================ training (isolated sampler)
def sample_windows(train_blocks, forbidden, patch_m: float, n: int, seed: int, max_tries: int = 50):
    """Whole-window exclusion sampler (protocol section 3 rule 3).

    Draw a centre inside a training block, form the full patch box, and reject it if the box
    touches forbidden ground (union of held-out, test, audit and validation blocks plus buffer).
    Returns a list of (x0, y0, x1, y1) boxes in map units.
    """
    from shapely.geometry import box
    rng = np.random.default_rng(seed)
    geoms = list(train_blocks.geometry)
    if not geoms:
        return []
    out, tries, h = [], 0, patch_m / 2
    while len(out) < n and tries < n * max_tries:
        tries += 1
        g = geoms[int(rng.integers(len(geoms)))]
        x0, y0, x1, y1 = g.bounds
        cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
        b = box(cx - h, cy - h, cx + h, cy + h)
        if forbidden is not None and b.intersects(forbidden):
            continue
        out.append(b.bounds)
    if len(out) < n:
        raise RuntimeError(f"sampler found {len(out)} of {n} windows clear of forbidden ground")
    return out


def fit_norm_stats(stack_path: Path, windows: list, max_windows: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """Per-channel mean and SD over training windows only (never over target or held-out ground)."""
    import rasterio
    from rasterio.windows import from_bounds
    s1 = s2 = cnt = None
    with rasterio.open(stack_path) as r:
        for bx in windows[:max_windows]:
            a = r.read(window=from_bounds(*bx, r.transform)).astype(np.float64)
            m = np.isfinite(a)
            a = np.where(m, a, 0)
            s1 = a.sum((1, 2)) if s1 is None else s1 + a.sum((1, 2))
            s2 = (a * a).sum((1, 2)) if s2 is None else s2 + (a * a).sum((1, 2))
            cnt = m.sum((1, 2)) if cnt is None else cnt + m.sum((1, 2))
    mu = s1 / np.maximum(cnt, 1)
    sd = np.sqrt(np.maximum(s2 / np.maximum(cnt, 1) - mu * mu, 1e-12))
    return mu.astype(np.float32), np.maximum(sd, 1e-6).astype(np.float32)


def fit_norm_stats_multi(sources: list[tuple]) -> tuple[np.ndarray, np.ndarray]:
    """Pooled per-channel mean and SD over (stack, label, windows) sources, each read on its own grid."""
    import rasterio
    from rasterio.windows import from_bounds
    s1 = s2 = cnt = 0.0
    for stack, _, windows in sources:
        with rasterio.open(stack) as r:
            for bx in windows[:400]:
                a = r.read(window=from_bounds(*bx, r.transform)).astype(np.float64)
                m = np.isfinite(a)
                a = np.where(m, a, 0)
                s1 = s1 + a.sum((1, 2))
                s2 = s2 + (a * a).sum((1, 2))
                cnt = cnt + m.sum((1, 2))
    mu = s1 / np.maximum(cnt, 1)
    sd = np.sqrt(np.maximum(s2 / np.maximum(cnt, 1) - mu * mu, 1e-12))
    return mu.astype(np.float32), np.maximum(sd, 1e-6).astype(np.float32)


def make_patch_dataset(sources: list[tuple[Path, Path, list]], mu, sd, patch_px: int, augment: bool, seed: int):
    """torch Dataset over (stack, label raster, windows) triples. Labels 255 = ignore."""
    import rasterio
    import torch
    from rasterio.windows import from_bounds
    from torch.utils.data import Dataset
    sys.path.insert(0, str(WSV2))
    from _dl import normalize, random_d4

    items = [(s, l, w) for s, l, ws in sources for w in ws]

    class _DS(Dataset):
        def __init__(self):
            self.rng = np.random.default_rng(seed)

        def __len__(self):
            return len(items)

        def __getitem__(self, i):
            s, l, bx = items[i]
            with rasterio.open(s) as rs, rasterio.open(l) as rl:
                win = from_bounds(*bx, rs.transform).round_offsets().round_lengths()
                x = rs.read(window=win, out_shape=(rs.count, patch_px, patch_px), boundless=True,
                            fill_value=np.nan).astype(np.float32)
                y = rl.read(1, window=from_bounds(*bx, rl.transform).round_offsets().round_lengths(),
                            out_shape=(patch_px, patch_px), boundless=True, fill_value=255).astype(np.int64)
            x = normalize(x, mu, sd)
            if augment:
                x, y = random_d4(x, y, self.rng)
            return torch.from_numpy(np.ascontiguousarray(x)), torch.from_numpy(np.ascontiguousarray(y))
    return _DS()


def train_unet(train_sources, val_sources, mu, sd, out_dir: Path, *, n_classes: int, patch_px: int,
               epochs: int, lr: float, alpha, seed: int, init_ckpt: Path | None = None, batch: int = 8,
               channels: list | None = None, extra: dict | None = None) -> dict:
    """Train or fine-tune the repo U-Net (_dl.UNet, FocalCE, train_loop). Mixed precision on CUDA.

    Selection uses validation windows only. Writes best.pt with mu, sd, channels and the split hash.
    """
    import torch
    from torch.utils.data import DataLoader
    sys.path.insert(0, str(WSV2))
    from _dl import FocalCE, UNet, train_loop
    torch.manual_seed(seed)
    in_ch = len(mu)
    model = UNet(in_ch=in_ch, n_classes=n_classes, base=32)
    if init_ckpt is not None:
        ck = torch.load(init_ckpt, map_location="cpu", weights_only=False)
        sd0 = ck["state_dict"]
        own = model.state_dict()
        loadable = {k: v for k, v in sd0.items() if k in own and own[k].shape == v.shape}
        own.update(loadable)
        model.load_state_dict(own)
    tl = DataLoader(make_patch_dataset(train_sources, mu, sd, patch_px, True, seed), batch_size=batch, shuffle=True)
    vl = DataLoader(make_patch_dataset(val_sources, mu, sd, patch_px, False, seed + 1), batch_size=batch)
    names = ("bg", "floor", "wall")[:n_classes] if n_classes == 3 else tuple(f"c{c}" for c in range(n_classes))
    return train_loop(model=model, train_loader=tl, val_loader=vl, loss_fn=FocalCE(alpha), epochs=epochs, lr=lr,
                      n_classes=n_classes, out_dir=out_dir, score=lambda iou: float(np.nanmean(iou[1:])),
                      checkpoint_extra={"mu": mu.tolist(), "sd": sd.tolist(), "channels": channels or
                                        [f"b{i}" for i in range(in_ch)], "seed": seed, **(extra or {})},
                      extra_iou_names=names)


# ============================================================================ prereg / provenance
def prereg_markdown(exp_id: str, cfg: dict) -> str:
    pr = cfg.get("prereg", {})
    lines = [f"# Preregistration draft {exp_id}", "", "Generated by the build agent from the config. "
             "Fill every TBD before scoring. Commit before any target score is seen.", "",
             "| Item | Value |", "|---|---|"]
    for k in ["primary_estimand", "k_per_km2", "margin", "delta_gain", "model_policy", "checkpoint_sha256",
              "master_seed", "buffer_m", "void_cap", "n_min_blocks", "strata", "annotation_protocol"]:
        v = pr.get(k, "TBD")
        lines.append(f"| {k} | {json.dumps(v) if not isinstance(v, str) else v} |")
    lines += ["", "Margins come from the burden tradeoff, never from fold spread or variance.",
              "One threshold serves success and failure. The band between is inconclusive."]
    return "\n".join(lines) + "\n"


def finish_run(run_dir: Path, inputs: list, outputs: list, params: dict, seeds: dict | None = None) -> Path:
    return ek.write_provenance(run_dir, inputs=inputs, outputs=outputs, params=params, seeds=seeds or {})


# ============================================================================ figures
def plot_recall_strata(df: pd.DataFrame, out_png: Path, title: str = "") -> Path:
    """Recall with intervals per stratum and arm. Colour plus marker shape (colourblind rule)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = [ek.PALETTE["blue"], ek.PALETTE["orange"], ek.PALETTE["grey"], ek.PALETTE["charcoal"]]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    strata = list(dict.fromkeys(df["stratum"]))
    for i, (arm, g) in enumerate(df.groupby("arm", sort=False)):
        x = [strata.index(s) + 0.12 * i for s in g["stratum"]]
        ax.errorbar(x, g["recall"], yerr=[g["recall"] - g["lo"], g["hi"] - g["recall"]], fmt=MARKERS.get(arm, "o"),
                    color=cols[i % len(cols)], label=arm, capsize=3)
    ax.set_xticks(range(len(strata)), strata)
    ax.set_ylabel(f"recall at K = {K_PER_KM2:.0f} per km2")
    ax.set_ylim(0, 1)
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


# ============================================================================ CLI
def _blocks_for_area(cfg: dict, area: str, exp_id: str):
    import geopandas as gpd
    a = cfg["areas"][area]
    p = area_transfer_dir(area) / f"xfer_blocks_roles_{area}.gpkg"
    if p.exists():
        g = gpd.read_file(p)
        ek.assert_crs(g, a["crs"])
        return g
    lon, lat = a["centre_lonlat"]
    w = window_box(lon, lat, a["crs"], a.get("side_km", 5.0))
    return make_blocks(w.bounds, a["crs"])


def _cmd_cover(args, cfg):
    df = window_cover_table([a["catalogue_window"] for a in cfg["areas"].values() if a.get("catalogue_window")])
    out = ek.sub(args.exp, "results/tables") / f"xfer_window_cover_{args.exp.replace('.', '_')}.csv"
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    print(f"wrote {out}")


def _cmd_density(args, cfg):
    a = cfg["areas"][args.area]
    lidar_dir = resolve(a["lidar_dir"], args.exp)
    tiles = sorted(Path(require_input(lidar_dir, f"lidar tiles for {args.area}", "LAZ/LAS with class 2",
                                      "pdal info --summary on one tile")).glob("*.la[sz]"))
    if args.max_tiles:
        tiles = tiles[:args.max_tiles]
    if not tiles:
        raise MissingInputError(f"no .las/.laz in {lidar_dir}")
    blocks = _blocks_for_area(cfg, args.area, args.exp)
    df = las_block_density(tiles, blocks)
    for k, v in REF_9T.items():
        df[f"ref9t_{k}"] = v
    out = area_transfer_dir(args.area) / f"xfer_density_void_{args.area}.csv"
    df.to_csv(out, index=False)
    finish_run(out.parent, tiles, [out], {"area": args.area, "class_totals": df.attrs.get("class_totals")})
    print(df.describe().T.to_string())
    print(f"wrote {out}")


def _cmd_blocks(args, cfg):
    a = cfg["areas"][args.area]
    blocks = _blocks_for_area(cfg, args.area, args.exp)
    dens = area_transfer_dir(args.area) / f"xfer_density_void_{args.area}.csv"
    if dens.exists():
        blocks = blocks.merge(pd.read_csv(dens)[["block_id", "void_frac_05", "ground_ppm2"]], on="block_id", how="left")
        blocks["over_void_cap"] = blocks["void_frac_05"] > cfg["prereg"].get("void_cap", 1.0)
    pr = cfg["prereg"]
    g = assign_roles(blocks, a.get("role_fractions", {"test": 1.0}), seed=int(pr.get("master_seed", 0)),
                     buffer_m=float(pr.get("buffer_m", 0.0)), strata_col=args.strata)
    over = g["over_void_cap"].fillna(False).astype(bool) if "over_void_cap" in g else False
    g["eligible"] = ~g["edge"] & ~over
    out = area_transfer_dir(args.area) / f"xfer_blocks_roles_{args.area}.gpkg"
    g.to_file(out, driver="GPKG")
    print(g["role"].value_counts().to_string())
    print(f"wrote {out}")


def _cmd_derive(args, cfg):
    a = cfg["areas"][args.area]
    lidar_dir = require_input(resolve(a["lidar_dir"], args.exp), f"lidar tiles for {args.area}")
    lon, lat = a["centre_lonlat"]
    bbox = window_box(lon, lat, a["crs"], a.get("side_km", 5.0)).bounds
    if args.pilot_km:
        bbox = window_box(lon, lat, a["crs"], args.pilot_km).bounds
    out = ek.area_dir(args.area) / "derived" / "05"
    cmd = build_derivatives_cmd(str(Path(lidar_dir) / "*.laz"), bbox, f"{args.area}_05", a["crs"],
                                a.get("src_crs"), out)
    print(" ".join(cmd))
    if args.execute:
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, check=True)
    else:
        print("dry run. Add --execute to build (time one block first, F: for heavy outputs).")


def _cmd_infer(args, cfg):
    a = cfg["areas"][args.area]
    m = cfg["model"][args.task]
    ckpt = resolve(m["checkpoint"], args.exp)
    feats = ek.area_dir(args.area) / "derived" / "05" / f"features_{args.area}_05.tif"
    run = ek.new_run(args.exp, f"infer_{args.task}", {"area": args.area, **m},
                     base=area_transfer_dir(args.area), why="frozen zero-shot inference")
    prob = frozen_infer(feats, ckpt, args.task, run, f"{args.area}_05", m.get("sha256"))
    finish_run(run, [feats, ckpt], [prob], {"task": args.task, "area": args.area})
    print(f"wrote {prob}")


def _cmd_score(args, cfg):
    import geopandas as gpd
    pr = cfg["prereg"]
    blocks = gpd.read_file(require_input(area_transfer_dir(args.area) / f"xfer_blocks_roles_{args.area}.gpkg",
                                         "block roles", "run the 'blocks' subcommand first"))
    blocks = blocks[blocks["role"].isin(args.roles.split(","))]
    if args.strata_filter:
        col, vals = args.strata_filter.split("=")
        blocks = blocks[blocks[col].isin(vals.split(","))]
    truth = gpd.read_file(require_input(area_transfer_dir(args.area) / f"xfer_truth_features_{args.area}.gpkg",
                                        "blind truth polygons", "polygons with truth_id, class, block_id"))
    truth = truth[truth["class"].isin(args.classes.split(","))] if "class" in truth else truth
    tab_t, cands = score_raster(Path(args.prob), truth, blocks)
    ref = json.loads(require_input(resolve(cfg["reference"]["tables"], args.exp), "9t reference block tables",
                                   "JSON {block_id: {cands: [...], n_truth, km2}} from 3.0").read_text())
    tab_ref = {b: {"c": pd.DataFrame(v["cands"]), "n_truth": v["n_truth"], "km2": v["km2"]} for b, v in ref.items()}
    by_area = cfg["prereg"].get("margin_by_area", {})
    margin = by_area.get(args.area)
    if margin is None:   # per-area margin (Canada, one per province) wins, else the single prereg margin
        margin = need_decision(cfg, "margin", "tolerable missed-feature burden at K")
    margin = float(margin)
    res = transfer_difference(tab_t, tab_ref, margin, B=args.B, seed=int(pr.get("master_seed", 0)))
    res.update({"arm": args.arm, "area": args.area, "evidence_level": "(a) drawn feature",
                "contrast_only": bool(args.contrast),
                "density_scaled_k": density_scaled_k(res["density_target"], res["density_ref"]),
                "ceiling_share_below_0p9": float((ceiling_per_block(tab_t)["ceiling"] < 0.9).mean())})
    run = Path(args.prob).parent
    out = run / f"xfer_score_k40_{args.arm}_{args.area}.json"
    out.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    cands.to_csv(run / f"xfer_candidates_{args.arm}_{args.area}.csv", index=False)
    print(json.dumps({k: res[k] for k in ("recall_target", "diff", "diff_ci", "decision")}, indent=2))
    print(f"wrote {out}")


def _cmd_width(args, cfg):
    pr = cfg["prereg"]
    ref = json.loads(require_input(resolve(cfg["reference"]["tables"], args.exp), "9t out-of-fold block tables",
                                   "JSON {block_id: {cands, n_truth, km2}}").read_text())
    tab = {b: {"c": pd.DataFrame(v["cands"]), "n_truth": v["n_truth"], "km2": v["km2"]} for b, v in ref.items()}
    w = ek.projected_width(lambda bl: pooled_recall_at_k(tab, bl), list(tab), args.n_target, B=args.B,
                           reps=args.reps, seed=int(pr.get("master_seed", 0)))
    m = float(need_decision(cfg, "margin", "tolerable missed-feature burden at K"))
    res = {"n_target": args.n_target, "median_width": w, "margin": m, "ok": bool(w <= 2 * m)}
    out = ek.sub(args.exp, "results/tables") / f"xfer_projected_width_{args.exp.replace('.', '_')}.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(res, f"\nwrote {out}")


def _cmd_agree(args, cfg):
    import geopandas as gpd
    a = gpd.read_file(require_input(Path(args.a), "annotator A polygons"))
    b = gpd.read_file(require_input(Path(args.b), "annotator B polygons"))
    ek.assert_crs(a, b.crs)
    r = polygon_f1(a, b)
    if "class" in a and "class" in b and r["pairs"]:
        r["class_kappa"] = cohen_kappa([a["class"].iloc[i] for i, _ in r["pairs"]],
                                       [b["class"].iloc[j] for _, j in r["pairs"]])
    r.pop("pairs")
    out = area_transfer_dir(args.area) / f"xfer_label_agreement_{args.area}.json"
    out.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(r, f"\nwrote {out}")


def _cmd_prereg(args, cfg):
    out = ek.sub(args.exp, "docs") / f"prereg_draft_{args.exp.replace('.', '_')}.md"
    out.write_text(prereg_markdown(args.exp, cfg), encoding="utf-8")
    print(f"wrote {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ["cover", "density", "blocks", "derive", "infer", "score", "width", "agree", "prereg"]:
        p = sp.add_parser(name)
        p.add_argument("--exp", required=True, help="expansion id, e.g. 3.4")
        if name not in ("cover", "width", "prereg"):
            p.add_argument("--area", required=True, help="area tag from the config, e.g. la_caddo")
        if name == "density":
            p.add_argument("--max-tiles", type=int, default=1, help="pilot rule. One tile first (0 = all)")
        if name == "blocks":
            p.add_argument("--strata", default=None, help="column to stratify the role draw on")
        if name == "derive":
            p.add_argument("--pilot-km", type=float, default=0.0, help="side of a pilot box (bootstrap rule)")
            p.add_argument("--execute", action="store_true")
        if name == "infer":
            p.add_argument("--task", choices=["pit", "pad"], default="pit")
        if name == "score":
            p.add_argument("--prob", required=True)
            p.add_argument("--arm", default="A0")
            p.add_argument("--roles", default="test")
            p.add_argument("--classes", default="pit,pad")
            p.add_argument("--strata-filter", default="", help="col=v1,v2 (e.g. wet_stratum=dry,mixed)")
            p.add_argument("--contrast", action="store_true", help="label as a contrast arm, never pooled")
            p.add_argument("--B", type=int, default=2000)
        if name == "width":
            p.add_argument("--n-target", type=int, required=True)
            p.add_argument("--B", type=int, default=2000)
            p.add_argument("--reps", type=int, default=50)
        if name == "agree":
            p.add_argument("--a", required=True)
            p.add_argument("--b", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(args.exp)
    try:
        globals()[f"_cmd_{args.cmd}"](args, cfg)
    except (MissingInputError, DecisionMissingError) as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

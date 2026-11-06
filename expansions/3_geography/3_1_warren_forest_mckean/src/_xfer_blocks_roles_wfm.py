"""3.1 S1. Blocks, eligibility and seeded roles for a transfer area.

Purpose
    Lay 375 m blocks over the union of tile footprints (geometries, never tile counts). Per
    block, record the covered share, measured ground density (class-2 points per m2) and the
    0.5 m void fraction, and the mean 1 m slope. A block is eligible when it is complete
    (cover >= min_cover), its void fraction is at or under the cap, and its ground density is
    at or above the rule. Blocks under the density rule form a labelled low-density stratum,
    never a silent drop. They enter the role draw (stratified apart) so the scorer has low-density test
    blocks to report, but they never enter the primary statistic (review G-07). Roles come from a seeded draw (assign_roles in _geo_xfer_lib).
    Adaptation is one contiguous strip at least the derived buffer from test and audit, and
    is dropped when the strip is under min_adapt_km2. Test and audit are stratified by slope
    tercile. A seeded 20% of test blocks is marked for the independent completeness recheck.

Inputs
    S0 inventory    results/tables/<area>/xfer_tile_inventory_<area>.csv
    tiles           config areas.<area>.tiles (read only with --density las)
    slope           config areas.<area>.slope_1m (optional; stratification falls back to none)
    9t reference    data/9t/derived/05/ground_density_9t_05.tif and pit_blocks_9t.gpkg (density rule 9t_p5)
    assumed         P1 derived buffer, read with ek.read_buffer(task) (review P1-03). --provisional-buffer
                    uses fallback_buffer_m and labels the output provisional.
    --from-roles    redraw roles from an existing roles GeoPackage's measured columns, without a LAS pass

Outputs
    expansions/3_geography/3_1_warren_forest_mckean/results/tables/<area>/xfer_blocks_roles_<area>.gpkg  (layer blocks)
    .../results/tables/<area>/xfer_audit_blocks_<area>_v1.csv
    .../results/tables/<area>/xfer_blocks_roles_<area>.json   (cut points, density rule, role counts, seed)

Run
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_blocks_roles_wfm.py --area warren --density las --provisional-buffer
    python expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_blocks_roles_wfm.py --area mckean --density las --seed 20261105
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _geo_xfer_lib as xl  # noqa: E402
from _xfer_tile_inventory_wfm import footprint_6346  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_1.json"


def tile_union(inv: pd.DataFrame):
    from shapely.ops import unary_union
    geoms = [footprint_6346(r, None if pd.isna(r["crs_epsg"]) else int(r["crs_epsg"])) for r in inv.to_dict("records")]
    return unary_union(geoms), geoms


def density_by_strips(blocks, tiles, tile_geoms, src_crs, res, rows_per_strip=4, block_m=375.0, tile_epsg=None):
    """Ground density and void per block, one strip of block rows at a time (bounded memory).
    tile_epsg (per tile, from the header) overrides src_crs, so mixed-CRS deliveries work."""
    dens = pd.Series(np.nan, index=blocks.index)
    void = pd.Series(np.nan, index=blocks.index)
    for iy0 in range(0, int(blocks.iy.max()) + 1, rows_per_strip):
        sel = blocks[(blocks.iy >= iy0) & (blocks.iy < iy0 + rows_per_strip)]
        if not len(sel):
            continue
        x0, y0, x1, y1 = sel.total_bounds
        from shapely.geometry import box
        strip = box(x0, y0, x1, y1)
        use = [t for t, g in zip(tiles, tile_geoms) if g.intersects(strip)]
        if not use:
            continue
        g = None
        for crs in sorted({(tile_epsg or {}).get(t.name, src_crs) or "" for t in use}):
            grp = [t for t in use if ((tile_epsg or {}).get(t.name, src_crs) or "") == crs]
            gi, tf, _ = xl.ground_grid(grp, (x0, y0, x1, y1), res, src_crs=crs or None)
            g = gi if g is None else g + gi
        d, v = xl.grid_stats_per_block(sel, g, tf, res)
        dens.loc[sel.index], void.loc[sel.index] = d, v
        print(f"  strip iy {iy0}-{iy0 + rows_per_strip - 1}: {len(use)} tiles, {len(sel)} blocks")
    return dens.to_numpy(), void.to_numpy()


def window_box(cfg, area):
    """Catalogue window box in EPSG:6346 when the area names a window (3.2 config), else None."""
    win = cfg["areas"][area].get("window")
    if not win or "catalogue" not in cfg:
        return None
    from pyproj import Transformer
    from shapely.geometry import box
    from shapely.ops import transform
    w = pd.read_csv(xl.resolve_path(cfg["catalogue"]["windows"]))
    w = w[w.window == win]
    if not len(w):
        raise xl.MissingInput(f"MISSING INPUT: window {win} not in the catalogue window table")
    w = w.iloc[0]
    tr = Transformer.from_crs(cfg["catalogue"]["tile_bbox_crs"], ek.DST_CRS, always_xy=True)
    return transform(lambda x, y: tr.transform(x, y), box(w.minx, w.miny, w.maxx, w.maxy).segmentize(0.001))


def ref_density_p5(cfg) -> float:
    """5th percentile of 9t block ground density (points per m2) from the held 9t raster."""
    import geopandas as gpd
    import rasterio
    R = cfg["reference"]
    b = gpd.read_file(xl.need(xl.resolve_path(R["blocks_9t"]), "9t blocks"), layer="blocks")
    with rasterio.open(xl.need(xl.resolve_path(R["ground_density_9t"]), "9t ground density")) as r:
        ek.assert_crs(r)
        g = r.read(1)
        d, _ = xl.grid_stats_per_block(b, g, r.transform, r.res[0])
    return float(np.nanpercentile(d, 5))


def derived_buffer(cfg, task: str, provisional: bool) -> tuple[float, bool]:
    """P1 derived buffer through ek.read_buffer (review P1-03). --provisional-buffer falls back, labelled."""
    try:
        p = xl.resolve_path(cfg["assumed"]["derived_buffer"]["spec"])
        return float(ek.read_buffer(task, p)), False
    except (FileNotFoundError, KeyError) as e:
        if not provisional:
            raise xl.MissingInput(f"MISSING INPUT: P1 derived buffer for task {task}\n  {e}\n"
                                  "  pass --provisional-buffer for a labelled provisional draw") from e
        return float(cfg["fallback_buffer_m"]), True


def eligibility_and_roles(blocks, cfg, dmin: float, buffer_m: float, seed: int, strat: str | None):
    """Eligibility flags and the seeded role draw.

    complete, void_ok, low_density as measured. 'eligible' is the PRIMARY stratum (complete, void_ok, not low
    density). Low-density blocks that are complete and void_ok enter the role draw too, stratified apart, so the
    low-density stratum has test blocks to score (review G-07). They never enter the primary statistic."""
    E, R = cfg["eligibility"], cfg["roles"]
    b = blocks.copy()
    b["complete"] = b.cover >= E["min_cover"]
    b["low_density"] = (b.ground_per_m2 < dmin).fillna(False).astype(bool)
    b["void_ok"] = b.void_frac.isna() | (b.void_frac <= E["max_void_frac"])
    b["eligible"] = b.complete & b.void_ok & ~b.low_density
    b["role_pool"] = b.complete & b.void_ok
    b["stratum"] = np.where(b.low_density, "low_density", "main")
    # main strata sort first, in the old tercile order, so the main-stratum draw is unchanged by adding
    # the low-density blocks (same seed, same rng sequence). Low-density strata are drawn after them.
    b["_strat"] = np.where(b.low_density, "1_low", "0_main") + ("_" + b[strat].astype(str) if strat else "")
    b, meta = xl.assign_roles(b, seed=seed, buffer_m=buffer_m, test_frac_of_rest=R["test_frac_of_rest"],
                              adapt_frac=R["adapt_frac"], min_adapt_km2=R["min_adapt_km2"], strat_col="_strat",
                              eligible_col="role_pool")
    b = b.drop(columns="_strat")
    rng = np.random.default_rng(ek.child_seed(seed, 0, 7))
    test_ids = b.loc[(b.role == "test") & b.eligible, "block_id"].to_numpy()
    n_re = int(np.ceil(R["recheck_frac"] * len(test_ids)))
    b["recheck"] = b.block_id.isin(rng.choice(test_ids, n_re, replace=False) if n_re else [])
    ek.assert_unique(b, "block_id")
    ek.assert_no_nan(b.block_id, "block ids")
    ek.assert_disjoint(b.block_id[b.role == "test"], b.block_id[b.role == "audit"], "test vs audit")
    meta["counts_by_stratum"] = {f"{s}/{r}": int(n) for (s, r), n in b.groupby(["stratum", "role"]).size().items()}
    return b, meta


def redraw_from_roles(a, cfg, ctx) -> int:
    """Redraw roles with this version from an existing roles file's measured columns. No LAS pass."""
    import geopandas as gpd
    old = gpd.read_file(a.from_roles, layer="blocks")
    keep = [c for c in ("block_id", "ix", "iy", "cover", "ground_per_m2", "void_frac", "slope_mean", "slope_tercile",
                        "geometry") if c in old]
    blocks = old[keep].copy()
    rule = cfg["eligibility"]["density_rule"]
    dmin = ref_density_p5(cfg) if rule == "9t_p5" else float(rule)
    buffer_m, buf_prov = derived_buffer(cfg, a.task, a.provisional_buffer)
    seed = a.seed if a.seed is not None else cfg["master_seed"]
    strat = "slope_tercile" if "slope_tercile" in blocks and (blocks.slope_tercile >= 0).any() else None
    blocks, meta = eligibility_and_roles(blocks, cfg, dmin, buffer_m, seed, strat)
    gp = ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg"
    blocks.to_file(gp, layer="blocks", driver="GPKG")
    au = ctx["tables"] / f"xfer_audit_blocks_{a.area}_v1.csv"
    blocks.loc[blocks.role == "audit", ["block_id"]].to_csv(au, index=False)
    cuts = (xl.terciles(blocks.slope_mean.where(blocks.cover >= cfg["eligibility"]["min_cover"]))[1]
            if "slope_mean" in blocks and blocks.slope_mean.notna().any() else None)
    meta.update({"area": a.area, "n_blocks": int(len(blocks)), "density_rule": rule, "density_min_per_m2": dmin,
                 "slope_cut_points_deg": cuts,
                 "buffer_provisional": buf_prov, "buffer_task": a.task, "seed": seed, "redrawn_from": str(a.from_roles),
                 "n_recheck": int(blocks.recheck.sum()),
                 "eligible_km2": float(blocks.geometry[blocks.eligible].area.sum() / 1e6),
                 "test_km2": float(blocks.geometry[(blocks.role == "test") & blocks.eligible].area.sum() / 1e6),
                 "low_density_test_km2": float(blocks.geometry[(blocks.role == "test") & blocks.low_density].area.sum() / 1e6)})
    js = ctx["tables"] / f"xfer_blocks_roles_{a.area}.json"
    js.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=float))
    print(f"wrote {gp}\n      {au}\n      {js}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--area", required=True)
    ap.add_argument("--density", choices=["las", "none"], default="las")
    ap.add_argument("--seed", type=int, default=None, help="role seed (goes in the prereg); default master_seed")
    ap.add_argument("--provisional-buffer", action="store_true")
    ap.add_argument("--rows-per-strip", type=int, default=4)
    ap.add_argument("--task", default="pit", help="task whose P1 buffer applies (ek.read_buffer)")
    ap.add_argument("--from-roles", default=None,
                    help="redraw roles from an existing roles GeoPackage's measured columns (no LAS pass)")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    ctx = xl.area_ctx(cfg, a.area)
    res, bm = cfg.get("res_m", 0.5), cfg.get("block_m", 375.0)
    if a.from_roles:
        return redraw_from_roles(a, cfg, ctx)
    inv_p = xl.need(ctx["tables"] / f"xfer_tile_inventory_{a.area}.csv", f"S0 inventory for {a.area}",
                    "run _xfer_tile_inventory_wfm.py first")
    inv = pd.read_csv(inv_p)
    cover, geoms = tile_union(inv)
    win = window_box(cfg, a.area)
    if win is not None:            # 3.2 windows: blocks only inside the catalogue window box
        cover = cover.intersection(win)
    x0, y0, x1, y1 = cover.bounds
    x0, y0 = np.floor(x0 / res) * res, np.floor(y0 / res) * res
    blocks = xl.make_blocks((x0, y0, x1, y1), size=bm)
    blocks["cover"] = xl.cover_fraction(blocks, cover)
    blocks = blocks[blocks.cover > 0].reset_index(drop=True)
    print(f"{a.area}: {len(blocks)} blocks touch the tile union ({cover.area / 1e6:.2f} km2)")

    buffer_m, buf_prov = derived_buffer(cfg, a.task, a.provisional_buffer)

    if a.density == "las":
        tiles = [t for t in ctx["tiles"] if t.name in set(inv.file)]
        if len(tiles) != len(inv):
            raise xl.MissingInput(f"MISSING INPUT: {len(inv) - len(tiles)} inventoried tiles not found under {ctx['tiles_pattern']}")
        geo_by = dict(zip(inv.file, geoms))
        epsg = {r.file: (f"EPSG:{int(r.crs_epsg)}" if pd.notna(r.crs_epsg) else None) for r in inv.itertuples()}
        blocks["ground_per_m2"], blocks["void_frac"] = density_by_strips(
            blocks, tiles, [geo_by[t.name] for t in tiles], ctx["src_crs"], res, a.rows_per_strip, bm, tile_epsg=epsg)
    else:
        blocks["ground_per_m2"], blocks["void_frac"] = np.nan, np.nan
    slope_p = ctx.get("slope_1m")
    if slope_p is not None and Path(slope_p).exists():
        blocks["slope_mean"] = xl.raster_mean_per_block(blocks, slope_p)
        blocks["slope_tercile"], cuts = xl.terciles(blocks.slope_mean.where(blocks.cover >= cfg["eligibility"]["min_cover"]))
        strat = "slope_tercile"
    else:
        blocks["slope_mean"], blocks["slope_tercile"], cuts, strat = np.nan, -1, None, None
        print(f"  no slope raster at {slope_p}; roles not stratified")

    rule = cfg["eligibility"]["density_rule"]
    dmin = ref_density_p5(cfg) if rule == "9t_p5" else float(rule)
    seed = a.seed if a.seed is not None else cfg["master_seed"]
    blocks, meta = eligibility_and_roles(blocks, cfg, dmin, buffer_m, seed, strat)

    gp = ctx["tables"] / f"xfer_blocks_roles_{a.area}.gpkg"
    blocks.to_file(gp, layer="blocks", driver="GPKG")
    au = ctx["tables"] / f"xfer_audit_blocks_{a.area}_v1.csv"
    blocks.loc[blocks.role == "audit", ["block_id"]].to_csv(au, index=False)
    meta.update({"area": a.area, "n_blocks": int(len(blocks)), "density_rule": rule, "density_min_per_m2": dmin,
                 "slope_cut_points_deg": cuts, "buffer_provisional": buf_prov, "buffer_task": a.task, "seed": seed,
                 "n_recheck": int(blocks.recheck.sum()),
                 "eligible_km2": float(blocks.geometry[blocks.eligible].area.sum() / 1e6),
                 "test_km2": float(blocks.geometry[(blocks.role == "test") & blocks.eligible].area.sum() / 1e6),
                 "low_density_test_km2": float(blocks.geometry[(blocks.role == "test") & blocks.low_density].area.sum() / 1e6),
                 "median_ground_per_m2": float(blocks.ground_per_m2.median()) if a.density == "las" else None,
                 "median_void_frac": float(blocks.void_frac.median()) if a.density == "las" else None})
    js = ctx["tables"] / f"xfer_blocks_roles_{a.area}.json"
    js.write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=float))
    print(f"wrote {gp}\n      {au}\n      {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

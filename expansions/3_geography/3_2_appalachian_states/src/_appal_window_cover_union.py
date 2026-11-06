"""3.2 S2. Lidar coverage and query audit per window, from tile geometries (never tile counts).

Purpose
    (1) Reconcile the catalogue query log. Each window is ok-complete, successful-empty,
        failed or incomplete (retrieved below the reported total). These are kept apart.
    (2) Union coverage. For each window and each project listed for it, the tile bounding
        boxes (lon/lat, EPSG:4269) are projected to EPSG:6346, unioned, and intersected with
        the window box. Cover = union area inside the window over window area. Bounding boxes
        are an upper bound on true footprints, so this cover is too. The configured program
        for each 3.2 window is marked, and the readiness flag compares its cover with the
        preregistered share (config prereg_cover_share).

Inputs (held, discovery only)
    data/_source/reference/lidar_catalogue/lidar_win_windows_us.csv, lidar_win_tile_window_us.csv,
    lidar_win_tiles_unique_us.csv, lidar_win_query_log_us.csv

Outputs
    expansions/3_geography/3_2_appalachian_states/results/tables/lidar_win_union_cover_appal.csv
    expansions/3_geography/3_2_appalachian_states/results/tables/lidar_win_query_audit_appal.csv

Run
    python expansions/3_geography/3_2_appalachian_states/src/_appal_window_cover_union.py
    python expansions/3_geography/3_2_appalachian_states/src/_appal_window_cover_union.py --all-windows
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "3_1_warren_forest_mckean" / "src"))
import _geo_xfer_lib as xl  # noqa: E402
ek = xl.ek

CFG = HERE.parent / "config_3_2.json"


def query_audit(log: pd.DataFrame) -> pd.DataFrame:
    q = log.copy()
    q["outcome"] = np.select(
        [q.status.ne("ok"), q.reported_total.fillna(0).eq(0), q.retrieved.lt(q.reported_total)],
        ["failed", "successful_empty", "incomplete"], default="ok_complete")
    return q


def window_cover(win_row, tiles: pd.DataFrame, src_crs: str, dst_crs: str = ek.DST_CRS):
    from pyproj import Transformer
    from shapely.geometry import box
    from shapely.ops import transform, unary_union
    tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    f = lambda g: transform(lambda x, y: tr.transform(x, y), g.segmentize(0.001))  # noqa: E731
    wbox = f(box(win_row.minx, win_row.miny, win_row.maxx, win_row.maxy))
    if not len(tiles):
        return 0.0, wbox.area / 1e6, 0
    u = unary_union([f(box(r.bb_minx, r.bb_miny, r.bb_maxx, r.bb_maxy)) for r in tiles.itertuples()])
    return float(u.intersection(wbox).area / wbox.area), float(wbox.area / 1e6), len(tiles)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--all-windows", action="store_true", help="every window in the catalogue, not only 3.2 tags")
    a = ap.parse_args(argv)
    cfg = xl.load_config(Path(a.config))
    C = cfg["catalogue"]
    wins = pd.read_csv(xl.need(xl.resolve_path(C["windows"]), "window table"))
    tw = pd.read_csv(xl.need(xl.resolve_path(C["tile_window"]), "tile-window table"))
    tu = pd.read_csv(xl.need(xl.resolve_path(C["tiles_unique"]), "unique tiles"))
    log = pd.read_csv(xl.need(xl.resolve_path(C["query_log"]), "query log"))
    n0 = len(tw)
    tw = tw.merge(tu[["url", "bb_minx", "bb_miny", "bb_maxx", "bb_maxy"]], on="url", how="left")
    ek.assert_rows(tw, n0, "tile-window joined to tile boxes")
    missing_bb = int(tw.bb_minx.isna().sum())
    qa = query_audit(log)
    T = ek.sub("3.2", "results/tables")
    qa.to_csv(T / "lidar_win_query_audit_appal.csv", index=False)
    tag_of = {v["window"]: (t, v.get("program")) for t, v in cfg["areas"].items()}
    targets = wins.window.tolist() if a.all_windows else list(tag_of)
    rows = []
    for w in targets:
        wr = wins[wins.window == w]
        tag, prog = tag_of.get(w, (None, None))
        if not len(wr):
            rows.append({"window": w, "tag": tag, "project": prog, "cover": np.nan, "note": "window not in rebuilt list"})
            continue
        wr = wr.iloc[0]
        q = qa[qa.window == w]
        sub = tw[(tw.window == w) & tw.bb_minx.notna()]
        for proj, g in sub.groupby("project"):
            cov, km2, n = window_cover(wr, g.drop_duplicates("url"), C["tile_bbox_crs"])
            rows.append({"window": w, "tag": tag, "project": proj, "configured": proj == prog, "tiles": n,
                         "window_km2": km2, "cover": cov, "query_outcome": q.outcome.iloc[0] if len(q) else "absent",
                         "ready_cover": bool(cov >= cfg["prereg_cover_share"]) if proj == prog else None})
        if prog and prog not in set(sub.project):
            rows.append({"window": w, "tag": tag, "project": prog, "configured": True, "tiles": 0, "cover": 0.0,
                         "ready_cover": False, "note": "configured program has no tiles listed for this window"})
    out = pd.DataFrame(rows)
    csv = T / "lidar_win_union_cover_appal.csv"
    out.to_csv(csv, index=False)
    print(out[out.configured.eq(True)].to_string(index=False))
    print(f"query outcomes {qa.outcome.value_counts().to_dict()}, tile rows without a box {missing_bb}")
    print(f"wrote {csv}\n      {T / 'lidar_win_query_audit_appal.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

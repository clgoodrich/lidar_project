"""S0. Flight-date bounds per lidar tile for the two 9t surveys (2006 to 2008 statewide, 2019 D20).

Purpose
    Eligibility needs real acquisition dates. File creation dates are not flight dates (protocol section 11).
    Three sources, in order of authority.
      1. metadata   USGS project metadata typed into flight_windows_metadata.csv (assumed input, D1)
      2. gps        point GPS time, only when the header says adjusted standard GPS time (seconds since
                    1980-01-06 minus 1e9). GPS week time carries no date and is reported as unresolvable.
                    A sampled read gives inner dates only and never sets an eligibility bound. --full-scan does.
      3. year_bounds the project's nominal years (2006-01-01 to 2008-12-31, 2019-01-01 to 2019-12-31).
                    Conservative only when the survey flew inside them. A sampled GPS date outside them widens the
                    window to hold it (method suffix +gps_widened). D20 over 9t flew 2020-03-18.
    The bound used per tile is the most authoritative one available.

Inputs
    data/9t/derived/lidar_2006_2008/*.laz                         held (2006 to 2008 tiles over 9t)
    data/_source/lidar/westernpa/USGS_LPC_PA_WesternPA_2019_D20_*.laz with data/_source/lidar/laz_tile_index.csv   held
    expansions/4_modalities/4_5_multitemporal_lidar/data/raw/flight_windows_metadata.csv   assumed (schema in config)

Outputs (run folder expansions/4_modalities/4_5_multitemporal_lidar/results/<YYYYMMDD>_dod_flight_<hash7>/)
    flight_windows_9t.csv    project, tile, bbox, gps_time_type, gps_first/last (sampled or full), window_start/end, method
    flight_windows_9t.json   per project bound used for eligibility and the method behind it
    _CONFIG.json, _RUN.md, _PROVENANCE.json

Run
    python expansions/4_modalities/4_5_multitemporal_lidar/src/_dod_flight_windows_9t.py [--full-scan] [--no-laz] [--out-root DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _dod_shared_io as io  # noqa: E402
from _dod_shared_io import ek  # noqa: E402

GPS_EPOCH = dt.datetime(1980, 1, 6, tzinfo=dt.timezone.utc)
LEAP_S = 18  # GPS minus UTC since 2017. Irrelevant at day precision. VERIFY for other dates.


def gps_adjusted_to_date(t: float) -> dt.date:
    return (GPS_EPOCH + dt.timedelta(seconds=float(t) + 1e9 - LEAP_S)).date()


# Header CRS -> the same CRS in US survey feet. The 2006 to 2008 statewide tiles over 9t label EPSG:32128
# (metres) but hold US-foot coordinates (EPSG:2271), found 2026-11-05.
FT_TWINS = {32128: "EPSG:2271", 32129: "EPSG:2272"}


def tile_bbox(h, dst_crs: str, area_bbox) -> dict:
    """Tile bbox in dst_crs from the header CRS. Falls back to the US-foot twin when the header-CRS bbox
    misses the study box, and says so."""
    from pyproj import Transformer
    try:
        crs = h.parse_crs()
    except Exception:  # noqa: BLE001
        crs = None
    if crs is None:
        return {"minx": np.nan, "miny": np.nan, "maxx": np.nan, "maxy": np.nan, "crs_note": "no CRS in header"}

    def tr(src):
        t = Transformer.from_crs(src, dst_crs, always_xy=True)
        xs, ys = t.transform([h.mins[0], h.maxs[0], h.mins[0], h.maxs[0]], [h.mins[1], h.mins[1], h.maxs[1], h.maxs[1]])
        return min(xs), min(ys), max(xs), max(ys)

    def hits(b):
        return b[0] < area_bbox[2] and b[2] > area_bbox[0] and b[1] < area_bbox[3] and b[3] > area_bbox[1]
    b, note = tr(crs), f"header EPSG:{crs.to_epsg()}"
    if not hits(b) and crs.to_epsg() in FT_TWINS and hits(tr(FT_TWINS[crs.to_epsg()])):
        b = tr(FT_TWINS[crs.to_epsg()])
        note = f"ALERT header says EPSG:{crs.to_epsg()} but coordinates fit {FT_TWINS[crs.to_epsg()]} (US feet)"
    return {"minx": b[0], "miny": b[1], "maxx": b[2], "maxy": b[3], "crs_note": note}


def scan_laz(path: Path, max_points: int | None, dst_crs: str = "EPSG:6346", area_bbox=(0, 0, 1e9, 1e9)) -> dict:
    """Header facts plus the GPS-time range of the first max_points points (all points if None)."""
    import laspy
    with laspy.open(path) as r:
        h = r.header
        rec = {"tile": path.name, **tile_bbox(h, dst_crs, area_bbox),
               "point_count": int(h.point_count), "gps_time_type": int(h.global_encoding.gps_time_type),
               "header_creation_date": str(h.creation_date), "scan": "full" if max_points is None else "sampled"}
        if "gps_time" not in h.point_format.dimension_names:
            rec.update(gps_first=None, gps_last=None, note="no gps_time")
            return rec
        lo, hi, seen = np.inf, -np.inf, 0
        for ch in r.chunk_iterator(1_000_000):
            g = np.asarray(ch.gps_time)
            lo, hi, seen = min(lo, g.min()), max(hi, g.max()), seen + len(g)
            if max_points is not None and seen >= max_points:
                break
        rec["points_scanned"] = seen
        if rec["gps_time_type"] == 1:
            rec["gps_first"], rec["gps_last"] = str(gps_adjusted_to_date(lo)), str(gps_adjusted_to_date(hi))
        else:
            rec.update(gps_first=None, gps_last=None,
                       note=f"GPS week time ({lo:.0f} to {hi:.0f} s of week). No date in the points.")
    return rec


def tile_window(rec: dict, project: dict, meta: pd.DataFrame | None) -> dict:
    name = project["name"]
    if meta is not None:
        m = meta[(meta.project == name) & ((meta.tile.fillna("") == rec["tile"]) | (meta.tile.fillna("") == ""))]
        if len(m):
            m = m.sort_values("tile", key=lambda s: s.fillna("") == "")  # tile row before project row
            return {"window_start": str(m.start_date.iloc[0]), "window_end": str(m.end_date.iloc[0]),
                    "method": "metadata", "method_source": str(m.source.iloc[0])}
    if rec.get("scan") == "full" and rec.get("gps_first"):
        return {"window_start": rec["gps_first"], "window_end": rec["gps_last"], "method": "gps_full_scan",
                "method_source": "point GPS time, adjusted standard"}
    out = {"window_start": f"{project['year_lo']}-01-01", "window_end": f"{project['year_hi']}-12-31",
           "method": "year_bounds", "method_source": f"nominal years of {name}"}
    # A file cannot be written before its points were flown, so the header creation date is an upper bound on
    # the flight end (reprocessing only moves it later). Used only when it tightens the year bound.
    cd = str(rec.get("header_creation_date") or "")
    if cd[:4].isdigit() and f"{project['year_lo']}-01-01" <= cd < out["window_end"]:
        out["window_end"], out["method"] = cd, "year_bounds+header_upper"
    # A sampled GPS date is a date the survey certainly flew on. When it falls outside the nominal years, the year
    # bounds are wrong for this tile, so the window is widened to hold it (fix 4.5-02, 2026-11-06). The D20 tiles
    # over 9t are labelled 2019 but their points are dated 2020-03-18, so a 2019-12-31 window end was false.
    gf, gl = rec.get("gps_first"), rec.get("gps_last")
    if gf and gl and (gf < out["window_start"] or gl > out["window_end"]):
        out["window_start"], out["window_end"] = min(gf, out["window_start"]), max(gl, out["window_end"])
        out["method"] += "+gps_widened"
    return out


def anomalies(rec: dict, project: dict) -> list[str]:
    """Sampled GPS dates outside the nominal years mean the year bounds are not safe for this project."""
    a = []
    lo, hi = f"{project['year_lo']}-01-01", f"{project['year_hi']}-12-31"
    for k in ("gps_first", "gps_last"):
        v = rec.get(k)
        if v and not (lo <= v <= hi):
            a.append(f"{rec['tile']}: {k} {v} outside nominal {lo} to {hi}")
    return a


def list_tiles(cfg: dict, which: str) -> list[Path]:
    p = cfg["projects"][which]
    d = io.resolve(p["laz_dir"])
    if d is None or not d.exists():
        return []
    tiles = sorted(d.glob(p["laz_glob"]))
    ti = io.resolve(p.get("tile_index"))
    if ti is not None and ti.exists():
        x0, y0, x1, y1 = cfg["bbox_9t"]
        idx = pd.read_csv(ti)
        keep = set(idx[(idx.max_x > x0) & (idx.min_x < x1) & (idx.max_y > y0) & (idx.min_y < y1)].filename)
        tiles = [t for t in tiles if t.name in keep] if keep else []
    return tiles


def run(cfg: dict, out_root: Path | None = None, full_scan: bool = False, use_laz: bool = True,
        tiles: dict | None = None) -> dict:
    meta_p = io.resolve(cfg["flight_metadata_csv"])
    meta = pd.read_csv(meta_p) if meta_p is not None and meta_p.exists() else None
    run_dir = ek.new_run(io.EXP, "dod_flight", {"projects": cfg["projects"], "full_scan": full_scan}, base=out_root,
                         why="S0 flight-date bounds per tile (fw_4_5 section 6).")
    rows, inputs = [], ([meta_p] if meta is not None else [])
    for which, proj in cfg["projects"].items():
        tl = (tiles or {}).get(which) if tiles else (list_tiles(cfg, which) if use_laz else [])
        if not tl:
            rec = {"tile": "", "scan": "none", "note": "no LAZ read"}
            rows.append({"which": which, "project": proj["name"], **rec, **tile_window(rec, proj, meta)})
            continue
        for t in tl:
            rec = scan_laz(Path(t), None if full_scan else int(cfg["gps_sample_points"]), cfg["crs"], cfg["bbox_9t"])
            rows.append({"which": which, "project": proj["name"], **rec, **tile_window(rec, proj, meta),
                         "anomaly": "; ".join(anomalies(rec, proj))})
            inputs.append(Path(t))
    tab = pd.DataFrame(rows)
    out_csv = run_dir / "flight_windows_9t.csv"
    tab.to_csv(out_csv, index=False)
    summ = {}
    for which, g in tab.groupby("which"):
        summ[which] = {"project": g.project.iloc[0], "n_tiles": int((g.tile != "").sum()),
                       "window_start_min": str(min(g.window_start)), "window_end_max": str(max(g.window_end)),
                       "methods": g.method.value_counts().to_dict(),
                       "gps_sampled_first": None if g.gps_first.dropna().empty else str(g.gps_first.dropna().min()),
                       "gps_sampled_last": None if g.gps_last.dropna().empty else str(g.gps_last.dropna().max())} \
            if "gps_first" in g else {"project": g.project.iloc[0], "methods": g.method.value_counts().to_dict(),
                                      "window_start_min": str(min(g.window_start)), "window_end_max": str(max(g.window_end))}
    an = [a for a in tab.get("anomaly", pd.Series(dtype=str)).fillna("") if a]
    crs_alerts = sorted({n for n in tab.get("crs_note", pd.Series(dtype=str)).fillna("") if n.startswith("ALERT")})
    an += crs_alerts
    summ["anomalies"] = an
    if an:
        summ["ALERT"] = (f"{len(an)} tiles have point dates outside the project's nominal years. Year bounds are then "
                         "an assumption, not a guarantee. Read the USGS metadata (D1) before eligibility is final.")
    summ["note"] = ("Eligibility uses window_end of early tiles and window_start of late tiles. year_bounds is "
                    "conservative only when no GPS date falls outside it. gps_full_scan dates are the flight days. "
                    "Replace with metadata (D1) to enlarge the eligible window.")
    js = run_dir / "flight_windows_9t.json"
    js.write_text(json.dumps(summ, indent=2, default=str), encoding="utf-8")
    ek.write_provenance(run_dir, inputs=inputs, outputs=[out_csv, js], params={"full_scan": full_scan},
                        hash_limit_mb=0)
    return {"run_dir": run_dir, "csv": out_csv, "summary": summ}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=io.CONFIG_PATH)
    ap.add_argument("--full-scan", action="store_true", help="read every point's GPS time (minutes per tile)")
    ap.add_argument("--no-laz", action="store_true", help="skip LAZ headers, use metadata or year bounds only")
    ap.add_argument("--out-root", type=Path, default=None)
    a = ap.parse_args()
    r = run(io.load_config(a.config), a.out_root, a.full_scan, not a.no_laz)
    print(json.dumps(r["summary"], indent=2, default=str))


if __name__ == "__main__":
    main()

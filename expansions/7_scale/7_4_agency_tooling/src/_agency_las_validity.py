"""Input-validity checks for an agency's LAS/LAZ tiles. Refuse or warn, never a quiet low score (7.4 section 7).

Purpose
    One record per tile with status ok, warn or refuse and reason codes. Checks follow fw_7_4 section 7.
    CRS          refuse if missing (and no --crs), geographic, or tiles disagree. Warn on US feet (converted)
                 and on a missing vertical datum. An --crs override applies only when the header has none.
    point format refuse on an unreadable or truncated file. Warn on LAS before 1.2.
    returns      refuse if return fields are missing. Warn if every point is a single return.
    ground       refuse on zero class-2 points or ground density below the floor. Warn between the floor and
                 the 9t-like value, and when the class-2 share is far from the 9t range.
    void         share of 0.5 m cells inside the occupied footprint with no ground return. Refuse above the
                 ceiling, warn between the 9t value (45.2%) and the ceiling.
    canopy       share of first returns that are not ground. Always a warn when outside the 9t range.
    tile size    warn when the tile is smaller than the largest model window plus margin.
    scan angle   warn beyond the 9t range. GPS time range is recorded (vintage).
    Density is measured from the points, never inferred from file size.
    Reading uses laspy (pure Python, held). PDAL stays the tool for building derivatives (CLAUDE.md).

Inputs
    a folder of .las/.laz tiles, config_7_4.json thresholds
Outputs
    validity_report.csv and validity_report.json in the chosen folder

Run
    python expansions/7_scale/7_4_agency_tooling/src/_agency_las_validity.py --lidar <folder> --out <folder> [--crs EPSG:6346]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

HERE = Path(__file__).resolve().parent
CFG = HERE / "config_7_4.json"
FEET = ("US survey foot", "foot", "ft", "us-ft", "foot_us")


def load_cfg(path: Path = CFG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cfg_path(entry: dict) -> Path:
    return ek.path_for(entry["key"]) / entry["rel"]


def _crs_info(crs):
    if crs is None:
        return None, None, None, False
    unit = crs.axis_info[0].unit_name if crs.axis_info else ""
    has_vert = crs.is_compound or any(s.is_vertical for s in getattr(crs, "sub_crs_list", []) or [])
    horiz = crs.sub_crs_list[0] if crs.is_compound else crs
    return horiz, unit, horiz.is_geographic, has_vert


def check_tile(path: Path, cfg: dict, crs_override: str | None = None) -> dict:
    import laspy
    from pyproj import CRS
    v = cfg["validity"]
    rec = {"tile_id": path.stem, "path": str(path), "status": "ok", "reasons": [], "warnings": []}
    try:
        with laspy.open(path) as f:
            hdr = f.header
            las = f.read()
    except Exception as e:  # noqa: BLE001 - any read failure is a refusal
        rec.update(status="refuse", reasons=[f"unreadable: {type(e).__name__}"])
        return rec
    rec.update(las_version=f"{hdr.version.major}.{hdr.version.minor}", point_format=int(hdr.point_format.id),
               n_points=int(hdr.point_count))
    if hdr.point_count == 0 or len(las.points) != hdr.point_count:
        rec["reasons"].append("truncated or empty")
    if (hdr.version.major, hdr.version.minor) < (1, 2):
        rec["warnings"].append("old LAS version")
    try:
        crs = hdr.parse_crs()
    except Exception:  # noqa: BLE001
        crs = None
    if crs is None and crs_override:
        crs = CRS.from_user_input(crs_override)
        rec["warnings"].append("CRS from --crs override")
    horiz, unit, geographic, has_vert = _crs_info(crs)
    rec["crs"] = horiz.to_string() if horiz is not None else None
    if horiz is None:
        rec["reasons"].append("CRS missing")
    elif geographic:
        rec["reasons"].append("geographic CRS")
    to_m = 1.0
    if unit and unit.lower() in [u.lower() for u in FEET] or (unit and "foot" in unit.lower()):
        rec["warnings"].append("units in feet (converted)")
        to_m = 0.3048006096 if "us" in unit.lower() else 0.3048
    if horiz is not None and not has_vert:
        rec["warnings"].append("vertical datum missing")
    dims = set(las.point_format.dimension_names)
    if not {"return_number", "number_of_returns", "classification"} <= dims:
        rec["reasons"].append("return or class fields missing")
        return _finish(rec)
    x, y = np.asarray(las.x) * to_m, np.asarray(las.y) * to_m
    cls = np.asarray(las.classification)
    g = cls == 2
    ext_x, ext_y = float(x.max() - x.min()) if len(x) else 0.0, float(y.max() - y.min()) if len(y) else 0.0
    rec.update(extent_x_m=round(ext_x, 2), extent_y_m=round(ext_y, 2))
    res = cfg["resolution_m"]
    occ = np.unique(np.c_[np.floor((x - x.min()) / 1.0), np.floor((y - y.min()) / 1.0)], axis=0) if len(x) else np.empty((0, 2))
    occ_area = float(len(occ))                       # m2 of 1 m cells with any return
    rec["occupied_area_m2"] = occ_area
    n_g = int(g.sum())
    rec["ground_points"] = n_g
    rec["ground_share"] = round(n_g / max(len(cls), 1), 4)
    rec["ground_density_ppsm"] = round(n_g / occ_area, 4) if occ_area else 0.0
    if n_g == 0:
        rec["reasons"].append("zero ground points")
    elif rec["ground_density_ppsm"] < v["ground_density_refuse"]:
        rec["reasons"].append("ground density below floor")
    elif rec["ground_density_ppsm"] < v["ground_density_warn"]:
        rec["warnings"].append("ground density below 9t-like value")
    lo, hi = v["ground_share_warn_range"]
    if n_g and not lo <= rec["ground_share"] <= hi:
        rec["warnings"].append("ground share outside 9t range")
    nr = np.asarray(las.number_of_returns)
    if len(nr) and (nr <= 1).all():
        rec["warnings"].append("single-return only")
    if n_g:
        sub = (np.floor((x - x.min()) / res).astype(np.int64), np.floor((y - y.min()) / res).astype(np.int64))
        occ_h = set(zip((sub[0] // int(1 / res)).tolist(), (sub[1] // int(1 / res)).tolist()))
        gcell = set(zip(sub[0][g].tolist(), sub[1][g].tolist()))
        n_cells = len(occ_h) * int(1 / res) ** 2
        rec["void_frac"] = round(1 - len(gcell) / max(n_cells, 1), 4)
        if rec["void_frac"] > v["void_frac_refuse"]:
            rec["reasons"].append("void fraction above ceiling")
        elif rec["void_frac"] > v["void_frac_warn"]:
            rec["warnings"].append("void fraction above 9t value")
    rn = np.asarray(las.return_number)
    first = rn == 1
    if first.any():
        share = float((first & ~g).sum() / first.sum())
        rec["canopy_first_nonground_share"] = round(share, 4)
        clo, chi = v["canopy_nonground_first_share_range"]
        if not clo <= share <= chi:
            rec["warnings"].append("canopy outside 9t range")
    if min(ext_x, ext_y) < v["min_tile_extent_m"]:
        rec["warnings"].append("tile smaller than model window plus margin")
    for nm in ("scan_angle", "scan_angle_rank"):
        if nm in dims:
            sa = np.abs(np.asarray(las[nm], float) * (0.006 if nm == "scan_angle" else 1.0))
            rec["scan_angle_abs_max"] = round(float(sa.max()), 2) if len(sa) else None
            if len(sa) and sa.max() > v["scan_angle_abs_warn"]:
                rec["warnings"].append("scan angle beyond 9t range")
            break
    if "gps_time" in dims and len(las.points):
        gt = np.asarray(las.gps_time)
        rec["gps_time_min"], rec["gps_time_max"] = float(gt.min()), float(gt.max())
    return _finish(rec)


def _finish(rec: dict) -> dict:
    rec["status"] = "refuse" if rec["reasons"] else ("warn" if rec["warnings"] else "ok")
    return rec


def check_folder(folder: Path, cfg: dict, crs_override: str | None = None, strict: bool = False) -> pd.DataFrame:
    tiles = sorted([*Path(folder).glob("*.las"), *Path(folder).glob("*.laz")])
    if not tiles:
        raise FileNotFoundError(f"no .las or .laz tiles in {folder}")
    recs = [check_tile(t, cfg, crs_override) for t in tiles]
    crs_set = {r.get("crs") for r in recs if r.get("crs")}
    if len(crs_set) > 1:
        for r in recs:
            r["reasons"].append("tiles disagree on CRS")
            _finish(r)
    if strict:
        for r in recs:
            if r["warnings"]:
                r["reasons"] += [f"strict: {w}" for w in r["warnings"]]
                _finish(r)
    df = pd.DataFrame(recs)
    df["reasons"] = df["reasons"].apply(";".join)
    df["warnings"] = df["warnings"].apply(";".join)
    ek.assert_unique(df, "tile_id")
    return df


def write_report(df: pd.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "validity_report.csv", index=False)
    (out / "validity_report.json").write_text(df.to_json(orient="records", indent=1), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.4 input-validity checks.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--lidar", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crs", default=None)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    try:
        df = check_folder(Path(a.lidar), load_cfg(Path(a.config)), a.crs, a.strict)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    write_report(df, Path(a.out))
    print(df[["tile_id", "status", "reasons", "warnings"]].to_string(index=False))
    return 2 if (df["status"] == "refuse").all() else 0


if __name__ == "__main__":
    sys.exit(main())

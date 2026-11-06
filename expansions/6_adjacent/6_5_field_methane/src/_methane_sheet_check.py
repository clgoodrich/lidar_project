"""6.5 S1. Field sheet check. Every visit passes or fails before its readings are used.

Purpose
    Check the crew sheet (one row per reading) against config_6_5.json. Columns present. Reading types known.
    Units match the instrument registry, so point (ppm) and path-integrated (ppm_m) readings never mix. One zero
    and one span reading per crew-day, inside tolerance. A background record per visit lasting at least 5 minutes
    and taken 20 to 50 m upwind. Wind on every reading and inside the usable range. Stop rows logged with a reason.
    Readings above the safety stop threshold are flagged. No duplicate readings.
Inputs
    data/9t/source/field_methane/field_methane_sheet_9t.csv (assumed; crews fill it during 7.5)
Outputs (data/9t/results/field/ unless --out)
    methane_sheet_check_9t.csv   one row per problem (visit, rule, detail)
    methane_visit_validity_9t.csv  one row per visit (valid yes or no, reasons)
Run
    python expansions/6_adjacent/6_5_field_methane/src/_methane_sheet_check.py [--sheet FILE] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

DEFAULT_CONFIG = HERE / "config_6_5.json"


def load_config(path=None) -> dict:
    return json.loads(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))


def resolve(spec: dict) -> Path:
    if "path" in spec:
        return Path(spec["path"])
    if "key" in spec:
        return ek.path_for(spec["key"]) / spec["rel"]
    return ek.area_dir(spec["area"]) / spec["rel"]


def read_sheet(cfg: dict, override=None) -> pd.DataFrame:
    p = Path(override) if override else resolve(cfg["inputs"]["sheet"])
    if not p.exists():
        raise FileNotFoundError(f"missing field sheet ({cfg['inputs']['sheet']['state']}) at {p}. "
                                f"Required columns {cfg['sheet_schema']['required']}. "
                                "Write a worked example with _methane_field_table.py --example.")
    s = pd.read_csv(p, dtype={"position": str, "site_id": str, "visit_id": str})
    return s


def check(cfg: dict, s: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sc, pr = cfg["sheet_schema"], cfg["protocol"]
    probs = []

    def bad(visit, rule, detail):
        probs.append({"visit_id": visit, "rule": rule, "detail": detail})
    miss = [c for c in sc["required"] if c not in s]
    if miss:
        bad("all", "columns", f"missing {miss}")
        return pd.DataFrame(probs), pd.DataFrame(columns=["visit_id", "valid", "reasons"])
    s = s.copy()
    s["ts"] = pd.to_datetime(s["date"].astype(str) + " " + s["time"].astype(str), errors="coerce")
    for i in s.index[s.ts.isna()]:
        bad(s.at[i, "visit_id"], "time", f"row {i} unparseable date or time")
    for i in s.index[~s.reading_type.isin(sc["reading_types"])]:
        bad(s.at[i, "visit_id"], "reading_type", f"row {i} {s.at[i, 'reading_type']}")
    inst = cfg["instruments"]
    for i in s.index[~s.instrument_id.isin(inst)]:
        bad(s.at[i, "visit_id"], "instrument", f"row {i} instrument {s.at[i, 'instrument_id']} not in the registry")
    known = s[s.instrument_id.isin(inst)]
    wrong_u = known[known.units != known.instrument_id.map(lambda k: inst[k]["units"])]
    for i in wrong_u.index:
        bad(s.at[i, "visit_id"], "units", f"row {i} units {s.at[i, 'units']} for {s.at[i, 'instrument_id']}")
    for v, g in s.groupby("visit_id"):
        if g.instrument_id.nunique() > 1 and len({inst.get(k, {}).get("type") for k in g.instrument_id.unique()}) > 1:
            bad(v, "units", "point and path-integrated instruments mixed in one visit")
    dup = s.duplicated(["visit_id", "reading_type", "position", "ts", "instrument_id"], keep=False)
    for i in s.index[dup]:
        bad(s.at[i, "visit_id"], "duplicate", f"row {i}")
    # calibration per crew-day
    s["day"] = s.ts.dt.date
    cal_ok = {}
    for (crew, day, iid), g in s.groupby(["crew", "day", "instrument_id"]):
        spec = inst.get(iid)
        z, sp = g[g.reading_type == "zero"], g[g.reading_type == "span"]
        ok = spec is not None and len(z) >= 1 and (len(sp) >= 1 or spec.get("span_gas_ppm") is None)
        if ok and len(z):
            ok &= bool((z.value.abs() <= spec["zero_tol"]).all())
        if ok and len(sp) and spec.get("span_gas_ppm"):
            ok &= bool(((sp.value - spec["span_gas_ppm"]).abs() <= spec["span_tol_rel"] * spec["span_gas_ppm"]).all())
        cal_ok[(crew, day, iid)] = ok
        if not ok:
            bad(",".join(sorted(g.visit_id.unique())), "calibration", f"crew {crew} day {day} {iid} zero/span missing or out of tolerance")
    wlo, whi = pr["wind_ms"]
    stop_thr = pr["stop_threshold_ppm"]
    val = []
    for v, g in s[s.reading_type.isin(["background", "screen", "stop"])].groupby("visit_id"):
        reasons = []
        key = (g.crew.iloc[0], g.day.iloc[0], g.instrument_id.iloc[0])
        if not cal_ok.get(key, False):
            reasons.append("calibration")
        bg = g[g.reading_type == "background"]
        if bg.empty:
            reasons.append("no background")
        else:
            dur = (bg.ts.max() - bg.ts.min()).total_seconds()
            if dur < pr["background_min_s"]:
                reasons.append(f"background {dur:.0f} s under {pr['background_min_s']} s")
            if "distance_m" in bg:
                dm = pd.to_numeric(bg.distance_m, errors="coerce")
                if dm.isna().any() or (dm < pr["background_upwind_m"][0]).any() or (dm > pr["background_upwind_m"][1]).any():
                    reasons.append("background distance outside 20 to 50 m")
        w = pd.to_numeric(g.wind_speed_ms, errors="coerce")
        if w.isna().any():
            reasons.append("wind missing")
        elif ((w < wlo) | (w > whi)).mean() > 0.5:
            reasons.append(f"wind outside {wlo} to {whi} m/s on most readings")
        scr = g[g.reading_type == "screen"]
        unknown_pos = set(scr.position.astype(str)) - set(pr["positions"])
        if unknown_pos:
            reasons.append(f"unknown positions {sorted(unknown_pos)}")
        stops = g[g.reading_type == "stop"]
        if len(stops) and stops.get("stop_reason", pd.Series(dtype=str)).isna().any():
            bad(v, "stop", "stop row without a reason")
        pts = g[g.instrument_id.map(lambda k: inst.get(k, {}).get("type")) == "point"]
        if (pd.to_numeric(pts.value, errors="coerce") >= stop_thr).any():
            bad(v, "safety", f"reading at or above the stop threshold {stop_thr} ppm. Confirm a stop row was logged")
            if not len(stops):
                reasons.append("stop threshold crossed without a stop row")
        for r_ in reasons:
            bad(v, "visit", r_)
        val.append({"visit_id": v, "site_id": g.site_id.iloc[0], "date": str(g.day.iloc[0]), "valid": not reasons,
                    "reasons": "; ".join(reasons), "stopped": bool(len(stops))})
    return pd.DataFrame(probs, columns=["visit_id", "rule", "detail"]), pd.DataFrame(val)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cfg = load_config(a.config)
    out = Path(a.out) if a.out else resolve(cfg["outputs"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    probs, val = check(cfg, read_sheet(cfg, a.sheet))
    p1, p2 = out / f"methane_sheet_check_{cfg['area']}.csv", out / f"methane_visit_validity_{cfg['area']}.csv"
    probs.to_csv(p1, index=False)
    val.to_csv(p2, index=False)
    print(f"{len(probs)} problems. {int(val.valid.sum()) if len(val) else 0} of {len(val)} visits valid.\nwrote {p1}\nwrote {p2}")
    return 0 if len(val) and val.valid.all() else 1


if __name__ == "__main__":
    raise SystemExit(main())

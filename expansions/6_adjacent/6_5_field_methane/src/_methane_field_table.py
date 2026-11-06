"""6.5 S2. Assemble screening readings per visit and per site. Concentration, not flux.

Purpose
    Per valid visit, the background level is the median of the upwind readings and the background spread is the
    95th percentile minus the median. Enhancement per position is the peak screening reading minus the background
    median. A position is "detected" when its enhancement exceeds the larger of the instrument detection limit
    and the background spread. Otherwise it is "below the instrument limit at that time and place". Per site, the
    table reports the range of enhancement over valid visits per position and whether repeat visits agree.
    Invalid visits stay in the visit table, marked, and are excluded from site shares.
    Descriptive shares use the site as the unit with Clopper-Pearson intervals, split by 7.5 identity status and
    era stratum when the site list exists. Strata are never pooled.
    --example writes a synthetic worked example sheet (labelled synthetic) for the protocol acceptance test.
Inputs
    data/9t/source/field_methane/field_methane_sheet_9t.csv (assumed), data/9t/results/field/field_sites_9t.csv (7.5, optional)
Outputs (data/9t/results/field/ unless --out)
    field_methane_by_visit.csv, field_methane_by_site.csv, field_methane_summary.json, _runs/<run_id>/_PROVENANCE.json
    --example: expansions/6_adjacent/6_5_field_methane/results/tables/methane_example_sheet.csv
Run
    python expansions/6_adjacent/6_5_field_methane/src/_methane_field_table.py [--sheet FILE] [--out DIR]
    python expansions/6_adjacent/6_5_field_methane/src/_methane_field_table.py --example
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _methane_sheet_check as SC
from _methane_sheet_check import ek

DISCLAIMER = ("Screening concentration readings. Concentration, not flux. A reading below the limit means below the "
              "instrument limit at that time and place. It is not evidence about whether the site leaks.")
DETECTED = "enhancement above the instrument limit"
BELOW = "below the instrument limit at that time and place"


def by_visit(cfg: dict, s: pd.DataFrame, validity: pd.DataFrame) -> pd.DataFrame:
    inst = cfg["instruments"]
    rows = []
    for v, g in s.groupby("visit_id"):
        bg = pd.to_numeric(g.loc[g.reading_type == "background", "value"], errors="coerce").dropna()
        iid = g.instrument_id.iloc[0]
        dl = inst.get(iid, {}).get("detection_limit", np.nan)
        med = float(bg.median()) if len(bg) else np.nan
        spread = float(bg.quantile(0.95) - med) if len(bg) else np.nan
        thr = float(np.nanmax([dl, spread])) if len(bg) else np.nan
        vrow = validity.set_index("visit_id").loc[v] if v in set(validity.visit_id) else None
        valid = bool(vrow["valid"]) if vrow is not None else False
        scr = g[g.reading_type == "screen"]
        for pos, gp in scr.groupby(scr.position.astype(str)):
            peak = float(pd.to_numeric(gp.value, errors="coerce").max())
            enh = peak - med if np.isfinite(med) else np.nan
            rows.append({"site_id": g.site_id.iloc[0], "visit_id": v, "date": str(g.date.iloc[0]), "crew": g.crew.iloc[0],
                         "instrument_id": iid, "units": g.units.iloc[0], "position": pos, "peak": peak,
                         "background_median": med, "background_spread": spread, "detection_limit": dl,
                         "threshold": thr, "enhancement": enh,
                         "category": (DETECTED if enh > thr else BELOW) if valid and np.isfinite(enh) else "invalid visit",
                         "valid_visit": valid, "invalid_reasons": "" if vrow is None else vrow["reasons"],
                         "wind_speed_ms_median": float(pd.to_numeric(gp.wind_speed_ms, errors="coerce").median())})
    return pd.DataFrame(rows)


def by_site(cfg: dict, bv: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for site, g in bv.groupby("site_id"):
        ok = g[g.valid_visit]
        visits = sorted(ok.visit_id.unique())
        cats = ok.groupby("visit_id").category.agg(lambda c: DETECTED if (c == DETECTED).any() else BELOW)
        r = {"site_id": site, "n_visits": int(g.visit_id.nunique()), "n_valid_visits": len(visits),
             "units": ",".join(sorted(g.units.unique())),
             "n_valid_visits_detected": int((cats == DETECTED).sum()),
             "repeat_agreement": (None if len(visits) < 2 else bool(cats.nunique() == 1)),
             "site_category": ("no valid visit" if not visits else
                               f"{DETECTED} on {int((cats == DETECTED).sum())} of {len(visits)} valid visits"
                               if (cats == DETECTED).any() else f"{BELOW} on all {len(visits)} valid visits"),
             "background_median_range": f"{ok.background_median.min():.2f} to {ok.background_median.max():.2f}" if len(ok) else ""}
        for pos in cfg["protocol"]["positions"]:
            e = ok.loc[ok.position == pos, "enhancement"]
            r[f"enh_{pos}_range"] = f"{e.min():.2f} to {e.max():.2f}" if len(e) else ""
        r["statement"] = DISCLAIMER
        rows.append(r)
    return pd.DataFrame(rows)


def summary(st: pd.DataFrame, sites: pd.DataFrame | None) -> dict:
    res = {"n_sites": int(len(st)), "statement": DISCLAIMER, "unit": "site"}
    v = st[st.n_valid_visits > 0]
    k = int((v.n_valid_visits_detected > 0).sum())
    res["share_sites_detected_any_visit"] = dict(zip(("share", "lo95", "hi95"), ek.clopper_pearson(k, len(v)))) | {"k": k, "n": int(len(v))} if len(v) else None
    rep = st[st.repeat_agreement.notna()]
    if len(rep):
        kk = int(rep.repeat_agreement.astype(bool).sum())
        res["repeat_agreement"] = dict(zip(("share", "lo95", "hi95"), ek.clopper_pearson(kk, len(rep)))) | {"k": kk, "n": int(len(rep))}
    if sites is not None:
        m = v.merge(sites, on="site_id", how="left")
        res["by_stratum"] = {}
        for keys, g in m.groupby(["identity_status", "era_stratum"], dropna=False):
            kk = int((g.n_valid_visits_detected > 0).sum())
            res["by_stratum"][" | ".join(map(str, keys))] = dict(zip(("share", "lo95", "hi95"), ek.clopper_pearson(kk, len(g)))) | {"k": kk, "n": int(len(g))}
    return res


def example_sheet(cfg: dict, seed: int | None = None) -> pd.DataFrame:
    """Synthetic worked example. Two sites, two visits each, one invalid visit (failed span). Labelled synthetic."""
    rng = np.random.default_rng(seed if seed is not None else cfg["master_seed"])
    rows = []
    base = {"instrument_id": "point_sampler_assumed", "units": "ppm", "temp_c": 12.0, "pressure_hpa": 1010.0,
            "wind_dir_deg": 270, "notes": "SYNTHETIC worked example. Not a measurement."}
    plan = [("SYN-A", "SYN-A-1", "2027-04-10", "crew1", 1.5, 8.0, 100.0),
            ("SYN-A", "SYN-A-2", "2027-04-17", "crew1", 2.5, 6.0, 101.0),
            ("SYN-B", "SYN-B-1", "2027-04-10", "crew2", 1.0, 0.0, 99.0),
            ("SYN-B", "SYN-B-2", "2027-04-18", "crew2", 3.0, 0.0, 130.0)]
    for site, visit, date, crew, wind, plume, span in plan:
        t = pd.Timestamp(f"{date} 08:00:00")
        rows.append(base | {"site_id": site, "visit_id": visit, "date": date, "time": t.strftime("%H:%M:%S"), "crew": crew,
                            "reading_type": "zero", "position": "", "value": 0.2, "wind_speed_ms": wind})
        rows.append(base | {"site_id": site, "visit_id": visit, "date": date, "time": (t + pd.Timedelta(minutes=2)).strftime("%H:%M:%S"),
                            "crew": crew, "reading_type": "span", "position": "", "value": span, "wind_speed_ms": wind})
        for m in range(7):
            rows.append(base | {"site_id": site, "visit_id": visit, "date": date, "crew": crew, "reading_type": "background",
                                "time": (t + pd.Timedelta(minutes=10 + m)).strftime("%H:%M:%S"), "position": "",
                                "distance_m": 30, "value": round(2.0 + rng.normal(0, 0.05), 3), "wind_speed_ms": wind})
        for j, (pos, f) in enumerate((("wellhead", 1.0), ("1", 0.6), ("5", 0.25), ("10", 0.1))):
            rows.append(base | {"site_id": site, "visit_id": visit, "date": date, "crew": crew, "reading_type": "screen",
                                "time": (t + pd.Timedelta(minutes=20 + j)).strftime("%H:%M:%S"), "position": pos,
                                "value": round(2.0 + plume * f + rng.normal(0, 0.05), 3), "wind_speed_ms": wind})
    return pd.DataFrame(rows)


def build(cfg: dict, s: pd.DataFrame, out: Path, sites: pd.DataFrame | None = None) -> dict:
    probs, val = SC.check(cfg, s)
    bv = by_visit(cfg, s, val)
    ek.assert_rows(bv, int(((s.reading_type == "screen")).groupby([s.visit_id, s.position.astype(str)]).any().sum()),
                   "visit-position rows")
    st = by_site(cfg, bv)
    res = summary(st, sites)
    out.mkdir(parents=True, exist_ok=True)
    p = {"visit": out / "field_methane_by_visit.csv", "site": out / "field_methane_by_site.csv",
         "summary": out / "field_methane_summary.json", "check": out / f"methane_sheet_check_{cfg['area']}.csv"}
    bv.to_csv(p["visit"], index=False)
    st.to_csv(p["site"], index=False)
    probs.to_csv(p["check"], index=False)
    p["summary"].write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    return {"paths": p, "summary": res, "by_site": st, "by_visit": bv}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--sites", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--example", action="store_true")
    a = ap.parse_args()
    cfg = SC.load_config(a.config)
    if a.example:
        p = ek.sub("6.5", "results/tables") / "methane_example_sheet.csv"
        example_sheet(cfg).to_csv(p, index=False)
        print(f"wrote {p} (synthetic worked example)")
        return 0
    s = SC.read_sheet(cfg, a.sheet)
    sp = Path(a.sites) if a.sites else SC.resolve(cfg["inputs"]["sites"])
    sites = pd.read_csv(sp) if sp.exists() else None
    out = Path(a.out) if a.out else SC.resolve(cfg["outputs"]["results"])
    r = build(cfg, s, out, sites)
    run = ek.new_run("6.5", "methane", cfg["protocol"], base=out / "_runs", why=DISCLAIMER)
    ek.write_provenance(run, inputs=[Path(a.sheet) if a.sheet else SC.resolve(cfg["inputs"]["sheet"])],
                        outputs=list(r["paths"].values()), params=cfg["protocol"])
    print(json.dumps(r["summary"], indent=2, default=str))
    print("\n".join(f"wrote {v}" for v in r["paths"].values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

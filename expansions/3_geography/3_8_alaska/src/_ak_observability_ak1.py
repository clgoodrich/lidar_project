"""S1 (3.8). Observability gate (protocol section 9) before any statistics.

Purpose
    Per site and mission posting. (1) Fraction of a radar pixel the pad fills (pad area over posting
    squared, capped at 1). Pad area comes from the IfSAR orthoimage (site covariates) or the default
    pad side. (2) Usable acquisitions per site, per thaw season, per year (dates flagged for snow,
    wet melt or flood removed). (3) Plausible signal against variability. delta against the noise floor
    once S3 has measured it. Decision go, no-go or defer per mission, written to the table.
Inputs
    expansions/3_geography/3_8_alaska/data/interim/ak_wells_sites_ak1.gpkg (S0)
    config_3_8.json inputs.site_covariates, acquisitions, weather_flags (assumed)
    data/ak1/results/ak_reference_stability_ak1.csv (S3, optional, gives the noise floor)
Outputs
    data/ak1/results/ak_observability_ak1.csv
Run
    python expansions/3_geography/3_8_alaska/src/_ak_observability_ak1.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.8"


def fill_fraction(pad_area_m2: float, posting_m: float) -> float:
    return float(min(1.0, pad_area_m2 / (posting_m * posting_m)))


def usable_per_season(acq: pd.DataFrame, flags: pd.DataFrame | None, thaw_months: list[int]) -> pd.DataFrame:
    a = acq.copy()
    a["date"] = pd.to_datetime(a["date"])
    a = a[a["date"].dt.month.isin(thaw_months)]
    if flags is not None and len(flags):
        f = flags.copy()
        f["date"] = pd.to_datetime(f["date"])
        bad = f[f[["snow", "wet_melt", "flood"]].any(axis=1)][["frame", "date"]]
        a = a.merge(bad.assign(_bad=True), on=["frame", "date"], how="left")
        a = a[a["_bad"].isna()].drop(columns="_bad")
    a["year"] = a["date"].dt.year
    return a.groupby(["frame", "mission", "year"]).size().rename("usable").reset_index()


def decide(fill: float, min_usable: int, need: int, delta, noise) -> str:
    if fill < 0.05 or min_usable < need:
        return "no-go"
    if delta is None or noise is None or not np.isfinite(noise):
        return "defer (delta or noise floor not set)"
    return "go" if 2 * noise < delta else "no-go (noise above delta / 2)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    import geopandas as gpd
    sites = gpd.read_file(gt.require_input(ek.sub(EXP, "data/interim") / "ak_wells_sites_ak1.gpkg", "S0 sites"))
    site_ids = sorted(sites["site_id"].unique())
    try:
        cov = pd.read_csv(gt.config_input(cfg, "site_covariates", EXP)).set_index("site_id")
    except gt.MissingInputError as e:
        print(str(e).splitlines()[0], "(using default pad side)", file=sys.stderr)
        cov = pd.DataFrame(index=site_ids)
    try:
        acq = pd.read_csv(gt.config_input(cfg, "acquisitions", EXP))
        try:
            flags = pd.read_csv(gt.config_input(cfg, "weather_flags", EXP))
        except gt.MissingInputError:
            flags = None
        use = usable_per_season(acq, flags, pr["thaw_months"])
    except gt.MissingInputError as e:
        print(str(e).splitlines()[0], "(acquisition counts unknown, decision deferred)", file=sys.stderr)
        use, cov = None, cov
    noise = np.nan
    rp = ek.area_dir("ak1") / "results" / "ak_reference_stability_ak1.csv"
    if rp.exists():
        noise = float(pd.read_csv(rp)["noise_floor_mm_yr"].median())
    rows = []
    for sid in site_ids:
        pad = float(cov["pad_area_m2"].get(sid, np.nan)) if "pad_area_m2" in cov else np.nan
        pad = pad if np.isfinite(pad) else pr["pad_side_m_default"] ** 2
        frame = cov["frame"].get(sid) if "frame" in cov else None
        for mission, post in pr["postings_m"].items():
            n_min = 0
            if use is not None and frame is not None:
                u = use[(use["frame"] == frame) & use["mission"].str.startswith(mission.split("_")[0])]
                n_min = int(u["usable"].min()) if len(u) else 0
            ff = fill_fraction(pad, post)
            rows.append({"site_id": sid, "mission_posting": mission, "posting_m": post, "pad_area_m2": pad,
                         "fill_fraction": ff, "min_usable_per_season": n_min if use is not None else None,
                         "noise_floor_mm_yr": noise, "delta_mm_yr": pr["delta_mm_yr"],
                         "decision": "defer (acquisitions unknown)" if use is None else
                         decide(ff, n_min, pr["min_acq_per_season"], pr["delta_mm_yr"], noise)})
    out = ek.area_dir("ak1") / "results" / "ak_observability_ak1.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(df.groupby("mission_posting")[["fill_fraction"]].median().to_string())
    print(df["decision"].value_counts().to_string(), f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

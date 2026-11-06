"""S7 (3.8, optional). Sanity check of the seasonal signal against active-layer monitoring sites.

Purpose
    For monitoring sites inside the radar frame, compare the radar seasonal LOS amplitude at the site
    with measured thaw depth and, where present, measured subsidence (Spearman correlation across
    site-years). A sanity check that the chain sees the seasonal cycle. It does not validate well results.
Inputs
    data/ak1/derived/ak_stack_ak1/ak_los_series_ak1.csv (S2, rows with kind = 'active_layer', point_id = site)
    config_3_8.json inputs.active_layer (assumed)
Outputs
    data/ak1/results/ak_active_layer_check_ak1.csv
Run
    python expansions/3_geography/3_8_alaska/src/_ak_active_layer_check_ak1.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.8"


def amplitude_by_year(series: pd.DataFrame, thaw: list[int]) -> pd.DataFrame:
    s = series.dropna(subset=["los_mm"]).copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s[s["date"].dt.month.isin(thaw)]
    return (s.groupby(["point_id", s["date"].dt.year])["los_mm"].agg(lambda v: v.max() - v.min())
            .rename("amp_mm").reset_index().rename(columns={"point_id": "site", "date": "year"}))


def compare(amp: pd.DataFrame, al: pd.DataFrame) -> dict:
    from scipy.stats import spearmanr
    j = amp.merge(al, on=["site", "year"])
    out = {"n_site_years": int(len(j))}
    for col in ("thaw_depth_cm", "subsidence_cm"):
        if col in j and j[col].notna().sum() >= 4:
            r, p = spearmanr(j["amp_mm"], j[col], nan_policy="omit")
            out[col] = {"spearman": float(r), "p": float(p)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    try:
        ser = pd.read_csv(gt.require_input(ek.area_dir("ak1") / "derived" / "ak_stack_ak1" / "ak_los_series_ak1.csv", "S2"))
        al = pd.read_csv(gt.config_input(cfg, "active_layer", EXP))
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    amp = amplitude_by_year(ser[ser["kind"] == "active_layer"], cfg["prereg"]["thaw_months"])
    res = compare(amp, al)
    out = ek.area_dir("ak1") / "results" / "ak_active_layer_check_ak1.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.json_normalize(res).to_csv(out, index=False)
    print(res, f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

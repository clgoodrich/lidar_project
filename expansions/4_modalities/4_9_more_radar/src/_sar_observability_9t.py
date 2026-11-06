"""S0 of framework 4.9. Observability gate per SAR arm and target. No scoring.

Purpose. Quantify, before any test, what each arm can see (protocol section 9).
  fill           target footprint over one resolution cell, capped at 1
  n_px           independent cells inside the footprint (at least 1)
  speckle_sd_db  single-look-equivalent intensity spread in dB for L looks, (10 / ln 10) sqrt(trigamma(L))
  noise_sd_db    footprint-mean noise, sqrt(speckle^2 / (n_px n_acq_ind) + clutter^2 / n_px). Clutter does not average over time
  snr            assumed contrast in dB over noise_sd_db
  reg_ok         registration residual under the target radius
An arm whose footprint fills under fill_cut (0.25) of a cell and has no sub-cell texture is labelled
"cannot see <target> at this resolution" and is dropped for that target only. That is a measurement. It is not a
failure of the hypothesis. A smaller delivered pixel is not more target information, so resolution is the sensor's
resolution, not its posting. Acquisition counts come from the catalogue table when present, else from the config.
Registration comes from the S3 summary when present, else from the config.
Inputs.
  expansions/4_modalities/4_9_more_radar/src/config_4_9.json (arms, targets, all VERIFY)
  expansions/4_modalities/4_9_more_radar/data/raw/sar_catalogue_9t.csv (assumed, optional)
  data/9t/results/sar_new/sar_registration_by_track_9t.csv (from S3, optional)
Outputs.
  data/9t/results/sar_new/sar_observability_by_arm_9t.csv
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_observability_9t.py [--catalogue CSV] [--registration CSV] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import polygamma

import _sar_kit_4_9 as sk


def speckle_sd_db(looks: float) -> float:
    return float(10 / np.log(10) * np.sqrt(polygamma(1, looks)))


def observe(arm: str, a: dict, tname: str, t: dict, clutter: float, fill_cut: float) -> dict:
    cell = a["res_az_m"] * a["res_rg_m"]
    fill = min(1.0, t["footprint_m2"] / cell)
    n_px = max(1.0, t["footprint_m2"] / cell)
    sp = speckle_sd_db(a["looks"])
    noise = float(np.sqrt(sp ** 2 / (n_px * a["n_acq_independent"]) + clutter ** 2 / n_px))
    blind = fill < fill_cut and not a["subcell_texture"]
    reg_ok = a["registration_m"] < t["radius_m"]
    verdict = f"cannot see {tname} at this resolution" if blind else ("registration too coarse" if not reg_ok else "observable")
    return {"arm": arm, "sensor": a["sensor"], "target": tname, "res_cell_m2": cell, "fill": round(fill, 4), "n_px": round(n_px, 2),
            "looks": a["looks"], "n_acq": a["n_acq"], "n_acq_independent": a["n_acq_independent"],
            "speckle_sd_db": round(sp, 3), "noise_sd_db": round(noise, 3), "contrast_db": t["contrast_db"],
            "snr": round(t["contrast_db"] / noise, 3), "registration_m": a["registration_m"], "reg_ok": reg_ok,
            "subcell_texture": a["subcell_texture"], "verdict": verdict, "assumed": a.get("assumed", True)}


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--registration", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    arms = {k: dict(v) for k, v in cfg["arms"].items()}
    cat_p = Path(a.catalogue) if a.catalogue else sk.resolve(cfg["inputs"]["catalogue"])
    if cat_p.exists():
        cat = pd.read_csv(cat_p)
        for arm, g in cat[cat.covers_9t.astype(bool)].groupby("arm"):
            if arm in arms:
                arms[arm]["n_acq"] = int(g.scene_id.nunique())
                arms[arm]["n_acq_independent"] = min(arms[arm]["n_acq_independent"], arms[arm]["n_acq"])
                arms[arm]["assumed"] = False
    out = Path(a.out) if a.out else sk.resolve(cfg["outputs"]["results"])
    reg_p = Path(a.registration) if a.registration else out / "sar_registration_by_track_9t.csv"
    if reg_p.exists():
        reg = pd.read_csv(reg_p)
        for arm, g in reg.groupby("arm"):
            if arm in arms:
                arms[arm]["registration_m"] = float(g.residual_median_m.max())
    rows = [observe(k, v, tn, t, cfg["clutter_sd_db"], pr["fill_cut"]) for k, v in arms.items() for tn, t in cfg["targets"].items()]
    df = pd.DataFrame(rows)
    sk.ek.assert_rows(df, len(arms) * len(cfg["targets"]), "arm x target")
    out.mkdir(parents=True, exist_ok=True)
    f = out / "sar_observability_by_arm_9t.csv"
    df.to_csv(f, index=False)
    sk.prov(out, "sar_observability_9t", inputs=[cat_p, reg_p], outputs=[f], params={"arms": arms, "targets": cfg["targets"]})
    print(df[["arm", "target", "fill", "snr", "verdict"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

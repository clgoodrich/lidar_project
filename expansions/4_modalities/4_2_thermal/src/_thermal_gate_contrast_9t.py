"""4.2 stages T0 and T1. Mechanism verdict and the observable-contrast gate per thermal sensor (9t).

Purpose
    T0. Read the physical routes table from config. Any route with an independent thermal term that lidar
        does not already carry keeps the satellite arm open. Otherwise CLOSE.
    T1. Per pad and per sensor, the fill fraction f (largest share of one native pixel the pad covers),
        on a fixed grid and averaged over random grid offsets. Share of pads with f >= 0.25. Usable scene
        counts by season and hour. Registration RMSE from tie points. Diluted contrast proxy_dT x f with a
        block bootstrap of the median. Contrast-to-spread. Gate verdict per sensor against delta_T.
        Without a measured proxy_dT, reports the break-even dT = delta_T / median f only.
Inputs
    pads            truth/annotations_proj_v2.gpkg layer pad (held)
    scene indexes   expansions/4_modalities/4_2_thermal/data/raw/scene_index_<sensor>_9t.csv (assumed)
    tie points      expansions/4_modalities/4_2_thermal/data/raw/tiepoints_<sensor>_9t.csv (assumed)
Outputs (run folder expansions/4_modalities/4_2_thermal/results/<YYYYMMDD>_thermal_gate_<hash7>/)
    thermal_gate_by_pad_9t.csv, thermal_gate_summary_9t.json, thermal_gate_fill_vs_contrast_9t.png,
    _CONFIG.json, _RUN.md, _PROVENANCE.json
Run
    python expansions/4_modalities/4_2_thermal/src/_thermal_gate_contrast_9t.py [--proxy-dT 3.0] [--max-pads N]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import _thermal_shared_io as io
from _thermal_shared_io import ek

SHORT = "thermal_gate"


def t0_verdict(routes: list[dict]) -> dict:
    if any(r.get("independent_thermal_term") is None or r.get("lidar_carries") is None for r in routes):
        v = "inconclusive"
    elif any(r["independent_thermal_term"] and not r["lidar_carries"] and r.get("testable", True) for r in routes):
        v = "success"
    else:
        v = "failure"
    open_routes = [r["route"] for r in routes if r.get("independent_thermal_term") and not r.get("lidar_carries")]
    return {"verdict": v, "action": "CLOSE satellite arm" if v == "failure" else "continue to T1",
            "routes_tested": open_routes, "null_routes": [r["route"] for r in routes if r.get("lidar_carries")],
            "not_testable": [r["route"] for r in routes if not r.get("testable", True)]}


def scene_counts(sensor: dict, g: dict, seasons: dict) -> dict:
    p = io.resolve(sensor.get("scene_index"))
    if p is None or not p.exists():
        return {"status": "missing_input", "path": str(p), "usable": None}
    s = pd.read_csv(p, parse_dates=["datetime_utc"])
    for c in ("scene_id", "datetime_utc", "cloud_frac", "qc_pass"):
        if c not in s.columns:
            raise KeyError(f"scene index {p}: column {c!r} missing")
    ek.assert_unique(s, "scene_id")
    u = s[s["qc_pass"].astype(bool) & (s["cloud_frac"] <= g["max_cloud_frac"])].copy()
    month2season = {m: k for k, ms in seasons.items() for m in ms}
    u["season"] = u["datetime_utc"].dt.month.map(month2season)
    out = {"status": "ok", "path": str(p), "n_listed": int(len(s)), "usable": int(len(u)),
           "by_season": u["season"].value_counts().to_dict(),
           "by_hour_utc": u["datetime_utc"].dt.hour.value_counts().sort_index().to_dict()}
    if "lst_err_K" in u.columns and u["lst_err_K"].notna().any():
        out["noise_K"] = float(u["lst_err_K"].median())
    return out


def registration(sensor: dict, g: dict) -> dict:
    p = io.resolve(sensor.get("tiepoints"))
    if p is None or not p.exists():
        return {"status": "missing_input", "path": str(p)}
    t = pd.read_csv(p)
    per = t.groupby("scene_id").apply(lambda d: float(np.sqrt(np.mean(d["dx_m"] ** 2 + d["dy_m"] ** 2))),
                                      include_groups=False)
    lim = g["max_registration_frac_pixel"] * sensor["native_pixel_m"]
    return {"status": "ok", "path": str(p), "n_scenes": int(len(per)), "rmse_m_median": float(per.median()),
            "limit_m": lim, "scenes_over_limit": sorted(per[per > lim].index.astype(str).tolist())}


def sensor_gate(df: pd.DataFrame, sensor: dict, g: dict, scenes: dict, reg: dict, seed: int) -> dict:
    name = sensor["name"]
    f = df[f"fill_{name}_offsets"].to_numpy(float)
    blocks = list(df["block_id"].unique())
    byb = {b: d[f"fill_{name}_offsets"].to_numpy(float) for b, d in df.groupby("block_id")}
    med_fill = float(np.nanmedian(f))
    res = {"native_pixel_m": sensor["native_pixel_m"], "median_fill": med_fill,
           "share_fill_ge_thr": float(np.nanmean(f >= g["fill_share_threshold"])),
           "breakeven_dT_K": g["delta_T_K"] / med_fill if med_fill > 0 else float("inf"),
           "scenes": scenes, "registration": reg}
    dT = g.get("proxy_dT_K")
    if dT is None:
        res.update(verdict="inconclusive", reason="proxy_dT_K not measured. Break-even dT reported only")
        return res
    stat = lambda bl: float(np.nanmedian(np.concatenate([byb[b] for b in bl]))) * dT  # noqa: E731
    pt, lo, hi, _ = ek.block_bootstrap(stat, blocks, B=g["bootstrap_B"], seed=seed)
    noise = scenes.get("noise_K") if isinstance(scenes, dict) and scenes.get("noise_K") else sensor["assumed_noise_K"]
    spread = g.get("spread_K") or noise
    cts = pt / spread if spread else float("nan")
    usable = scenes.get("usable") if isinstance(scenes, dict) else None
    res.update(diluted_median_K=pt, lo=lo, hi=hi, noise_K=noise, spread_K=spread, contrast_to_spread=cts)
    if hi < g["delta_T_K"]:
        res["verdict"] = "failure"
    elif lo > g["delta_T_K"] and cts >= 1 and usable is not None and usable >= g["min_usable_scenes"]:
        res["verdict"] = "success"
    else:
        res["verdict"] = "inconclusive"
    res["action"] = {"failure": "pre-specified CLOSE for this sensor", "success": "run T2",
                     "inconclusive": "report, collect scenes or measure proxy_dT"}[res["verdict"]]
    return res


def figure(df, sensors, g, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = [ek.PALETTE["blue"], ek.PALETTE["orange"], ek.PALETTE["charcoal"]]
    fig, ax = plt.subplots(figsize=(7, 4))
    for (s, c, ls) in zip(sensors, cols, ("-", "--", ":")):
        v = np.sort(df[f"fill_{s['name']}_offsets"].dropna().to_numpy())
        ax.plot(v, np.arange(1, len(v) + 1) / len(v), color=c, ls=ls, lw=2,
                label=f"{s['name']} ({s['native_pixel_m']:.0f} m native)")
    ax.axvline(g["fill_share_threshold"], color=ek.PALETTE["grey"], lw=1)
    ax.text(g["fill_share_threshold"], 0.05, " f = 0.25", color=ek.PALETTE["charcoal"])
    ax.set_xlabel("Fill fraction f (pad share of one native pixel)")
    ax.set_ylabel("Cumulative share of pads")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(cfg: dict, out_root: Path | None = None, pads_path: Path | None = None, max_pads: int | None = None,
        proxy_dT: float | None = None) -> dict:
    g = dict(cfg["gate"])
    if proxy_dT is not None:
        g["proxy_dT_K"] = proxy_dT
    pin = cfg["inputs"]["pads"]
    pp = Path(pads_path) if pads_path else io.resolve(pin)
    pads = io.read_polys(pp, pin.get("layer"), pin["id_col"], "pad polygons")
    n_all = len(pads)
    pads = io.within_raster(pads, io.need(io.resolve(cfg["inputs"]["chm"]), "9t CHM (extent only)"))
    if max_pads:
        pads = pads.head(max_pads)
    run_dir = ek.new_run(io.EXP, SHORT, {"gate": g, "sensors": cfg["sensors"], "routes": cfg["t0_routes"],
                                          "n_pads": len(pads)}, base=out_root,
                         why="T0 mechanism verdict and T1 fill-fraction gate.")
    rng = np.random.default_rng(ek.child_seed(cfg["master_seed"]))
    c = pads.geometry.centroid
    df = pd.DataFrame({"pad_id": pads[pin["id_col"]].to_numpy(), "area_m2": pads.geometry.area.to_numpy(),
                       "x": c.x.to_numpy(), "y": c.y.to_numpy()})
    df["block_id"] = io.block_of(df.x, df.y)
    for s in cfg["sensors"]:
        px = s["native_pixel_m"]
        df[f"fill_{s['name']}_fixed"] = [io.fill_fraction(geom, px) for geom in pads.geometry]
        df[f"fill_{s['name']}_offsets"] = [io.fill_fraction_offsets(geom, px, g["n_offsets"], rng) for geom in pads.geometry]
    ek.assert_rows(df, len(pads), "pad to fill table")
    ek.assert_no_nan(df["block_id"], "block_id")
    summary = {"stage": "T0+T1", "evidence_level": "(a) at best. Not a well or leak claim",
               "t0": t0_verdict(cfg["t0_routes"]), "n_pads_layer": int(n_all), "n_pads": int(len(df)), "delta_T_K": g["delta_T_K"],
               "proxy_dT_K": g.get("proxy_dT_K"), "sensors": {}}
    for i, s in enumerate(cfg["sensors"]):
        sc = scene_counts(s, g, cfg["season_windows"])
        rg = registration(s, g)
        summary["sensors"][s["name"]] = sensor_gate(df, s, g, sc, rg, ek.child_seed(cfg["master_seed"], arm=i + 1))
    out_csv = run_dir / "thermal_gate_by_pad_9t.csv"
    out_json = run_dir / "thermal_gate_summary_9t.json"
    out_png = run_dir / "thermal_gate_fill_vs_contrast_9t.png"
    df.to_csv(out_csv, index=False)
    out_json.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    figure(df, cfg["sensors"], g, out_png)
    return io.finish(run_dir, summary, inputs=[pp], outputs=[out_csv, out_json, out_png], params=g,
                     seeds={"master": cfg["master_seed"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--pads", type=Path, default=None)
    ap.add_argument("--max-pads", type=int, default=None)
    ap.add_argument("--proxy-dT", type=float, default=None, help="measured pad minus clearing dT in K")
    a = ap.parse_args()
    s = run(io.load_config(a.config), a.out_root, a.pads, a.max_pads, a.proxy_dT)
    print(json.dumps({k: s[k] for k in ("t0", "run_dir")}, indent=1, default=str))
    for k, v in s["sensors"].items():
        print(k, "median fill", round(v["median_fill"], 4), "share f>=0.25", round(v["share_fill_ge_thr"], 3),
              "break-even dT K", round(v["breakeven_dT_K"], 1), "verdict", v["verdict"])


if __name__ == "__main__":
    main()

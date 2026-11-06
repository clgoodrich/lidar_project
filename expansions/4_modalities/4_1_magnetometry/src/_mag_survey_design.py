"""S1. Survey line plan and detection-depth forward model for one magnetometry site.

Purpose
    Lays out parallel survey lines over a grid centred on a site (EPSG:6346), with the along-line sample spacing,
    the number of samples and the walking time. A vertical steel casing is modelled as a magnetic monopole at its
    top, so the vertical-field anomaly at offset x is B(x) = p z / (x^2 + z^2)^1.5 with z = sensor height + depth.
    The peak is p / z^2. Detection needs peak >= k sigma, so the deepest detectable casing top is
    sqrt(p / (k sigma)) - sensor height. The anomaly full width at half maximum is about 1.53 z. A line spacing
    above that width can step over an anomaly, so the script flags it. Pole strengths are assumed (config).
    The model is a design aid. It is not a sensitivity estimate.

Inputs
    expansions/4_modalities/4_1_magnetometry/src/config_4_1.json  (survey block)
    Site centre from --site-id with --easting/--northing, or from the assumed pilot_sites.csv

Outputs
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_survey_lines_<site>.gpkg (layers lines, waypoints)
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_survey_design_<site>.json
    expansions/4_modalities/4_1_magnetometry/results/<run_id>/mag_detect_depth_<site>.csv

Run
    python expansions/4_modalities/4_1_magnetometry/src/_mag_survey_design.py --site-id demo --easting 621750 --northing 4595250
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mag_shared_io as io  # noqa: E402
from _mag_shared_io import ek  # noqa: E402

FWHM_FACTOR = 2.0 * np.sqrt(2 ** (2 / 3) - 1)   # monopole vertical field, about 1.533


def line_plan(cx: float, cy: float, sv: dict) -> dict:
    """North-south lines, alternating direction. Returns line endpoints, waypoints and timing."""
    gx, gy, ds = sv["grid_x_m"], sv["grid_y_m"], sv["line_spacing_m"]
    xs = cx - gx / 2 + np.arange(0, gx + 1e-9, ds)
    y0, y1 = cy - gy / 2, cy + gy / 2
    lines = [(i, x, (y0, y1) if i % 2 == 0 else (y1, y0)) for i, x in enumerate(xs)]
    along = sv["walk_speed_m_s"] / sv["sample_rate_hz"]
    n_per_line = int(np.floor(gy / along)) + 1
    t = len(lines) * (gy / sv["walk_speed_m_s"]) + (len(lines) - 1) * sv["turn_time_s"]
    return {"lines": lines, "n_lines": len(lines), "along_line_spacing_m": along, "samples_per_line": n_per_line,
            "n_samples": n_per_line * len(lines), "line_length_total_m": gy * len(lines),
            "survey_time_min": t / 60.0, "area_m2": gx * gy,
            "area_per_hour_m2": gx * gy / (t / 3600.0)}


def monopole_field(x, y, p: float, z: float):
    """Vertical field of a monopole of strength p (nT m2) at depth z below the sensor plane."""
    r2 = np.asarray(x) ** 2 + np.asarray(y) ** 2 + z ** 2
    return p * z / r2 ** 1.5


def detect_depth(p: float, sigma: float, k: float, h: float) -> float:
    """Deepest casing top (m below ground) with peak >= k sigma. Negative means undetectable even at the surface."""
    return float(np.sqrt(p / (k * sigma)) - h)


def depth_table(sv: dict) -> pd.DataFrame:
    rows = []
    lo, hi = sv["pole_strength_range_nT_m2"]
    for p in np.geomspace(lo, hi, 5):
        for sig in (0.5 * sv["noise_sigma_nT"], sv["noise_sigma_nT"], 2 * sv["noise_sigma_nT"]):
            d = detect_depth(p, sig, sv["detect_k_sigma"], sv["sensor_height_m"])
            z = max(d, 0) + sv["sensor_height_m"]
            rows.append({"pole_nT_m2": round(float(p), 1), "noise_sigma_nT": sig,
                         "max_depth_m": round(d, 2), "fwhm_at_max_depth_m": round(FWHM_FACTOR * z, 2),
                         "line_spacing_ok": bool(sv["line_spacing_m"] <= FWHM_FACTOR * z)})
    return pd.DataFrame(rows)


def run(cfg: dict, out_root: Path | None = None, site_id: str = "demo", easting=None, northing=None) -> dict:
    import geopandas as gpd
    from shapely.geometry import LineString, Point
    sv = cfg["survey"]
    if easting is None or northing is None:
        p = io.need_input(cfg, "pilot_sites")
        ps = pd.read_csv(p).set_index("site_id")
        easting, northing = float(ps.loc[site_id, "easting"]), float(ps.loc[site_id, "northing"])
    plan = line_plan(float(easting), float(northing), sv)
    lines = gpd.GeoDataFrame({"line_id": [i for i, _, _ in plan["lines"]]},
                             geometry=[LineString([(x, a), (x, b)]) for _, x, (a, b) in plan["lines"]], crs=cfg["crs"])
    wp = gpd.GeoDataFrame({"line_id": [i for i, _, _ in plan["lines"] for _ in (0, 1)],
                           "end": ["start", "end"] * plan["n_lines"]},
                          geometry=[Point(x, y) for _, x, ab in plan["lines"] for y in ab], crs=cfg["crs"])
    ek.assert_crs(lines, cfg["crs"])
    tab = depth_table(sv)
    design = {k: v for k, v in plan.items() if k != "lines"}
    design.update(site_id=site_id, centre=[easting, northing], survey=sv,
                  model="vertical monopole at casing top, peak p/z^2, assumed pole strengths",
                  note="Design aid. Not a sensitivity estimate. Pole range VERIFY")
    rd = ek.new_run(cfg["exp_id"], "magdesign", {"survey": sv, "site": site_id, "c": [easting, northing]},
                    base=out_root, why="S1 line plan and detection depth")
    g, j, c = rd / f"mag_survey_lines_{site_id}.gpkg", rd / f"mag_survey_design_{site_id}.json", rd / f"mag_detect_depth_{site_id}.csv"
    lines.to_file(g, layer="lines", driver="GPKG")
    wp.to_file(g, layer="waypoints", driver="GPKG")
    j.write_text(json.dumps(design, indent=2, default=str), encoding="utf-8")
    tab.to_csv(c, index=False)
    ek.write_provenance(rd, [], [g, j, c], params=sv)
    print(json.dumps(design, indent=2, default=str))
    return {"run_dir": rd, "design": design, "depth": tab}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--site-id", default="demo")
    ap.add_argument("--easting", type=float, default=None)
    ap.add_argument("--northing", type=float, default=None)
    a = ap.parse_args()
    run(io.load_config(a.config), a.out_root, a.site_id, a.easting, a.northing)


if __name__ == "__main__":
    main()

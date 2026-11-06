"""S3 of framework 4.6. Georeference a scan from ground control points and measure accuracy on independent check points.

Purpose. Fit pixel -> EPSG:6346 from the GCPs only (polynomial order 1 or 2, or thin-plate spline), predict the
check points, and report RMSE and max error in metres with a bootstrap interval over check points. A source is
"unusable here" when RMSE exceeds the preregistered limit. Optionally warps the scan with GDAL using the same GCPs
(gdal_translate -gcp then gdalwarp -order or -tps), so the image a digitiser sees matches the accuracy reported.
Check points never enter the fit. The script asserts the two sets are disjoint.
Inputs.
  data/_source/historic_topo_probe/<source>_gcp.csv (assumed, schema in config_4_6.json)
  the raw scan (only with --warp)
Outputs.
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_georef_<source>_9t.json   RMSE, interval, verdict
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_georef_<source>_resid_9t.csv  residual per check point
  data/_source/historic_topo_probe/<source>_georef_6346.tif (only with --warp)
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_georef_check_9t.py --source NAME [--gcp CSV] [--method poly1|poly2|tps] [--warp SCAN]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import _hist_kit_4_6 as hk


def _design(px, py, order):
    cols = [np.ones_like(px), px, py]
    if order >= 2:
        cols += [px * py, px ** 2, py ** 2]
    return np.column_stack(cols)


def fit_transform(gcp: pd.DataFrame, method: str):
    """Return f(px, py) -> (x, y) fitted on the GCP rows."""
    px, py = gcp.px.to_numpy(float), gcp.py.to_numpy(float)
    xy = gcp[["x", "y"]].to_numpy(float)
    if method in ("poly1", "poly2"):
        order = int(method[-1])
        need = 3 if order == 1 else 6
        if len(gcp) < need:
            raise ValueError(f"{method} needs at least {need} GCPs, got {len(gcp)}")
        A = _design(px, py, order)
        coef, *_ = np.linalg.lstsq(A, xy, rcond=None)
        return lambda qx, qy: _design(np.asarray(qx, float), np.asarray(qy, float), order) @ coef
    if method == "tps":
        from scipy.interpolate import RBFInterpolator
        f = RBFInterpolator(np.column_stack([px, py]), xy, kernel="thin_plate_spline")
        return lambda qx, qy: f(np.column_stack([np.asarray(qx, float), np.asarray(qy, float)]))
    raise ValueError(method)


def accuracy(gcp_tab: pd.DataFrame, method: str, B: int, seed: int) -> tuple[dict, pd.DataFrame]:
    g = gcp_tab[gcp_tab.role == "gcp"]
    c = gcp_tab[gcp_tab.role == "check"].copy()
    hk.ek.assert_disjoint(g.point_id, c.point_id, "gcp vs check point ids")
    f = fit_transform(g, method)
    pred = f(c.px, c.py)
    c["dx"], c["dy"] = pred[:, 0] - c.x, pred[:, 1] - c.y
    c["err_m"] = np.hypot(c.dx, c.dy)
    e2 = c.err_m.to_numpy() ** 2
    rng = np.random.default_rng(seed)
    draws = np.sqrt([e2[rng.integers(0, len(e2), len(e2))].mean() for _ in range(B)])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    gr = f(g.px, g.py)
    res = {"method": method, "n_gcp": int(len(g)), "n_check": int(len(c)),
           "rmse_m": float(np.sqrt(e2.mean())), "rmse_lo": float(lo), "rmse_hi": float(hi),
           "max_err_m": float(c.err_m.max()), "median_err_m": float(c.err_m.median()),
           "mean_dx_m": float(c.dx.mean()), "mean_dy_m": float(c.dy.mean()),
           "gcp_fit_rmse_m": float(np.sqrt(((gr - g[["x", "y"]].to_numpy()) ** 2).sum(1).mean()))}
    return res, c


def verdict(res: dict, limit: float, min_gcp: int, min_check: int) -> str:
    if res["n_gcp"] < min_gcp or res["n_check"] < min_check:
        return "inconclusive (too few points)"
    return "unusable here (RMSE over limit)" if res["rmse_m"] > limit else "within limit"


def gdal_warp(scan: Path, gcp: pd.DataFrame, method: str, dst: Path, crs: str) -> Path:
    for exe in ("gdal_translate", "gdalwarp"):
        if shutil.which(exe) is None:
            raise FileNotFoundError(f"{exe} not on PATH. Install GDAL or run without --warp")
    tmp = dst.with_name(dst.stem + "_gcp.vrt")
    cmd = ["gdal_translate", "-of", "VRT", "-a_srs", crs]
    for r in gcp.itertuples():
        cmd += ["-gcp", str(r.px), str(r.py), str(r.x), str(r.y)]
    subprocess.run(cmd + [str(scan), str(tmp)], check=True, capture_output=True, text=True)
    warp = ["gdalwarp", "-overwrite", "-t_srs", crs, "-r", "bilinear", "-co", "COMPRESS=DEFLATE"]
    warp += ["-tps"] if method == "tps" else ["-order", method[-1]]
    subprocess.run(warp + [str(tmp), str(dst)], check=True, capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    return dst


def main(argv=None) -> int:
    cfg = hk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--gcp", default=None)
    ap.add_argument("--method", default="poly1", choices=["poly1", "poly2", "tps"])
    ap.add_argument("--warp", default=None, help="raw scan to warp with the GCPs (needs GDAL CLI)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    spec = cfg["inputs"]["gcp_table"]
    path = hk.need(Path(a.gcp) if a.gcp else hk.resolve(spec, source=a.source), f"GCP table for {a.source}", spec)
    tab = pd.read_csv(path)
    miss = [c for c in spec["schema"] if c not in tab.columns]
    if miss:
        raise ValueError(f"{path} lacks {miss}")
    hk.ek.assert_unique(tab, "point_id")
    if set(tab.role) - {"gcp", "check"}:
        raise ValueError("role must be gcp or check")
    res, resid = accuracy(tab, a.method, pr["B"], pr["master_seed"])
    res["limit_m"] = pr["rmse_limit_m"]
    res["verdict"] = verdict(res, pr["rmse_limit_m"], pr["min_gcp"], pr["min_check"])
    out = Path(a.out) if a.out else hk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    outs = [out / f"hist_georef_{a.source}_9t.json", out / f"hist_georef_{a.source}_resid_9t.csv"]
    if a.warp:
        dst = hk.resolve(cfg["outputs"]["crops"]) / f"{a.source}_georef_6346.tif"
        outs.append(gdal_warp(hk.need(Path(a.warp), "raw scan"), tab[tab.role == "gcp"], a.method, dst, cfg["crs"]))
    outs[0].write_text(json.dumps(res, indent=2), encoding="utf-8")
    resid.to_csv(outs[1], index=False)
    hk.prov(out, f"hist_georef_{a.source}", inputs=[path], outputs=outs, params=res, seeds={"bootstrap": pr["master_seed"]})
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""S3 of framework 4.9. Registration check of each SAR track against independent permanent scatterers.

Purpose. For each arm and track, offset in metres between the SAR peak of each permanent scatterer (building corner,
bridge) and its independent reference position (survey or orthophoto, not the lidar-based check used before).
Report median and maximum. A track whose maximum offset exceeds one resolution cell gets a fitted translation (the
median dx, dy, robust to one bad scatterer), and the residual after the shift is reported and logged. A track with
fewer than 10 scatterers is "insufficient". No feature is built before this check. --apply writes a shifted copy
of a raster by moving its geotransform only (no resampling).
Inputs.
  expansions/4_modalities/4_9_more_radar/data/raw/sar_scatterers_9t.csv (assumed; columns track, scatterer_id, sar_x,
  sar_y, ref_x, ref_y, ref_source, plus arm)
Outputs.
  data/9t/results/sar_new/sar_registration_by_track_9t.csv
  <raster stem>_shifted.tif beside the raster (only with --apply)
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_registration_9t.py [--scatterers CSV] [--apply ARM:TRACK:RASTER] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import _sar_kit_4_9 as sk

MIN_SCATTERERS = 10


def by_track(sc: pd.DataFrame, arms: dict) -> pd.DataFrame:
    rows = []
    for (arm, tr), g in sc.groupby(["arm", "track"]):
        dx, dy = (g.sar_x - g.ref_x).to_numpy(), (g.sar_y - g.ref_y).to_numpy()
        off = np.hypot(dx, dy)
        cell = max(arms[arm]["res_az_m"], arms[arm]["res_rg_m"]) if arm in arms else np.nan
        shift = bool(off.max() > cell)
        sx, sy = (float(np.median(dx)), float(np.median(dy))) if shift else (0.0, 0.0)
        res = np.hypot(dx - sx, dy - sy)
        rows.append({"arm": arm, "track": tr, "n": len(g), "median_m": float(np.median(off)), "max_m": float(off.max()),
                     "cell_m": cell, "shift_applied": shift, "shift_x_m": sx, "shift_y_m": sy,
                     "residual_median_m": float(np.median(res)), "residual_max_m": float(res.max()),
                     "status": "insufficient" if len(g) < MIN_SCATTERERS else ("drop track" if res.max() > cell else "ok")})
    return pd.DataFrame(rows)


def apply_shift(raster: Path, sx: float, sy: float) -> Path:
    """Copy with the transform moved by (-sx, -sy) so SAR positions land on the reference."""
    import rasterio
    from rasterio.transform import Affine
    out = raster.with_name(raster.stem + "_shifted.tif")
    with rasterio.open(raster) as s:
        prof = s.profile.copy()
        prof["transform"] = Affine.translation(-sx, -sy) * s.transform
        with rasterio.open(out, "w", **prof) as d:
            d.write(s.read())
            d.update_tags(registration_shift=f"{-sx:.3f},{-sy:.3f}")
    return out


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    spec = cfg["inputs"]["scatterers"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scatterers", default=None)
    ap.add_argument("--apply", nargs="*", default=[], help="ARM:TRACK:RASTER (raster path may hold a drive colon)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    sp = sk.need(Path(a.scatterers) if a.scatterers else sk.resolve(spec), "permanent scatterer table", spec)
    sc = pd.read_csv(sp)
    miss = [c for c in spec["schema"] + ["arm"] if c not in sc.columns]
    if miss:
        raise ValueError(f"{sp} lacks {miss}")
    sk.ek.assert_unique(sc.assign(k=sc.arm + "/" + sc.track.astype(str) + "/" + sc.scatterer_id.astype(str)), "k")
    tab = by_track(sc, cfg["arms"])
    out = Path(a.out) if a.out else sk.resolve(cfg["outputs"]["results"])
    out.mkdir(parents=True, exist_ok=True)
    f = out / "sar_registration_by_track_9t.csv"
    tab.to_csv(f, index=False)
    outs = [f]
    for spec_a in a.apply:
        arm, tr, ras = spec_a.split(":", 2)
        r = tab[(tab.arm == arm) & (tab.track.astype(str) == tr)].iloc[0]
        outs.append(apply_shift(sk.need(Path(ras), "raster to shift"), r.shift_x_m, r.shift_y_m))
    sk.prov(out, "sar_registration_9t", inputs=[sp], outputs=outs, params={"min_scatterers": MIN_SCATTERERS})
    print(tab.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

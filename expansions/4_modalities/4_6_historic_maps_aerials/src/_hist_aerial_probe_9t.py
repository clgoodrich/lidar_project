"""S2 of framework 4.6. Aerial frame probe. Pick frames over 9t from the index and rate legibility per date.

Purpose. An index entry does not guarantee a scan. For every date in the D7 frame index this script lists the
frames that touch 9t, marks which have a local scan, and for scanned frames measures ground sample distance (when
the frame is georeferenced) and a sharpness score (variance of the Laplacian on the grey image). A frame is
"legible candidate" when a 20 m pad or derrick spans at least legible_px_per_20m pixels. The final legibility call
is human. This table only says which frames are worth showing to the two digitisers.
Inputs.
  expansions/4_modalities/4_6_historic_maps_aerials/data/raw/aerial_frame_index_9t.csv (assumed, schema in config_4_6.json)
  the scans named in its path column
Outputs.
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_aerial_frames_9t.csv   one row per frame
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_aerial_dates_9t.csv    verdict per date
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_aerial_probe_9t.py [--index CSV] [--out DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi

import _hist_kit_4_6 as hk


def frame_metrics(path: Path, max_px: int = 4000) -> dict:
    """GSD in metres (nan if the scan has no georeference) and Laplacian variance on a decimated grey image."""
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(path) as d:
        f = max(1, int(np.ceil(max(d.width, d.height) / max_px)))
        a = d.read(out_shape=(d.count, d.height // f, d.width // f), resampling=Resampling.average).astype(float)
        gsd = float("nan")
        if d.crs is not None and d.crs.is_projected:
            gsd = abs(d.transform.a) * (d.crs.linear_units_factor[1] if d.crs.linear_units_factor else 1.0)
    grey = a[:3].mean(0) if a.shape[0] >= 3 else a[0]
    return {"gsd_m": gsd, "sharpness": float(ndi.laplace(grey).var()), "decimation": f}


def date_verdicts(fr: pd.DataFrame, px_need: float) -> pd.DataFrame:
    rows = []
    for date, g in fr.groupby("date"):
        scanned = g[g.has_scan]
        px = (20.0 / scanned.gsd_m).replace([np.inf], np.nan)
        if not len(g):
            v = "no coverage"
        elif not len(scanned):
            v = "inconclusive (index only, no scan)"
        elif px.notna().any() and (px >= px_need).any():
            v = "legible candidate"
        elif px.notna().any():
            v = "unusable here (too coarse)"
        else:
            v = "inconclusive (scan not georeferenced)"
        rows.append({"date": date, "n_frames": len(g), "n_scanned": len(scanned),
                     "best_px_per_20m": float(px.max()) if px.notna().any() else float("nan"), "verdict": v})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    cfg = hk.load_cfg()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    spec = cfg["inputs"]["aerial_index"]
    idx_path = hk.need(Path(a.index) if a.index else hk.resolve(spec), "aerial frame index", spec)
    idx = pd.read_csv(idx_path)
    miss = [c for c in spec["schema"] if c not in idx.columns]
    if miss:
        raise ValueError(f"{idx_path} lacks {miss}")
    hk.ek.assert_unique(idx, "frame_id")
    box = hk.bbox_lonlat(cfg["bbox_9t"], cfg["crs"])
    idx["cover_share_9t"] = [hk.cover_share(r.west, r.south, r.east, r.north, box) for r in idx.itertuples()]
    fr = idx[idx.cover_share_9t > 0].copy()
    mets = []
    for r in fr.itertuples():
        p = Path(str(r.path)) if isinstance(r.path, str) and r.path else None
        if p is not None and not p.is_absolute():
            p = hk.ek.REPO / p
        if p is not None and p.exists():
            mets.append({"has_scan": True, **frame_metrics(p)})
        else:
            mets.append({"has_scan": False, "gsd_m": np.nan, "sharpness": np.nan, "decimation": np.nan})
    fr = pd.concat([fr.reset_index(drop=True), pd.DataFrame(mets)], axis=1)
    hk.ek.assert_rows(fr, int((idx.cover_share_9t > 0).sum()), "frames over 9t")
    fr["px_per_20m"] = 20.0 / fr.gsd_m
    dv = date_verdicts(fr, cfg["prereg"]["legible_px_per_20m"])
    out = Path(a.out) if a.out else hk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    fr.to_csv(out / "hist_aerial_frames_9t.csv", index=False)
    dv.to_csv(out / "hist_aerial_dates_9t.csv", index=False)
    hk.prov(out, "hist_aerial_probe_9t", inputs=[idx_path], outputs=[out / "hist_aerial_dates_9t.csv"],
            params={"legible_px_per_20m": cfg["prereg"]["legible_px_per_20m"]})
    print(dv.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Speckle-filtered NISAR images for viewing in QGIS: one date, each filter, HH and HV in dB.

Filters are the ones in `_nisar_speckle_filter_seasonal_9t.py` (median, Frost, Gamma-MAP,
improved Lee sigma; linear intensity, 1 look, --win window). `none` is the unfiltered image.

Input   nisar/derived/9t/nisar_slc_lidar_5m/nisar_slc_lidar_<date>_t<track>_9t.tif (complex HH, HV)
Output  nisar/derived/9t/nisar_speckle_filters/nisar_speckle_<filter>_<date>_t<track>_9t.tif
        band 1 HH dB, band 2 HV dB, float32, same grid and CRS as the input. 0 (no sample) -> NaN.

Run:
  python nisar/code/s5_eval/_nisar_speckle_filter_maps_9t.py 20251104_t090A 20260714_t090A
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "notebooks" / "wellsight_v2"))   # _common
from _common import path_for  # noqa: E402
from _nisar_speckle_filter_seasonal_9t import FILTERS, apply  # noqa: E402

SRC = path_for("data").parent / "nisar" / "derived" / "9t" / "nisar_slc_lidar_5m"
OUT = path_for("data").parent / "nisar" / "derived" / "9t" / "nisar_speckle_filters"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes", nargs="+", help="<yyyymmdd>_t<track><A|D>")
    ap.add_argument("--win", type=int, default=5)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for sc in a.scenes:
        with rasterio.open(SRC / f"nisar_slc_lidar_{sc}_9t.tif") as r:
            s = r.read()
            prof = r.profile
        valid = (s != 0) & np.isfinite(s)
        inten = [np.where(valid[i], np.abs(s[i]) ** 2, np.nan) for i in (0, 1)]
        prof.update(dtype="float32", count=2, nodata=np.nan, compress="deflate")
        for name in FILTERS:
            out = OUT / f"nisar_speckle_{name}_{sc}_9t.tif"
            with np.errstate(divide="ignore", invalid="ignore"):
                bands = [10 * np.log10(apply(ch, name, a.win)) for ch in inten]
            with rasterio.open(out, "w", **prof) as dst:
                for i, b in enumerate(bands, 1):
                    dst.write(b.astype(np.float32), i)
                dst.set_band_description(1, f"HH dB, {name} {a.win}x{a.win}")
                dst.set_band_description(2, f"HV dB, {name} {a.win}x{a.win}")
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

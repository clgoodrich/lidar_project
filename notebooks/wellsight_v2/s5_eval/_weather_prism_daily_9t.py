"""Daily rain and temperature at the 9t centre from PRISM (4 km, observed), for the NISAR rain/freeze products.

PRISM Climate Group web service, https://services.nacse.org/prism/data/get/us/4km/<var>/<YYYYMMDD>.
Variables ppt (mm), tmin, tmax (deg C). One 4 km cell at the area centre; the 9t tile is smaller than a cell.
Recent days are PRISM provisional values and can be revised. Only the cell value is kept, the zips are discarded.

  python notebooks/wellsight_v2/s5_eval/_weather_prism_daily_9t.py
"""
import io
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import rasterio
import requests

LON, LAT = -79.5413, 41.4997        # 9t centre (EPSG:4326 of the 5 m grid centre)
START, END = date(2025, 9, 1), date(2026, 10, 18)
VARS = ("ppt", "tmin", "tmax")
OUT = Path(__file__).resolve().parents[3] / "data" / "9t" / "derived" / "weather" / "weather_prism_daily_9t.csv"


def one(args):
    var, d = args
    url = f"https://services.nacse.org/prism/data/get/us/4km/{var}/{d:%Y%m%d}"
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                tif = [n for n in z.namelist() if n.endswith(".tif")][0]
                with rasterio.MemoryFile(z.read(tif)) as mf, mf.open() as src:
                    v = float(next(src.sample([(LON, LAT)]))[0])
                    return var, d, (None if v == src.nodata or v < -9000 else v)
            if r.status_code == 404:
                return var, d, None
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return var, d, None


def main():
    days = [START + timedelta(i) for i in range((END - START).days + 1)]
    jobs = [(v, d) for d in days for v in VARS]
    rows = {}
    with ThreadPoolExecutor(4) as ex:
        for k, (var, d, v) in enumerate(ex.map(one, jobs)):
            rows.setdefault(d, {})[var] = v
            if k % 150 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    df = pd.DataFrame([dict(date=d, **rows[d]) for d in days])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(df.describe().to_string(), "\nmissing:", df[list(VARS)].isna().sum().to_dict(), flush=True)


if __name__ == "__main__":
    main()

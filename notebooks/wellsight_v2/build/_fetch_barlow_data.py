"""Fetch the public datasets behind the Barlow MDV dissertation / FINESST expansion.

Targets J:\\barlow_data (large; off the repo). Datasets and access status:

  [AUTO]  REMA v2.0 mosaic (PGC) — satellite DEM epoch, 2m + 10m, MDV supertiles
          17_34/17_35/18_34/18_35. Public AWS Open Data bucket pgc-opendata-dems
          (anonymous). This is the cornerstone of the lidar-vs-satellite validation.
  [KEY]   MDV airborne lidar 2014-15 (NCALM via OpenTopography, /raster/MDV_2014).
          S3 listing needs an OpenTopography API key (free) — get one and set
          OT_API_KEY, or pull via the OT portal/AWS CLI. Not auto here.
  [EDI]   MCM-LTER climate + stream data (met network, discharge, stream polygons) —
          Environmental Data Initiative packages; small CSV. Add package IDs to fetch.
  [CDS]   ERA5 reanalysis — needs a Copernicus CDS account + ~/.cdsapirc; not auto.

CLI:
  python notebooks/wellsight_v2/build/_fetch_barlow_data.py --rema           # 2m+10m
  python notebooks/wellsight_v2/build/_fetch_barlow_data.py --rema --res 10m # overview only
  python notebooks/wellsight_v2/build/_fetch_barlow_data.py --list           # plan only
"""
from __future__ import annotations

import argparse
from pathlib import Path

DST = Path("J:/barlow_data")
REMA_BUCKET = "pgc-opendata-dems"
REMA_TILES = ["17_34", "17_35", "18_34", "18_35"]   # MDV supertiles (calibrated from tile bounds)


def _s3():
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
    return boto3.client("s3", "us-west-2", config=Config(signature_version=UNSIGNED))


def fetch_rema(resolutions, list_only=False, dem_only=True):
    s3 = _s3()
    out = DST / "rema"; out.mkdir(parents=True, exist_ok=True)
    grand = 0
    for res in resolutions:
        for tl in REMA_TILES:
            pref = f"rema/mosaics/v2.0/{res}/{tl}/"
            r = s3.list_objects_v2(Bucket=REMA_BUCKET, Prefix=pref)
            for o in r.get("Contents", []):
                key = o["Key"]
                if dem_only and not key.endswith("_dem.tif"):
                    continue
                dest = out / res / Path(key).name
                grand += o["Size"]
                if list_only:
                    print(f"   [{res}] {o['Size']/1e6:7.0f} MB  {Path(key).name}")
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.stat().st_size == o["Size"]:
                    print(f"   skip {dest.name}"); continue
                print(f"   get  [{res}] {o['Size']/1e6:.0f} MB  {dest.name}")
                s3.download_file(REMA_BUCKET, key, str(dest))
    print(f"\nREMA {'planned' if list_only else 'downloaded'}: {grand/1e9:.1f} GB -> {out}")


# MCM-LTER EDI packages (scope.identifier.revision). Daily aggregates = drivers for
# the geomorphic-change coupling; high-freq 15-min also available per station/stream.
LTER_PACKAGES = {
    "lter_climate": [("knb-lter-mcm", "7003", "22")],   # meteorology network
    "lter_streams": [("knb-lter-mcm", "9128", "11")],   # stream gauge discharge (flow seasons)
}


def fetch_edi(list_only=False):
    import urllib.request
    for sub, pkgs in LTER_PACKAGES.items():
        out = DST / sub; out.mkdir(parents=True, exist_ok=True)
        for scope, ident, rev in pkgs:
            base = f"https://pasta.lternet.edu/package/data/eml/{scope}/{ident}/{rev}"
            try:
                ids = urllib.request.urlopen(base, timeout=30).read().decode().split()
            except Exception as e:  # noqa: BLE001
                print(f"  {sub} {scope}.{ident}.{rev}: list err {e}"); continue
            print(f"  {sub} {scope}.{ident}.{rev}: {len(ids)} entities")
            for eid in ids:
                if list_only:
                    print(f"     {eid}"); continue
                ok = False
                for attempt in range(4):
                    try:
                        with urllib.request.urlopen(f"{base}/{eid}", timeout=300) as r:
                            cd = r.headers.get("Content-Disposition", "")
                            fn = cd.split("filename=")[-1].strip('"') if "filename=" in cd else f"{eid}.csv"
                            dest = out / fn; tmp = dest.with_suffix(dest.suffix + ".part")
                            n = 0
                            with open(tmp, "wb") as f:
                                while True:
                                    chunk = r.read(1 << 20)
                                    if not chunk:
                                        break
                                    f.write(chunk); n += len(chunk)
                            tmp.rename(dest)
                        print(f"     ok {fn} ({n/1e6:.1f} MB)"); ok = True; break
                    except Exception as e:  # noqa: BLE001
                        print(f"     retry {attempt+1} {eid}: {type(e).__name__}")
                if not ok:
                    print(f"     FAIL {eid}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rema", action="store_true", help="fetch REMA MDV mosaic tiles")
    ap.add_argument("--lter", action="store_true", help="fetch MCM-LTER EDI met+stream packages")
    ap.add_argument("--res", default="2m,10m", help="REMA resolutions (comma): 2m,10m,32m")
    ap.add_argument("--list", action="store_true", help="plan only")
    args = ap.parse_args()
    DST.mkdir(parents=True, exist_ok=True)
    if args.rema:
        fetch_rema(args.res.split(","), list_only=args.list)
    if args.lter:
        fetch_edi(list_only=args.list)
    if not (args.rema or args.lter):
        print("nothing selected; use --rema and/or --lter (add --list to plan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fetch the public datasets behind the Barlow MDV dissertation / FINESST expansion.

Targets E:\\barlow_data_DO_NOT_DELETE (large; off the repo). Datasets and access status:

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

DST = Path("E:/barlow_data_DO_NOT_DELETE")
REMA_BUCKET = "pgc-opendata-dems"
REMA_TILES = ["17_34", "17_35", "18_34", "18_35"]   # MDV supertiles (calibrated from tile bounds)

# --- OpenTopography MDV airborne lidar (NCALM 2014-15) -----------------------
# Dataset MDV_2014 / OTLAS.112016.3294.1 / DOI 10.5069/G9D50JX3, CRS EPSG:3294.
# Hosted on OpenTopography's public Ceph S3 (anonymous; the API key is only needed
# for the *portal* download path, NOT this bulk S3). Bare-earth 1 m DEMs are the
# product directly comparable to REMA for change detection; point clouds in pc-bulk.
OT_ENDPOINT = "https://opentopography.s3.sdsc.edu"
OT_RASTER_BUCKET = "raster"
OT_PC_BUCKET = "pc-bulk"
# regions ordered so those matching met/REMA we already have land first
OT_BE_REGIONS = ["Taylor_Valley", "North", "Garwood", "Beacon", "Capes_MCMD_Pegasus"]
# point-cloud (pc-bulk) folder names are irregular — map region -> actual prefix.
# Taylor Valley PC carries the lidar INTENSITY returns that Barlow et al. (2022) use as
# a U-Net input (elevation/slope/flow-accum come from the bare-earth DEM; intensity needs
# the point cloud). doi:10.3390/rs14010234.
OT_PC_PREFIX = {
    "Taylor_Valley": "Taylor_adj47",
    "North": "Tiles_North", "Garwood": "Tiles_GAR", "Beacon": "Beacon_Tiles",
}


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
# Revision = None -> auto-resolve newest via PASTA (avoids the stale-rev 0-entities bug).
# Stream discharge is per-gauge; the 9100-series are the "Daily summarized" products
# (clean daily drivers for the geomorphic-change coupling). All MDV gauges included.
_MCM_DAILY_DISCHARGE = ["9102", "9103", "9107", "9109", "9110", "9111", "9113",
                        "9114", "9115", "9116", "9117", "9118", "9119", "9120",
                        "9121", "9122", "9123", "9124", "9127", "9128", "9129"]
_MCM_SOIL = ["4020", "4021", "4022", "4023", "4024"]   # continuous soil T / active layer
# Full MDV meteorology network (7000-series high-freq/hourly/daily). 7003 (Bonney) was
# the original pull; the rest give per-basin air-T / radiation / wind so every stream can
# be tied to its nearest station instead of extrapolating from one lake basin.
_MCM_MET = {
    "7003": "Bonney", "7005": "Brownworth", "7006": "Canada", "7007": "Commonwealth",
    "7008": "ExplorersCove", "7010": "Fryxell", "7011": "Hoare", "7012": "Howard",
    "7013": "Taylor", "7014": "UpperHoward", "7015": "Vanda", "7016": "Vida",
    "7017": "FriisHills", "7018": "MountFleming", "7020": "Miers", "7021": "Garwood",
    "7019": "GarwoodIceCliff", "7002": "Beacon", "7030": "station_locations",
}
# Pre-modeled glacier-melt energy-balance inputs (8000-series, 1996-2011): shortwave,
# longwave, air T, RH, wind speed/direction + reader. Ready-made O1 driver-energy terms.
_MCM_MELT = ["8005", "8007", "8008", "8009", "8011", "8012", "8010"]
LTER_PACKAGES = {
    "lter_climate": [("knb-lter-mcm", "7003", None)],   # Bonney (kept for back-compat)
    "lter_met_network": [("knb-lter-mcm", m, None) for m in _MCM_MET],  # full met network
    "lter_streams": [("knb-lter-mcm", g, None) for g in _MCM_DAILY_DISCHARGE],
    "lter_glacier": [("knb-lter-mcm", "2006", None)],   # snow/ice/total glacier mass balance
    "lter_melt_model": [("knb-lter-mcm", p, None) for p in _MCM_MELT],  # energy-balance drivers
    "lter_soil": [("knb-lter-mcm", s, None) for s in _MCM_SOIL],  # active-layer/permafrost
    # Ground-ice / permafrost proxies: deep ground-temperature profiles (DVDP borehole 11)
    # + the SLIME moat stations that instrument the soil<->lake ice-cementation boundary.
    "lter_groundice": [("knb-lter-mcm", "501", None),
                       ("knb-lter-mcm", "5100", None), ("knb-lter-mcm", "5101", None),
                       ("knb-lter-mcm", "5102", None), ("knb-lter-mcm", "5103", None)],
    # Lake level + ice thickness: independent check on the standing-water screen (the
    # Fryxell ~1.5 m rise) and a base-level control on stream long profiles.
    "lter_lakelevel": [("knb-lter-mcm", "68", None),    # lake level surveys 1968-2026
                       ("knb-lter-mcm", "67", None),    # lake ice thickness/density
                       ("knb-lter-mcm", "3104", None)], # continuous 1-min stage
    # label source: GIS stream-channel/watershed/glacier shapefiles (public stand-in for
    # Barlow's author-only 217 tiles) + relict-channel locations. Unzip the shapefile zip
    # under labels/ before use (the .zip lands in labels/, extract to labels/gis/).
    "labels": [("knb-lter-mcm", "6007", None), ("knb-lter-mcm", "26", None)],
}


def _latest_rev(scope: str, ident: str) -> str | None:
    """Newest revision number for an EDI package, via PASTA."""
    import urllib.request
    url = f"https://pasta.lternet.edu/package/eml/{scope}/{ident}"
    try:
        revs = urllib.request.urlopen(url, timeout=30).read().decode().split()
        return max(revs, key=int) if revs else None
    except Exception as e:  # noqa: BLE001
        print(f"  rev lookup err {scope}.{ident}: {e}"); return None


def fetch_edi(list_only=False):
    import urllib.request
    for sub, pkgs in LTER_PACKAGES.items():
        out = DST / sub; out.mkdir(parents=True, exist_ok=True)
        for scope, ident, rev in pkgs:
            if rev is None:
                rev = _latest_rev(scope, ident)
                if rev is None:
                    print(f"  {sub} {scope}.{ident}: no revision found, skip"); continue
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
                            if dest.exists() and dest.stat().st_size > 0:
                                print(f"     skip {fn}"); ok = True; break
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


# --- 2001 ATM lidar (the OTHER change-detection epoch) ----------------------
# Barlow's 2001 epoch is NASA ATM (Dec 2001 campaign), processed to 2 m DEMs by
# UB/Csatho-Schenk, distributed FREE/anonymous on USGS ScienceBase (NOT OpenTopography,
# which only has 2014). 18 MDV sites under one parent collection; ~2.5 GB total.
SB_PARENT_2001 = "5d0d1d81e4b0941bde52a1a1"
SB_ITEM = "https://www.sciencebase.gov/catalog/item/{iid}?format=json"
SB_CHILDREN = ("https://www.sciencebase.gov/catalog/items?parentId={pid}"
               "&format=json&max=100&fields=title,files")


def fetch_atm2001(list_only=False, min_free_gb=5.0):
    """Download the 2001 ATM MDV 2 m DEMs (all 18 sites) from USGS ScienceBase."""
    import shutil
    import urllib.request
    import json as _json
    req = lambda u: urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60)
    out = DST / "mdv_lidar_2001"; out.mkdir(parents=True, exist_ok=True)
    kids = _json.load(req(SB_CHILDREN.format(pid=SB_PARENT_2001))).get("items", [])
    grand = 0
    for it in sorted(kids, key=lambda x: x.get("title", "")):
        site = it["title"].split(" Digital")[0].replace(" ", "_")
        zips = [f for f in it.get("files", []) if f.get("name", "").endswith(".zip")]
        for f in zips:
            url = f.get("url") or f.get("downloadUri")
            dest = out / site / f["name"]
            grand += f.get("size", 0)
            if list_only:
                print(f"   [{site}] {f.get('size',0)/1e6:6.0f} MB {f['name']}"); continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size == f.get("size", 0):
                print(f"   skip {site}/{dest.name}"); continue
            if shutil.disk_usage(str(DST)).free / 1e9 < min_free_gb:
                print("   STOP: low disk"); return
            print(f"   get  [{site}] {f.get('size',0)/1e6:.0f} MB {dest.name}")
            urllib.request.urlretrieve(url, dest)
    print(f"\nATM2001 {'planned' if list_only else 'downloaded'}: {grand/1e9:.2f} GB -> {out}")


def _ot_s3():
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=OT_ENDPOINT, config=Config(signature_version=UNSIGNED))


def fetch_opentopo(regions=None, list_only=False, point_cloud=False, min_free_gb=10.0):
    """Pull MDV_2014 NCALM lidar from OpenTopography S3 (anonymous).

    Bare-earth 1 m DEMs by default (REMA-comparable). --pc adds point-cloud .laz tiles.
    """
    import shutil
    s3 = _ot_s3()
    pag = s3.get_paginator("list_objects_v2")
    regions = regions or OT_BE_REGIONS
    bucket = OT_PC_BUCKET if point_cloud else OT_RASTER_BUCKET
    out = DST / "mdv_lidar" / ("pc" if point_cloud else "be_dem_1m")
    out.mkdir(parents=True, exist_ok=True)
    grand = 0
    for reg in regions:
        if point_cloud:
            sub = OT_PC_PREFIX.get(reg)
            if not sub:
                print(f"  no PC prefix mapped for {reg}; skip"); continue
            pref = f"MDV_2014/{sub}/"
        else:
            pref = f"MDV_2014/MDV_2014_be/{reg}/"
        ext = ".laz" if point_cloud else ".tif"
        for pg in pag.paginate(Bucket=bucket, Prefix=pref):
            for o in pg.get("Contents", []):
                key = o["Key"]
                if not key.endswith(ext):
                    continue
                dest = out / reg / Path(key).name
                grand += o["Size"]
                if list_only:
                    print(f"   [{reg}] {o['Size']/1e6:8.0f} MB  {Path(key).name}")
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.stat().st_size == o["Size"]:
                    print(f"   skip {reg}/{dest.name}"); continue
                free = shutil.disk_usage(str(DST)).free / 1e9
                if free < min_free_gb:
                    print(f"  STOP: only {free:.1f} GB free (< {min_free_gb})"); return
                print(f"   get  [{reg}] {o['Size']/1e6:.0f} MB  {dest.name}")
                s3.download_file(bucket, key, str(dest))
    print(f"\nMDV lidar {'planned' if list_only else 'downloaded'}: "
          f"{grand/1e9:.1f} GB -> {out}")


# --- ERA5 reanalysis (Copernicus CDS) ---------------------------------------
# Climate drivers for the FINESST "geomorphic change vs. physical/climate drivers"
# coupling. Needs a (free) CDS account + ~/.cdsapirc (see setup_cds()). MDV box.
ERA5_AREA = [-77.0, 160.0, -78.5, 164.5]   # N, W, S, E (Taylor/Wright/Victoria/Garwood)
ERA5_VARS = [
    "2m_temperature", "skin_temperature",
    "10m_u_component_of_wind", "10m_v_component_of_wind",
    "surface_solar_radiation_downwards", "surface_net_solar_radiation",
    "total_precipitation", "snowmelt", "snow_depth",
]   # melt / surface-energy-balance drivers of MDV streamflow + geomorphic change


def setup_cds(token: str):
    """Write ~/.cdsapirc for the NEW CDS (single Personal Access Token)."""
    import os
    home = Path(os.path.expanduser("~"))
    dest = home / ".cdsapirc"
    dest.write_text(f"url: https://cds.climate.copernicus.eu/api\nkey: {token.strip()}\n")
    print(f"wrote {dest} (url + key, {len(token.strip())}-char token)")


# --- AMPS (Antarctic Mesoscale Prediction System) ---------------------------
# WRF forecast output over Antarctica; d3 = 2.67 km Ross Sea domain that COVERS the
# MDV (~10x finer than ERA5 there). Full GRIB files are ~240 MB (whole continent), but
# NCSS subsetting on GDEX THREDDS returns the MDV box at ~140 KB/timestep. Anonymous.
# Long GRIB archive = GDEX dataset d473002, WRF24 era (Oct 2017-present). Earlier eras
# (WRF30/45/60, MM5/MM560) use different domain numbering/encoding — not wired here.
AMPS_NCSS = ("https://tds.gdex.ucar.edu/thredds/ncss/grid/files/d473002/grib/WRF24/"
             "{yyyy}/{mm}/{dd}/{yyyy}{mm}{dd}{hh}_WRF_d{g}_f{fff}.grb")
AMPS_VARS = [
    "Temperature_height_above_ground",
    "U-component_of_horizontal_wind_height_above_ground",
    "V-component_of_horizontal_wind_height_above_ground",
    "Pressure_surface", "Sensible_heat_flux_surface", "Latent_heat_flux_surface",
    "Albedo_surface", "Geopotential_height_surface",
]   # surface / 2m / 10m drivers; d3 NCSS exposes these as CF grid names


def fetch_amps(dates, inits=("00", "12"), fhours=("000",), domain="3",
               area=None, list_only=False):
    """Pull AMPS d3 drivers over the MDV box via NCSS (tiny per-timestep subsets).

    dates: iterable of 'YYYYMMDD'. inits: forecast cycles (00/12 UTC). fhours: lead
    hours ('000'=analysis). Writes one small netCDF per (date,init,fhour) to amps/.
    """
    import urllib.parse, urllib.request, urllib.error
    area = area or {"north": -77.0, "south": -78.5, "west": 160.0, "east": 164.5}
    out = DST / "amps" / "mdv"; out.mkdir(parents=True, exist_ok=True)
    got = 0
    for ymd in dates:
        yyyy, mm, dd = ymd[:4], ymd[4:6], ymd[6:8]
        for hh in inits:
            for fff in fhours:
                url = AMPS_NCSS.format(yyyy=yyyy, mm=mm, dd=dd, hh=hh, g=domain, fff=fff)
                q = ([("var", v) for v in AMPS_VARS]
                     + [("north", area["north"]), ("south", area["south"]),
                        ("west", area["west"]), ("east", area["east"]),
                        ("accept", "netcdf")])
                full = url + "?" + urllib.parse.urlencode(q)
                dest = out / f"amps_d{domain}_mdv_{ymd}{hh}_f{fff}.nc"
                if list_only:
                    print(f"   PLAN {dest.name}"); continue
                if dest.exists():
                    print(f"   skip {dest.name}"); got += 1; continue
                try:
                    urllib.request.urlretrieve(full, dest)
                    print(f"   ok {dest.name} ({dest.stat().st_size/1024:.0f} KB)"); got += 1
                except urllib.error.HTTPError as e:
                    print(f"   miss {dest.name}: HTTP {e.code}")
    print(f"\nAMPS {'planned' if list_only else 'downloaded'}: {got} timesteps -> {out}")


def _postprocess_era5(raw: Path, target: Path):
    """The new CDS wraps netCDF in a .zip and splits vars by stepType (avgua T00 vs
    avgad T06). Extract, align the month axis, merge to one clean netCDF."""
    import zipfile
    if not zipfile.is_zipfile(raw):   # already a plain .nc
        raw.replace(target); print(f"  ok {target.name} (plain nc)"); return
    import xarray as xr
    ex = raw.parent / "_extract"; ex.mkdir(exist_ok=True)
    zipfile.ZipFile(raw).extractall(ex)
    dsl = []
    for f in sorted(ex.glob("*.nc")):
        ds = xr.open_dataset(f)
        if "valid_time" in ds:   # snap to month start so step-types align exactly
            vt = ds["valid_time"].values.astype("datetime64[M]").astype("datetime64[ns]")
            ds = ds.assign_coords(valid_time=vt)
        dsl.append(ds)
    merged = xr.merge(dsl, join="exact", compat="override")
    merged.to_netcdf(target)
    for ds in dsl:
        ds.close()
    print(f"  ok {target.name} ({target.stat().st_size/1e6:.1f} MB, "
          f"{len(merged.data_vars)} vars, {merged.sizes.get('valid_time')} months)")


def fetch_era5(years=None, monthly=True, area=None, list_only=False):
    """ERA5 single-level drivers over the MDV box via cdsapi.

    monthly=True -> reanalysis-era5-single-levels-monthly-means (tiny; whole record).
    monthly=False -> hourly reanalysis-era5-single-levels (large; per-year files).
    Requires ~/.cdsapirc (run setup_cds first). Accept the dataset Terms of Use on the
    CDS website once before this will succeed.
    """
    import cdsapi
    area = area or ERA5_AREA
    years = years or [str(y) for y in range(1993, 2025)]   # spans LTER + lidar epochs
    out = DST / "era5"; out.mkdir(parents=True, exist_ok=True)
    months = [f"{m:02d}" for m in range(1, 13)]
    if monthly:
        ds = "reanalysis-era5-single-levels-monthly-means"
        req = {"product_type": "monthly_averaged_reanalysis", "variable": ERA5_VARS,
               "year": years, "month": months, "time": "00:00",
               "area": area, "data_format": "netcdf"}
        target = out / "era5_mdv_monthly_1993-2024.nc"
        print(f"  {'PLAN' if list_only else 'GET '} {ds} -> {target.name} "
              f"({len(ERA5_VARS)} vars, {len(years)} yr, area {area})")
        if list_only:
            return
        raw = out / "_era5_monthly_raw.nc"
        cdsapi.Client().retrieve(ds, req, str(raw))
        _postprocess_era5(raw, target)
        return
    ds = "reanalysis-era5-single-levels"
    for yr in years:
        target = out / f"era5_mdv_hourly_{yr}.nc"
        if target.exists():
            print(f"  skip {target.name}"); continue
        req = {"product_type": "reanalysis", "variable": ERA5_VARS, "year": yr,
               "month": months, "day": [f"{d:02d}" for d in range(1, 32)],
               "time": [f"{h:02d}:00" for h in range(24)],
               "area": area, "data_format": "netcdf"}
        print(f"  {'PLAN' if list_only else 'GET '} {ds} {yr} -> {target.name}")
        if list_only:
            continue
        cdsapi.Client().retrieve(ds, req, str(target))
        print(f"  ok {target.name} ({target.stat().st_size/1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rema", action="store_true", help="fetch REMA MDV mosaic tiles")
    ap.add_argument("--lter", action="store_true", help="fetch MCM-LTER EDI met+stream packages")
    ap.add_argument("--lidar", action="store_true", help="fetch MDV_2014 NCALM bare-earth 1m DEMs (OpenTopography)")
    ap.add_argument("--atm2001", action="store_true", help="fetch 2001 ATM MDV 2m DEMs (USGS ScienceBase)")
    ap.add_argument("--pc", action="store_true", help="with --lidar: fetch point-cloud .laz instead of DEMs")
    ap.add_argument("--regions", help="comma list of MDV regions (default: all, valleys first)")
    ap.add_argument("--amps", action="store_true", help="fetch AMPS d3 MDV drivers via NCSS (anonymous)")
    ap.add_argument("--amps-start", help="AMPS start date YYYYMMDD")
    ap.add_argument("--amps-end", help="AMPS end date YYYYMMDD (inclusive)")
    ap.add_argument("--amps-fhours", default="000", help="AMPS forecast lead hours, comma (e.g. 000,012)")
    ap.add_argument("--era5", action="store_true", help="fetch ERA5 MDV drivers (needs ~/.cdsapirc)")
    ap.add_argument("--era5-hourly", action="store_true", help="with --era5: hourly (large) instead of monthly")
    ap.add_argument("--setup-cds", metavar="TOKEN", help="write ~/.cdsapirc with your CDS Personal Access Token")
    ap.add_argument("--res", default="2m,10m", help="REMA resolutions (comma): 2m,10m,32m")
    ap.add_argument("--list", action="store_true", help="plan only")
    args = ap.parse_args()
    if args.setup_cds:
        setup_cds(args.setup_cds); return 0
    DST.mkdir(parents=True, exist_ok=True)
    if args.rema:
        fetch_rema(args.res.split(","), list_only=args.list)
    if args.lter:
        fetch_edi(list_only=args.list)
    if args.lidar:
        regions = args.regions.split(",") if args.regions else None
        fetch_opentopo(regions=regions, list_only=args.list, point_cloud=args.pc)
    if args.atm2001:
        fetch_atm2001(list_only=args.list)
    if args.amps:
        import datetime as _dt
        if not (args.amps_start and args.amps_end):
            print("--amps needs --amps-start and --amps-end (YYYYMMDD)"); return 2
        d0 = _dt.datetime.strptime(args.amps_start, "%Y%m%d").date()
        d1 = _dt.datetime.strptime(args.amps_end, "%Y%m%d").date()
        dates = [(d0 + _dt.timedelta(days=i)).strftime("%Y%m%d")
                 for i in range((d1 - d0).days + 1)]
        fetch_amps(dates, fhours=tuple(args.amps_fhours.split(",")), list_only=args.list)
    if args.era5:
        fetch_era5(monthly=not args.era5_hourly, list_only=args.list)
    if not (args.rema or args.lter or args.lidar or args.atm2001 or args.era5 or args.amps):
        print("nothing selected; use --rema / --lter / --lidar / --atm2001 / --era5 / --amps (add --list to plan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

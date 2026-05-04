"""Regenerate output3_2008.las as a clean merge of PAMAP 2006-2008 tiles
clipped to the output3 footprint.

Steps per source tile:
  1. read EPSG:2271 (PA State Plane N, US feet)
  2. reproject horizontal to EPSG:6346 (UTM 17N, metres); PDAL leaves Z alone
  3. scale Z by US-survey-ft -> m  (0.3048006096)
  4. crop to output3 bounds
then merge surviving points and write.

No vertical offset is applied — we're keeping the datasets separate, so
temporal alignment is not attempted here.
"""
import json, subprocess, shutil, time
from pathlib import Path

ROOT = Path('data/files')
OLD  = ROOT / 'older_files'
OUT  = ROOT / 'output3_2008.las'
PDAL = shutil.which('pdal') or 'pdal'

X0, Y0, X1, Y1 = 621000.0, 4594500.0, 622500.0, 4596000.0

# The four tiles that intersect output3 (confirmed from prior work).
TILES = [
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002958.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002959.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003111.laz',
    OLD / 'USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003112.laz',
]
for t in TILES:
    assert t.exists(), f'missing source tile: {t}'

stages = []
for t in TILES:
    stages.append({'type': 'readers.las', 'filename': str(t),
                   'override_srs': 'EPSG:2271'})
# horizontal reprojection for all readers
stages.append({'type': 'filters.reprojection', 'out_srs': 'EPSG:6346'})
# convert Z from US survey feet -> metres
stages.append({'type': 'filters.assign',
               'value': 'Z = Z * 0.3048006096'})
# clip to output3 footprint
stages.append({'type': 'filters.crop',
               'bounds': f'([{X0},{X1}],[{Y0},{Y1}])'})
# single merged writer
stages.append({'type': 'writers.las',
               'filename': str(OUT),
               'a_srs': 'EPSG:6346',
               'minor_version': 4,
               'dataformat_id': 6,
               'forward': 'all',
               'compression': 'false'})

pipeline = {'pipeline': stages}

tmp = Path('data/derivatives/_tmp_build_2008.json')
tmp.parent.mkdir(parents=True, exist_ok=True)
with open(tmp, 'w') as f:
    json.dump(pipeline, f, indent=2)

t0 = time.time()
r = subprocess.run([PDAL, 'pipeline', str(tmp)], capture_output=True, text=True, timeout=1800)
print(f'rc={r.returncode} in {time.time()-t0:.1f}s')
if r.returncode != 0:
    print('STDOUT:', r.stdout[-2000:])
    print('STDERR:', r.stderr[-2000:])
    raise SystemExit(1)
tmp.unlink(missing_ok=True)

# Verify
info = subprocess.run([PDAL, 'info', str(OUT), '--metadata'],
                      capture_output=True, text=True, timeout=120).stdout
meta = json.loads(info)['metadata']
print(f'points:  {meta["count"]:,}')
print(f'bounds:  X {meta["minx"]:.1f}..{meta["maxx"]:.1f}  '
      f'Y {meta["miny"]:.1f}..{meta["maxy"]:.1f}')
print(f'z:       {meta["minz"]:.2f}..{meta["maxz"]:.2f} m')

"""KML of the NISAR marker sites named in the 2026-11-15 review (Codex read, checked against results).

9t: pad 303 (permit 121-26498, coherence event 2025-10-28/11-09), pad 316 (121-32125, two events
Aug-Sep 2026), pad 993 (HH +1.5 to +1.7 dB all seasons). 613590: pit row 718 (HV +1.0 to +2.1 dB).
Ids are the seasonal-stack ids (pads: pad_id of the `plat` layer; pits: row of `pit_outside` in the area window).
Run once per area (writes a per-area KML in nisar/results/kml/):
  python nisar/code/s6_review/_nisar_marker_sites_kml.py            (9t)
  python nisar/code/s6_review/_nisar_marker_sites_kml.py --area 613590
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s5_eval"))
import importlib
seas = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")
A = seas.A
SITES = {"9t": {"pad": {303: "Pad 303, permit 121-26498. Coherence 0.185 on pad vs 0.530 ring, 2025-10-28 to 11-09, track 162. One event (chance-level alone).",
                        316: "Pad 316, permit 121-32125. Two coherence-loss events, 2026-08-19 to 09-12, track 90.",
                        993: "Pad 993. HH core +1.70 / +1.51 / +1.47 dB vs ring (fall / winter / summer). 54 pixels. Selected as extreme of 650."}},
         "613590": {"pit": {718: "Pit row 718. HV +1.90 / +2.06 / +1.03 dB vs ring (fall / winter / summer); HH near zero. 7 pixels. Selected as extreme of 36."}}}
pads = seas.read_layer(seas.ANN, "plat").to_crs(seas.CRS)[["pad_id", "geometry"]].dissolve(by="pad_id").reset_index()
pits = seas.read_layer(seas.ANN, "pit_outside").to_crs(seas.CRS).reset_index(drop=True)
rows = []
for kind, d in SITES[A.TAG].items():
    for fid, note in d.items():
        g = pads.loc[pads.pad_id == fid, "geometry"].iloc[0] if kind == "pad" else pits.geometry.iloc[fid]
        rows.append(dict(Name=f"{A.TAG}_{kind}_{fid}", Description=note, geometry=g))
import geopandas as gpd
gdf = gpd.GeoDataFrame(rows, crs=seas.CRS).to_crs("EPSG:4326")
c = gdf.geometry.centroid
gdf["Description"] = [f"{d} Centroid {y:.6f}, {x:.6f}" for d, x, y in zip(gdf.Description, c.x, c.y)]
out = A.NISAR_ROOT / "results" / "kml" / f"nisar_marker_sites_{A.TAG}.kml"
gdf.to_file(out, driver="KML")
print(out); print(gdf.drop(columns="geometry").to_string())

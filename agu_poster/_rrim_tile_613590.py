"""Crop the 0.5 m RRIM of Area B (613590) to the 1.5 km tile 17TPF616591 (616500, 4591500) and write GeoTIFF + PNG."""
import rasterio
from rasterio.windows import from_bounds
from PIL import Image
R = "data/613590"
B = (616500, 4591500, 618000, 4593000)
OUT = f"{R}/results/rrim"
with rasterio.open(f"{R}/derived/05/rrim_openness_613590_05.tif") as s:
    w = from_bounds(*B, s.transform)
    a = s.read(window=w)
    tr = s.window_transform(w)
    prof = s.profile | dict(height=a.shape[1], width=a.shape[2], transform=tr, compress="deflate")
with rasterio.open(f"{OUT}/rrim_tile616591_613590.tif", "w", **prof) as d:
    d.write(a)
Image.fromarray(a.transpose(1, 2, 0)).save(f"{OUT}/rrim_tile616591_613590.png")
print(a.shape)

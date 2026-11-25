"""Locator map for the poster: documented orphan wells in western Pennsylvania, with a scale bar.

Input   docs/figures/Pennsylvania Map Abandoned.png   (QGIS export, 180 km scale bar = 925 px, north up)
Output  agu_poster/figures/poster_pa_wells_locator.png
Crops the western part of the export (where the wells are), redraws a 100 km scale bar and a north arrow,
and adds lat/long-free neat borders. Wells are yellow points on a satellite base, as in the source.
Run     python agu_poster/_make_poster_locator.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "docs/figures/Pennsylvania Map Abandoned.png"
OUT = HERE / "figures/poster_pa_wells_locator.png"
PX_PER_KM = (1835 - 910) / 180.0          # measured from the source scale bar

im = Image.open(SRC).convert("RGB")
W, H = im.size
f = W / 2000.0                              # the displayed 2000 px copy was used for measuring
box = (0, 0, int(1300 * f), int(1050 * f))
im = im.crop(box)
d = ImageDraw.Draw(im)
font = ImageFont.truetype("arial.ttf", int(44 * f)) if True else None
km100 = int(100 * PX_PER_KM * f)
x0, y0 = int(60 * f), im.size[1] - int(90 * f)
bar_h = int(22 * f)
d.rectangle([x0 - 6, y0 - int(70 * f), x0 + km100 + int(130 * f), y0 + bar_h + int(10 * f)], fill=(0, 0, 0))
d.rectangle([x0, y0, x0 + km100 // 2, y0 + bar_h], fill="black", outline="white", width=3)
d.rectangle([x0 + km100 // 2, y0, x0 + km100, y0 + bar_h], fill="white", outline="white", width=3)
for xx, lab in ((x0, "0"), (x0 + km100 // 2, "50"), (x0 + km100, "100 km")):
    d.text((xx, y0 - int(58 * f)), lab, fill="white", font=font)
ax, ay = im.size[0] - int(110 * f), int(40 * f)
d.polygon([(ax, ay), (ax - int(26 * f), ay + int(90 * f)), (ax, ay + int(66 * f)), (ax + int(26 * f), ay + int(90 * f))], fill="white", outline="black")
d.text((ax - int(14 * f), ay + int(98 * f)), "N", fill="white", font=font)
im.save(OUT)
print(OUT, im.size)

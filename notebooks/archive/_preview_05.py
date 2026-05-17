"""Regenerate tile_overview_05.png and per-derivative PNG previews from the
fresh output3-only 0.5 m derivative stack."""
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from pathlib import Path

DERIV = Path('data/derivatives')

def read(name):
    with rasterio.open(DERIV/name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a==nd, np.nan, a)
    return a

def stretch(a, lo=2, hi=98):
    m = np.isfinite(a)
    if not m.any(): return np.zeros_like(a)
    v0, v1 = np.nanpercentile(a[m], [lo, hi])
    if v1 <= v0: return np.zeros_like(a)
    return np.clip((a - v0)/(v1 - v0), 0, 1)

panels = [
    ('hillshade_05.tif',        'hillshade',           'gray',   (None,None)),
    ('dem_05.tif',              'DEM (m)',             'terrain',(None,None)),
    ('slope_05.tif',            'slope (deg)',         'magma',  (0, 30)),
    ('intensity_ground_05.tif', 'ground intensity',    'cividis',(None,None)),
    ('ground_density_05.tif',   'ground density',      'viridis',(0, 8)),
    ('chm_05.tif',              'CHM (m)',             'Greens', (0, 30)),
    ('lrm_11_05.tif',           'LRM 11',              'RdBu_r', (-0.6, 0.6)),
    ('lrm_25_05.tif',           'LRM 25',              'RdBu_r', (-0.8, 0.8)),
    ('tpi_15_05.tif',           'TPI 15 m',            'RdBu_r', (-0.5, 0.5)),
    ('openness_pos_05.tif',     'openness_pos',        'viridis',(None,None)),
    ('openness_neg_05.tif',     'openness_neg',        'viridis',(None,None)),
    ('local_relief_10_05.tif',  'local relief (10 m)', 'magma',  (0, 3)),
]

fig, axes = plt.subplots(3, 4, figsize=(20, 15))
for ax, (fname, title, cmap, lim) in zip(axes.ravel(), panels):
    try:
        a = read(fname)
    except Exception as e:
        ax.set_title(f'{title}  [missing]'); ax.axis('off'); continue
    if lim[0] is None:
        im = ax.imshow(a, cmap=cmap)
    else:
        im = ax.imshow(a, cmap=cmap, vmin=lim[0], vmax=lim[1])
    ax.set_title(f'{title}  ({fname})', fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

fig.suptitle('output3 0.5 m derivative stack (2019 only, no stacking)', fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.98])
fig.savefig(DERIV/'tile_overview_05.png', dpi=130, bbox_inches='tight')
plt.close(fig)
print('wrote tile_overview_05.png')

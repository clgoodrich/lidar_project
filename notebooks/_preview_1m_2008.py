"""12-panel overview PNG for the 2008 1 m derivative stack."""
import numpy as np, rasterio
import matplotlib.pyplot as plt
from pathlib import Path

DERIV = Path('data/derivatives')

def read(name):
    with rasterio.open(DERIV/name) as ds:
        a = ds.read(1).astype(np.float32); nd = ds.nodata
    if nd is not None: a = np.where(a==nd, np.nan, a)
    return a

panels = [
    ('hillshade_2008_1m.tif',        'hillshade',           'gray',   (None,None)),
    ('dem_2008_1m.tif',              'DEM (m)',             'terrain',(None,None)),
    ('slope_2008_1m.tif',            'slope (deg)',         'magma',  (0, 30)),
    ('intensity_ground_2008_1m.tif', 'ground intensity',    'cividis',(None,None)),
    ('ground_density_2008_1m.tif',   'ground density',      'viridis',(0, 3)),
    ('chm_2008_1m.tif',              'CHM (m)',             'Greens', (0, 30)),
    ('lrm_5_2008_1m.tif',            'LRM 5',               'RdBu_r', (-0.6, 0.6)),
    ('lrm_11_2008_1m.tif',           'LRM 11',              'RdBu_r', (-0.8, 0.8)),
    ('tpi_15_2008_1m.tif',           'TPI 15 m',            'RdBu_r', (-0.5, 0.5)),
    ('openness_pos_2008_1m.tif',     'openness_pos',        'viridis',(None,None)),
    ('openness_neg_2008_1m.tif',     'openness_neg',        'viridis',(None,None)),
    ('local_relief_10_2008_1m.tif',  'local relief (10 m)', 'magma',  (0, 3)),
]

fig, axes = plt.subplots(3, 4, figsize=(20, 15))
for ax, (fname, title, cmap, lim) in zip(axes.ravel(), panels):
    try: a = read(fname)
    except Exception: ax.set_title(f'{title}  [missing]'); ax.axis('off'); continue
    if lim[0] is None:
        im = ax.imshow(a, cmap=cmap)
    else:
        im = ax.imshow(a, cmap=cmap, vmin=lim[0], vmax=lim[1])
    ax.set_title(f'{title}  ({fname})', fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

fig.suptitle('PAMAP 2006-2008 — 1 m derivative stack (output3_2008.las)', fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.98])
fig.savefig(DERIV/'tile_overview_2008_1m.png', dpi=130, bbox_inches='tight')
plt.close(fig)
print('wrote tile_overview_2008_1m.png')

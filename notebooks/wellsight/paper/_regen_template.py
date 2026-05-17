import geopandas as gpd
import rasterio
import numpy as np
import matplotlib.pyplot as plt

DERIV = 'data/derivatives'
HALF = 8
WIN = 2 * HALF + 1
TEMPLATE_CHANNELS = ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg', 'hillshade']
CHANNEL_LABELS = ['LRM 5', 'LRM 11', 'TPI 5m', 'Openness\n(negative)', 'Hillshade']

ann = gpd.read_file(f'{DERIV}/annotations/wellhead_pits.gpkg')

# Read rasters for tile 9t
def read_tile(ch):
    return rasterio.open(f'{DERIV}/9t/{ch}_9t_05.tif')

raster_datasets = {ch: read_tile(ch) for ch in TEMPLATE_CHANNELS}
rasters = {ch: ds.read(1) for ch, ds in raster_datasets.items()}
ref_ds = raster_datasets['lrm_5']
H, W = rasters['lrm_5'].shape

ann_proj = ann.to_crs(ref_ds.crs)
X0, Y1 = ref_ds.bounds.left, ref_ds.bounds.top
RES = ref_ds.res[0]

all_cutouts = {ch: [] for ch in TEMPLATE_CHANNELS}

for _, row in ann_proj.iterrows():
    x, y = row.geometry.x, row.geometry.y
    r = int(round((Y1 - y) / RES))
    c = int(round((x - X0) / RES))
    r1, r2 = r - HALF, r + HALF + 1
    c1, c2 = c - HALF, c + HALF + 1
    if r1 < 0 or c1 < 0 or r2 > H or c2 > W:
        continue
    valid = True
    for ch in TEMPLATE_CHANNELS:
        win = rasters[ch][r1:r2, c1:c2]
        if np.isnan(win).mean() > 0.2:
            valid = False
            break
    if valid:
        for ch in TEMPLATE_CHANNELS:
            all_cutouts[ch].append(rasters[ch][r1:r2, c1:c2].astype(np.float32))

print(f'Valid cutouts: {len(all_cutouts["lrm_5"])}')

fig, axes = plt.subplots(2, len(TEMPLATE_CHANNELS), figsize=(3.5 * len(TEMPLATE_CHANNELS), 7.5))
fig.patch.set_facecolor('#1a1a2e')

for j, (ch, label) in enumerate(zip(TEMPLATE_CHANNELS, CHANNEL_LABELS)):
    arr = np.stack(all_cutouts[ch], axis=0)

    mean_img = np.nanmean(arr, axis=0)
    med_img = np.nanmedian(arr, axis=0)

    axes[0, j].imshow(mean_img, cmap='RdBu_r')
    axes[0, j].set_title(f'{label}\nmean', fontsize=16, fontweight='bold', color='white', pad=8)
    axes[0, j].axis('off')

    axes[1, j].imshow(med_img, cmap='RdBu_r')
    axes[1, j].set_title('median', fontsize=14, color='#cccccc', pad=6)
    axes[1, j].axis('off')

fig.suptitle(f'Mean & Median Pit Templates (n={len(all_cutouts["lrm_5"])} pits, 17×17 m windows)',
             fontsize=18, fontweight='bold', color='white', y=0.99)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(f'{DERIV}/pit_1m_template_mean.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close(fig)
print('Saved pit_1m_template_mean.png')

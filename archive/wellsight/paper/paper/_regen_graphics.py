import geopandas as gpd
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import box

hs_ds = rasterio.open('data/derivatives/hillshade.tif')
hs = hs_ds.read(1)
bounds = hs_ds.bounds
vmin, vmax = np.percentile(hs[hs > 0], [2, 98])

ann = gpd.read_file('data/derivatives/annotations/wellhead_pits.gpkg').to_crs(hs_ds.crs)
wells = gpd.read_file('data/derivatives/wells_in_tile_enriched.gpkg').to_crs(hs_ds.crs)

tile_box = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
ann_clip = ann[ann.within(tile_box)]
wells_clip = wells[wells.within(tile_box)]

status_style = {
    'Active':                        {'color': '#4466AA', 'size': 40, 'label': 'Active'},
    'Plugged OG Well':               {'color': '#88AA44', 'size': 40, 'label': 'Plugged OG Well'},
    'DEP Abandoned List':            {'color': '#DDAA44', 'size': 40, 'label': 'DEP Abandoned'},
    'DEP Orphan List':               {'color': '#FF8800', 'size': 55, 'label': 'DEP Orphan'},
    'Operator Reported Not Drilled': {'color': '#888888', 'size': 35, 'label': 'Not Drilled'},
}

def get_window(x0, y0, zone_size):
    x1, y1 = x0 + zone_size, y0 + zone_size
    col0 = int((x0 - bounds.left) / hs_ds.res[0])
    col1 = int((x1 - bounds.left) / hs_ds.res[0])
    row0 = int((bounds.top - y1) / hs_ds.res[1])
    row1 = int((bounds.top - y0) / hs_ds.res[1])
    row0, row1 = max(0, row0), min(hs.shape[0], row1)
    col0, col1 = max(0, col0), min(hs.shape[1], col1)
    return hs[row0:row1, col0:col1], x0, y0, x1, y1

def plot_wells(ax, z_wells):
    for status, style in status_style.items():
        subset = z_wells[z_wells['WELL_STATU'] == status]
        if len(subset) > 0:
            ax.scatter(subset.geometry.x, subset.geometry.y,
                       c=style['color'], s=style['size'], marker='o',
                       edgecolors='white', linewidths=0.5, zorder=3)

def make_legend(ax, z_wells, include_picks=False):
    elems = []
    for status, style in status_style.items():
        subset = z_wells[z_wells['WELL_STATU'] == status]
        if len(subset) > 0:
            elems.append(Line2D([0], [0], marker='o', color='w',
                         markerfacecolor=style['color'], markersize=8,
                         label=style['label'], linestyle='None'))
    if include_picks:
        elems.append(Line2D([0], [0], marker=(6, 2, 0), color='w',
                     markerfacecolor='none', markeredgecolor='#00FF88',
                     markersize=10, markeredgewidth=1.5,
                     label='Manual Picks', linestyle='None'))
    leg = ax.legend(handles=elems, loc='upper right', fontsize=10,
              facecolor='#1a1a2e', edgecolor='#444466', labelcolor='white',
              framealpha=0.9, title='Well Locations', title_fontsize=11)
    leg.get_title().set_color('white')

def scalebar(ax, x0, y0, bar_len=200):
    bx, by = x0 + 30, y0 + 30
    ax.plot([bx, bx + bar_len], [by, by], 'w-', linewidth=3)
    ax.text(bx + bar_len/2, by + 15, f'{bar_len} m', color='white', fontsize=10,
            ha='center', fontweight='bold')

# === GRAPHIC 1: Manual Picks (slide 7) ===
zone_size = 800
best = (0, 0, 0)
for x0 in np.arange(bounds.left, bounds.right - zone_size, 50):
    for y0 in np.arange(bounds.bottom, bounds.top - zone_size, 50):
        zb = box(x0, y0, x0 + zone_size, y0 + zone_size)
        na = ann_clip[ann_clip.within(zb)].shape[0]
        nw = wells_clip[wells_clip.within(zb)].shape[0]
        if na * 2 + nw > best[0]:
            best = (na * 2 + nw, x0, y0)

_, x0, y0 = best
zb = box(x0, y0, x0 + zone_size, y0 + zone_size)
z_ann = ann_clip[ann_clip.within(zb)]
z_wells = wells_clip[wells_clip.within(zb)]

fig, ax = plt.subplots(figsize=(10, 8))
fig.patch.set_facecolor('#1a1a2e')
chunk, x0_, y0_, x1_, y1_ = get_window(x0, y0, zone_size)
ax.imshow(chunk, cmap='gray', vmin=vmin, vmax=vmax, extent=[x0_, x1_, y0_, y1_], origin='upper')
if len(z_ann) > 0:
    ax.scatter(z_ann.geometry.x, z_ann.geometry.y,
               facecolors='none', edgecolors='#00FF88', s=120,
               marker=(6, 2, 0), linewidths=1.5, zorder=2)
plot_wells(ax, z_wells)
make_legend(ax, z_wells, include_picks=True)
scalebar(ax, x0, y0)
ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
ax.set_xticks([]); ax.set_yticks([])
plt.tight_layout()
plt.savefig('Manual Picks.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print('Saved Manual Picks.png')

# === GRAPHIC 2: DEP errors (slide 12) ===
orphan_aband = wells_clip[wells_clip['WELL_STATU'].isin(['DEP Orphan List', 'DEP Abandoned List'])]
zone_size2 = 600
best2 = (0, 0, 0)
for x0 in np.arange(bounds.left, bounds.right - zone_size2, 50):
    for y0 in np.arange(bounds.bottom, bounds.top - zone_size2, 50):
        zb = box(x0, y0, x0 + zone_size2, y0 + zone_size2)
        noa = orphan_aband[orphan_aband.within(zb)].shape[0]
        na = ann_clip[ann_clip.within(zb)].shape[0]
        if noa + na > best2[0] and noa >= 3:
            best2 = (noa + na, x0, y0)

_, x0, y0 = best2
zb = box(x0, y0, x0 + zone_size2, y0 + zone_size2)
z_wells2 = wells_clip[wells_clip.within(zb)]
z_ann2 = ann_clip[ann_clip.within(zb)]

fig, ax = plt.subplots(figsize=(10, 8))
fig.patch.set_facecolor('#1a1a2e')
chunk, x0_, y0_, x1_, y1_ = get_window(x0, y0, zone_size2)
ax.imshow(chunk, cmap='gray', vmin=vmin, vmax=vmax, extent=[x0_, x1_, y0_, y1_], origin='upper')
if len(z_ann2) > 0:
    ax.scatter(z_ann2.geometry.x, z_ann2.geometry.y,
               facecolors='none', edgecolors='#00FF88', s=120,
               marker=(6, 2, 0), linewidths=1.5, zorder=2)
plot_wells(ax, z_wells2)
oa_in = z_wells2[z_wells2['WELL_STATU'].isin(['DEP Orphan List', 'DEP Abandoned List'])]
for _, well in oa_in.iterrows():
    if len(z_ann2) > 0:
        dists = z_ann2.geometry.distance(well.geometry)
        d = dists.min()
        if d < 300:
            nearest = z_ann2.loc[dists.idxmin()]
            ax.plot([well.geometry.x, nearest.geometry.x],
                    [well.geometry.y, nearest.geometry.y],
                    'r--', linewidth=1.5, alpha=0.8, zorder=2)
            mid_x = (well.geometry.x + nearest.geometry.x) / 2
            mid_y = (well.geometry.y + nearest.geometry.y) / 2
            ax.text(mid_x, mid_y, f'{d:.0f}m', color='red', fontsize=9,
                    fontweight='bold', ha='center', va='bottom')
make_legend(ax, z_wells2, include_picks=True)
scalebar(ax, x0, y0, bar_len=100)
ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
ax.set_xticks([]); ax.set_yticks([])
plt.tight_layout()
plt.savefig('close up errors.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print('Saved close up errors.png')

# === GRAPHIC 3: Orphans with no terrain signature (slide 13) ===
orphans = wells_clip[wells_clip['WELL_STATU'] == 'DEP Orphan List']
lonely = []
for _, orph in orphans.iterrows():
    if len(ann_clip) > 0:
        d = ann_clip.geometry.distance(orph.geometry).min()
        if d > 50:
            lonely.append(orph)
print(f'Orphans with no nearby annotation (>50m): {len(lonely)}')

if len(lonely) > 0:
    lonely_gdf = gpd.GeoDataFrame(lonely, crs=wells_clip.crs)
    zone_size3 = 600
    best3 = (0, 0, 0)
    for x0 in np.arange(bounds.left, bounds.right - zone_size3, 50):
        for y0 in np.arange(bounds.bottom, bounds.top - zone_size3, 50):
            zb = box(x0, y0, x0 + zone_size3, y0 + zone_size3)
            n = lonely_gdf[lonely_gdf.within(zb)].shape[0]
            if n > best3[0]:
                best3 = (n, x0, y0)
    _, x0, y0 = best3
    zb = box(x0, y0, x0 + zone_size3, y0 + zone_size3)
    z_wells3 = wells_clip[wells_clip.within(zb)]
    z_lonely = lonely_gdf[lonely_gdf.within(zb)]

    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor('#1a1a2e')
    chunk, x0_, y0_, x1_, y1_ = get_window(x0, y0, zone_size3)
    ax.imshow(chunk, cmap='gray', vmin=vmin, vmax=vmax, extent=[x0_, x1_, y0_, y1_], origin='upper')
    plot_wells(ax, z_wells3)
    for _, orph in z_lonely.iterrows():
        circle = plt.Circle((orph.geometry.x, orph.geometry.y), 30,
                           fill=False, edgecolor='red', linewidth=2, linestyle='--', zorder=5)
        ax.add_patch(circle)
        ax.text(orph.geometry.x, orph.geometry.y - 40, 'No pit visible',
                color='red', fontsize=8, ha='center', fontweight='bold')
    make_legend(ax, z_wells3)
    scalebar(ax, x0, y0, bar_len=100)
    ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
    ax.set_xticks([]); ax.set_yticks([])
    plt.tight_layout()
    plt.savefig('orphaned with no clear wells.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print('Saved orphaned with no clear wells.png')

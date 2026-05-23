import matplotlib
matplotlib.use('Agg')
import geopandas as gpd
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import box

DERIV = r'C:\Users\colto\Documents\GitHub\lidar_project\data\derivatives'

hs_ds = rasterio.open(f'{DERIV}/hillshade.tif')
hs = hs_ds.read(1)
bounds = hs_ds.bounds
vmin, vmax = np.percentile(hs[hs > 0], [2, 98])

ann = gpd.read_file(f'{DERIV}/annotations/wellhead_pits.gpkg').to_crs(hs_ds.crs)
wells = gpd.read_file(f'{DERIV}/wells_in_tile_enriched.gpkg').to_crs(hs_ds.crs)

tile_box = box(bounds.left, bounds.bottom, bounds.right, bounds.top)
ann_clip = ann[ann.within(tile_box)]
wells_clip = wells[wells.within(tile_box)]

def get_window(x0, y0, zone_size):
    x1, y1 = x0 + zone_size, y0 + zone_size
    col0 = int((x0 - bounds.left) / hs_ds.res[0])
    col1 = int((x1 - bounds.left) / hs_ds.res[0])
    row0 = int((bounds.top - y1) / hs_ds.res[1])
    row1 = int((bounds.top - y0) / hs_ds.res[1])
    row0, row1 = max(0, row0), min(hs.shape[0], row1)
    col0, col1 = max(0, col0), min(hs.shape[1], col1)
    return hs[row0:row1, col0:col1], x0, y0, x1, y1

def scalebar(ax, x0, y0, bar_len=200):
    bx, by = x0 + 30, y0 + 30
    ax.plot([bx, bx + bar_len], [by, by], 'w-', linewidth=3)
    ax.text(bx + bar_len/2, by + 15, f'{bar_len} m', color='white', fontsize=11,
            ha='center', fontweight='bold')

# ============================================================
# GRAPHIC 1: Manual Picks (slide 8)
# ============================================================
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

# Manual picks - bright green stars, BIG
if len(z_ann) > 0:
    ax.scatter(z_ann.geometry.x, z_ann.geometry.y,
               c='#00FF88', s=350, marker='*',
               edgecolors='none', linewidths=0, zorder=2, alpha=0.9)

# All wells as single bright color - BIG
if len(z_wells) > 0:
    ax.scatter(z_wells.geometry.x, z_wells.geometry.y,
               c='#FF6644', s=80, marker='o',
               edgecolors='white', linewidths=0.8, zorder=3)

elems = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF6644',
           markersize=10, label=f'DEP Well Records ({len(z_wells)})', linestyle='None'),
    Line2D([0], [0], marker='*', color='w', markerfacecolor='#00FF88',
           markersize=16, label=f'Manual Picks ({len(z_ann)})', linestyle='None'),
]
leg = ax.legend(handles=elems, loc='upper right', fontsize=13,
          facecolor='#1a1a2e', edgecolor='#444466', labelcolor='white', framealpha=0.9)
scalebar(ax, x0, y0)
ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
ax.set_xticks([]); ax.set_yticks([])
for spine in ax.spines.values():
    spine.set_visible(False)
plt.tight_layout()
fig.savefig('Manual Picks.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f'Saved Manual Picks.png ({len(z_ann)} picks, {len(z_wells)} wells)')

# ============================================================
# GRAPHIC 2: DEP Records Problem (slide 13) - no red lines
# ============================================================
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

# Annotations - bright green stars, big
if len(z_ann2) > 0:
    ax.scatter(z_ann2.geometry.x, z_ann2.geometry.y,
               c='#00FF88', s=350, marker='*',
               edgecolors='none', linewidths=0, zorder=2, alpha=0.9)

# DEP wells - single bright color, big
if len(z_wells2) > 0:
    ax.scatter(z_wells2.geometry.x, z_wells2.geometry.y,
               c='#FF6644', s=100, marker='o',
               edgecolors='white', linewidths=0.8, zorder=3)

elems = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF6644',
           markersize=10, label=f'DEP Well Records ({len(z_wells2)})', linestyle='None'),
    Line2D([0], [0], marker='*', color='w', markerfacecolor='#00FF88',
           markersize=16, label=f'Visible Pits ({len(z_ann2)})', linestyle='None'),
]
leg = ax.legend(handles=elems, loc='upper right', fontsize=13,
          facecolor='#1a1a2e', edgecolor='#444466', labelcolor='white', framealpha=0.9)
scalebar(ax, x0, y0, bar_len=100)
ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
ax.set_xticks([]); ax.set_yticks([])
for spine in ax.spines.values():
    spine.set_visible(False)
plt.tight_layout()
fig.savefig('close up errors.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print('Saved close up errors.png')

# ============================================================
# GRAPHIC 3: Orphans with no terrain signature (slide 14)
# ============================================================
orphans = wells_clip[wells_clip['WELL_STATU'] == 'DEP Orphan List']
lonely = []
for _, orph in orphans.iterrows():
    if len(ann_clip) > 0:
        d = ann_clip.geometry.distance(orph.geometry).min()
        if d > 50:
            lonely.append(orph)

# If not enough orphans, also use abandoned wells far from annotations
if len(lonely) < 3:
    abandoned = wells_clip[wells_clip['WELL_STATU'] == 'DEP Abandoned List']
    for _, ab in abandoned.iterrows():
        if len(ann_clip) > 0:
            d = ann_clip.geometry.distance(ab.geometry).min()
            if d > 50:
                lonely.append(ab)

print(f'Wells with no nearby annotation (>50m): {len(lonely)}')

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

    # All wells - single color, big
    if len(z_wells3) > 0:
        ax.scatter(z_wells3.geometry.x, z_wells3.geometry.y,
                   c='#FF6644', s=100, marker='o',
                   edgecolors='white', linewidths=0.8, zorder=3)

    # Lonely orphans highlighted with large dashed circles
    for _, orph in z_lonely.iterrows():
        circle = plt.Circle((orph.geometry.x, orph.geometry.y), 40,
                           fill=False, edgecolor='#FFFF00', linewidth=2.5, linestyle='--', zorder=5)
        ax.add_patch(circle)

    elems = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#FF6644',
               markersize=10, label=f'DEP Well Records ({len(z_wells3)})', linestyle='None'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='none',
               markeredgecolor='#FFFF00', markersize=12, markeredgewidth=2,
               label=f'No Pit Visible ({len(z_lonely)})', linestyle='None'),
    ]
    leg = ax.legend(handles=elems, loc='upper right', fontsize=13,
              facecolor='#1a1a2e', edgecolor='#444466', labelcolor='white', framealpha=0.9)
    scalebar(ax, x0, y0, bar_len=100)
    ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    plt.tight_layout()
    fig.savefig('orphaned with no clear wells.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print('Saved orphaned with no clear wells.png')

# ============================================================
# GRAPHIC 4: Future Work - rim polygons with BIGGER polygons
# ============================================================
# Regenerate from morphology data
morph = gpd.read_file(f'{DERIV}/pit_1m_morphology_audit.gpkg').to_crs(hs_ds.crs)

# Use full tile hillshade, zoom to a good area with many pits
zone_size4 = 500
best4 = (0, 0, 0)
for x0 in np.arange(bounds.left, bounds.right - zone_size4, 50):
    for y0 in np.arange(bounds.bottom, bounds.top - zone_size4, 50):
        zb = box(x0, y0, x0 + zone_size4, y0 + zone_size4)
        n = ann_clip[ann_clip.within(zb)].shape[0]
        if n > best4[0]:
            best4 = (n, x0, y0)

_, x0, y0 = best4
zb = box(x0, y0, x0 + zone_size4, y0 + zone_size4)
z_ann4 = ann_clip[ann_clip.within(zb)]
z_morph4 = morph[morph.within(zb)]

fig, ax = plt.subplots(figsize=(10, 8))
fig.patch.set_facecolor('#1a1a2e')
chunk, x0_, y0_, x1_, y1_ = get_window(x0, y0, zone_size4)
ax.imshow(chunk, cmap='gray', vmin=vmin, vmax=vmax, extent=[x0_, x1_, y0_, y1_], origin='upper')

# Draw rim polygons as large cyan circles based on diameter
for _, pit in z_morph4.iterrows():
    radius = pit['diameter_m'] / 2 if 'diameter_m' in pit.index else 6.0
    circle = plt.Circle((pit.geometry.x, pit.geometry.y), radius,
                        fill=False, edgecolor='#00DDFF', linewidth=2.5, zorder=4)
    ax.add_patch(circle)

# Center points
if len(z_morph4) > 0:
    ax.scatter(z_morph4.geometry.x, z_morph4.geometry.y,
               c='#FF4444', s=40, marker='+', linewidths=2, zorder=5)

elems = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor='none',
           markeredgecolor='#00DDFF', markersize=12, markeredgewidth=2,
           label=f'Computed Rim Boundary ({len(z_morph4)})', linestyle='None'),
    Line2D([0], [0], marker='+', color='#FF4444',
           markersize=10, markeredgewidth=2,
           label='Annotated Center', linestyle='None'),
]
leg = ax.legend(handles=elems, loc='upper right', fontsize=13,
          facecolor='#1a1a2e', edgecolor='#444466', labelcolor='white', framealpha=0.9)
scalebar(ax, x0, y0, bar_len=100)
ax.set_xlim(x0_, x1_); ax.set_ylim(y0_, y1_)
ax.set_xticks([]); ax.set_yticks([])
for spine in ax.spines.values():
    spine.set_visible(False)
plt.tight_layout()
fig.savefig('future_work_rims.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print('Saved future_work_rims.png')

print('\nAll graphics regenerated.')

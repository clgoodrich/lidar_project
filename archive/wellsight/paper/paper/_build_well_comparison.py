import geopandas as gpd
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

hs_path = 'data/derivatives/hillshade_9t_1m.tif'
with rasterio.open(hs_path) as src:
    hs = src.read(1)
    bounds = src.bounds
    hs_crs = src.crs
    hs_transform = src.transform
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

hs_min, hs_max = np.percentile(hs[hs > 0], [2, 98])
print(f"Hillshade value range: {hs.min()}-{hs.max()}, display range: {hs_min:.0f}-{hs_max:.0f}")
print(f"Hillshade bounds: {bounds}")
print(f"Hillshade shape: {hs.shape}")

wells = gpd.read_file('data/derivatives/venango_wells_all.gpkg')

tile_box = box(bounds.left - 50, bounds.bottom - 50, bounds.right + 50, bounds.top + 50)
wells_in_tile = wells[wells.geometry.within(tile_box)].copy()
print(f"Wells within LiDAR tile: {len(wells_in_tile)}")
print("Status breakdown:")
print(wells_in_tile['WELL_STATU'].value_counts().to_string())

wells_in_tile.to_file('data/derivatives/wells_in_tile_enriched.gpkg', driver='GPKG')
print(f"\nSaved enriched wells to wells_in_tile_enriched.gpkg")

status_config = {
    'Active':                        {'color': '#2196F3', 'marker': 'o', 'size': 30, 'zorder': 5},
    'Plugged OG Well':               {'color': '#4CAF50', 'marker': 's', 'size': 30, 'zorder': 4},
    'DEP Orphan List':               {'color': '#FF5722', 'marker': '*', 'size': 60, 'zorder': 7},
    'DEP Abandoned List':            {'color': '#FF9800', 'marker': 'D', 'size': 30, 'zorder': 6},
    'DEP Plugged':                   {'color': '#8BC34A', 'marker': 'v', 'size': 25, 'zorder': 3},
    'Operator Reported Not Drilled': {'color': '#9E9E9E', 'marker': 'x', 'size': 20, 'zorder': 2},
}

# --- Figure 1: All wells by status ---
fig, ax = plt.subplots(1, 1, figsize=(14, 14))
ax.imshow(hs, cmap='gray', extent=extent, vmin=hs_min, vmax=hs_max, origin='upper')

legend_handles = []
for status, cfg in status_config.items():
    subset = wells_in_tile[wells_in_tile['WELL_STATU'] == status]
    if len(subset) > 0:
        ax.scatter(subset.geometry.x, subset.geometry.y,
                   c=cfg['color'], marker=cfg['marker'], s=cfg['size'],
                   edgecolors='black', linewidths=0.3, zorder=cfg['zorder'],
                   alpha=0.85)
        legend_handles.append(mpatches.Patch(color=cfg['color'], label=f"{status} ({len(subset)})"))

other = wells_in_tile[~wells_in_tile['WELL_STATU'].isin(status_config.keys())]
if len(other) > 0:
    ax.scatter(other.geometry.x, other.geometry.y, c='white', marker='.', s=15,
               edgecolors='black', linewidths=0.3, zorder=1, alpha=0.7)
    legend_handles.append(mpatches.Patch(color='white', label=f"Other ({len(other)})"))

ax.legend(handles=legend_handles, loc='upper right', fontsize=9, framealpha=0.9)
ax.set_title(f"All Well Locations by Status on LiDAR Hillshade\n{len(wells_in_tile)} wells in tile", fontsize=13)
ax.set_xlabel('Easting (m)')
ax.set_ylabel('Northing (m)')

bar_len = 500
bar_x = bounds.left + 100
bar_y = bounds.bottom + 100
ax.plot([bar_x, bar_x + bar_len], [bar_y, bar_y], 'k-', linewidth=3)
ax.text(bar_x + bar_len/2, bar_y + 30, f'{bar_len} m', ha='center', fontsize=9, fontweight='bold')

plt.tight_layout()
fig.savefig('data/derivatives/wells_by_status_hillshade.png', dpi=200, bbox_inches='tight')
print("Saved: wells_by_status_hillshade.png")
plt.close()

# --- Figure 2: Side-by-side zoom panels ---
# Only use wells that are INSIDE the raster bounds
inside_mask = (
    (wells_in_tile.geometry.x >= bounds.left + 200) &
    (wells_in_tile.geometry.x <= bounds.right - 200) &
    (wells_in_tile.geometry.y >= bounds.bottom + 200) &
    (wells_in_tile.geometry.y <= bounds.top - 200)
)
wells_inside = wells_in_tile[inside_mask].copy()
print(f"\nWells fully inside raster (with 200m buffer): {len(wells_inside)}")

orphans = wells_inside[wells_inside['WELL_STATU'] == 'DEP Orphan List']
actives = wells_inside[wells_inside['WELL_STATU'] == 'Active']
plugged = wells_inside[wells_inside['WELL_STATU'] == 'Plugged OG Well']
abandoned = wells_inside[wells_inside['WELL_STATU'] == 'DEP Abandoned List']

print(f"  Orphans inside: {len(orphans)}")
print(f"  Active inside: {len(actives)}")
print(f"  Plugged inside: {len(plugged)}")
print(f"  Abandoned inside: {len(abandoned)}")

cx, cy = (bounds.left + bounds.right) / 2, (bounds.bottom + bounds.top) / 2

def pick_spread(gdf, n=2):
    """Pick wells spread across the tile, not just nearest to center."""
    if len(gdf) <= n:
        return gdf
    dists = gdf.geometry.apply(lambda g: ((g.x - cx)**2 + (g.y - cy)**2)**0.5)
    sorted_idx = dists.sort_values().index
    step = max(1, len(sorted_idx) // n)
    picks = [sorted_idx[i * step] for i in range(n)]
    return gdf.loc[picks]

zoom_radius = 150

categories = [
    ('DEP Orphan List', orphans, '#FF5722'),
    ('Active', actives, '#2196F3'),
    ('Plugged OG Well', plugged, '#4CAF50'),
    ('DEP Abandoned List', abandoned, '#FF9800'),
]

fig, axes = plt.subplots(2, 4, figsize=(22, 11))

for col_idx, (status, subset, color) in enumerate(categories):
    if len(subset) < 1:
        for row in range(2):
            axes[row, col_idx].set_visible(False)
        continue

    examples = pick_spread(subset, n=2)

    for row, (idx, well) in enumerate(examples.iterrows()):
        if row >= 2:
            break
        ax = axes[row, col_idx]
        wx, wy = well.geometry.x, well.geometry.y

        # Use rasterio transform for precise pixel mapping
        col_px, row_px = ~hs_transform * (wx, wy)
        col_px, row_px = int(col_px), int(row_px)
        half = zoom_radius  # 1m pixels, so 150 pixels = 150m

        r_min = max(0, row_px - half)
        r_max = min(hs.shape[0], row_px + half)
        c_min = max(0, col_px - half)
        c_max = min(hs.shape[1], col_px + half)

        crop = hs[r_min:r_max, c_min:c_max]

        # Convert pixel bounds back to map coords
        left = bounds.left + c_min
        right = bounds.left + c_max
        top = bounds.top - r_min
        bottom = bounds.top - r_max
        crop_extent = [left, right, bottom, top]

        print(f"  {status} row={row}: well=({wx:.0f},{wy:.0f}) px=({col_px},{row_px}) crop={crop.shape} "
              f"extent=[{left:.0f},{right:.0f},{bottom:.0f},{top:.0f}]")

        ax.imshow(crop, cmap='gray', extent=crop_extent, vmin=hs_min, vmax=hs_max, origin='upper')
        ax.plot(wx, wy, marker='o', markersize=14, markerfacecolor='none',
                markeredgecolor=color, markeredgewidth=2.5, zorder=10)
        ax.plot(wx, wy, marker='+', markersize=10, color=color, markeredgewidth=2, zorder=10)

        spud = str(well.get('SPUD_DATE', ''))[:10]
        name = str(well.get('WELL_NAME', ''))[:22]
        wtype = str(well.get('WELL_TYPE', ''))
        operator = str(well.get('OPERATOR', ''))[:28]

        title = f"{status}\n{name} ({wtype})\nSPUD: {spud} | Op: {operator}"
        ax.set_title(title, fontsize=8, color=color, fontweight='bold')
        ax.set_xticks([])
        ax.set_yticks([])

        sb_x = crop_extent[0] + 10
        sb_y = crop_extent[2] + 15
        ax.plot([sb_x, sb_x + 50], [sb_y, sb_y], 'w-', linewidth=2.5)
        ax.text(sb_x + 25, sb_y + 8, '50m', ha='center', fontsize=7, color='white', fontweight='bold')

    if len(examples) < 2:
        axes[1, col_idx].set_visible(False)

fig.suptitle('Well Status Comparison on LiDAR Hillshade (300m zoom windows)',
             fontsize=14, fontweight='bold')
plt.tight_layout()
fig.savefig('data/derivatives/well_status_comparison_zoom.png', dpi=200, bbox_inches='tight')
print("\nSaved: well_status_comparison_zoom.png")
plt.close()

# Print orphan well details
print("\n=== All orphan wells in tile ===")
for _, w in orphans.iterrows():
    print(f"  {str(w['WELL_NAME']):25s} | SPUD: {str(w['SPUD_DATE'])[:10]:12s} | "
          f"Type: {str(w['WELL_TYPE']):12s} | Op: {str(w['OPERATOR'])[:30]} | "
          f"Lat: {w['LATITUDE']:.6f} Lon: {w['LONGITUDE']:.6f}")

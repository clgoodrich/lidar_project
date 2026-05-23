"""Generate all figures for the WellSight paper."""
import numpy as np, rasterio, geopandas as gpd, pandas as pd, matplotlib.pyplot as plt
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from matplotlib.patches import FancyBboxPatch

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'

# ---- Figure 1: Pit morphology box plots ----
df = pd.read_csv(DERIV / 'pit_1m_morphology_audit.csv')
fig, axes = plt.subplots(2, 3, figsize=(12, 7))
params = [
    ('depth_from_rim_mean_m', 'Depth from Rim (m)'),
    ('depth_from_rim_max_m', 'Max Depth (m)'),
    ('rim_radius_m', 'Rim Radius (m)'),
    ('diameter_m', 'Diameter (m)'),
    ('aspect_ratio', 'Aspect Ratio'),
    ('volume_approx_m3', 'Volume (m\u00b3)'),
]
for ax, (col, label) in zip(axes.flat, params):
    data = df[col].dropna()
    bp = ax.boxplot(data, vert=True, patch_artist=True, widths=0.5)
    bp['boxes'][0].set_facecolor('#4C72B0')
    bp['boxes'][0].set_alpha(0.7)
    ax.set_ylabel(label)
    ax.set_xticks([])
    ax.grid(alpha=0.3, axis='y')
    ax.set_title(f'n={len(data)}, \u03bc={data.mean():.2f}, \u03c3={data.std():.2f}', fontsize=9)
fig.suptitle('Pit Morphology Parameter Distributions (n=856 annotated pits)', fontsize=12, y=0.98)
fig.tight_layout()
fig.savefig(DERIV / 'paper_fig_morphology_boxplots.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 1: paper_fig_morphology_boxplots.png')

# ---- Figure 2: PCA anomaly scatter ----
feat_cols = ['depth_from_rim_mean_m', 'depth_from_rim_max_m', 'rim_radius_m',
             'effective_radius_m', 'diameter_m', 'aspect_ratio',
             'rim_symmetry_std_m', 'volume_approx_m3', 'lrm5_depth_m', 'lrm11_depth_m',
             'slope_inner_deg']
X = df[feat_cols].fillna(df[feat_cols].median())
X_scaled = StandardScaler().fit_transform(X)
pca = PCA()
scores = pca.fit_transform(X_scaled)

fig, ax = plt.subplots(figsize=(9, 7))
sc = ax.scatter(scores[:, 0], scores[:, 1], c=df['mahalanobis'], cmap='YlOrRd',
                s=15, alpha=0.7, edgecolors='none')
ax.set_xlabel(f'PC1 - Depth/Volume ({pca.explained_variance_ratio_[0]:.0%} variance)')
ax.set_ylabel(f'PC2 - Size vs Slope ({pca.explained_variance_ratio_[1]:.0%} variance)')
ax.set_title('Principal Component Analysis of Pit Morphology\n(color = Mahalanobis anomaly score)')
plt.colorbar(sc, ax=ax, label='Mahalanobis Distance', shrink=0.8)
ax.grid(alpha=0.2)
top5 = df.nlargest(5, 'mahalanobis')
for _, row in top5.iterrows():
    idx = df.index.get_loc(row.name)
    ax.annotate(f'FID {int(row["original_index"])}',
                xy=(scores[idx, 0], scores[idx, 1]),
                fontsize=7, color='red', ha='left')
fig.tight_layout()
fig.savefig(DERIV / 'paper_fig_pca_anomaly.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 2: paper_fig_pca_anomaly.png')

# ---- Figure 3: Hillshade with pit polygons ----
hs_path = DERIV / 'hillshade_9t_1m.tif'
with rasterio.open(hs_path) as ds:
    hs = ds.read(1).astype(np.float32)
    hs_bounds = ds.bounds

polys = gpd.read_file(DERIV / 'pit_1m_polygons.gpkg')
polys_9t = polys[polys['tile'] == '9t']
pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)

cx, cy = 621700, 4595200
hw = 250
extent = [cx-hw, cx+hw, cy-hw, cy+hw]

fig, ax = plt.subplots(figsize=(10, 10))
r1 = int((hs_bounds.top - (cy+hw)) / 1.0)
r2 = int((hs_bounds.top - (cy-hw)) / 1.0)
c1 = int(((cx-hw) - hs_bounds.left) / 1.0)
c2 = int(((cx+hw) - hs_bounds.left) / 1.0)
ax.imshow(hs[r1:r2, c1:c2], cmap='gray', extent=extent, origin='upper')

polys_clip = polys_9t.cx[cx-hw:cx+hw, cy-hw:cy+hw]
for _, row in polys_clip.iterrows():
    xs, ys = row.geometry.exterior.xy
    ax.plot(xs, ys, color='cyan', linewidth=1.5, alpha=0.9)
    ax.fill(xs, ys, color='cyan', alpha=0.15)

pits_clip = pits.cx[cx-hw:cx+hw, cy-hw:cy+hw]
ax.scatter(pits_clip.geometry.x, pits_clip.geometry.y, marker='+', c='red',
           s=60, linewidths=1.5, zorder=5)

ax.set_xlim(cx-hw, cx+hw)
ax.set_ylim(cy-hw, cy+hw)
ax.set_xlabel('Easting (m)')
ax.set_ylabel('Northing (m)')
ax.set_title('LiDAR Hillshade with Computed Pit Rim Polygons\n(cyan = rim boundary, red + = annotated center)')
fig.tight_layout()
fig.savefig(DERIV / 'paper_fig_hillshade_polygons.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 3: paper_fig_hillshade_polygons.png')

# ---- Figure 4: Spoke quality ----
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
axes[0].hist(polys['pct_normal'], bins=20, color='#4C72B0', alpha=0.7,
             edgecolor='black', linewidth=0.5)
axes[0].axvline(0.75, color='red', linestyle='--', label='75% threshold')
axes[0].set_xlabel('Fraction of Normal Spokes')
axes[0].set_ylabel('Count')
axes[0].set_title('Spoke Quality Distribution')
axes[0].legend()
axes[0].grid(alpha=0.3)

sc = axes[1].scatter(polys['pct_truncated'], polys['circularity'],
                     c=polys['depth_m'], cmap='viridis', s=12, alpha=0.6)
axes[1].set_xlabel('Fraction Truncated Spokes')
axes[1].set_ylabel('Circularity')
axes[1].set_title('Circularity vs. Spoke Truncation (color=depth)')
plt.colorbar(sc, ax=axes[1], label='Depth (m)', shrink=0.8)
axes[1].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(DERIV / 'paper_fig_spoke_quality.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 4: paper_fig_spoke_quality.png')

# ---- Figure 5: Morphology summary table as image ----
stats = df[['depth_from_rim_mean_m', 'depth_from_rim_max_m', 'rim_radius_m',
            'diameter_m', 'aspect_ratio', 'rim_symmetry_std_m',
            'volume_approx_m3', 'slope_inner_deg']].describe().round(3)
stats = stats.loc[['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']]
stats.columns = ['Depth\n(rim mean)', 'Depth\n(rim max)', 'Rim\nRadius', 'Diameter',
                 'Aspect\nRatio', 'Rim Sym\nStd', 'Volume', 'Slope\n(inner)']

fig, ax = plt.subplots(figsize=(12, 3.5))
ax.axis('off')
table = ax.table(cellText=stats.values, colLabels=stats.columns,
                 rowLabels=stats.index, cellLoc='center', loc='center')
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.0, 1.4)
ax.set_title('Table 1: Pit Morphology Descriptive Statistics (n=856)', fontsize=11, pad=20)
fig.tight_layout()
fig.savefig(DERIV / 'paper_fig_morphology_table.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 5: paper_fig_morphology_table.png')

# ---- Figure 6: Radial profile concept diagram ----
fig, ax = plt.subplots(figsize=(8, 4))
r = np.linspace(0, 8, 100)
# Idealized pit profile
elev = 0.3 * (1 - np.exp(-0.5 * (r/3)**2)) + 0.5 * np.tanh((r - 4) / 1.5) * 0.5
elev = elev - elev[0]  # normalize bottom to 0
ax.plot(r, elev, 'b-', linewidth=2, label='Elevation profile')
ax.axhline(elev[-1], color='gray', linestyle=':', alpha=0.5, label='Surrounding terrain')
ax.axvline(4.5, color='red', linestyle='--', alpha=0.7, label='Rim (break in slope)')
ax.fill_between(r, 0, elev, alpha=0.1, color='blue')
ax.annotate('Pit Bottom', xy=(0.5, 0.02), fontsize=9, color='blue')
ax.annotate('Wall', xy=(2.5, 0.15), fontsize=9, color='blue')
ax.annotate('Rim', xy=(4.6, elev[56]+0.02), fontsize=9, color='red')
ax.annotate('Terrain', xy=(6.5, elev[-1]-0.03), fontsize=9, color='gray')
ax.set_xlabel('Distance from pit center (m)')
ax.set_ylabel('Relative elevation (m)')
ax.set_title('Idealized Radial Pit Profile\n(spoke-based rim detection finds the break in slope)')
ax.legend(loc='lower right')
ax.grid(alpha=0.3)
ax.set_xlim(0, 8)
ax.set_ylim(-0.05, max(elev) + 0.1)
fig.tight_layout()
fig.savefig(DERIV / 'paper_fig_radial_profile.png', dpi=150, bbox_inches='tight')
plt.close()
print('Fig 6: paper_fig_radial_profile.png')

print('\nAll paper figures generated.')

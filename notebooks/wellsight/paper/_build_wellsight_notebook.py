"""Generate the consolidated WellSight pipeline notebook with descriptive naming."""
import nbformat as nbf
from pathlib import Path

nb = nbf.v4.new_notebook()
nb.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}

def md(text): return nbf.v4.new_markdown_cell(text)
def code(text): return nbf.v4.new_code_cell(text)

cells = []

cells.append(md("""# WellSight: Pit Detection and Morphological Characterization Pipeline

**Full pipeline from terrain derivatives through morphological analysis.**

**Stages:**
1. Setup and tile discovery
2. Template learning and candidate generation (normalized cross-correlation)
3. Feature extraction (48 terrain-derived features)
4. Ensemble classification (XGBoost + LightGBM + HistGradientBoosting)
5. Morphological measurement (depth, radius, diameter, volume, etc.)
6. Anomaly detection and PCA
7. Paper figures
"""))

# ============================================================
cells.append(md("""## 1. Setup

We start by loading all the libraries we need. The main ones are:
- **numpy** for math on arrays (grids of numbers, like our raster images)
- **rasterio** for reading/writing GeoTIFF raster files (the terrain maps)
- **geopandas** for working with geographic vector data (points, polygons on a map)
- **scikit-learn**, **xgboost**, **lightgbm** for the machine learning models that classify pit candidates

We also define constants that control the pipeline: how big our analysis window is,
what counts as the "inner" ring (pit bottom) vs the "rim" ring (surrounding terrain), etc.
"""))
cells.append(code("""import numpy as np, rasterio, geopandas as gpd, pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from shapely.geometry import Point
from shapely import make_valid
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from scipy.spatial.distance import mahalanobis
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA as PrincipalComponentAnalysis
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.isotonic import IsotonicRegression
from sklearn.preprocessing import StandardScaler
from skimage.feature import match_template, peak_local_max
import xgboost as xgb
import lightgbm as lgb
import glob, warnings
warnings.filterwarnings('ignore')

DERIVATIVES_DIR = Path('data/derivatives')
ANNOTATIONS_DIR = Path('data/derivatives/annotations')
COORDINATE_REFERENCE_SYSTEM = 'EPSG:6346'
CELL_RESOLUTION_METERS = 1.0
POSITIVE_MATCH_DISTANCE_METERS = 10.0
HALF_WINDOW_CELLS = 8
INNER_RING_RADIUS_CELLS = 3
OUTER_RING_START_CELLS = 6
SNAP_SEARCH_RADIUS_CELLS = 3
MINIMUM_PEAK_DISTANCE_CELLS = 5

print('Setup complete.')
"""))

# ============================================================
cells.append(md("""## 2. Tile Discovery

The LiDAR data is split into geographic tiles (like puzzle pieces covering the landscape).
Each tile has a DEM and a set of terrain derivative rasters (slope, roughness, etc.).
This cell scans the derivatives folder to find which tiles have ALL the rasters we need.
If a tile is missing any required layer, we skip it.

We also load the expert annotations — the 861 pit locations that were hand-picked in QGIS
by looking at hillshade images and identifying circular depressions.
"""))
cells.append(code("""available_tiles_dict = {}
for dem_filepath in sorted(glob.glob(str(DERIVATIVES_DIR / 'dem_*_1m.tif'))):
    filepath = Path(dem_filepath)
    file_suffix = filepath.name.replace('dem', '')
    tile_tag = file_suffix.replace('_1m.tif', '').strip('_')
    required_prefixes_lst = ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg', 'slope', 'hillshade',
                             'lrm_25', 'tpi_15', 'chm', 'ground_density', 'roughness_5',
                             'local_relief_10', 'openness_pos']
    if all((DERIVATIVES_DIR / f'{prefix}{file_suffix}').exists() for prefix in required_prefixes_lst):
        available_tiles_dict[tile_tag] = file_suffix

print(f'Tiles with full derivative stacks: {list(available_tiles_dict.keys())}')

annotated_pits_geodataframe = gpd.read_file(ANNOTATIONS_DIR / 'wellhead_pits.gpkg').to_crs(COORDINATE_REFERENCE_SYSTEM)
print(f'Total annotated pits: {len(annotated_pits_geodataframe)}')
"""))

# ============================================================
cells.append(md("""## 3. Helper Functions

These are utility functions used throughout the rest of the pipeline. Think of them
as reusable tools:

- **read_raster_tile_as_array**: Opens a terrain raster file and gives us back a grid of numbers.
- **get_tile_bounds_and_shape**: Tells us the geographic extent and pixel size of a tile.
- **compute_inner_rim_statistics**: Compares the center of a pit (inner ring) to its edges (rim ring).
  This is the core measurement — a real pit has a center that's lower than its rim.
- **compute_radial_symmetry_standard_deviation**: Checks if the pit is circular. It samples
  elevation at 8 evenly-spaced compass points around the rim. If they're all the same height,
  it's a perfect circle. If they vary a lot, the pit is lopsided.
- **compute_morphological_features_from_local_relief_model**: Extracts shape descriptors
  from the Local Relief Model. It measures how deep the center is, how the depth changes
  as you move outward (radial profile), and how concentrated the depression is.

We also pre-compute the **ring masks** — these are like cookie cutters that tell us which
pixels belong to the "inner ring" (pit bottom zone) and which belong to the "rim ring"
(surrounding terrain zone).
"""))
cells.append(code("""def read_raster_tile_as_array(tile_suffix, raster_prefix):
    \"\"\"Open a terrain raster file (like a DEM or slope map) and return it as a grid of numbers.
    Any missing-data pixels get turned into NaN so they don't mess up our math later.\"\"\"
    raster_path = DERIVATIVES_DIR / f'{raster_prefix}{tile_suffix}'
    with rasterio.open(raster_path) as dataset:
        elevation_arr = dataset.read(1).astype(np.float32)
        nodata_value = dataset.nodata
        if nodata_value is not None:
            elevation_arr = np.where(elevation_arr == nodata_value, np.nan, elevation_arr)
        return elevation_arr


def get_tile_bounds_and_shape(tile_suffix):
    \"\"\"Look up a tile's DEM file and return its geographic extent (where it is on the map)
    and its pixel dimensions (how many rows and columns the grid has).\"\"\"
    dem_path = DERIVATIVES_DIR / f'dem{tile_suffix}'
    with rasterio.open(dem_path) as dataset:
        return dataset.bounds, dataset.shape


def compute_inner_rim_statistics(window_arr, inner_ring_mask, rim_ring_mask):
    \"\"\"Compare the pit bottom (inner ring) to the surrounding terrain (rim ring).
    A real pit has an inner zone that's lower than the rim. This function measures
    how much lower, plus the spread of values in each zone.
    Returns: (inner_minimum, inner_mean, rim_mean, rim_minus_inner_contrast, inner_std_dev)\"\"\"
    inner_values = window_arr[inner_ring_mask]
    rim_values = window_arr[rim_ring_mask]
    if np.isfinite(inner_values).any() and np.isfinite(rim_values).any():
        inner_minimum = np.nanmin(inner_values)
        inner_mean = np.nanmean(inner_values)
        rim_mean = np.nanmean(rim_values)
        rim_minus_inner_contrast = rim_mean - inner_minimum
        inner_standard_deviation = np.nanstd(inner_values)
        return inner_minimum, inner_mean, rim_mean, rim_minus_inner_contrast, inner_standard_deviation
    return (np.nan,) * 5


def compute_radial_symmetry_standard_deviation(window_arr):
    \"\"\"Check how circular a pit is by sampling elevation at 8 compass points around its rim.
    If all 8 readings are similar, the pit is nicely round (low std dev).
    If they vary a lot, the pit is lopsided or has one side eroded away (high std dev).\"\"\"
    angle_samples_arr = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    sampled_elevations_lst = []
    for angle_radians in angle_samples_arr:
        sample_row = int(round(HALF_WINDOW_CELLS + INNER_RING_RADIUS_CELLS * np.sin(angle_radians)))
        sample_col = int(round(HALF_WINDOW_CELLS + INNER_RING_RADIUS_CELLS * np.cos(angle_radians)))
        if 0 <= sample_row < window_arr.shape[0] and 0 <= sample_col < window_arr.shape[1]:
            sample_value = window_arr[sample_row, sample_col]
            if np.isfinite(sample_value):
                sampled_elevations_lst.append(sample_value)
    return float(np.std(sampled_elevations_lst)) if len(sampled_elevations_lst) >= 4 else np.nan


def compute_morphological_features_from_local_relief_model(local_relief_model_window_arr):
    \"\"\"Describe the shape of a pit using the Local Relief Model (LRM) — a raster that
    shows how much each cell deviates from its local average elevation.
    We measure: how deep the center is, the average depth at three distance bands
    (close/medium/far), whether depth increases smoothly outward (monotonicity),
    and how concentrated the depression is in the center vs spread out (compactness).\"\"\"
    features_dict = {}
    center_value = local_relief_model_window_arr[HALF_WINDOW_CELLS, HALF_WINDOW_CELLS]
    features_dict['morph_center_depth'] = float(center_value) if np.isfinite(center_value) else np.nan

    for ring_inner_radius, ring_outer_radius, ring_label in [(0, 2, 'r0_2'), (2, 5, 'r2_5'), (5, 8, 'r5_8')]:
        ring_mask = (radial_distance_from_center_arr >= ring_inner_radius) & (radial_distance_from_center_arr < ring_outer_radius)
        ring_values = local_relief_model_window_arr[ring_mask]
        features_dict[f'morph_ring_{ring_label}'] = float(np.nanmean(ring_values)) if np.isfinite(ring_values).any() else np.nan

    ring_mean_values_lst = []
    for radius_cells in range(1, HALF_WINDOW_CELLS + 1):
        annular_ring_mask = (radial_distance_from_center_arr >= radius_cells - 0.5) & (radial_distance_from_center_arr < radius_cells + 0.5)
        annular_values = local_relief_model_window_arr[annular_ring_mask]
        if np.isfinite(annular_values).any():
            ring_mean_values_lst.append(np.nanmean(annular_values))

    if len(ring_mean_values_lst) >= 4:
        spearman_correlation, _ = spearmanr(range(len(ring_mean_values_lst)), ring_mean_values_lst)
        features_dict['morph_radial_monotonicity'] = float(spearman_correlation)
    else:
        features_dict['morph_radial_monotonicity'] = np.nan

    inner_absolute_sum = np.nansum(np.abs(local_relief_model_window_arr[inner_ring_boolean_mask]))
    total_absolute_sum = np.nansum(np.abs(local_relief_model_window_arr))
    features_dict['morph_compactness'] = float(inner_absolute_sum / total_absolute_sum) if total_absolute_sum > 0 else np.nan
    return features_dict


# Pre-compute ring masks
row_offsets_arr, col_offsets_arr = np.ogrid[-HALF_WINDOW_CELLS:HALF_WINDOW_CELLS+1, -HALF_WINDOW_CELLS:HALF_WINDOW_CELLS+1]
radial_distance_from_center_arr = np.sqrt(col_offsets_arr**2 + row_offsets_arr**2)
inner_ring_boolean_mask = radial_distance_from_center_arr <= INNER_RING_RADIUS_CELLS
rim_ring_boolean_mask = (radial_distance_from_center_arr >= OUTER_RING_START_CELLS) & (radial_distance_from_center_arr <= HALF_WINDOW_CELLS)

TEMPLATE_CHANNEL_NAMES_LST = ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg', 'hillshade']
DEPTH_CHANNEL_NAMES_LST = ['lrm_5', 'lrm_11', 'lrm_25', 'tpi_05', 'tpi_15', 'openness_neg']
SURFACE_CHANNEL_NAMES_LST = ['slope', 'roughness_5', 'local_relief_10', 'chm']
FULL_WINDOW_SIZE_CELLS = 2 * HALF_WINDOW_CELLS + 1

print(f'Window size: {FULL_WINDOW_SIZE_CELLS}x{FULL_WINDOW_SIZE_CELLS} cells ({FULL_WINDOW_SIZE_CELLS * CELL_RESOLUTION_METERS:.0f} m)')
print(f'Inner ring: r <= {INNER_RING_RADIUS_CELLS} cells ({INNER_RING_RADIUS_CELLS * CELL_RESOLUTION_METERS:.0f} m)')
print(f'Rim ring: {OUTER_RING_START_CELLS} <= r <= {HALF_WINDOW_CELLS} cells ({OUTER_RING_START_CELLS * CELL_RESOLUTION_METERS:.0f}-{HALF_WINDOW_CELLS * CELL_RESOLUTION_METERS:.0f} m)')
"""))

# ============================================================
cells.append(md("""## 4. Template Learning

This is where we teach the pipeline what a pit looks like. For every annotated pit,
we cut out a small square window from each terrain raster (like cropping a photo).
We then "snap" the center to the deepest nearby point (in case our click was slightly off),
subtract the average value so all pits are on the same scale regardless of absolute elevation,
and stack all 861 cutouts together. The **median** across all of them gives us the
"average pit" — the canonical template.

We also cluster the cutouts into 3 groups using PCA + KMeans, because not all pits look
the same. Some are symmetric bowls, some are lopsided, some have a raised rim on one side.
Having 3 templates instead of 1 helps us find a wider variety of pits."""))

cells.append(code("""per_channel_cutouts_dict = {channel: [] for channel in TEMPLATE_CHANNEL_NAMES_LST}
snapped_cutout_count = 0

for tile_tag, tile_suffix in available_tiles_dict.items():
    tile_bounds, tile_shape = get_tile_bounds_and_shape(tile_suffix=tile_suffix)
    tile_height, tile_width = tile_shape
    tile_x_min, tile_y_min, tile_x_max, tile_y_max = tile_bounds.left, tile_bounds.bottom, tile_bounds.right, tile_bounds.top

    tile_pits_geodataframe = annotated_pits_geodataframe.cx[tile_x_min:tile_x_max, tile_y_min:tile_y_max]
    if len(tile_pits_geodataframe) == 0:
        continue

    local_relief_model_5m_arr = read_raster_tile_as_array(tile_suffix=tile_suffix, raster_prefix='lrm_5')
    channel_rasters_dict = {channel: read_raster_tile_as_array(tile_suffix=tile_suffix, raster_prefix=channel) for channel in TEMPLATE_CHANNEL_NAMES_LST}

    for _, pit_row in tile_pits_geodataframe.iterrows():
        pit_easting, pit_northing = pit_row.geometry.x, pit_row.geometry.y
        pixel_row = int(round((tile_y_max - pit_northing) / CELL_RESOLUTION_METERS))
        pixel_col = int(round((pit_easting - tile_x_min) / CELL_RESOLUTION_METERS))

        snap_row_start = max(0, pixel_row - SNAP_SEARCH_RADIUS_CELLS)
        snap_row_end = min(tile_height, pixel_row + SNAP_SEARCH_RADIUS_CELLS + 1)
        snap_col_start = max(0, pixel_col - SNAP_SEARCH_RADIUS_CELLS)
        snap_col_end = min(tile_width, pixel_col + SNAP_SEARCH_RADIUS_CELLS + 1)
        snap_window_arr = local_relief_model_5m_arr[snap_row_start:snap_row_end, snap_col_start:snap_col_end]

        if not np.isfinite(snap_window_arr).any():
            continue
        flat_minimum_index = np.nanargmin(snap_window_arr)
        minimum_row_offset, minimum_col_offset = divmod(flat_minimum_index, snap_window_arr.shape[1])
        snapped_row, snapped_col = snap_row_start + minimum_row_offset, snap_col_start + minimum_col_offset

        window_row_start = snapped_row - HALF_WINDOW_CELLS
        window_row_end = snapped_row + HALF_WINDOW_CELLS + 1
        window_col_start = snapped_col - HALF_WINDOW_CELLS
        window_col_end = snapped_col + HALF_WINDOW_CELLS + 1
        if window_row_start < 0 or window_col_start < 0 or window_row_end > tile_height or window_col_end > tile_width:
            continue

        cutout_is_valid = True
        for channel_name in TEMPLATE_CHANNEL_NAMES_LST:
            channel_window_arr = channel_rasters_dict[channel_name][window_row_start:window_row_end, window_col_start:window_col_end]
            if np.isnan(channel_window_arr).mean() > 0.2:
                cutout_is_valid = False
                break
            per_channel_cutouts_dict[channel_name].append(channel_window_arr - np.nanmean(channel_window_arr))

        if cutout_is_valid:
            snapped_cutout_count += 1

print(f'Snapped cutouts: {snapped_cutout_count}')

# Median templates per channel
median_templates_dict = {}
for channel_name in TEMPLATE_CHANNEL_NAMES_LST:
    stacked_cutouts_arr = np.stack(per_channel_cutouts_dict[channel_name], axis=0)
    median_templates_dict[channel_name] = np.nanmedian(stacked_cutouts_arr, axis=0)
    print(f'  {channel_name}: {stacked_cutouts_arr.shape[0]} cutouts -> template {median_templates_dict[channel_name].shape}')

# Sub-type clustering via PCA + KMeans
local_relief_model_cutouts_arr = np.stack(per_channel_cutouts_dict['lrm_5'], axis=0)
flattened_cutouts_arr = np.nan_to_num(local_relief_model_cutouts_arr.reshape(len(local_relief_model_cutouts_arr), -1), nan=0.0)
subtype_pca_model = PrincipalComponentAnalysis(n_components=5)
subtype_kmeans_model = KMeans(n_clusters=3, random_state=42, n_init=10)
cluster_labels_arr = subtype_kmeans_model.fit_predict(subtype_pca_model.fit_transform(flattened_cutouts_arr))
print(f'Sub-type cluster sizes: {np.bincount(cluster_labels_arr)}')

cluster_median_templates_dict = {}
for cluster_index in range(3):
    cluster_mask = cluster_labels_arr == cluster_index
    cluster_median_templates_dict[cluster_index] = {
        'lrm_5': np.nanmedian(local_relief_model_cutouts_arr[cluster_mask], axis=0)
    }
"""))

# ============================================================
cells.append(md("""## 5. Normalized Cross-Correlation Scanning and Candidate Generation

Now we slide our learned pit template across the entire landscape, like dragging a
stencil over the terrain and checking how well it matches at every location. This is
called **Normalized Cross-Correlation (NCC)** — it gives a score from -1 to +1 at each
pixel, where +1 means "this looks exactly like our template" and 0 means "no similarity."

We do this for multiple terrain channels (LRM, TPI, openness) and average the scores.
Then we find the peaks — locations where the match score is locally the highest — and
those become our **candidate pit locations**. This step casts a wide net on purpose:
it finds everything that even remotely resembles a pit. The ML model in the next step
will sort the real pits from the false alarms."""))
cells.append(code("""all_candidate_records_lst = []

for tile_tag, tile_suffix in available_tiles_dict.items():
    tile_bounds, tile_shape = get_tile_bounds_and_shape(tile_suffix=tile_suffix)
    tile_height, tile_width = tile_shape
    tile_x_min, tile_y_min, tile_x_max, tile_y_max = tile_bounds.left, tile_bounds.bottom, tile_bounds.right, tile_bounds.top

    per_channel_correlation_scores_dict = {}
    for channel_name in ['lrm_5', 'lrm_11', 'tpi_05', 'openness_neg']:
        raster_arr = np.nan_to_num(read_raster_tile_as_array(tile_suffix=tile_suffix, raster_prefix=channel_name), nan=0.0)
        template_arr = np.nan_to_num(median_templates_dict[channel_name].copy(), nan=0.0)
        if template_arr.std() < 1e-6:
            continue
        per_channel_correlation_scores_dict[channel_name] = match_template(raster_arr, template_arr, pad_input=True, mode='constant')

    if not per_channel_correlation_scores_dict:
        continue
    averaged_correlation_score_arr = np.nanmean(np.stack(list(per_channel_correlation_scores_dict.values()), axis=0), axis=0)

    # Save match score raster
    with rasterio.open(DERIVATIVES_DIR / f'dem{tile_suffix}') as reference_dataset:
        output_profile = reference_dataset.profile.copy()
    output_profile.update(dtype='float32', count=1, nodata=-9999)
    with rasterio.open(DERIVATIVES_DIR / f'pit_1m_match_score_{tile_tag}.tif', 'w', **output_profile) as output_dataset:
        output_dataset.write(averaged_correlation_score_arr.astype(np.float32), 1)

    # Determine threshold from annotated pit scores
    tile_pits_geodataframe = annotated_pits_geodataframe.cx[tile_x_min:tile_x_max, tile_y_min:tile_y_max]
    annotated_pit_scores_lst = []
    for _, pit_row in tile_pits_geodataframe.iterrows():
        pixel_row = int(round((tile_y_max - pit_row.geometry.y) / CELL_RESOLUTION_METERS))
        pixel_col = int(round((pit_row.geometry.x - tile_x_min) / CELL_RESOLUTION_METERS))
        if 0 <= pixel_row < tile_height and 0 <= pixel_col < tile_width:
            annotated_pit_scores_lst.append(averaged_correlation_score_arr[pixel_row, pixel_col])

    score_threshold = max(
        np.percentile(annotated_pit_scores_lst, 25) if annotated_pit_scores_lst
        else np.percentile(averaged_correlation_score_arr[np.isfinite(averaged_correlation_score_arr)], 95),
        0.05)

    cleaned_score_arr = np.nan_to_num(averaged_correlation_score_arr, nan=-1.0)
    peak_coordinates_arr = peak_local_max(cleaned_score_arr, min_distance=MINIMUM_PEAK_DISTANCE_CELLS,
                                          threshold_abs=score_threshold, exclude_border=HALF_WINDOW_CELLS)
    print(f'  {tile_tag}: threshold={score_threshold:.3f}, {len(peak_coordinates_arr)} peaks')

    for (peak_row, peak_col) in peak_coordinates_arr:
        candidate_easting = tile_x_min + (peak_col + 0.5) * CELL_RESOLUTION_METERS
        candidate_northing = tile_y_max - (peak_row + 0.5) * CELL_RESOLUTION_METERS
        all_candidate_records_lst.append({
            'easting': candidate_easting, 'northing': candidate_northing,
            'template_match_score': float(averaged_correlation_score_arr[peak_row, peak_col]),
            'tile': tile_tag})

candidates_df = pd.DataFrame(all_candidate_records_lst)
candidates_geodataframe = gpd.GeoDataFrame(
    candidates_df.drop(columns=['easting', 'northing']),
    geometry=[Point(east, north) for east, north in zip(candidates_df['easting'], candidates_df['northing'])],
    crs=COORDINATE_REFERENCE_SYSTEM)
candidates_geodataframe.to_file(DERIVATIVES_DIR / 'pit_1m_candidates_template.gpkg', driver='GPKG')
print(f'\\nTotal template candidates: {len(candidates_geodataframe)}')
"""))

# ============================================================
cells.append(md("""## 6. Feature Extraction

For each candidate location from the previous step, we now measure 48 different properties
of the terrain around it. These are the numbers that the machine learning model will use
to decide "is this a real pit or not?"

The features fall into a few groups:
- **Depth/contrast features (30):** For each of 6 terrain channels, we compare the inner ring
  (pit bottom) to the rim ring (surrounding terrain). A real pit is lower in the center.
- **Surface features (8):** Slope steepness, roughness, elevation range, and canopy height.
- **Density and match (4):** How many LiDAR points hit this area, and the template match score.
- **Morphology (6):** Shape descriptors — is it a clean bowl? Does depth increase smoothly outward?

We also **label** each candidate: if it's within 10 meters of an annotated pit, it's a positive
(real pit). Everything else is a negative. Finally, we assign spatial groups so that nearby
candidates end up in the same cross-validation fold — this prevents the model from "cheating"
by memorizing local terrain patterns."""))
cells.append(code("""print('Extracting features per tile...')
all_feature_records_lst = []
valid_candidate_indices_lst = []

for tile_tag, tile_suffix in available_tiles_dict.items():
    tile_bounds, tile_shape = get_tile_bounds_and_shape(tile_suffix=tile_suffix)
    tile_height, tile_width = tile_shape
    tile_x_min, tile_y_min, tile_x_max, tile_y_max = tile_bounds.left, tile_bounds.bottom, tile_bounds.right, tile_bounds.top

    tile_candidates_mask = candidates_geodataframe['tile'] == tile_tag
    tile_candidates_geodataframe = candidates_geodataframe[tile_candidates_mask]
    if len(tile_candidates_geodataframe) == 0:
        continue
    print(f'  {tile_tag}: {len(tile_candidates_geodataframe)} candidates...')

    tile_rasters_dict = {}
    for channel_name in DEPTH_CHANNEL_NAMES_LST + SURFACE_CHANNEL_NAMES_LST + ['ground_density', 'dem']:
        tile_rasters_dict[channel_name] = read_raster_tile_as_array(tile_suffix=tile_suffix, raster_prefix=channel_name)

    match_score_path = DERIVATIVES_DIR / f'pit_1m_match_score_{tile_tag}.tif'
    if match_score_path.exists():
        with rasterio.open(match_score_path) as dataset:
            tile_rasters_dict['match_score'] = dataset.read(1).astype(np.float32)
    else:
        tile_rasters_dict['match_score'] = np.zeros(tile_shape, dtype=np.float32)

    for candidate_index, candidate_row in tile_candidates_geodataframe.iterrows():
        candidate_easting, candidate_northing = candidate_row.geometry.x, candidate_row.geometry.y
        pixel_row = int(round((tile_y_max - candidate_northing) / CELL_RESOLUTION_METERS))
        pixel_col = int(round((candidate_easting - tile_x_min) / CELL_RESOLUTION_METERS))

        window_row_start = pixel_row - HALF_WINDOW_CELLS
        window_row_end = pixel_row + HALF_WINDOW_CELLS + 1
        window_col_start = pixel_col - HALF_WINDOW_CELLS
        window_col_end = pixel_col + HALF_WINDOW_CELLS + 1
        if window_row_start < 0 or window_col_start < 0 or window_row_end > tile_height or window_col_end > tile_width:
            continue

        feature_record = {}

        for channel_name in DEPTH_CHANNEL_NAMES_LST:
            channel_window_arr = tile_rasters_dict[channel_name][window_row_start:window_row_end, window_col_start:window_col_end]
            inner_min, inner_mean, rim_mean, rim_contrast, inner_std = compute_inner_rim_statistics(
                window_arr=channel_window_arr, inner_ring_mask=inner_ring_boolean_mask, rim_ring_mask=rim_ring_boolean_mask)
            feature_record[f'{channel_name}_inner_min'] = inner_min
            feature_record[f'{channel_name}_inner_mean'] = inner_mean
            feature_record[f'{channel_name}_rim_mean'] = rim_mean
            feature_record[f'{channel_name}_rim_minus'] = rim_contrast
            feature_record[f'{channel_name}_sym'] = compute_radial_symmetry_standard_deviation(window_arr=channel_window_arr)

        for channel_name in SURFACE_CHANNEL_NAMES_LST:
            channel_window_arr = tile_rasters_dict[channel_name][window_row_start:window_row_end, window_col_start:window_col_end]
            inner_values = channel_window_arr[inner_ring_boolean_mask]
            feature_record[f'{channel_name}_inner_mean'] = float(np.nanmean(inner_values)) if np.isfinite(inner_values).any() else np.nan
            feature_record[f'{channel_name}_window_max'] = float(np.nanmax(channel_window_arr)) if np.isfinite(channel_window_arr).any() else np.nan

        density_window_arr = tile_rasters_dict['ground_density'][window_row_start:window_row_end, window_col_start:window_col_end]
        feature_record['density_inner_mean'] = float(np.nanmean(density_window_arr[inner_ring_boolean_mask]))
        feature_record['density_window_mean'] = float(np.nanmean(density_window_arr))

        dem_window_arr = tile_rasters_dict['dem'][window_row_start:window_row_end, window_col_start:window_col_end]
        _, _, _, dem_cut_depth, _ = compute_inner_rim_statistics(
            window_arr=dem_window_arr, inner_ring_mask=inner_ring_boolean_mask, rim_ring_mask=rim_ring_boolean_mask)
        feature_record['dem_cut_m'] = dem_cut_depth
        feature_record['match_score_center'] = float(tile_rasters_dict['match_score'][pixel_row, pixel_col])

        local_relief_model_window_arr = tile_rasters_dict['lrm_5'][window_row_start:window_row_end, window_col_start:window_col_end]
        feature_record.update(compute_morphological_features_from_local_relief_model(
            local_relief_model_window_arr=local_relief_model_window_arr))

        all_feature_records_lst.append(feature_record)
        valid_candidate_indices_lst.append(candidate_index)

features_df = pd.DataFrame(all_feature_records_lst)
valid_candidates_geodataframe = candidates_geodataframe.loc[valid_candidate_indices_lst].reset_index(drop=True)
features_df = features_df.reset_index(drop=True)
print(f'Feature matrix: {features_df.shape}')

# Label candidates by proximity to annotated pits
annotated_pit_coordinates_arr = np.array([[geom.x, geom.y] for geom in annotated_pits_geodataframe.geometry])
pit_locations_kdtree = cKDTree(annotated_pit_coordinates_arr)
candidate_coordinates_arr = np.array([[geom.x, geom.y] for geom in valid_candidates_geodataframe.geometry])
nearest_pit_distances_arr, _ = pit_locations_kdtree.query(candidate_coordinates_arr, k=1)
positive_labels_arr = (nearest_pit_distances_arr <= POSITIVE_MATCH_DISTANCE_METERS).astype(np.int8)
valid_candidates_geodataframe['nearest_pit_m'] = nearest_pit_distances_arr
print(f'Positives: {positive_labels_arr.sum()} / {len(positive_labels_arr)} ({positive_labels_arr.mean():.2%})')

# Spatial groups for cross-validation
spatial_group_resolution_meters = 500
group_easting_indices = (candidate_coordinates_arr[:, 0] // spatial_group_resolution_meters).astype(int)
group_northing_indices = (candidate_coordinates_arr[:, 1] // spatial_group_resolution_meters).astype(int)
spatial_group_labels_arr = group_easting_indices * 10000 + group_northing_indices
"""))

# ============================================================
cells.append(md("""## 7. Ensemble Training (XGBoost + LightGBM + HistGradientBoosting)

We train three different machine learning models on the same data and average their
predictions. This is called an **ensemble** — it works better than any single model
because the three models make different kinds of mistakes, and averaging smooths those out.

**GroupKFold cross-validation** splits the data into 5 groups based on geography (500m grid
cells). Each fold trains on 4 groups and tests on the 1 held-out group. This way the model
never sees nearby candidates during training and testing at the same time, which would
inflate the scores unfairly.

After training, we apply **isotonic calibration** — this adjusts the raw probability scores
so that when the model says "80% confident," roughly 80% of those candidates really are pits."""))
cells.append(code("""feature_matrix_arr = features_df.fillna(0).to_numpy(dtype=np.float32)
feature_names_lst = list(features_df.columns)
number_of_cv_splits = 5
group_kfold_splitter = GroupKFold(n_splits=number_of_cv_splits)

out_of_fold_xgboost_probabilities_arr = np.zeros(len(positive_labels_arr), dtype=np.float64)
out_of_fold_lightgbm_probabilities_arr = np.zeros(len(positive_labels_arr), dtype=np.float64)
out_of_fold_histgb_probabilities_arr = np.zeros(len(positive_labels_arr), dtype=np.float64)

for fold_number, (training_indices, validation_indices) in enumerate(group_kfold_splitter.split(feature_matrix_arr, positive_labels_arr, spatial_group_labels_arr)):
    training_features_arr = feature_matrix_arr[training_indices]
    validation_features_arr = feature_matrix_arr[validation_indices]
    training_labels_arr = positive_labels_arr[training_indices]
    validation_labels_arr = positive_labels_arr[validation_indices]
    positive_weight_scale = (training_labels_arr == 0).sum() / max((training_labels_arr == 1).sum(), 1)

    # XGBoost
    xgboost_training_data = xgb.DMatrix(training_features_arr, label=training_labels_arr, feature_names=feature_names_lst)
    xgboost_validation_data = xgb.DMatrix(validation_features_arr, label=validation_labels_arr, feature_names=feature_names_lst)
    xgboost_parameters = dict(objective='binary:logistic', eval_metric='aucpr', tree_method='hist',
                              max_depth=5, eta=0.05, scale_pos_weight=positive_weight_scale,
                              subsample=0.8, colsample_bytree=0.8, verbosity=0)
    xgboost_model = xgb.train(xgboost_parameters, xgboost_training_data, num_boost_round=500,
                              evals=[(xgboost_validation_data, 'val')], early_stopping_rounds=50, verbose_eval=False)
    out_of_fold_xgboost_probabilities_arr[validation_indices] = xgboost_model.predict(xgboost_validation_data)

    # LightGBM
    lightgbm_training_data = lgb.Dataset(training_features_arr, label=training_labels_arr)
    lightgbm_parameters = dict(objective='binary', metric='average_precision', num_leaves=31,
                               learning_rate=0.05, scale_pos_weight=positive_weight_scale,
                               subsample=0.8, colsample_bytree=0.8, verbosity=-1)
    lightgbm_model = lgb.train(lightgbm_parameters, lightgbm_training_data, num_boost_round=500,
                               valid_sets=[lgb.Dataset(validation_features_arr, label=validation_labels_arr)],
                               callbacks=[lgb.early_stopping(50, verbose=False)])
    out_of_fold_lightgbm_probabilities_arr[validation_indices] = lightgbm_model.predict(validation_features_arr)

    # HistGradientBoosting
    histgb_classifier = HistGradientBoostingClassifier(max_depth=5, learning_rate=0.05, max_iter=500,
                                                       early_stopping=True, validation_fraction=0.15,
                                                       class_weight='balanced', random_state=42)
    histgb_classifier.fit(training_features_arr, training_labels_arr)
    out_of_fold_histgb_probabilities_arr[validation_indices] = histgb_classifier.predict_proba(validation_features_arr)[:, 1]

    print(f'  Fold {fold_number+1}: XGB={roc_auc_score(validation_labels_arr, out_of_fold_xgboost_probabilities_arr[validation_indices]):.4f}  '
          f'LGB={roc_auc_score(validation_labels_arr, out_of_fold_lightgbm_probabilities_arr[validation_indices]):.4f}  '
          f'HGB={roc_auc_score(validation_labels_arr, out_of_fold_histgb_probabilities_arr[validation_indices]):.4f}')

# Ensemble average + isotonic calibration
ensemble_average_probabilities_arr = (out_of_fold_xgboost_probabilities_arr + out_of_fold_lightgbm_probabilities_arr + out_of_fold_histgb_probabilities_arr) / 3.0
isotonic_calibrator = IsotonicRegression(out_of_bounds='clip')
isotonic_calibrator.fit(ensemble_average_probabilities_arr, positive_labels_arr)
calibrated_probabilities_arr = isotonic_calibrator.predict(ensemble_average_probabilities_arr)

print(f'\\nEnsemble OOF: ROC-AUC={roc_auc_score(positive_labels_arr, ensemble_average_probabilities_arr):.4f}  '
      f'PR-AUC={average_precision_score(positive_labels_arr, ensemble_average_probabilities_arr):.4f}')
"""))

# ============================================================
cells.append(md("""## 8. Save Ensemble Results

Save the ranked candidate list as a GeoPackage file that can be loaded directly in QGIS.
Each candidate has a calibrated probability score — higher means the model is more confident
it's a real pit. We also print a summary table showing how many pits we find at different
confidence thresholds, along with the precision (what fraction of candidates above that
threshold are actually real pits)."""))
cells.append(code("""valid_candidates_geodataframe['proba_raw'] = ensemble_average_probabilities_arr
valid_candidates_geodataframe['proba'] = calibrated_probabilities_arr
valid_candidates_geodataframe['is_hit_10m'] = (nearest_pit_distances_arr <= 10.0)
valid_candidates_geodataframe['is_hit_25m'] = (nearest_pit_distances_arr <= 25.0)
ranked_candidates_geodataframe = valid_candidates_geodataframe.sort_values('proba', ascending=False).reset_index(drop=True)
ranked_candidates_geodataframe.to_file(DERIVATIVES_DIR / 'pit_1m_candidates_ensemble.gpkg', driver='GPKG')
print(f'Wrote pit_1m_candidates_ensemble.gpkg ({len(ranked_candidates_geodataframe)} rows)')

print(f'\\n{\"thr\":>5} {\"n\":>7} {\"hits10\":>7} {\"pits_cov\":>9} {\"fp\":>7} {\"prec\":>7}')
for probability_threshold in [0.30, 0.40, 0.50, 0.70, 0.80, 0.90]:
    above_threshold_geodataframe = ranked_candidates_geodataframe[ranked_candidates_geodataframe['proba'] >= probability_threshold]
    if len(above_threshold_geodataframe) == 0:
        print(f'{probability_threshold:5.2f} {0:7d} {0:7d} {0:9d} {0:7d} {0:7.2%}'); continue
    threshold_coordinates_arr = np.c_[above_threshold_geodataframe.geometry.x, above_threshold_geodataframe.geometry.y]
    threshold_distances_arr, _ = pit_locations_kdtree.query(threshold_coordinates_arr, k=1)
    hits_within_10m_count = int((threshold_distances_arr <= 10).sum())
    _, matched_pit_indices = pit_locations_kdtree.query(threshold_coordinates_arr[threshold_distances_arr <= 10], k=1) if hits_within_10m_count else (None, np.array([]))
    distinct_pits_covered_count = len(np.unique(matched_pit_indices)) if hits_within_10m_count else 0
    false_positive_count = len(above_threshold_geodataframe) - hits_within_10m_count
    precision_value = hits_within_10m_count / max(len(above_threshold_geodataframe), 1)
    print(f'{probability_threshold:5.2f} {len(above_threshold_geodataframe):7d} {hits_within_10m_count:7d} {distinct_pits_covered_count:9d} {false_positive_count:7d} {precision_value:7.2%}')
"""))

# ============================================================
cells.append(md("""## 9. Morphological Measurement

Now we measure the actual physical dimensions of each pit. For every one of the 861
annotated pit locations, we look at the DEM within a small window and extract:

- **Depth:** How deep the pit is (bottom elevation vs. rim elevation)
- **Rim radius:** How far from center the highest surrounding ring is
- **Diameter:** Twice the rim radius — how wide the pit is across
- **Aspect ratio:** Depth divided by diameter — how "bowl-shaped" vs "saucer-shaped" it is
- **Rim symmetry:** Whether the rim is evenly high all around or lopsided on one side
- **Volume:** A rough estimate of how much material was removed (using a cone shape)
- **LRM depth:** The Local Relief Model value at the pit center (how anomalous the depth is)
- **Inner slope:** How steep the ground is right at the pit center

The function first "snaps" the pit center to the nearest local minimum within 3 cells,
because our hand-placed annotation points might be slightly off from the actual deepest spot."""))
cells.append(code("""def read_geotiff_as_array_with_metadata(geotiff_path):
    \"\"\"Open a GeoTIFF file and return three things: the elevation grid as an array,
    the geographic bounds (where it is on the map), and the pixel dimensions (rows x cols).\"\"\"
    with rasterio.open(geotiff_path) as dataset:
        elevation_arr = dataset.read(1).astype(np.float32)
        nodata_value = dataset.nodata
        if nodata_value is not None:
            elevation_arr = np.where(elevation_arr == nodata_value, np.nan, elevation_arr)
        return elevation_arr, dataset.bounds, dataset.shape


def measure_pit_morphology_from_elevation_model(pit_easting, pit_northing,
                                                 digital_elevation_model_arr,
                                                 local_relief_model_5m_arr,
                                                 local_relief_model_11m_arr,
                                                 slope_arr,
                                                 tile_bounds, tile_shape):
    \"\"\"Take one pit location and measure everything about its physical shape.
    We look at the DEM in a small window around the pit, find the deepest point (bottom),
    find the highest surrounding ring (rim), and compute depth, radius, diameter,
    how bowl-shaped it is (aspect ratio), how circular the rim is (symmetry),
    an estimated volume, and how steep the inner walls are.
    Returns None if the pit is too close to the edge or has too much missing data.\"\"\"
    tile_height, tile_width = tile_shape
    tile_x_origin = tile_bounds.left
    tile_y_top = tile_bounds.top
    pixel_row = int(round((tile_y_top - pit_northing) / CELL_RESOLUTION_METERS))
    pixel_col = int(round((pit_easting - tile_x_origin) / CELL_RESOLUTION_METERS))
    measurement_half_window = 8

    window_row_start = pixel_row - measurement_half_window
    window_row_end = pixel_row + measurement_half_window + 1
    window_col_start = pixel_col - measurement_half_window
    window_col_end = pixel_col + measurement_half_window + 1
    if window_row_start < 0 or window_col_start < 0 or window_row_end > tile_height or window_col_end > tile_width:
        return None

    dem_window_arr = digital_elevation_model_arr[window_row_start:window_row_end, window_col_start:window_col_end]
    if np.isnan(dem_window_arr).mean() > 0.5:
        return None

    # Snap to local minimum
    snap_radius = 3
    snap_start = measurement_half_window - snap_radius
    snap_end = measurement_half_window + snap_radius + 1
    snap_window_arr = dem_window_arr[snap_start:snap_end, snap_start:snap_end]
    if not np.isfinite(snap_window_arr).any():
        return None
    flat_min_index = np.nanargmin(snap_window_arr)
    min_row_offset, min_col_offset = divmod(flat_min_index, snap_window_arr.shape[1])
    snapped_center_row = snap_start + min_row_offset
    snapped_center_col = snap_start + min_col_offset
    pit_bottom_elevation = dem_window_arr[snapped_center_row, snapped_center_col]

    row_offsets, col_offsets = np.ogrid[-snapped_center_row:dem_window_arr.shape[0]-snapped_center_row,
                                        -snapped_center_col:dem_window_arr.shape[1]-snapped_center_col]
    distance_from_center_arr = np.sqrt(col_offsets**2 + row_offsets**2) * CELL_RESOLUTION_METERS

    # Find rim via annular ring analysis
    annular_ring_elevations_lst = []
    for ring_radius_meters in np.arange(1.0, 8.0, 0.5):
        ring_mask = (distance_from_center_arr >= ring_radius_meters - 0.5) & (distance_from_center_arr <= ring_radius_meters + 0.5)
        ring_elevation_values = dem_window_arr[ring_mask]
        valid_ring_values = ring_elevation_values[np.isfinite(ring_elevation_values)]
        if len(valid_ring_values) > 0:
            annular_ring_elevations_lst.append((ring_radius_meters, np.mean(valid_ring_values), np.max(valid_ring_values)))
    if not annular_ring_elevations_lst:
        return None

    ring_statistics_arr = np.array(annular_ring_elevations_lst)
    highest_mean_ring_index = np.argmax(ring_statistics_arr[:, 1])
    rim_radius_meters = ring_statistics_arr[highest_mean_ring_index, 0]
    rim_mean_elevation = ring_statistics_arr[highest_mean_ring_index, 1]
    rim_max_elevation = ring_statistics_arr[highest_mean_ring_index, 2]
    depth_from_rim_mean = rim_mean_elevation - pit_bottom_elevation
    depth_from_rim_max = rim_max_elevation - pit_bottom_elevation

    # Effective radius (half-depth contour)
    half_depth_elevation = pit_bottom_elevation + depth_from_rim_mean / 2.0
    above_half_depth_mask = dem_window_arr >= half_depth_elevation
    distances_above_half_depth = distance_from_center_arr[above_half_depth_mask & (distance_from_center_arr < 8.0)]
    effective_radius_meters = float(np.median(distances_above_half_depth)) if len(distances_above_half_depth) > 0 else np.nan

    # Rim symmetry
    angular_samples_arr = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    rim_elevation_samples_lst = []
    for angle_radians in angular_samples_arr:
        sample_row = int(round(snapped_center_row + rim_radius_meters / CELL_RESOLUTION_METERS * np.sin(angle_radians)))
        sample_col = int(round(snapped_center_col + rim_radius_meters / CELL_RESOLUTION_METERS * np.cos(angle_radians)))
        if 0 <= sample_row < dem_window_arr.shape[0] and 0 <= sample_col < dem_window_arr.shape[1]:
            elevation_value = dem_window_arr[sample_row, sample_col]
            if np.isfinite(elevation_value):
                rim_elevation_samples_lst.append(elevation_value)
    rim_symmetry_standard_deviation = float(np.std(rim_elevation_samples_lst)) if len(rim_elevation_samples_lst) >= 4 else np.nan

    diameter_meters = 2.0 * rim_radius_meters
    depth_to_diameter_aspect_ratio = depth_from_rim_mean / diameter_meters if diameter_meters > 0 else np.nan
    volume_cubic_meters = (1/3) * np.pi * rim_radius_meters**2 * depth_from_rim_mean

    # LRM values at snapped center
    lrm_5m_window = local_relief_model_5m_arr[window_row_start:window_row_end, window_col_start:window_col_end]
    lrm_11m_window = local_relief_model_11m_arr[window_row_start:window_row_end, window_col_start:window_col_end]
    lrm_5m_center_value = float(lrm_5m_window[snapped_center_row, snapped_center_col]) if snapped_center_row < lrm_5m_window.shape[0] and snapped_center_col < lrm_5m_window.shape[1] else np.nan
    lrm_11m_center_value = float(lrm_11m_window[snapped_center_row, snapped_center_col]) if snapped_center_row < lrm_11m_window.shape[0] and snapped_center_col < lrm_11m_window.shape[1] else np.nan

    slope_window_arr = slope_arr[window_row_start:window_row_end, window_col_start:window_col_end]
    inner_slope_values = slope_window_arr[distance_from_center_arr <= 2.0]
    inner_slope_mean_degrees = float(np.nanmean(inner_slope_values)) if np.isfinite(inner_slope_values).any() else np.nan

    return {
        'pit_bottom_elev_m': float(pit_bottom_elevation), 'rim_mean_elev_m': float(rim_mean_elevation),
        'rim_max_elev_m': float(rim_max_elevation), 'depth_from_rim_mean_m': float(depth_from_rim_mean),
        'depth_from_rim_max_m': float(depth_from_rim_max), 'rim_radius_m': float(rim_radius_meters),
        'effective_radius_m': float(effective_radius_meters), 'diameter_m': float(diameter_meters),
        'aspect_ratio': float(depth_to_diameter_aspect_ratio), 'rim_symmetry_std_m': float(rim_symmetry_standard_deviation),
        'volume_approx_m3': float(volume_cubic_meters), 'lrm5_depth_m': float(lrm_5m_center_value),
        'lrm11_depth_m': float(lrm_11m_center_value), 'slope_inner_deg': float(inner_slope_mean_degrees)}


# Process all tiles
TILE_SUFFIX_MAP = {'9t': '_9t_1m.tif', 'mk5': '_mk5_1m.tif', 'mk': '_mk_1m.tif', 'mkf': '_mkf_1m.tif'}
morphology_records_lst = []
processed_pit_indices_set = set()

for tile_tag, tile_suffix in TILE_SUFFIX_MAP.items():
    dem_filepath = DERIVATIVES_DIR / f'dem{tile_suffix}'
    if not dem_filepath.exists():
        continue
    dem_arr, tile_bounds, tile_shape = read_geotiff_as_array_with_metadata(geotiff_path=str(dem_filepath))
    lrm_5m_arr, _, _ = read_geotiff_as_array_with_metadata(geotiff_path=str(DERIVATIVES_DIR / f'lrm_5{tile_suffix}'))
    lrm_11m_arr, _, _ = read_geotiff_as_array_with_metadata(geotiff_path=str(DERIVATIVES_DIR / f'lrm_11{tile_suffix}'))
    slope_arr, _, _ = read_geotiff_as_array_with_metadata(geotiff_path=str(DERIVATIVES_DIR / f'slope{tile_suffix}'))

    tile_extent = tile_bounds
    pits_in_tile_geodataframe = annotated_pits_geodataframe.cx[tile_extent.left:tile_extent.right, tile_extent.bottom:tile_extent.top]
    if len(pits_in_tile_geodataframe) == 0:
        continue
    print(f'  {tile_tag}: {len(pits_in_tile_geodataframe)} pits')

    for pit_index, pit_row in pits_in_tile_geodataframe.iterrows():
        if pit_index in processed_pit_indices_set:
            continue
        measurement_result = measure_pit_morphology_from_elevation_model(
            pit_easting=pit_row.geometry.x,
            pit_northing=pit_row.geometry.y,
            digital_elevation_model_arr=dem_arr,
            local_relief_model_5m_arr=lrm_5m_arr,
            local_relief_model_11m_arr=lrm_11m_arr,
            slope_arr=slope_arr,
            tile_bounds=tile_bounds,
            tile_shape=tile_shape)
        if measurement_result is not None:
            measurement_result['original_index'] = pit_index
            measurement_result['easting'] = pit_row.geometry.x
            measurement_result['northing'] = pit_row.geometry.y
            measurement_result['tile'] = tile_tag
            measurement_result['notes'] = pit_row.get('notes', '')
            morphology_records_lst.append(measurement_result)
            processed_pit_indices_set.add(pit_index)

morphology_df = pd.DataFrame(morphology_records_lst)
morphology_df = morphology_df.drop_duplicates(subset=['original_index'], keep='first').reset_index(drop=True)
print(f'\\nTotal pits measured: {len(morphology_df)}')
"""))

# ============================================================
cells.append(md("""## 10. Anomaly Detection and PCA

Not all of our 861 annotations are necessarily correct — some might be mis-clicks, some
might be natural features we mistook for pits. This section identifies the **statistical
outliers** in our pit measurements so we can review them.

We use four methods:
- **Z-scores:** For each measurement (depth, radius, etc.), how many standard deviations is
  this pit from the average? A z-score of 3+ means "this is very unusual for that metric."
- **Mahalanobis distance:** Like a z-score but for all 11 measurements at once. It accounts
  for the fact that some measurements are correlated (deeper pits also tend to have larger
  volume). A pit that's deep AND large isn't weird, but one that's deep with a tiny radius is.
- **Isolation Forest:** A machine learning method that finds points that are "easy to isolate"
  from the rest of the data — i.e., they're in sparse, unusual regions of the feature space.
- **PCA (Principal Component Analysis):** Reduces our 11 measurements down to 2-3 summary
  axes so we can plot all 856 pits on a single scatter chart and see which ones are outliers.

The output is a GeoPackage and CSV where every pit has all its measurements plus anomaly
scores and a rank. The most anomalous pits are at the top — those are the ones to review
in QGIS against the hillshade."""))
cells.append(code("""morphology_feature_names_lst = [
    'depth_from_rim_mean_m', 'depth_from_rim_max_m', 'rim_radius_m',
    'effective_radius_m', 'diameter_m', 'aspect_ratio',
    'rim_symmetry_std_m', 'volume_approx_m3', 'lrm5_depth_m', 'lrm11_depth_m',
    'slope_inner_deg']

morphology_features_filled_df = morphology_df[morphology_feature_names_lst].fillna(
    morphology_df[morphology_feature_names_lst].median())
feature_scaler = StandardScaler()
standardized_features_arr = feature_scaler.fit_transform(morphology_features_filled_df)

# Per-feature z-scores
morphology_df['max_zscore'] = np.abs(standardized_features_arr).max(axis=1)
morphology_df['mean_zscore'] = np.abs(standardized_features_arr).mean(axis=1)

# Mahalanobis distance
covariance_matrix = np.cov(standardized_features_arr.T)
inverse_covariance_matrix = np.linalg.pinv(covariance_matrix)
population_center_arr = standardized_features_arr.mean(axis=0)
morphology_df['mahalanobis'] = [mahalanobis(row, population_center_arr, inverse_covariance_matrix) for row in standardized_features_arr]

# Isolation Forest
isolation_forest_model = IsolationForest(n_estimators=200, contamination=0.1, random_state=42)
isolation_forest_model.fit(morphology_features_filled_df)
morphology_df['iso_anomaly_score'] = -isolation_forest_model.score_samples(morphology_features_filled_df)

# PCA
principal_component_model = PrincipalComponentAnalysis()
principal_component_scores_arr = principal_component_model.fit_transform(standardized_features_arr)
morphology_df['PC1_depth_volume'] = principal_component_scores_arr[:, 0]
morphology_df['PC2_size_vs_slope'] = principal_component_scores_arr[:, 1]
morphology_df['PC3_rim_asymmetry'] = principal_component_scores_arr[:, 2]

for feature_index, feature_name in enumerate(morphology_feature_names_lst):
    morphology_df[f'z_{feature_name}'] = standardized_features_arr[:, feature_index]

# Identify dominant anomaly reason per pit
absolute_zscores_arr = np.abs(standardized_features_arr)
worst_feature_indices_arr = np.argmax(absolute_zscores_arr, axis=1)
morphology_df['anomaly_reason'] = [morphology_feature_names_lst[idx] for idx in worst_feature_indices_arr]
morphology_df['anomaly_reason_zscore'] = [standardized_features_arr[row, worst_feature_indices_arr[row]] for row in range(len(morphology_df))]
morphology_df['anomaly_rank'] = morphology_df['mahalanobis'].rank(ascending=False).astype(int)

morphology_sorted_df = morphology_df.sort_values('mahalanobis', ascending=False).reset_index(drop=True)

# Save outputs
pit_geometry_lst = [Point(east, north) for east, north in zip(morphology_sorted_df['easting'], morphology_sorted_df['northing'])]
morphology_geodataframe = gpd.GeoDataFrame(morphology_sorted_df.drop(columns=['easting', 'northing']), geometry=pit_geometry_lst, crs=COORDINATE_REFERENCE_SYSTEM)
morphology_geodataframe.to_file(DERIVATIVES_DIR / 'pit_1m_morphology_audit.gpkg', driver='GPKG')
morphology_geodataframe.drop(columns='geometry').to_csv(DERIVATIVES_DIR / 'pit_1m_morphology_audit.csv', index=False, float_format='%.4f')
print(f'Saved: pit_1m_morphology_audit.gpkg ({len(morphology_geodataframe)} features, {len(morphology_geodataframe.columns)} columns)')

print(f'\\nMorphology summary statistics:')
print(morphology_df[morphology_feature_names_lst].describe().round(3).to_string())
print(f'\\nPCA variance explained: PC1={principal_component_model.explained_variance_ratio_[0]:.1%}, '
      f'PC2={principal_component_model.explained_variance_ratio_[1]:.1%}, '
      f'PC3={principal_component_model.explained_variance_ratio_[2]:.1%}')
print(f'\\nTop 10 most anomalous pits:')
display_columns_lst = ['original_index', 'tile', 'depth_from_rim_mean_m', 'rim_radius_m', 'diameter_m', 'mahalanobis', 'anomaly_reason']
print(morphology_sorted_df[display_columns_lst].head(10).round(3).to_string(index=False))
"""))

# ============================================================
cells.append(md("""## 11. Paper Figures

Generate the key visualizations used in the paper:

1. **Morphology box plots:** Shows the distribution of each physical parameter across all
   856 pits. Each box shows the median, quartiles, and outliers so you can see at a glance
   what "typical" looks like and which pits are unusual.

2. **PCA scatter plot:** Projects all 856 pits from 11-dimensional measurement space down to
   2 dimensions. Each dot is a pit, colored by its Mahalanobis anomaly score (yellow = normal,
   red = weird). The five most anomalous pits are labeled with their feature ID."""))
cells.append(code("""# Morphology box plots
fig, axes = plt.subplots(2, 3, figsize=(12, 7))
plot_parameters_lst = [
    ('depth_from_rim_mean_m', 'Depth from Rim (m)'),
    ('depth_from_rim_max_m', 'Max Depth (m)'),
    ('rim_radius_m', 'Rim Radius (m)'),
    ('diameter_m', 'Diameter (m)'),
    ('aspect_ratio', 'Aspect Ratio'),
    ('volume_approx_m3', 'Volume (m\\u00b3)')]

for axis, (column_name, axis_label) in zip(axes.flat, plot_parameters_lst):
    column_data = morphology_df[column_name].dropna()
    box_plot = axis.boxplot(column_data, vert=True, patch_artist=True, widths=0.5)
    box_plot['boxes'][0].set_facecolor('#4C72B0')
    box_plot['boxes'][0].set_alpha(0.7)
    axis.set_ylabel(axis_label)
    axis.set_xticks([])
    axis.grid(alpha=0.3, axis='y')
    axis.set_title(f'n={len(column_data)}, \\u03bc={column_data.mean():.2f}, \\u03c3={column_data.std():.2f}', fontsize=9)

fig.suptitle(f'Pit Morphology Parameter Distributions (n={len(morphology_df)} pits)', fontsize=12, y=0.98)
fig.tight_layout()
fig.savefig(DERIVATIVES_DIR / 'paper_fig_morphology_boxplots.png', dpi=150, bbox_inches='tight')
plt.show()

# PCA scatter plot
fig, axis = plt.subplots(figsize=(9, 7))
scatter_plot = axis.scatter(
    principal_component_scores_arr[:, 0],
    principal_component_scores_arr[:, 1],
    c=morphology_df['mahalanobis'], cmap='YlOrRd', s=15, alpha=0.7, edgecolors='none')
axis.set_xlabel(f'PC1 - Depth/Volume ({principal_component_model.explained_variance_ratio_[0]:.0%} variance)')
axis.set_ylabel(f'PC2 - Size vs Slope ({principal_component_model.explained_variance_ratio_[1]:.0%} variance)')
axis.set_title('PCA of Pit Morphology (color = Mahalanobis Distance)')
plt.colorbar(scatter_plot, ax=axis, label='Mahalanobis Distance', shrink=0.8)
axis.grid(alpha=0.2)

top_five_anomalies_df = morphology_df.nlargest(5, 'mahalanobis')
for _, anomaly_row in top_five_anomalies_df.iterrows():
    row_index = morphology_df.index.get_loc(anomaly_row.name)
    axis.annotate(f'FID {int(anomaly_row["original_index"])}',
                  xy=(principal_component_scores_arr[row_index, 0], principal_component_scores_arr[row_index, 1]),
                  fontsize=7, color='red')
fig.tight_layout()
fig.savefig(DERIVATIVES_DIR / 'paper_fig_pca_anomaly.png', dpi=150, bbox_inches='tight')
plt.show()

print('Figures saved.')
"""))

nb.cells = cells
output_path = Path('notebooks/wellsight_morphology_pipeline.ipynb')
nbf.write(nb, str(output_path))
print(f'Notebook saved: {output_path}')

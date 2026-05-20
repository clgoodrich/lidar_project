"""Project paths, CRS, and channel-order constants.

Single source of truth — everywhere else in wsight should import from here.
"""
from pathlib import Path

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
DATA = ROOT / "data"
DERIV = DATA / "derivatives"
TILE_DIR = DERIV / "9t"
ANN_DIR = DERIV / "annotations"
ITERATIONS_DIR = TILE_DIR / "iterations"

ANN_GPKG = ANN_DIR / "annotations_proj.gpkg"

# Label rasters
PIT_LABELS = TILE_DIR / "labels_pit_9t_05.tif"
PLAT_LABELS = TILE_DIR / "labels_plat_9t_05.tif"
ROAD_LABELS = TILE_DIR / "labels_road_9t_05.tif"

# Spatial-block split + manifests
BLOCKS_GPKG = TILE_DIR / "pit_blocks_9t.gpkg"
PIT_MANIFEST = TILE_DIR / "pit_dataset_manifest.csv"
PLAT_MANIFEST = TILE_DIR / "plat_dataset_manifest.csv"
ROAD_MANIFEST = TILE_DIR / "road_dataset_manifest.csv"
ROAD_SAMPLES = TILE_DIR / "road_classifier_samples.csv"

# Feature stacks
FEATURES_7CH = TILE_DIR / "features_pit_9t_05.tif"
FEATURES_STATS_7CH = TILE_DIR / "feature_stats.json"

# DTM reference (for new derived features)
DEM_PATH = TILE_DIR / "dem_9t_05.tif"
HILLSHADE_PATH = TILE_DIR / "hillshade_9t_05.tif"

# CRS used by every projected layer in this project
PROJECT_CRS = "EPSG:6346"

# Canonical channel orders. The order MUST match the band order in the corresponding
# stacked feature TIF, and the iteration trainer MUST use the same order at inference.
CHANNEL_ORDER_7CH = [
    "lrm_25", "lrm_5", "slope", "tpi_05",
    "openness_pos", "openness_neg", "roughness_11",
]
CHANNEL_ORDER_11CH = CHANNEL_ORDER_7CH + [
    "lrm_11", "lrm_51", "curvature", "geomorphons",
]

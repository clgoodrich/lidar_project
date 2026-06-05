"""Generate docs/WellSight_Methodology.docx — the detailed-but-plain methodology
write-up (process names + parameters), formatted as a Word document.

This is the technical companion to docs/HOW_IT_WORKS.md: same story, but with the
actual tool names, parameters, and process steps spelled out. Regenerate with:

    C:/Python313/python.exe docs/_build_methodology_docx.py
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Inches

OUT = Path(__file__).resolve().parent / "WellSight_Methodology.docx"

ACCENT = RGBColor(0x1F, 0x49, 0x6E)   # deep blue
MONO_BG = RGBColor(0x33, 0x33, 0x33)


def main() -> int:
    doc = Document()

    # ---- base styles -----------------------------------------------------
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.08

    for lvl, sz in ((1, 17), (2, 13)):
        st = doc.styles[f"Heading {lvl}"]
        st.font.name = "Calibri"
        st.font.size = Pt(sz)
        st.font.color.rgb = ACCENT
        st.font.bold = True

    def code(text: str):
        """A shaded monospace paragraph for commands / file names."""
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(8)
        r = p.add_run(text)
        r.font.name = "Consolas"
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0x11, 0x11, 0x11)
        return p

    def bullets(items):
        for it in items:
            p = doc.add_paragraph(style="List Bullet")
            if isinstance(it, tuple):
                lead, rest = it
                r = p.add_run(lead)
                r.bold = True
                p.add_run(rest)
            else:
                p.add_run(it)

    def table(headers, rows, widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Light Grid Accent 1"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr = t.rows[0].cells
        for i, h in enumerate(headers):
            hdr[i].text = ""
            r = hdr[i].paragraphs[0].add_run(h)
            r.bold = True
            r.font.size = Pt(10)
        for row in rows:
            cells = t.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = ""
                r = cells[i].paragraphs[0].add_run(str(val))
                r.font.size = Pt(9.5)
        if widths:
            for row in t.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Inches(w)
        doc.add_paragraph()
        return t

    # ---- title -----------------------------------------------------------
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("WellSight — Detection Methodology")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = ACCENT

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("LiDAR-based detection of orphaned / abandoned oil & gas wells, "
                    "western Pennsylvania")
    r.italic = True
    r.font.size = Pt(12)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run("Technical methodology overview — plain language with process names · "
                     "generated 2026-06-03")
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()
    intro = doc.add_paragraph()
    intro.add_run(
        "WellSight locates the faint ground scars left by abandoned wells — small "
        "depressions (pits), flat cleared platforms (pads), and access-road remnants — "
        "that are invisible in ordinary aerial photos because they sit under forest "
        "canopy. It does this by reading the shape of the bare earth from airborne "
        "LiDAR, exaggerating that shape with terrain filters, and training neural "
        "networks to recognise the features against a ground-truth catalog of known "
        "wells. This document walks the full pipeline in order, naming the actual "
        "tools, processes, and parameters at each stage."
    )

    # ---- 1. source data --------------------------------------------------
    doc.add_heading("1. Source data", level=1)

    doc.add_heading("1a. Airborne LiDAR point clouds", level=2)
    doc.add_paragraph(
        "The primary input is airborne LiDAR: an aircraft fires hundreds of thousands "
        "of laser pulses per second straight down; each return records a 3-D ground "
        "position. Crucially, some pulses penetrate gaps in the canopy and strike bare "
        "soil, so the terrain surface can be reconstructed even under dense forest — "
        "something optical imagery cannot do."
    )
    bullets([
        ("Source: ", "Public USGS 3DEP (3D Elevation Program) LiDAR surveys, "
         "delivered as ASPRS .las / .laz tiles, one work-unit per survey."),
        ("Classification: ", "Every point carries an ASPRS class code (2 = ground, "
         "5 = high vegetation, 6 = building, 9 = water, 20 = ignored/hydro-flattened "
         "ground). The ground class is what we keep. Note: surveys differ — the Oil "
         "Creek tiles were hydro-flattened (classes 9 & 20 present), while McKean / 9t "
         "were not, which is why streams are derived differently per region."),
        ("Header inspection: ", "Before any spatial operation, the LAS header is read "
         "to confirm point format, count, density, bounding box, and CRS — never "
         "assumed."),
        ("Study tiles: ", "the '9t' mosaic (training / validation area, EPSG:6346 "
         "NAD83(2011) / UTM 17N), the Oil Creek 22-tile mosaic, and McKean blocks."),
    ])

    doc.add_heading("1b. Ground-truth well catalog", level=2)
    doc.add_paragraph(
        "Validation uses output_wells.csv — coordinates and attributes for already-"
        "mapped wells from the Pennsylvania DEP (Department of Environmental Protection) "
        "oil & gas catalog. This is the answer key: detectors are tuned so that they "
        "fire where known wells are, then applied to unmapped ground to surface new "
        "candidates. The file is treated as strictly read-only and always copied before "
        "use."
    )

    # ---- 2. point cloud -> DEM ------------------------------------------
    doc.add_heading("2. Point cloud → bare-earth DEM", level=1)
    doc.add_paragraph(
        "Millions of irregular 3-D points are reduced to regular raster grids "
        "(images where each pixel is a measurement). The processing engine is PDAL "
        "(Point Data Abstraction Library)."
    )
    bullets([
        ("PDAL invocation: ", "the PDAL Python bindings are non-functional in this "
         "environment, so every operation is run by writing a pipeline JSON to a temp "
         "file and calling the PDAL CLI via subprocess (the run_pipeline() helper)."),
        ("Ground filtering: ", "the point cloud is filtered to ASPRS class 2 (ground) "
         "to strip vegetation and structures."),
        ("Gridding to DEM: ", "ground returns are interpolated to a Digital Elevation "
         "Model (bare-earth height per pixel) at 1 m and 0.5 m resolution."),
        ("Hydrological conditioning: ", "for flow analysis the DEM is breached "
         "(BreachDepressionsLeastCost in WhiteboxTools) and/or filled (FillDepressions) "
         "so spurious sinks don't trap simulated water. The conditioned grid is cached "
         "(e.g. dem_breached_9t_1m.tif) and reused."),
    ])
    doc.add_paragraph(
        "Companion surface models are also gridded: the DSM (Digital Surface Model, "
        "top-of-canopy) and the CHM (Canopy Height Model = DSM − DEM)."
    )

    # ---- 3. feature engineering -----------------------------------------
    doc.add_heading("3. Terrain-derivative feature engineering", level=1)
    doc.add_paragraph(
        "A raw height map does not make well scars visible — a pad may differ from "
        "surrounding soil by only centimetres. So the DEM is run through a family of "
        "geomorphometric filters (WhiteboxTools and GDAL), each of which exaggerates a "
        "different landform property. Build script: build/_build_derivatives.py."
    )
    table(
        ["Derivative (process)", "What it measures / highlights"],
        [
            ["Slope (degrees)", "Steepness — flat pads vs. natural hillsides."],
            ["LRM — Local Relief Model (radii 3/5/11/25)",
             "Removes regional topography, leaving only small-scale bumps and dips — "
             "ideal for faint man-made scars."],
            ["TPI — Topographic Position Index (05/15/25) + gradient",
             "Whether a cell sits above/below its neighbourhood — ridges vs. pits."],
            ["Openness (positive & negative)",
             "How exposed vs. recessed a location is — strong on depressions & edges."],
            ["Roughness (stdev of elevation, radius 11)",
             "Local surface texture — disturbed ground reads differently."],
            ["Hillshade (multi-azimuth) / Multidirectional hillshade",
             "Simulated illumination for human visual interpretation."],
            ["DSM / CHM, ground density, intensity (ground)",
             "Auxiliary context layers (canopy, return density, laser reflectance)."],
        ],
        widths=[2.9, 3.6],
    )
    doc.add_heading("The 7-band model input ('feature stack')", level=2)
    doc.add_paragraph(
        "Seven of these derivatives are stacked, in a fixed channel order, into a "
        "single multi-band GeoTIFF (features_*.tif) that every model consumes. This is "
        "the definitive answer to 'what data inputs go into the model' — not photos, "
        "not raw points, but these seven terrain-shape layers derived from the "
        "bare-earth DEM:"
    )
    code("(1) lrm_25   (2) lrm_5   (3) slope   (4) tpi_05\n"
         "(5) openness_pos   (6) openness_neg   (7) roughness_11")
    bullets([
        ("Why these, not canopy: ", "the CHM (tree height) was tested and dropped — "
         "canopy cover is inconsistent across well sites and adds noise; the terrain "
         "filters describe the soil itself, which carries the scar."),
        ("Normalization: ", "each band is z-score normalized (centred at 0, unit "
         "spread) using per-channel mean/std stored in feature_stats.json. The "
         "mean/std vectors (mu, sd) are saved inside each model checkpoint so inference "
         "applies the identical scaling."),
    ])

    # ---- 4. annotation & dataset ----------------------------------------
    doc.add_heading("4. Annotation & dataset construction", level=1)
    doc.add_paragraph(
        "Supervised learning needs labelled examples. A human digitises polygons over "
        "the terrain derivatives in QGIS:"
    )
    bullets([
        ("Pits: ", "labelled as two classes — floor (the depression bottom) and wall "
         "(the surrounding rim) — so the model learns the full landform, not just the "
         "hole."),
        ("Pads: ", "the flat cleared drilling platforms (polygon outlines)."),
        ("Splits: ", "annotations are partitioned into train / validation / test; the "
         "test split is held out and never seen during training, for an honest final "
         "score. Manifests (pit_dataset_manifest.csv, etc.) record the split."),
        ("Patch sampling: ", "fixed-size windows are cut from the feature stack centred "
         "on each labelled instance, with random positional jitter so the network "
         "cannot memorise absolute coordinates. Pits: 256 px (~128 m at 0.5 m/px), "
         "jitter 30 m, ~4 patches/instance. Pads: 384 px, jitter 40 m."),
    ])
    doc.add_paragraph(
        "A current, acknowledged limitation: only ~110 pit and ~79 pad polygons exist, "
        "which is thin for a 45.9 M-parameter network and the dominant cause of "
        "overfitting. Growing the label set from the PA DEP catalog (1,069 wells in the "
        "9t tile alone) is the top-priority backlog item."
    )

    # ---- 5. models -------------------------------------------------------
    doc.add_heading("5. Models", level=1)
    doc.add_paragraph(
        "Three model families are trained on the same 7-band stack and compared on the "
        "same test split, because they answer slightly different questions:"
    )
    table(
        ["Model (process)", "Type", "Question it answers"],
        [
            ["U-Net", "Semantic segmentation (per-pixel labels)",
             "Which areas are well-related? Best for long, thin features (roads/streams)."],
            ["Mask R-CNN (torchvision maskrcnn_resnet50_fpn_v2)",
             "Instance segmentation (per-object outlines)",
             "Where is each distinct pit / pad, as countable objects?"],
            ["YOLO-seg (Ultralytics)", "Instance segmentation, speed-optimised",
             "Fast independent cross-check of the instance results."],
        ],
        widths=[2.5, 2.0, 2.0],
    )
    doc.add_heading("Mask R-CNN training detail", level=2)
    bullets([
        ("Backbone: ", "maskrcnn_resnet50_fpn_v2, initialised from COCO-pretrained "
         "weights (transfer learning)."),
        ("Multispectral input adapter: ", "the pretrained first conv expects 3 "
         "channels; it is widened to 7 by copying the RGB weights and averaging them "
         "into the 4 extra channels (conv1 widening), so pretrained low-level filters "
         "are retained."),
        ("Pit head: ", "3 classes (background / floor / wall); the box & mask "
         "predictors are reinitialised for that class count."),
        ("Optimisation: ", "input mean/std set to 0/1 (normalization already applied "
         "upstream); trained a few epochs (best checkpoint typically epoch 0–1, "
         "consistent with the thin-data regime). Checkpoint stores arch, in_channels, "
         "channel list, mu, sd, and weights."),
    ])

    # ---- 6. inference ----------------------------------------------------
    doc.add_heading("6. Inference (running a trained model on a full tile)", level=1)
    bullets([
        ("Sliding window: ", "a PATCH×PATCH window slides across the whole feature "
         "stack with overlap; the model predicts instances in each window."),
        ("Score threshold: ", "detections below score 0.3 are dropped."),
        ("Global de-duplication: ", "per-class non-maximum suppression (global_nms) "
         "merges overlapping detections from adjacent windows."),
        ("Outputs: ", "per-class probability rasters (e.g. pit_prob_floor.tif, "
         "pit_prob_wall.tif) plus per-detection polygons written to GeoPackage, each "
         "carrying a confidence score and distance to the nearest known well."),
    ])

    # ---- 7. evaluation ---------------------------------------------------
    doc.add_heading("7. Evaluation metric", level=1)
    doc.add_paragraph(
        "All models are graded identically on the held-out test set using per-instance "
        "IoU (Intersection-over-Union: overlap between a predicted outline and the true "
        "one, 0 = none, 1 = exact). The headline number is recall@IoU — the fraction of "
        "real wells matched at a given overlap (e.g. recall@IoU 0.5 = found with ≥50% "
        "shape agreement). Identical metric + identical test instances is what keeps "
        "the leaderboard apples-to-apples."
    )
    doc.add_heading("Latest results (9t test split, 7-band)", level=2)
    table(
        ["Model", "recall@0.1", "recall@0.3", "recall@0.5", "mean IoU", "detections"],
        [
            ["pit_07 Mask R-CNN (v2, 7-band)", "1.00", "1.00", "0.95", "0.664", "2027"],
            ["pad_05 Mask R-CNN (v2, 7-band)", "1.00", "1.00", "0.889", "0.631", "2546"],
        ],
        widths=[2.6, 0.9, 0.9, 0.9, 0.8, 1.0],
    )
    doc.add_paragraph(
        "Interpretation: pit recall is strong (0.95). Pad detection count (~2546 for "
        "~79 real pads) shows the open problem is over-prediction / precision, traced "
        "to label quantity and a permissive 0.3 score threshold rather than feature "
        "richness — the 7-band stack only cut pad false positives ~22% vs. the 3-band "
        "baseline."
    )

    # ---- 8. streams ------------------------------------------------------
    doc.add_heading("8. Stream / road sub-pipeline", level=1)
    doc.add_paragraph(
        "Access roads to old wells often follow or cross natural drainage, so mapping "
        "streams helps separate man-made road scars from natural gullies. The stream "
        "network is derived purely from the DEM (WhiteboxTools), since the 9t / McKean "
        "surveys carry no water classification."
    )
    doc.add_heading("Stage 1 — extraction (build/_build_streams_9t.py)", level=2)
    bullets([
        "d8_pointer on the breached DEM → flow-direction grid.",
        "d8_flow_accumulation (out_type=cells) → upslope contributing area per cell.",
        "extract_streams at threshold = 5000 cells (t5000) → raw stream raster.",
        "raster_streams_to_vector → linestrings, CRS forced to EPSG:6346.",
    ])
    doc.add_paragraph("Result: streams_t5000_9t_1m = 2,693 lines, 274.5 km.")
    doc.add_heading("Stage 2 — cross-section road filter "
                    "(build/_filter_streams_xsec_9t.py)", level=2)
    doc.add_paragraph(
        "Run on the RAW (un-breached) DEM, because breaching fills the very channels "
        "the test measures. At samples along each line the local tangent is rotated "
        "90°, the DEM is sampled ±5 m to each side, and a concavity statistic "
        "xdrop_m = median( mean(z_left, z_right) − z_center ) is computed. Natural "
        "channels are concave (xdrop_m > 0); graded road cuts are flat-to-convex "
        "(xdrop_m ≤ 0) and are dropped. Two passes run together: per-line (one verdict "
        "per line) and per-chunk (~25 m segments judged independently). Parameters: "
        "--chunk 25 --perp 5 --drop 0.30."
    )
    table(
        ["Product", "Features", "Length"],
        [
            ["raw streams_t5000_9t_1m", "2,693 lines", "274.5 km"],
            ["kept_xsec (per-line)", "1,497 lines", "97.9 km"],
            ["chunked_kept_xsec (per-chunk)", "4,973 chunks", "88.8 km"],
        ],
        widths=[3.0, 1.8, 1.5],
    )

    # ---- 9. diagnostics --------------------------------------------------
    doc.add_heading("9. Diagnostic derivatives (research layer)", level=1)
    doc.add_paragraph(
        "A second wave of geomorphometric layers (build/_build_diagnostics_9t.py, "
        "WhiteboxTools) is computed for analysis — NOT yet wired into any model — to "
        "test which additional signals separate pits / pads / roads. Layers include "
        "depth-in-sink (FillDepressions − DEM), TWI (wetness index), the full curvature "
        "family (profile / plan / total / mean / gaussian), geomorphons (categorical "
        "landform), spherical std-dev of normals, TRI (ruggedness), surface-area ratio, "
        "and downslope index."
    )
    doc.add_paragraph(
        "Validation against the 110 pit annotations identified two standout pit signals:"
    )
    bullets([
        ("depth_in_sink: ", "median 0.36 m at pit centroids, 90% sit in a closed "
         "depression, vs. 0.00 m / 1% at random background — a ~90× separation."),
        ("geomorphons: ", "106 of 110 pits fall in concave landform classes "
         "(depression / valley / hollow)."),
    ])
    doc.add_paragraph(
        "Caveat: these were validated AT known pits (recall), not for precision. Before "
        "either is promoted into the model feature stack they must be recomputed at "
        "0.5 m and have their full-tile false-positive rate (culverts, natural kettles) "
        "measured."
    )

    # ---- 10. QC ----------------------------------------------------------
    doc.add_heading("10. Quality control & reproducibility", level=1)
    bullets([
        ("CRS discipline: ", "the CRS is read from each source and verified before any "
         "spatial operation; mismatches are flagged, never silently reprojected."),
        ("Bootstrap rule: ", "expensive processes are piloted on a small subset around "
         "a few known wells before scaling to a full tile."),
        ("Candidate labelling: ", "model outputs are always reported as 'candidate' / "
         "'probable' with a confidence score and distance to nearest known well — never "
         "as confirmed wells."),
        ("Documentation: ", "every iteration gets a docs/iterations/<name>.md write-up; "
         "results go on LEADERBOARD.md; an append-only analysis_log.md records every "
         "decision; a BACKLOG.md tracks deferred ideas."),
        ("Large-file hygiene: ", "any output ≥100 MB gets a .gitignore rule in the same "
         "change, audited with a find + git check-ignore sweep."),
    ])

    # ---- 11. summary -----------------------------------------------------
    doc.add_heading("11. Pipeline in one paragraph", level=1)
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.2)
    r = p.add_run(
        "Airborne USGS 3DEP LiDAR → filter to ASPRS ground class (PDAL CLI) → grid a "
        "bare-earth DEM at 0.5/1 m → compute terrain derivatives (WhiteboxTools/GDAL) "
        "→ stack 7 of them (lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, "
        "roughness_11) and z-score normalize → cut jittered patches around QGIS-labelled "
        "pit/pad polygons → train Mask R-CNN / U-Net / YOLO via transfer learning with "
        "a widened first conv → slide the trained model over the full tile, threshold + "
        "NMS the detections → grade with recall@IoU on a held-out test set → report "
        "matches as scored candidates, never confirmed wells. Streams are derived "
        "separately by D8 flow accumulation + a cross-section concavity road filter."
    )
    r.italic = True

    # ---- Appendix A: what the model scripts actually do ------------------
    doc.add_page_break()
    doc.add_heading("Appendix A — What the model scripts actually do, step by step",
                    level=1)
    doc.add_paragraph(
        "This traces the real operations in the pit Mask R-CNN pipeline: "
        "pits/_pit_maskrcnn.py (training), _instance_common.py (data + assembly "
        "helpers), and pits/_pit_maskrcnn_infer.py (full-tile inference). The pad "
        "pipeline is identical with patch size 384 and a single foreground class."
    )

    doc.add_heading("A1. Input preparation", level=2)
    bullets([
        ("load_feature_stats() ", "reads feature_stats.json and builds two length-7 "
         "vectors: the per-channel mean (mu) and standard deviation (sd) for the bands "
         "lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11 "
         "(sd floored at 1e-6 to avoid divide-by-zero)."),
        ("load_feature_array(mu, sd) ", "reads the entire features_pit_9t_05.tif stack "
         "(7 × ~9000 × 9000 float32 ≈ 2.27 GB) into RAM once, applies "
         "(array − mu) / sd per channel, and replaces NaN / nodata with 0 (the channel "
         "mean in normalized space). It is cached in a module-global so every patch is "
         "a fast in-RAM slice (~0.5 ms) instead of a ~160 ms file read."),
        ("load_pit_set(with_walls=True) ", "loads annotation polygons from "
         "annotations_proj.gpkg — pit_inside polygons become class 'floor', pit_outside "
         "become class 'wall' — and joins the train / val / test assignment from "
         "pit_dataset_manifest.csv (74 / 16 / 20)."),
    ])

    doc.add_heading("A2. Patch sampling (PitPatchDataset)", level=2)
    bullets([
        "Take the split's floor polygons and compute each polygon's centroid.",
        ("Train split: jittered_centers(centers, jitter_m=30, patches_per_inst=4) ",
         "replicates every centroid four times, each offset by a random vector up to "
         "30 m — yielding ~300 training centers from 74 pits. Val / test use the bare "
         "centroids, one deterministic patch each."),
        ("patch_window_around(cx, cy, parent_tf, 256) ", "converts a world centroid to "
         "a 256 × 256 pixel window (128 m at 0.5 m/px) on the feature grid."),
        ("slice_feat_patch(feat, win) ", "slices a (7, 256, 256) patch from the cached "
         "normalized array, zero-padding any part of the window past the tile edge."),
        ("polygons_intersecting(all_polys, win) ", "spatial-index query for every "
         "annotation polygon overlapping the window — it uses the full polygon set, not "
         "just the split, so a neighbouring pit caught in-frame is still masked."),
        ("build_maskrcnn_target(...) ", "for each polygon: clip it to the patch box, "
         "rasterize() it to a 256 × 256 uint8 binary mask, derive the xyxy box from the "
         "mask extent, and assign a class id (floor = 1, wall = 2). Returns the "
         "torchvision target dict {boxes, labels, masks}; empty patches return "
         "zero-length tensors."),
    ])

    doc.add_heading("A3. Model construction (build_model, in_channels=7, "
                    "num_classes=3)", level=2)
    bullets([
        ("maskrcnn_resnet50_fpn_v2(weights='DEFAULT') ", "instantiates the COCO-"
         "pretrained network (~45.9 M parameters)."),
        ("First-conv widening: ", "the stem conv backbone.body.conv1 (64 × 3 × 7 × 7) "
         "is replaced with a 64 × 7 × 7 × 7 conv. The pretrained RGB weights are copied "
         "into input channels 1–3; the 4 extra channels are warm-started from the mean "
         "of those RGB weights. All downstream COCO weights are retained."),
        ("Identity input transform: ", "transform.image_mean and image_std are set to "
         "0 and 1 over all 7 channels, because patches are already z-scored — the "
         "detector must not normalize them again."),
        ("Head replacement: ", "the box predictor (FastRCNNPredictor) and mask "
         "predictor (MaskRCNNPredictor) are reinitialised for 3 classes "
         "(background / floor / wall)."),
    ])

    doc.add_heading("A4. Training loop", level=2)
    bullets([
        ("Optimizer / schedule: ", "AdamW(lr=5e-4, weight_decay=1e-4) with a "
         "CosineAnnealingLR schedule over the epoch count."),
        ("train_one_epoch: ", "model in train() mode; each batch is moved to GPU; "
         "batches with no boxes are skipped; the forward pass returns Mask R-CNN's loss "
         "dict (RPN objectness + RPN box + classifier + box regression + mask losses), "
         "which are summed, back-propagated, gradient-clipped at max-norm 5.0, then the "
         "optimizer steps."),
        ("val_loss: ", "torchvision only emits losses in train() mode, so validation is "
         "run under train() + torch.no_grad() to get a comparable loss without taking a "
         "gradient step."),
        ("Checkpointing: ", "each epoch logs epoch / tr_loss / va_loss / lr / seconds "
         "to train_log.csv. Whenever val loss improves, best.pt is saved with the "
         "weights plus metadata: epoch, patch, num_classes, class_names, in_channels, "
         "channel list, mu, sd, val_loss, arch. (Best is usually epoch 0–1 — the small "
         "label set overfits fast.)"),
    ])

    doc.add_heading("A5. Full-tile inference (_pit_maskrcnn_infer.py)", level=2)
    bullets([
        ("Load: ", "best.pt is read, the model rebuilt with the stored in_channels / "
         "num_classes, weights loaded, and mu / sd recovered from the checkpoint."),
        ("sliding_windows(W, H, patch=256, overlap=64) ", "tiles the whole feature grid "
         "in 192-px steps, snapping the final row/column flush to the tile edge."),
        ("Per window: ", "slice the normalized patch, run the model in eval() mode → "
         "{boxes, scores, masks, labels}; keep detections with score ≥ 0.3; clamp each "
         "box into the patch, crop the soft mask to its box, and record "
         "{score, cls_id, box in tile-pixel coords, cropped mask}. Class ids map "
         "1 → floor, 2 → wall."),
        ("global_nms(detections, iou_thresh=0.4) ", "runs torchvision.ops.nms "
         "per class (floor and wall separately, so they don't suppress each other) to "
         "remove duplicates from the overlapping windows."),
        ("stitch_prob_raster (per class) ", "composites each detection's "
         "(score × soft mask) into a full-tile float32 raster by per-pixel maximum, "
         "writing pit_prob_floor.tif and pit_prob_wall.tif."),
        ("detections_to_gpkg ", "binarizes each mask at 0.5, polygonizes it with "
         "rasterio.features.shapes, and writes per-detection polygons + score (+ class) "
         "to instances.gpkg."),
    ])

    doc.add_heading("A6. Evaluation (per_instance_metrics, test split)", level=2)
    bullets([
        "For each held-out test ground-truth floor polygon, candidate predictions are "
        "found via spatial index and scored by IoU = intersection.area / union.area; "
        "the best-overlapping prediction is kept.",
        "A ground-truth pit counts as matched at IoU ≥ 0.1. The script reports "
        "recall at IoU 0.1 / 0.3 / 0.5 plus mean and median best-IoU, written to "
        "test_metrics.json and test_per_pit.csv.",
    ])

    # ---- Appendix B: what the stream scripts actually do -----------------
    doc.add_heading("Appendix B — What the stream scripts actually do, step by step",
                    level=1)

    doc.add_heading("B1. Network extraction — build/_build_streams_9t.py "
                    "(WhiteboxTools)", level=2)
    bullets([
        ("Condition the surface: ", "reuse the cached dem_breached_9t_1m.tif if it "
         "exists; otherwise run breach_depressions_least_cost(dist=50, "
         "flat_increment=1e-3) once on the raw DEM and cache the result. Breaching "
         "carves outlets through spurious sinks so flow is continuous."),
        ("d8_pointer(dem=breached) ", "computes the D8 flow-direction grid (each cell "
         "points to its single steepest-descent neighbour)."),
        ("d8_flow_accumulation(out_type='cells', log=False) ", "counts how many upslope "
         "cells drain through each cell."),
        ("extract_streams(flow_accum, threshold=5000) ", "keeps cells whose accumulated "
         "flow ≥ 5000 cells as the raw stream raster."),
        ("Seed cleanup: ", "the WhiteboxTools NoData-background raster is converted to a "
         "clean 0/1 uint8 seed raster (stream_seed_t5000_9t_1m.tif, LZW-compressed, "
         "nodata 255)."),
        ("raster_streams_to_vector(streams, d8_pntr) ", "traces the raster channels "
         "into linestrings. A .prj is written with the explicit NAD83(2011) / UTM 17N "
         "WKT, then geopandas forces set_crs(epsg=6346) and writes both a Shapefile and "
         "a GeoPackage. Temp pointer/accumulation/raw rasters are deleted."),
    ])
    doc.add_paragraph("Result: streams_t5000_9t_1m = 2,693 lines, 274.5 km.")

    doc.add_heading("B2. Cross-section road filter — "
                    "build/_filter_streams_xsec_9t.py", level=2)
    doc.add_paragraph(
        "Runs on the RAW dem_9t_1m.tif (not the breached one — breaching fills the "
        "channels this test depends on). The DEM is read into a numpy array with nodata "
        "set to NaN."
    )
    doc.add_paragraph("Core concavity test — _xdrop(line, dem, tf, step, perp_m):")
    bullets([
        ("_resample(line, step) ", "interpolates evenly spaced points along the line "
         "every `step` metres."),
        ("Tangent + perpendicular: ", "the local tangent is computed from np.gradient of "
         "the x and y coordinates, normalised, then rotated 90° to give the "
         "perpendicular unit vector (px, py) = (−ty, tx)."),
        ("_sample_dem ", "reads the DEM elevation at the centre point and at ±perp_m "
         "(5 m) along the perpendicular on each side (nearest-cell lookup via the "
         "inverse affine transform)."),
        ("Concavity statistic: ", "drop = (z_left + z_right) / 2 − z_center, and the "
         "function returns the median of `drop` over all valid samples. A channel sits "
         "in a V/U valley so the median is positive; a flat or raised road cut gives "
         "≈ 0 or negative."),
    ])
    doc.add_paragraph("Two passes run together against the threshold "
                      "xdrop_m < 0.30 m → 'roadlike':")
    bullets([
        ("run_per_line ", "gives one verdict per whole line. Lines shorter than 30 m or "
         "with too few valid samples are tagged 'short'; sampling step is 5 m. Writes "
         "three Shapefiles: _xsec (all lines with xdrop_m + klass attributes), "
         "_kept_xsec (non-roadlike), and _roadlike_xsec (dropped)."),
        ("run_chunked ", "first cuts each line into ~25 m segments with _chunk_line "
         "(re-densified every 5 m internally), then judges each segment independently "
         "with a 2.5 m step and 15 m minimum length. This catches lines that are part "
         "stream and part road. Same three output sets with a chunked_ prefix, carrying "
         "parent_id / seg_idx / seg_len_m attributes."),
    ])
    table(
        ["Pass", "Kept features", "Kept length"],
        [
            ["per-line", "1,497 lines", "97.9 km"],
            ["per-chunk", "4,973 chunks", "88.8 km"],
        ],
        widths=[2.4, 2.0, 1.8],
    )

    doc.save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

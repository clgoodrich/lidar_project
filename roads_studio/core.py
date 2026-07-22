"""Roads Studio — engine layer.

Thin wrapper over the existing road post-processing arsenal in
``notebooks/wellsight_v2/build/_road_optimize.py``. That module already turns a
road-probability raster into vector centerlines via a configurable pipeline
(enhance -> threshold -> path-open -> skeleton -> prune -> reconnect -> island
filter). This layer just:

  * discovers every road_prob raster on disk and pairs it with its sibling
    drainage_prob / hillshade / slope,
  * loads one source into the ``D`` dict the pipeline expects,
  * runs the pipeline for a given knob config,
  * renders a preview PNG (hillshade + road overlay),
  * exports the chosen layer to GeoPackage + Shapefile for QGIS.

No algorithm lives here — the studio is purely a knob board over that engine.
"""
from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio

REPO = Path(__file__).resolve().parent.parent
_BUILD = REPO / "notebooks" / "wellsight_v2" / "build"

import sys

if str(_BUILD) not in sys.path:
    sys.path.insert(0, str(_BUILD))

import _road_optimize as ropt  # noqa: E402  (path set above)

DST_CRS = ropt.DST_CRS
TILES = REPO / "data" / "derivatives" / "tiles"
D3X3 = TILES / "data_3x3" / "westernpa_d20"
R9 = TILES / "9t"
EXPORTS = Path(__file__).resolve().parent / "exports"
EXPORTS.mkdir(exist_ok=True)


# ===========================================================================
# discovery
# ===========================================================================
@dataclass
class Source:
    """One (block, model) pair pointing at a road_prob raster + siblings."""

    block: str
    model: str
    road: Path
    drainage: Path | None
    hillshade: Path | None
    slope: Path | None

    @property
    def key(self) -> str:
        return f"{self.block}:{self.model}"


# friendly labels for the 9t single-block variant dirs
_MODEL_LABELS = {
    "road_unet_1m_corrected": "champion (corrected)",
    "road_unet_1m_recall": "recall",
    "road_sweep_202607/cldice": "sweep · cldice",
    "road_sweep_202607/boundary": "sweep · boundary",
    "road_sweep_202607/alpha078": "sweep · alpha078",
    "road_sweep_202607/orient": "sweep · orient",
    "drainage_unet_1m": "drainage-unet",
}


def _first(pat_dir: Path, glob: str) -> Path | None:
    hits = sorted(pat_dir.glob(glob))
    return hits[0] if hits else None


def discover() -> dict[str, list[Source]]:
    """Return {block_id: [Source, ...]} for every block that has a road_prob.

    Each data_3x3 block contributes its in-block 'deployed' model. Block 613590
    additionally gets every 9t model variant that produced a 613590 prob, so the
    studio can compare models on the same ground.
    """
    out: dict[str, list[Source]] = {}
    for d in sorted(D3X3.iterdir()):
        if not d.is_dir():
            continue
        block = d.name
        road = _first(d, "road_prob_*_1m.tif")
        if road is None:
            continue
        out.setdefault(block, []).append(
            Source(
                block=block,
                model="deployed",
                road=road,
                drainage=_first(d, "drainage_prob_*_1m.tif"),
                hillshade=_first(d, "hillshade_*_1m.tif"),
                slope=_first(d, "slope_*_1m.tif"),
            )
        )

    # 613590 model variants living under tiles/9t/<dir>/road_prob_613590_1m.tif
    blk = "613590"
    bdir = D3X3 / blk
    hs = _first(bdir, "hillshade_*_1m.tif")
    sl = _first(bdir, "slope_*_1m.tif")
    for road in sorted(R9.glob("**/road_prob_613590_1m.tif")):
        rel = road.parent.relative_to(R9).as_posix()
        label = _MODEL_LABELS.get(rel, rel)
        out.setdefault(blk, []).append(
            Source(
                block=blk,
                model=label,
                road=road,
                drainage=_first(road.parent, "drainage_prob_613590_1m.tif"),
                hillshade=hs,
                slope=sl,
            )
        )
    return out


# ===========================================================================
# load one source -> D dict for the pipeline
# ===========================================================================
@dataclass
class Loaded:
    src: Source
    D: dict
    hillshade: np.ndarray | None
    extent: tuple  # (xmin, xmax, ymin, ymax) for imshow


def _decimate_shape(r, scale: int) -> tuple[int, int]:
    return max(1, r.height // scale), max(1, r.width // scale)


def load(src: Source, use_drainage: bool, scale: int = 1) -> Loaded:
    """Load a source into the pipeline ``D`` dict.

    ``scale`` decimates the rasters for a snappy live preview (2 = half res,
    4 = quarter). Export always re-loads at scale=1 for a full-resolution layer.
    """
    from affine import Affine
    from rasterio.enums import Resampling

    with rasterio.open(src.road) as r:
        nh, nw = _decimate_shape(r, scale)
        prob = r.read(1, out_shape=(nh, nw), resampling=Resampling.bilinear).astype(np.float32)
        sx, sy = r.width / nw, r.height / nh
        tf = r.transform * Affine.scale(sx, sy)
        crs = r.crs
        res = r.res[0] * sx
        b = r.bounds
    extent = (b.left, b.right, b.bottom, b.top)

    # arg raster: pipeline treats class==2 as drainage and masks it out
    # (margin = arg != 2). Synthesize it from drainage_prob when suppression on.
    arg = None
    if use_drainage and src.drainage and src.drainage.exists():
        with rasterio.open(src.drainage) as r:
            drain = r.read(1, out_shape=(nh, nw), resampling=Resampling.bilinear).astype(np.float32)
        if drain.shape == prob.shape:
            arg = np.where(drain > prob, 2, 0).astype(np.uint8)

    slope = None
    if src.slope and src.slope.exists():
        with rasterio.open(src.slope) as r:
            slope = r.read(1, out_shape=(nh, nw), resampling=Resampling.bilinear).astype(np.float32)

    hill = None
    if src.hillshade and src.hillshade.exists():
        with rasterio.open(src.hillshade) as r:
            hh, hw = _decimate_shape(r, scale)
            hill = r.read(1, out_shape=(hh, hw), resampling=Resampling.bilinear).astype(np.float32)

    D = dict(prob=prob, arg=arg, slope=slope, tf=tf, crs=crs, res=res)
    return Loaded(src=src, D=D, hillshade=hill, extent=extent)


# ===========================================================================
# extract + score
# ===========================================================================
def to_pipeline_cfg(ucfg: dict, res: float) -> dict:
    """Translate the studio's scale-independent knobs into the pixel-unit cfg
    the pipeline expects. Area/length knobs are in map units (m2 / m) so a
    half- or quarter-res preview behaves like the full-res export."""
    res = res or 1.0
    cfg = dict(
        enhance=ucfg["enhance"],
        thresh=ucfg["thresh"],
        t=ucfg.get("t", 0.5),
        lo=ucfg.get("lo", 0.3),
        hi=ucfg.get("hi", 0.6),
        skel=ucfg["skel"],
        spur=ucfg.get("spur", 20),          # meters (map units) — as-is
        island=ucfg.get("island", 120),      # meters — as-is
        reconnect=ucfg.get("reconnect", "none"),
        min_px=max(1, int(round(ucfg.get("min_area_m2", 40) / (res * res)))),
        simplify_m=ucfg.get("simplify_m", 0.0),   # map units — Douglas-Peucker tol
        smooth=int(ucfg.get("smooth", 0)),          # Chaikin passes
    )
    if ucfg.get("slope_max"):
        cfg["slope_max"] = ucfg["slope_max"]
    if ucfg.get("pathopen"):
        cfg["pathopen"] = True
        cfg["po_len"] = max(3, int(round(ucfg.get("po_len_m", 14) / res)))
    return cfg


def extract(loaded: Loaded, ucfg: dict):
    """Run the road pipeline for the given studio knobs -> GeoDataFrame."""
    cfg = to_pipeline_cfg(ucfg, loaded.D["res"])
    return ropt.run_pipeline(loaded.D, cfg)


def stats(gdf) -> dict:
    if gdf is None or len(gdf) == 0:
        return dict(km=0.0, segments=0)
    km = float(gdf.geometry.length.sum() / 1000.0)
    return dict(km=round(km, 3), segments=int(len(gdf)))


# ===========================================================================
# render preview
# ===========================================================================
def render_png(loaded: Loaded, gdf, background: str = "hillshade") -> str:
    """Return a base64 data-URI PNG: background raster + road overlay."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if background == "hillshade" and loaded.hillshade is not None:
        bg = loaded.hillshade
        cmap = "gray"
    else:
        bg = loaded.D["prob"]
        cmap = "magma"

    h, w = bg.shape
    dpi = 100
    fig_w = min(9.0, max(4.0, w / 200))
    fig_h = fig_w * h / w
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.imshow(bg, cmap=cmap, extent=loaded.extent, origin="upper",
              interpolation="nearest")
    if gdf is not None and len(gdf):
        for geom in gdf.geometry:
            if geom.is_empty:
                continue
            geoms = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
            for g in geoms:
                xs, ys = g.xy
                ax.plot(xs, ys, color="#00e5ff", linewidth=1.4, solid_capstyle="round")
    ax.set_xlim(loaded.extent[0], loaded.extent[1])
    ax.set_ylim(loaded.extent[2], loaded.extent[3])
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ===========================================================================
# export
# ===========================================================================
def export(gdf, src: Source, cfg: dict, tag: str) -> dict:
    """Write GeoPackage (+ Shapefile) for QGIS. Returns paths written."""
    if gdf is None or len(gdf) == 0:
        raise ValueError("nothing to export — the current knobs produced 0 roads")
    safe_model = re.sub(r"[^a-z0-9]+", "_", src.model.lower()).strip("_")
    base = f"roads_{src.block}_{safe_model}_{tag}"
    gpkg = EXPORTS / f"{base}.gpkg"
    shp = EXPORTS / f"{base}.shp"
    out = gdf.copy()
    out["length_m"] = out.geometry.length.round(2)
    out.to_file(gpkg, layer="roads", driver="GPKG")
    out.to_file(shp, driver="ESRI Shapefile")
    # sidecar config so the layer is reproducible
    (EXPORTS / f"{base}.cfg.txt").write_text(
        f"source: {src.road}\nblock: {src.block}\nmodel: {src.model}\n"
        f"config: {cfg}\n",
        encoding="utf-8",
    )
    return dict(gpkg=str(gpkg), shp=str(shp), segments=len(out),
                km=round(float(out.geometry.length.sum() / 1000), 3))

"""Small helpers shared by the 4.7 drone lidar density ladder scripts.

Purpose. Config loading, path resolution through expkit, clear failures for assumed inputs, per-script provenance,
point counting by class with laspy, and gridded counts through the PDAL CLI (run_pdal in _common).
Inputs. expansions/4_modalities/4_7_drone_lidar/src/config_4_7.json
Outputs. None.
Run. Imported only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "_shared" / "src"))
import expkit as ek  # noqa: E402
from _common import run_pdal, read_tif  # noqa: E402  (expkit puts notebooks/wellsight_v2 on sys.path)

CFG_PATH = HERE / "config_4_7.json"


def load_cfg(path=None) -> dict:
    return json.loads(Path(path or CFG_PATH).read_text(encoding="utf-8"))


def resolve(spec: dict, **fmt) -> Path:
    rel = spec["rel"].format(**fmt) if fmt else spec["rel"]
    if "key" in spec:
        return ek.path_for(spec["key"]) / rel
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / rel
    if "area" in spec:
        return ek.area_dir(spec["area"]) / rel
    raise KeyError(spec)


def need(path, what: str, spec: dict | None = None) -> Path:
    path = Path(path)
    if path.exists():
        return path
    msg = f"missing input: {what}\n  expected at {path}"
    if spec:
        if spec.get("schema"):
            msg += f"\n  assumed schema (config_4_7.json): {', '.join(spec['schema'])}"
        if spec.get("note"):
            msg += f"\n  note: {spec['note']}"
        if spec.get("assumed"):
            msg += "\n  this input is assumed, not held (VERIFY). It arrives with the NETL reply (R2)."
    raise FileNotFoundError(msg)


def prov(out_dir, script: str, inputs=None, outputs=None, params=None, seeds=None) -> Path:
    d = Path(out_dir) / "_provenance" / script
    d.mkdir(parents=True, exist_ok=True)
    return ek.write_provenance(d, inputs=inputs, outputs=outputs, params=params, seeds=seeds)


def _horiz_epsg(crs):
    """EPSG of the horizontal part. Compound CRS (EPSG:6346 + NAVD88) report None from to_epsg()."""
    if crs is None:
        return None
    e = crs.to_epsg()
    if e is None and crs.is_compound:
        e = crs.sub_crs_list[0].to_epsg()
    return e


def las_info(path: Path, ground_class: int = 2) -> dict:
    """Header facts and counts by class, read in chunks."""
    import laspy
    with laspy.open(str(path)) as f:
        h = f.header
        crs = h.parse_crs()
        counts: dict[int, int] = {}
        for pts in f.chunk_iterator(2_000_000):
            u, c = np.unique(np.asarray(pts.classification), return_counts=True)
            for k, v in zip(u.tolist(), c.tolist()):
                counts[k] = counts.get(k, 0) + v
        info = {"path": str(path), "version": f"{h.version.major}.{h.version.minor}",
                "point_format": int(h.point_format.id), "n_points": int(h.point_count),
                "crs": crs.to_string() if crs else None, "epsg": _horiz_epsg(crs),
                "mins": [float(v) for v in h.mins], "maxs": [float(v) for v in h.maxs],
                "scales": [float(v) for v in h.scales], "class_counts": {str(k): v for k, v in sorted(counts.items())},
                "n_ground": int(counts.get(ground_class, 0))}
    info["n_nonground"] = info["n_points"] - info["n_ground"]
    return info


def grid_of(mins, maxs, res: float):
    """Snap a header extent to a res grid: (x0, y0, W, H)."""
    x0, y0 = np.floor(mins[0] / res) * res, np.floor(mins[1] / res) * res
    W = int(np.ceil((maxs[0] - x0) / res)) or 1
    H = int(np.ceil((maxs[1] - y0) / res)) or 1
    return float(x0), float(y0), W, H


def count_raster(las: Path, out_tif: Path, res: float, grid, limits: str | None, tmp_dir: Path, label: str) -> np.ndarray:
    """Points per cell through PDAL writers.gdal (output_type count, binmode so each point counts in one cell only;
    without binmode the default radius res*sqrt(2) counts a point in several cells). limits is a filters.range expression."""
    x0, y0, W, H = grid
    st = [{"type": "readers.las", "filename": str(las)}]
    if limits:
        st.append({"type": "filters.range", "limits": limits})
    st.append({"type": "writers.gdal", "filename": str(out_tif), "output_type": "count", "binmode": True, "resolution": res,
               "origin_x": x0, "origin_y": y0, "width": W, "height": H, "data_type": "float32", "nodata": -9999})
    run_pdal(st, label=label, tmp_dir=tmp_dir, verbose=False)
    a = read_tif(out_tif)
    return np.nan_to_num(a, nan=0.0)


def rung_sfx(tag: str, rate: float, seed_idx: int, res: float) -> str:
    """oc_drone_r0p50_s1_05: rate and seed in the name because rungs sit side by side."""
    return f"{tag}_drone_r{rate:.2f}".replace(".", "p") + f"_s{seed_idx}_" + ("05" if res == 0.5 else f"{res:g}m".replace(".", "p"))

"""Small helpers shared by the 4.8 leaf-off optical scripts.

Purpose. Config, path resolution through expkit, clear failures for assumed inputs, per-script provenance, chip
fetchers (PASDA ArcGIS export, NAIP STAC, local GeoTIFF) and the image measures used by several stages (blank test,
cloud and shadow shares, visible ground fraction by excess green and brightness).
The PASDA URL and layer ids are imported from notebooks/wellsight_v2/s5_eval/_pit_leafoff_geotiff_9t.py and the
NAIP signer from _pit_naip_chip_9t.py, so there is one copy of each.
Inputs. expansions/4_modalities/4_8_leafoff_optical/src/config_4_8.json
Outputs. None.
Run. Imported only.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "_shared" / "src"))
import expkit as ek  # noqa: E402

CFG_PATH = HERE / "config_4_8.json"
S5_EVAL = ek.REPO / "notebooks" / "wellsight_v2" / "s5_eval"


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
            msg += f"\n  assumed schema (config_4_8.json): {', '.join(spec['schema'])}"
        if spec.get("note"):
            msg += f"\n  note: {spec['note']}"
        if spec.get("assumed"):
            msg += "\n  this input is assumed, not held (VERIFY)."
    raise FileNotFoundError(msg)


def prov(out_dir, script: str, inputs=None, outputs=None, params=None, seeds=None) -> Path:
    d = Path(out_dir) / "_provenance" / script
    d.mkdir(parents=True, exist_ok=True)
    return ek.write_provenance(d, inputs=inputs, outputs=outputs, params=params, seeds=seeds)


# ----------------------------------------------------------------------------- season
def is_leafoff(date: str | None, months) -> bool | None:
    """True or False from a YYYY-MM-DD or YYYYMMDD date. None when the date is unknown."""
    if not date or str(date) in ("nan", "None"):
        return None
    s = str(date).replace("-", "")
    return int(s[4:6]) in set(months)


# ----------------------------------------------------------------------------- fetchers
def fetch_chip(source_id: str, src: dict, bbox, px: int, crs: str = "EPSG:6346"):
    """(rgb uint8 H x W x 3 or None, info dict). Network only for arcgis_export and naip_stac."""
    x0, y0, x1, y1 = bbox
    try:
        if src["kind"] == "local":
            import rasterio
            from rasterio.enums import Resampling
            from rasterio.windows import from_bounds
            p = resolve(src["path"]) if isinstance(src["path"], dict) else Path(src["path"])
            with rasterio.open(need(p, f"local mosaic for {source_id}", src)) as d:
                ek.assert_crs(d, crs)
                w = from_bounds(x0, y0, x1, y1, transform=d.transform)
                a = d.read([1, 2, 3], window=w, out_shape=(3, px, px), boundless=True, fill_value=0,
                           resampling=Resampling.bilinear)
            return np.moveaxis(a, 0, -1).astype(np.uint8), {"date": src.get("date")}
        if src["kind"] == "arcgis_export":
            import io
            import requests
            from PIL import Image
            sys.path.insert(0, str(S5_EVAL))
            from _pit_leafoff_geotiff_9t import URL
            r = requests.get(URL, params=dict(bbox=f"{x0},{y0},{x1},{y1}", bboxSR=6346, imageSR=6346, size=f"{px},{px}",
                                              layers=f"show:{src['layer']}", format="png", f="image"), timeout=90)
            r.raise_for_status()
            return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB")), {"date": src.get("date")}
        if src["kind"] == "naip_stac":
            return _naip(src, bbox, px)
    except FileNotFoundError:
        raise
    except Exception as e:  # noqa: BLE001  unavailable is a status, not a crash
        return None, {"error": f"{type(e).__name__}: {e}"[:300]}
    raise ValueError(f"unknown source kind {src['kind']}")


def _naip(src: dict, bbox, px: int):
    import rasterio
    import requests
    from pyproj import Transformer
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds
    sys.path.insert(0, str(S5_EVAL))
    from _pit_naip_chip_9t import STAC, sign
    x0, y0, x1, y1 = bbox
    lon, lat = Transformer.from_crs(6346, 4326, always_xy=True).transform((x0 + x1) / 2, (y0 + y1) / 2)
    items = requests.post(f"{STAC}/search", json={"collections": ["naip"], "intersects": {"type": "Point", "coordinates": [lon, lat]},
                                                   "limit": 20}, timeout=60).json()["features"]
    by = {f["properties"]["datetime"][:10].replace("-", ""): f for f in items}
    year = next((y for y in src["years"] if y in by), None)
    if year is None:
        return None, {"error": "no NAIP item for the listed dates"}
    with rasterio.open(sign(by[year]["assets"]["image"]["href"])) as s:
        t = Transformer.from_crs(6346, s.crs, always_xy=True)
        (a0, b0), (a1, b1) = t.transform(x0, y0), t.transform(x1, y1)
        w = from_bounds(a0, b0, a1, b1, transform=s.transform)
        a = s.read([1, 2, 3], window=w, out_shape=(3, px, px), boundless=True, fill_value=0, resampling=Resampling.bilinear)
    return np.moveaxis(a, 0, -1).astype(np.uint8), {"date": year}


# ----------------------------------------------------------------------------- image measures
def image_measures(rgb: np.ndarray, pr: dict, mask: np.ndarray | None = None) -> dict:
    """Blank test, cloud and shadow shares, and visible ground fraction (inside mask when given)."""
    a = rgb.astype(float)
    nod = (a.sum(-1) == 0) | (a.min(-1) >= 254)
    s = a.sum(-1) + 1e-6
    r, g, b = a[..., 0] / s, a[..., 1] / s, a[..., 2] / s
    exg = 2 * g - r - b
    bright = a.mean(-1)
    lo, hi = pr["ground_brightness"]
    ground = (exg < pr["exg_max_ground"]) & (bright >= lo) & (bright <= hi) & ~nod
    valid = ~nod
    m = valid if mask is None else (valid & mask)
    return {"nodata_share": float(nod.mean()), "mean": float(bright[valid].mean()) if valid.any() else 255.0,
            "std": float(bright[valid].std()) if valid.any() else 0.0,
            "saturated_share": float((a[valid].min(-1) >= 245).mean()) if valid.any() else 0.0,
            "dark_share": float((bright[valid] < 25).mean()) if valid.any() else 0.0,
            "visible_ground_fraction": float(ground[m].mean()) if m.any() else float("nan"),
            "green_share": float((exg[valid] > 0.08).mean()) if valid.any() else 0.0}


def chip_status(rgb, info: dict, meas: dict | None, pr: dict, offset_m: float | None) -> tuple[str, str]:
    """(status, reason). Order matters. Missing data is never a negative."""
    if rgb is None:
        return "unavailable", info.get("error", "no image")
    if meas["nodata_share"] > pr["nodata_share_blank"] or meas["mean"] >= pr["blank_mean"] or meas["std"] < pr["blank_std"]:
        return "blank", f"nodata {meas['nodata_share']:.2f}, mean {meas['mean']:.0f}, std {meas['std']:.1f}"
    lo = is_leafoff(info.get("date"), pr["leafoff_months"])
    if lo is None:
        return "undated", "flight date not verified"
    if not lo:
        return "off-season", f"date {info.get('date')}"
    if offset_m is not None and offset_m > pr["max_offset_m"]:
        return "unregistered", f"offset {offset_m:.1f} m"
    if meas["saturated_share"] > pr["saturated_share_cloud"] or meas["dark_share"] > pr["dark_share_shadow"]:
        return "cloud or shadow", f"saturated {meas['saturated_share']:.2f}, dark {meas['dark_share']:.2f}"
    if not np.isfinite(meas["visible_ground_fraction"]) or meas["visible_ground_fraction"] < pr["visible_ground_cutoff"]:
        return "low visible ground", f"fraction {meas['visible_ground_fraction']:.2f}"
    return "usable", "" if offset_m is not None else "registration not yet measured"


def today() -> str:
    return dt.date.today().isoformat()

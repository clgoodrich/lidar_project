"""Small helpers shared by the 4.6 historic maps and aerials scripts.

Purpose. Load config_4_6.json, resolve its path specs through expkit, and fail with a clear message when an assumed
input is missing. No processing happens here.
Inputs. expansions/4_modalities/4_6_historic_maps_aerials/src/config_4_6.json
Outputs. None.
Run. Imported only (python -c "import _hist_kit_4_6" from this folder to check it loads).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "_shared" / "src"))
import expkit as ek  # noqa: E402

CFG_PATH = HERE / "config_4_6.json"


def load_cfg(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or CFG_PATH).read_text(encoding="utf-8"))


def resolve(spec: dict, **fmt) -> Path:
    """{key, rel} -> path_for(key)/rel. {exp, rel} -> expansion folder/rel. {area, rel} -> data/<area>/rel."""
    rel = spec["rel"].format(**fmt) if fmt else spec["rel"]
    if "key" in spec:
        return ek.path_for(spec["key"]) / rel
    if "exp" in spec:
        return ek.exp_dir(spec["exp"]) / rel
    if "area" in spec:
        return ek.area_dir(spec["area"]) / rel
    raise KeyError(f"path spec needs key, exp or area: {spec}")


def need(path: Path, what: str, spec: dict | None = None) -> Path:
    """Return path if it exists, else stop with the input name and its assumed schema."""
    path = Path(path)
    if path.exists():
        return path
    msg = f"missing input: {what}\n  expected at {path}"
    if spec:
        if spec.get("schema"):
            msg += f"\n  assumed schema (config_4_6.json): {', '.join(spec['schema'])}"
        if spec.get("note"):
            msg += f"\n  note: {spec['note']}"
        if spec.get("assumed"):
            msg += "\n  this input is assumed, not held (VERIFY). Supply it or point the config at it."
    raise FileNotFoundError(msg)


def bbox_lonlat(bbox, crs: str = "EPSG:6346"):
    """(west, south, east, north) in EPSG:4326 for a projected bbox, for catalogue searches."""
    from pyproj import Transformer
    t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    x0, y0, x1, y1 = bbox
    xs, ys = zip(*[t.transform(x, y) for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))])
    return min(xs), min(ys), max(xs), max(ys)


def cover_share(w, s, e, n, box) -> float:
    """Share of box (west, south, east, north) covered by the rectangle (w, s, e, n). Same CRS."""
    bw, bs, be, bn = box
    iw, ie = max(w, bw), min(e, be)
    is_, in_ = max(s, bs), min(n, bn)
    if ie <= iw or in_ <= is_:
        return 0.0
    return (ie - iw) * (in_ - is_) / ((be - bw) * (bn - bs))


def prov(out_dir: Path, script: str, inputs=None, outputs=None, params=None, seeds=None) -> Path:
    """_PROVENANCE.json for one script, kept apart per script: <out_dir>/_provenance/<script>/_PROVENANCE.json."""
    d = Path(out_dir) / "_provenance" / script
    d.mkdir(parents=True, exist_ok=True)
    return ek.write_provenance(d, inputs=inputs, outputs=outputs, params=params, seeds=seeds)

"""Small shared helpers for the 5.x task expansions (5.1 to 5.6). Library, not a script.

Purpose
    One place for config loading, path-spec resolution, clear missing-input failures, the 9t block grid,
    DEP record loading and evidence-level tagging. Every 5.x script imports it so the six expansions
    behave the same way. Statistics come from expansions/_shared/src/expkit.py, not from here.

Path specs (used in every config_<id>.json, so no script spells a data path)
    "@<paths.toml key>/<rel>"    resolves to ek.path_for(key) / rel        e.g. "@results_9t/pit/x.gpkg"
    "@exp:<id>/<rel>"            resolves to ek.exp_dir(id) / rel           e.g. "@exp:5.6/data/processed/x.gpkg"
    anything else                a plain filesystem path (tests use tmp paths this way)

Import from any 5.x src/ script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
    import _task5_helpers as th

Inputs / outputs
    None by itself.
Run
    Not runnable. Imported by the 5.x scripts. Tested by expansions/5_tasks/5_6_record_association/src/test_5_6.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_SHARED = Path(__file__).resolve().parents[3] / "_shared" / "src"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
import expkit as ek  # noqa: E402

CRS = "EPSG:6346"
EVIDENCE = {"a": "drawn feature", "b": "historical", "c": "steel", "d": "confirmed well"}
CONDITIONAL = "conditional on the feature model"


class MissingInput(SystemExit):
    """Raised when an assumed or upstream input is not on disk. Exits non-zero with a message naming it."""

    def __init__(self, name: str, path, hint: str = ""):
        msg = f"MISSING INPUT [{name}]: {path}"
        if hint:
            msg += f"\n  -> {hint}"
        super().__init__(msg)
        self.name, self.path, self.hint = name, path, hint


# ----------------------------------------------------------------------------- config and paths
def resolve(spec) -> Path:
    """Resolve a path spec (see module docstring)."""
    if spec is None:
        raise ValueError("path spec is None")
    s = str(spec)
    if s.startswith("@exp:"):
        exp_id, _, rel = s[5:].partition("/")
        return ek.exp_dir(exp_id) / rel
    if s.startswith("@"):
        key, _, rel = s[1:].partition("/")
        return ek.path_for(key) / rel if rel else ek.path_for(key)
    return Path(s)


def load_cfg(script_file: str, override: str | None = None) -> dict:
    """Read config_<id>.json beside the script, or an override path (tests, sensitivity runs)."""
    if override:
        p = Path(override)
    else:
        hits = sorted(Path(script_file).resolve().parent.glob("config_*.json"))
        if len(hits) != 1:
            raise FileNotFoundError(f"expected one config_*.json beside {script_file}, found {hits}")
        p = hits[0]
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["_config_path"] = str(p)
    return cfg


def inp(cfg: dict, name: str, must_exist: bool = True) -> Path:
    """Resolve cfg['inputs'][name]. If must_exist and absent, fail naming the input and its hint."""
    ent = cfg["inputs"][name]
    spec, hint = (ent["path"], ent.get("hint", "")) if isinstance(ent, dict) else (ent, "")
    p = resolve(spec)
    if must_exist and not p.exists():
        raise MissingInput(name, p, hint)
    return p


def has(cfg: dict, name: str) -> bool:
    try:
        return inp(cfg, name, must_exist=False).exists()
    except KeyError:
        return False


def outp(cfg: dict, name: str) -> Path:
    """Resolve cfg['outputs'][name] and create its parent folder."""
    p = resolve(cfg["outputs"][name])
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_json(path: Path, obj) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default), encoding="utf-8")
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def require_columns(df, cols, label: str) -> None:
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise SystemExit(f"SCHEMA MISMATCH [{label}]: missing columns {miss}. Present: {list(df.columns)[:30]}")


# ----------------------------------------------------------------------------- vectors
def read_vector(path: Path, layer: str | None = None, crs: str = CRS):
    """Read a vector, reproject to the project CRS when it has another one, and assert the result."""
    import geopandas as gpd
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if g.crs is None:
        raise AssertionError(f"{path} has no CRS")
    if g.crs.to_string() != crs:
        g = g.to_crs(crs)
    ek.assert_crs(g, crs)
    return g


# ----------------------------------------------------------------------------- 9t block grid
def block_cells(xy: np.ndarray, origin=(619500.0, 4593000.0), size: float = 375.0) -> np.ndarray:
    """(ix, iy) grid index of each point. 375 m blocks on 9t, origin at the tile's lower-left."""
    xy = np.atleast_2d(np.asarray(xy, float))
    return np.floor((xy - np.asarray(origin, float)) / size).astype(int)


def in_cells(xy: np.ndarray, cells: set, origin=(619500.0, 4593000.0), size: float = 375.0) -> np.ndarray:
    ij = block_cells(xy, origin, size)
    return np.array([(int(a), int(b)) in cells for a, b in ij], bool)


def block_id_of(xy: np.ndarray, blocks_gdf) -> np.ndarray:
    """block_id of each point by polygon containment (-1 when outside every block)."""
    import geopandas as gpd
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xy[:, 0], xy[:, 1]), crs=blocks_gdf.crs)
    j = gpd.sjoin(pts, blocks_gdf[["block_id", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated(keep="first")]
    return j["block_id"].fillna(-1).astype(int).to_numpy()


# ----------------------------------------------------------------------------- DEP records
def load_dep(path: Path, bbox=None, crs: str = CRS):
    """DEP well export (read-only). Optional bbox (xmin, ymin, xmax, ymax). Adds x, y. Never writes back."""
    w = read_vector(path, crs=crs)
    w = w[~w.geometry.is_empty & w.geometry.notna()].copy()
    w["x"], w["y"] = w.geometry.x, w.geometry.y
    if bbox is not None:
        x0, y0, x1, y1 = bbox
        w = w[(w.x >= x0) & (w.x <= x1) & (w.y >= y0) & (w.y <= y1)].copy()
    return w


def status_group(series, groups: dict) -> np.ndarray:
    """Map WELL_STATU values to the config's group names. Unlisted statuses become 'other'."""
    inv = {s: g for g, ss in groups.items() for s in ss}
    return np.array([inv.get(v, "other") for v in series], dtype=object)


def tag(df, level: str, analysis: str = "exploratory"):
    """Stamp evidence level and analysis type on an output table (fw_00 section 9). Levels never merge."""
    if level not in EVIDENCE:
        raise ValueError(level)
    df = df.copy()
    df["evidence_level"] = level
    df["analysis"] = analysis
    return df

"""Shared helpers for the 6.1 screening package (also used by 6.4 through --profile hydrogen).

Purpose
    Config loading, path resolution through expkit, profile selection, run folders, record and
    candidate readers, and the evidence-level contract. Every 6.1 stage script imports this.
Inputs
    expansions/6_adjacent/6_1_co2_geothermal/src/config_6_1.json (or any config passed with --config)
Outputs
    None directly. run_dir() creates data/<area>/results/screening/<subdir>/<run_id>/ through ek.new_run.
Run
    Not a script. Imported by the _co2_*.py stage scripts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

DEFAULT_CONFIG = HERE / "config_6_1.json"
EVIDENCE = {"a": "a drawn or detected surface feature", "b": "historical or agency record",
            "c": "steel anomaly", "d": "confirmed well", "coverage": "coverage, not evidence",
            "context": "context polygon, not evidence", "limits": "limits table"}


class MissingInput(FileNotFoundError):
    """An assumed input is not on disk. The message names the input and its schema."""


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    return json.loads(p.read_text(encoding="utf-8"))


def load_profile(cfg: dict, profile: str = "co2", profile_file: str | Path | None = None) -> dict:
    """A profile is a dict in cfg['profiles'] or a JSON file (6.4 passes its own)."""
    if profile_file:
        prof = json.loads(Path(profile_file).read_text(encoding="utf-8"))
        if "profiles" in prof:
            prof = prof["profiles"][profile]
    else:
        prof = cfg["profiles"][profile]
    base = cfg["profiles"].get("co2", {})
    if prof.get("extends") == "co2":
        merged = dict(base)
        merged.update({k: v for k, v in prof.items() if k not in ("limits_add", "banned_add")})
        merged["limits"] = list(base["limits"]) + list(prof.get("limits_add", []))
        merged["banned_phrases"] = list(base["banned_phrases"]) + list(prof.get("banned_add", []))
        prof = merged
    return prof


def resolve(spec: dict) -> Path:
    """Resolve an input spec without spelling a data path literal."""
    if "key" in spec:
        root = ek.path_for(spec["key"])
    elif "area" in spec:
        root = ek.area_dir(spec["area"])
    elif "exp" in spec:
        root = ek.exp_dir(spec["exp"])
    elif "path" in spec:          # explicit override (tests, CLI)
        return Path(spec["path"])
    else:
        raise KeyError(f"input spec needs key, area, exp or path: {spec}")
    return root / spec["rel"]


def input_path(cfg: dict, name: str, override: str | Path | None = None, required: bool | None = None) -> Path | None:
    """Path of a named input. Required inputs that are missing raise MissingInput with the schema."""
    spec = cfg["inputs"][name]
    p = Path(override) if override else resolve(spec)
    req = (not spec.get("optional", False)) if required is None else required
    if not p.exists():
        if req:
            raise MissingInput(
                f"missing input '{name}' ({spec.get('state', '?')}). Expected at {p}. "
                f"Schema {json.dumps(spec.get('schema', 'see framework'))}. "
                f"Build it upstream or pass an override on the command line.")
        return None
    return p


def run_dir(cfg: dict, prof: dict, out: str | Path | None, short: str = "screen") -> Path:
    """Run folder. --out wins. Else data/<area>/results/screening/<subdir>/<run_id>/ (same config, same day, same folder)."""
    if out:
        d = Path(out)
        d.mkdir(parents=True, exist_ok=True)
        return d
    base = ek.area_dir(cfg["area"]) / "results" / "screening"
    if prof.get("out_subdir"):
        base = base / prof["out_subdir"]
    base.mkdir(parents=True, exist_ok=True)
    return ek.new_run(cfg["exp_id"], f"{short}{prof.get('tag', '')}", {"cfg": cfg, "profile": prof}, base=base,
                      why=f"Screening package, profile {prof['name']}.")


def fname(stem: str, prof: dict, area: str, ext: str) -> str:
    """screening_package + _h2 + _9t + .gpkg"""
    tag = prof.get("tag", "")
    return f"{stem}{tag}_{area}.{ext}"


def read_vector(path: Path, crs: str, layer: str | None = None):
    import geopandas as gpd
    g = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    if g.crs is None:
        raise AssertionError(f"{path} has no CRS")
    if g.crs.to_epsg() != int(crs.split(":")[1]):
        g = g.to_crs(crs)
    ek.assert_crs(g, crs)
    return g


def horizontal_epsg(crs) -> int | None:
    """EPSG of the horizontal part. The 9t DSM carries a compound 6346+5703 CRS."""
    from pyproj import CRS
    c = CRS.from_user_input(crs)
    if c.is_compound:
        c = c.sub_crs_list[0]
    return c.to_epsg()


def screening_area(cfg: dict, blocks, override: str | Path | None = None):
    """Partner polygon if held, else the block extent labelled hypothetical (decision on file)."""
    import geopandas as gpd
    p = input_path(cfg, "partner_area", override, required=False)
    if p is not None:
        a = read_vector(p, cfg["crs"])
        a = gpd.GeoDataFrame({"name": ["partner screening area"], "source": ["partner"]},
                             geometry=[a.union_all()], crs=cfg["crs"])
    else:
        if cfg["decisions"].get("partner") != "hypothetical":
            raise MissingInput("partner_area missing and decisions.partner is not 'hypothetical'")
        a = gpd.GeoDataFrame({"name": ["hypothetical screening area (block extent)"], "source": ["hypothetical"]},
                             geometry=[blocks.union_all().envelope], crs=cfg["crs"])
    return a


def read_records(cfg: dict, area_poly, buffer_m: float, dep_override=None, partner_override=None):
    """L1 records inside the screening area plus buffer. Missing fields stay missing (NaN)."""
    import geopandas as gpd
    import pandas as pd
    f = cfg["record_fields"]
    dep = read_vector(input_path(cfg, "dep_wells", dep_override), cfg["crs"])
    n_in = len(dep)
    rec = gpd.GeoDataFrame({
        "record_id": dep[f["id"]].astype(str),
        "source": "PA DEP export",
        "status": dep[f["status"]] if f.get("status") in dep else np.nan,
        "well_type": dep[f["type"]] if f.get("type") in dep else np.nan,
        "depth_ft": pd.to_numeric(dep[f["depth"]], errors="coerce") if f.get("depth") in dep else np.nan,
        "plug_date": dep[f["plug_date"]].astype(str).replace({"NaT": None, "None": None}) if f.get("plug_date") in dep else None,
        "spud_year": pd.to_datetime(dep[f["spud_date"]], errors="coerce").dt.year if f.get("spud_date") in dep else np.nan,
        "storage_field": dep[f["storage_field"]] if f.get("storage_field") in dep else None,
        "coord_source": dep[f["coord_source"]] if f.get("coord_source") and f["coord_source"] in dep else "not stated",
    }, geometry=dep.geometry.values, crs=cfg["crs"])
    ek.assert_rows(rec, n_in, "DEP records read")
    pw = input_path(cfg, "partner_wells", partner_override, required=False)
    if pw is not None:
        p = pd.read_csv(pw)
        pg = gpd.GeoDataFrame({"record_id": p["permit"].astype(str), "source": "partner",
                               "status": p.get("status"), "depth_ft": p.get("depth_ft"),
                               "plug_date": p.get("plug_date"), "coord_source": "partner"},
                              geometry=gpd.points_from_xy(p["x"], p["y"]),
                              crs=p["crs"].iloc[0] if "crs" in p else cfg["crs"]).to_crs(cfg["crs"])
        rec = pd.concat([rec, pg], ignore_index=True)
    rec["spud_sentinel"] = rec["spud_year"] == cfg["params"]["sentinel_year"]
    zone = area_poly.geometry.iloc[0].buffer(buffer_m)
    rec = rec[rec.within(zone)].copy()
    rec["in_screen_area"] = rec.within(area_poly.geometry.iloc[0])
    rec["evidence_level"] = "b"
    return rec.reset_index(drop=True)


def read_candidates(cfg: dict, pit_override=None, pad_override=None):
    """L2 candidate sites from the 5.6 well-level outputs. Points at the site centroid."""
    import geopandas as gpd
    import pandas as pd
    parts = []
    for name, ov, kind in (("candidates_pit", pit_override, "pit"), ("candidates_pad", pad_override, "pad")):
        p = input_path(cfg, name, ov, required=(name == "candidates_pit"))
        if p is None:
            continue
        g = read_vector(p, cfg["crs"])
        # 5.6 S0 keys rows by det_id (cand_id restarts per source layer). Accept it as the site id.
        id_col = cfg["inputs"][name].get("id_col", "site_id")
        if id_col in g and id_col != "site_id":
            g = g.rename(columns={id_col: "site_id"})
        for col in ("site_id", "score"):
            if col not in g:
                raise MissingInput(f"{p} lacks column '{col}' (schema {cfg['inputs'][name]['schema']})")
        area = g.geometry.area if g.geom_type.iloc[0] != "Point" else pd.Series(np.nan, index=g.index)
        parts.append(gpd.GeoDataFrame({"site_id": g["site_id"].astype(str), "kind": kind,
                                       "score": g["score"].astype(float), "area_m2": area.values},
                                      geometry=g.geometry.centroid.values, crs=cfg["crs"]))
    c = pd.concat(parts, ignore_index=True)
    ek.assert_unique(c.assign(uid=c.kind + ":" + c.site_id), "uid")
    c = c[c.score >= cfg["params"]["frozen_cutoff"]].reset_index(drop=True)
    return c


def nearest_dist(a_xy: np.ndarray, b_xy: np.ndarray) -> np.ndarray:
    from scipy.spatial import cKDTree
    if len(b_xy) == 0:
        return np.full(len(a_xy), np.inf)
    d, _ = cKDTree(b_xy).query(a_xy, k=1)
    return d


def xy(g) -> np.ndarray:
    return np.column_stack([g.geometry.x.values, g.geometry.y.values]) if len(g) else np.zeros((0, 2))


def assert_single_level(layers: dict) -> None:
    """QC 5. No layer mixes evidence levels in its rows."""
    for name, df in layers.items():
        if df is None or "evidence_level" not in df:
            raise AssertionError(f"layer {name} has no evidence_level column")
        lv = set(df["evidence_level"].dropna().unique())
        if len(lv) > 1:
            raise AssertionError(f"layer {name} mixes evidence levels {lv}")


def block_of(points, blocks) -> np.ndarray:
    """Block id per point (NaN outside every block)."""
    import geopandas as gpd
    if not len(points):
        return np.array([])
    j = gpd.sjoin(points[["geometry"]], blocks[["block_id", "geometry"]], how="left", predicate="intersects")
    j = j[~j.index.duplicated()]
    return j["block_id"].reindex(points.index).to_numpy()

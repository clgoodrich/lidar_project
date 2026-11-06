"""Build the T1 validity fixtures and check that the tool refuses or warns on each (7.4 test plan T1).

Purpose
    Write small synthetic LAS files, one folder per fixture, each built to trigger one check.
    ok, no_crs, geographic, crs_mismatch (two tiles), zero_ground, low_density, high_void, single_return,
    truncated, feet_units. `check` runs _agency_las_validity.check_folder on every fixture and compares the
    status and reason with the expected outcome. Zero silent passes are allowed. A silent pass is a fixture
    expected to refuse or warn that comes back ok.

Inputs
    config_7_4.json validity thresholds. --size-m sets the tile edge (the check for small tiles is relaxed
    to fit, and that change is recorded in the report).
Outputs
    <out>/<fixture>/*.las and <out>/fixture_check_7_4.json (expected, observed, pass per fixture)

Run
    python expansions/7_scale/7_4_agency_tooling/src/_agency_fixture_las_build.py --out expansions/7_scale/7_4_agency_tooling/data/interim/fixtures
"""
from __future__ import annotations

import argparse
import json
import zlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _agency_las_validity as va  # noqa: E402
from _agency_las_validity import CFG, load_cfg  # noqa: E402

EXPECTED = {
    "ok": ("ok", ""),
    "no_crs": ("refuse", "CRS missing"),
    "geographic": ("refuse", "geographic CRS"),
    "crs_mismatch": ("refuse", "tiles disagree on CRS"),
    "zero_ground": ("refuse", "zero ground points"),
    "low_density": ("refuse", "ground density below floor"),
    "high_void": ("refuse", "void fraction above ceiling"),
    "single_return": ("warn", "single-return only"),
    "truncated": ("refuse", "unreadable"),
    "feet_units": ("warn", "units in feet"),
}


def write_las(path: Path, size_m: float, ground_ppsm: float, veg_ppsm: float, epsg: int | None, seed: int,
              x0: float = 620000.0, y0: float = 4594000.0, single: bool = False, ground_corner: float = 1.0,
              unit_scale: float = 1.0) -> None:
    import laspy
    from pyproj import CRS
    rng = np.random.default_rng(seed)
    area = size_m * size_m
    ng, nv = int(ground_ppsm * area), int(veg_ppsm * area)
    gx = x0 + rng.uniform(0, size_m * ground_corner, ng)
    gy = y0 + rng.uniform(0, size_m * ground_corner, ng)
    vx, vy = x0 + rng.uniform(0, size_m, nv), y0 + rng.uniform(0, size_m, nv)
    h = laspy.LasHeader(point_format=6, version="1.4")
    h.scales = np.array([1e-7, 1e-7, 0.001]) if epsg == 4326 else np.array([0.001, 0.001, 0.001])
    if epsg is not None:
        crs = CRS.from_epsg(epsg)
        if epsg != 4326:
            crs = CRS.from_user_input(f"{crs.to_string()}+5703")       # compound with NAVD88 height
        h.add_crs(crs)
    las = laspy.LasData(h)
    x = np.r_[gx, vx]; y = np.r_[gy, vy]
    if epsg == 4326:
        x, y = -79.5 + (x - x0) / 85000.0, 41.4 + (y - y0) / 111000.0
    else:
        x, y = x0 + (x - x0) * unit_scale, y0 + (y - y0) * unit_scale
    h.offsets = np.array([x.min(), y.min(), 0.0])
    las.x, las.y = x, y
    las.z = np.r_[rng.normal(300, 1, ng), rng.normal(315, 5, nv)]
    las.classification = np.r_[np.full(ng, 2, np.uint8), np.full(nv, 1, np.uint8)]
    n = ng + nv
    if single:
        las.return_number = np.ones(n, np.uint8); las.number_of_returns = np.ones(n, np.uint8)
    else:
        nr = rng.integers(1, 4, n).astype(np.uint8)
        las.number_of_returns = nr
        las.return_number = np.r_[nr[:ng], np.ones(nv, np.uint8)]
    las.gps_time = rng.uniform(3e8, 3e8 + 1e4, n)
    las.write(path)


def build(out: Path, size_m: float = 50.0) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    good = dict(ground_ppsm=5.0, veg_ppsm=6.0)
    spec = {
        "ok": [dict(epsg=6346, **good)],
        "no_crs": [dict(epsg=None, **good)],
        "geographic": [dict(epsg=4326, **good)],
        "crs_mismatch": [dict(epsg=6346, **good), dict(epsg=26917, **good)],
        "zero_ground": [dict(epsg=6346, ground_ppsm=0.0, veg_ppsm=8.0)],
        "low_density": [dict(epsg=6346, ground_ppsm=0.2, veg_ppsm=8.0)],
        "high_void": [dict(epsg=6346, ground_ppsm=3.0, veg_ppsm=8.0, ground_corner=0.3)],
        "single_return": [dict(epsg=6346, single=True, **good)],
        "truncated": [dict(epsg=6346, **good)],
        "feet_units": [dict(epsg=2272, unit_scale=1 / 0.3048006096, x0=1300000.0, y0=400000.0, **good)],
    }
    paths = {}
    for name, tiles in spec.items():
        d = out / name
        d.mkdir(exist_ok=True)
        for f in d.glob("*.las"):
            f.unlink()
        for i, kw in enumerate(tiles):
            p = d / f"{name}_{i}.las"
            write_las(p, size_m, seed=zlib.crc32(name.encode()) % 1000 + i, **kw)
        if name == "truncated":
            b = p.read_bytes()
            p.write_bytes(b[: len(b) // 3])
        paths[name] = d
    return paths


def check(paths: dict, cfg: dict) -> dict:
    res = {}
    for name, d in paths.items():
        df = va.check_folder(d, cfg)
        exp_status, exp_reason = EXPECTED[name]
        obs = df.iloc[0]
        text = obs["reasons"] if exp_status == "refuse" else obs["warnings"]
        ok = obs["status"] == exp_status and (exp_reason in text)
        silent = exp_status != "ok" and obs["status"] == "ok"
        res[name] = {"expected": exp_status, "reason": exp_reason, "observed": obs["status"],
                     "reasons": obs["reasons"], "warnings": obs["warnings"], "pass": bool(ok), "silent_pass": bool(silent)}
    res["_summary"] = {"n": len(paths), "passed": sum(v["pass"] for v in res.values()),
                       "silent_passes": sum(v["silent_pass"] for v in res.values())}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.4 T1 validity fixtures.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--out", required=True)
    ap.add_argument("--size-m", type=float, default=50.0)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    cfg["validity"]["min_tile_extent_m"] = min(cfg["validity"]["min_tile_extent_m"], a.size_m - 5)
    res = check(build(Path(a.out), a.size_m), cfg)
    res["_summary"]["min_tile_extent_m_used"] = cfg["validity"]["min_tile_extent_m"]
    (Path(a.out) / "fixture_check_7_4.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res["_summary"]))
    return 0 if res["_summary"]["silent_passes"] == 0 and res["_summary"]["passed"] == res["_summary"]["n"] else 1


if __name__ == "__main__":
    sys.exit(main())

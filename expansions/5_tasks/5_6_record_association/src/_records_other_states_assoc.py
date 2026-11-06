"""5.6 S5. The same association on other state well databases (later, only if wanted).

Purpose
    Each state is a separate case study with its own status definitions and coordinate methods. Never pooled.
    Per state the script needs three things, all named in config_5_6.json other_states.states.<ST>.
    1. records          the downloaded database folder (data/_source/reference/wells_<st>_*). Read with a reader in
                        this folder, never a script from the download.
    2. status_col + status_map   which column holds status and how values map to orphan_abandoned, plugged, active.
                        Today these are "assumed" and empty. Harmonisation is a user decision per state.
    3. detector_full_pit + footprint   a full detector output in the 5.6 S0 schema (cx, cy, novel) and a block
                        footprint (block_id, geometry) for a lidar area in that state. None exists yet.
    The analysis is pit level at the primary radius with the shifted null, one row per state x group.

Inputs
    config other_states block. Records folders are held for NY, KY, OK, IL, WV, OH, KS.
Outputs
    expansions/5_tasks/5_6_record_association/results/tables/records_other_states_excess.csv
Run
    python expansions/5_tasks/5_6_record_association/src/_records_other_states_assoc.py --state NY
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402

ek = th.ek
READABLE = (".gpkg", ".shp", ".geojson", ".csv")


def find_records(folder: Path) -> Path:
    if folder.is_file():
        return folder
    hits = sorted(p for p in folder.rglob("*") if p.suffix.lower() in READABLE and not p.name.startswith("_"))
    if not hits:
        raise th.MissingInput("records", folder, "No readable well file in the state folder.")
    return hits[0]


def read_records(path: Path):
    import geopandas as gpd
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, low_memory=False)
        lon = next((c for c in df.columns if c.lower() in ("longitude", "lon", "long", "x")), None)
        lat = next((c for c in df.columns if c.lower() in ("latitude", "lat", "y")), None)
        if lon is None or lat is None:
            raise SystemExit(f"SCHEMA MISMATCH [records {path.name}]: no longitude/latitude columns")
        g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
        return g
    return gpd.read_file(path)


def check_metric_crs(crs, label: str):
    """Radii and 200 to 500 m shifts are in metres. Refuse a geographic or non-metre CRS (review minor)."""
    if crs is None:
        raise SystemExit(f"CRS MISSING [{label}]: no CRS, so distances in metres are undefined.")
    if not crs.is_projected:
        raise SystemExit(f"CRS NOT PROJECTED [{label}]: {crs.to_string()} is geographic. Reproject to a metric UTM CRS.")
    units = {ax.unit_name.lower() for ax in crs.axis_info}
    if not units <= {"metre", "meter"}:
        raise SystemExit(f"CRS UNITS [{label}]: {crs.to_string()} uses {sorted(units)}, not metres.")
    return crs


def run_state(st: str, spec: dict, cfg: dict, n_shift: int):
    import geopandas as gpd
    if spec.get("status_col") in (None, "", "assumed") or not spec.get("status_map"):
        raise th.MissingInput(f"{st}.status_map", spec.get("records"),
                              "Set other_states.states.%s.status_col and status_map (harmonisation is a user decision)." % st)
    det_p, fp_p = th.resolve(spec["detector_full_pit"]), th.resolve(spec["footprint"])
    for nm, p in (("detector_full_pit", det_p), ("footprint", fp_p)):
        if not p.exists():
            raise th.MissingInput(f"{st}.{nm}", p, "Needs a lidar area and a detector run in that state.")
    rec = read_records(find_records(th.resolve(spec["records"])))
    det = gpd.read_file(det_p)
    fp = gpd.read_file(fp_p)
    crs = check_metric_crs(det.crs, f"{st}.detector_full_pit")
    if rec.crs is None:
        raise SystemExit(f"CRS MISSING [{st}.records]: the well file has no CRS. Declare it before running.")
    rec = rec.to_crs(crs)
    if fp.crs is None:
        raise SystemExit(f"CRS MISSING [{st}.footprint]: the footprint has no CRS.")
    fpu = fp.to_crs(crs).geometry.union_all()
    rec["group"] = th.status_group(rec[spec["status_col"]], spec["status_map"])
    r = cfg["pit"]["primary_radius_m"]
    rate = core.pit_rate_fn(np.c_[det["cx"], det["cy"]], [r])

    def elig(xy):
        from shapely import points, contains
        return np.asarray(contains(fpu, points(xy)), bool)
    rows = []
    for gi, (g, x) in enumerate(rec[rec.group != "other"].groupby("group")):
        xy = np.c_[x.geometry.x, x.geometry.y]
        xy = xy[elig(xy)]
        nl = cfg["null"]
        seed = ek.child_seed(int(cfg["seed"]) + 500, fold=sorted(cfg["other_states"]["states"]).index(st), arm=gi)
        nul = core.shift_null(xy, elig, rate, n_shift, nl["shift_min_m"], nl["shift_max_m"], nl["max_loss"],
                              np.random.default_rng(seed), nl["max_tries"])
        e = core.excess(rate(xy)[r] if len(xy) else float("nan"), [d[r] for d in nul["draws"]])
        rows.append(dict(state=st, group=g, radius_m=r, n_records=len(xy), **e, seed=seed))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--state", action="append", help="state code, repeatable. Default all configured.")
    ap.add_argument("--n-shift", type=int)
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    states = cfg["other_states"]["states"]
    todo = a.state or list(states)
    rows = []
    for st in todo:
        rows += run_state(st, states[st], cfg, a.n_shift or cfg["null"]["n_shift"])
    R = th.tag(pd.DataFrame(rows), "a", "exploratory_case_study_per_state")
    out = th.outp(cfg, "other_states")
    R.to_csv(out, index=False)
    print(R.to_string(index=False), "\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""P2 S4. Reserve the absolute audit area in Warren before any inference runs there.

Purpose
    Read the Warren block frame (3.1 output, role column) and take the rows with role `audit`. Refuse if
    any model output already exists over those blocks, since the rule is that nobody has seen model output
    for the reserved area. Model output is any file under data/warren/ matching the config globs whose
    raster or vector extent overlaps a reserved block. Each extent is reprojected from its own CRS to the
    block frame's CRS before the test. An extent with no CRS counts as seen. Then write the reserved list with a header and a
    SHA-256. Default is a dry run. `--freeze` writes the v1 file and its `.sha256` sidecar and refuses to
    overwrite. Freezing is a user decision, and the user also decides whether Warren is the absolute area.

Inputs (assumed, see config_p2.json `warren.assumed_inputs.blocks`)
    data/warren/results/transfer/warren_blocks.gpkg, layer blocks, columns block_id (int), role (str), geometry (EPSG:6346)

Outputs
    freeze   C:/Users/colto/Documents/GitHub/lidar_project/data/warren/results/transfer/audit_blocks_warren_v1.csv (+ .sha256)
    dry run  expansions/0_prerequisites/p2_audit_set/data/interim/audit_blocks_warren_dryrun.csv
    Run record under expansions/0_prerequisites/p2_audit_set/results/<run_id>/

Run
    python expansions/0_prerequisites/p2_audit_set/src/_audit_reserve_warren.py [--blocks PATH] [--freeze]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import _audit_guard_lib as ag  # noqa: E402
ek = ag.ek
CFG = json.loads((HERE.parent / "config_p2.json").read_text(encoding="utf-8"))["warren"]


def output_extents(root: Path, globs: list[str]):
    """(path, shapely box, crs) for every model-output file under root. crs is None when unknown."""
    from shapely.geometry import box
    out = []
    for g in globs:
        for p in sorted(root.glob(g)):
            try:
                if p.suffix.lower() == ".tif":
                    import rasterio
                    with rasterio.open(p) as r:
                        out.append((p, box(*r.bounds), r.crs.to_wkt() if r.crs else None))
                else:
                    import pyogrio
                    info = pyogrio.read_info(p)
                    if info.get("total_bounds") is not None:
                        out.append((p, box(*info["total_bounds"]), info.get("crs")))
            except Exception as e:  # noqa: BLE001
                out.append((p, None, None))
                print(f"could not read extent of {p}: {e}")
    return out


def to_block_crs(ext, crs, blocks):
    """The extent polygon in the block frame's CRS. Its bounding box after reprojection, densified."""
    import geopandas as gpd
    g = gpd.GeoSeries([ext], crs=crs)
    if blocks.crs is not None and not g.crs.equals(blocks.crs):
        g = gpd.GeoSeries([ext.segmentize(max(ext.length / 400, 1e-9))], crs=crs).to_crs(blocks.crs)
    return g.iloc[0]


def reserve(blocks, outputs) -> tuple[pd.DataFrame, list[str]]:
    aud = blocks[blocks["role"].astype(str) == "audit"].copy()
    if aud.empty:
        raise SystemExit("no rows with role == 'audit' in the Warren block frame")
    problems = []
    for p, ext, crs in outputs:
        if ext is None:
            problems.append(f"{p}: extent unreadable, treat as seen")
            continue
        if crs is None:
            problems.append(f"{p}: extent has no CRS, treat as seen")
            continue
        ext = to_block_crs(ext, crs, blocks)
        hit = aud[aud.geometry.intersects(ext)]
        if len(hit):
            problems.append(f"{p}: model output overlaps reserved blocks {sorted(hit.block_id.astype(int))[:10]}")
    rows = pd.DataFrame({"block_id": aud.block_id.astype(int), "role": "audit", "stratum": aud.get("stratum", ""),
                         "area": "warren"}).sort_values("block_id")
    return rows, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P2 S4 reserve the Warren absolute audit area")
    ap.add_argument("--blocks", type=Path, default=None, help="override the assumed block frame path")
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args(argv)
    spec = CFG["assumed_inputs"]["blocks"]
    bp = a.blocks or (ek.area_dir(spec["area"]) / spec["rel"])
    if not bp.exists():
        raise SystemExit(f"assumed input missing. Warren block frame {bp} (schema in config_p2.json warren.assumed_inputs.blocks, "
                         f"produced by 3.1).")
    import geopandas as gpd
    blocks = gpd.read_file(bp, layer=spec["layer"])
    ek.assert_crs(blocks)
    ek.assert_unique(blocks, "block_id")
    rows, problems = reserve(blocks, output_extents(ek.area_dir("warren"), CFG["model_output_globs"]))
    if problems:
        print("REFUSING. Model output exists over the reserved area:\n  " + "\n  ".join(problems))
        return 1
    dst = (ek.area_dir("warren") / CFG["output_rel"]) if a.freeze else (ek.sub("p2", "data/interim") / "audit_blocks_warren_dryrun.csv")
    if a.freeze and dst.exists():
        raise SystemExit(f"{dst} exists and is frozen.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    head = ["# Absolute audit area, Warren. No model output viewed before preregistration.",
            f"# frame={bp.name} frame_sha256={ek.sha256(bp)} written={dt.datetime.now().isoformat(timespec='seconds')}"]
    dst.write_text("\n".join(head) + "\n" + rows.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline="\n")
    h = ek.sha256(dst)
    if a.freeze:
        Path(str(dst) + ".sha256").write_text(f"{h}  {dst.name}\n", encoding="utf-8")
    run = ek.new_run("p2", "reserve_warren" + ("_freeze" if a.freeze else "_dry"), {"blocks": str(bp)},
                     why="S4 reserve the absolute audit area.")
    ek.write_provenance(run, inputs=[bp], outputs=[dst])
    print(f"{len(rows)} reserved blocks\nwrote {dst} (sha256 {h})\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

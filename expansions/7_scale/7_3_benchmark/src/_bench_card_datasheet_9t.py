"""Write the benchmark datasheet from saved files only (7.3 S0).

Purpose
    Fill the datasheet sections of fw_7_3 S0 (motivation, composition, collection, label provenance,
    exclusions, buffers, uncertainty, uses, distribution) with numbers read from the release folder.
    No number is typed. A section whose input is absent says "not measured" or "VERIFY".

Inputs
    <release>/_export_summary.json, splits/splits_<name>.json, labels/*.gpkg, blocks/*.gpkg, tiles/*.tif
    second-reviewer labels path from config_7_3.json (from 6.3, optional)
Outputs
    <release>/DATASHEET.md
    expansions/7_scale/7_3_benchmark/results/tables/bench_card_terrain_v1.md (small copy, in git)
    expansions/7_scale/7_3_benchmark/results/tables/bench_composition_terrain_v1.csv

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_card_datasheet_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bench_export_release_9t import CFG, cfg_path, load_cfg, write_manifest  # noqa: E402


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines)


def composition(root: Path) -> pd.DataFrame:
    import geopandas as gpd
    rows = []
    blocks = {p.stem.replace("blocks_", ""): gpd.read_file(p) for p in sorted((root / "blocks").glob("blocks_*.gpkg"))}
    for role, b in blocks.items():
        area = float(b.geometry.area.sum()) / 1e6
        lab = root / "labels" / f"labels_{role}.gpkg"
        layers = []
        if lab.exists():
            import pyogrio
            layers = [n for n, _ in pyogrio.list_layers(str(lab))]
        for task in layers or ["(none)"]:
            if task == "(none)":
                rows.append({"role": role, "task": "(labels withheld)" if role in ("test", "buffer") else "(no labels)",
                             "n_blocks": len(b), "area_km2": area, "n_features": None, "per_km2": None,
                             "share_blocks_empty": None})
                continue
            f = gpd.read_file(lab, layer=task)
            per_block = f["block_id"].value_counts()
            empty = sum(1 for x in b["block_id"] if per_block.get(x, 0) == 0) / max(len(b), 1)
            rows.append({"role": role, "task": task, "n_blocks": len(b), "area_km2": round(area, 4),
                         "n_features": len(f), "per_km2": round(len(f) / area, 3) if area else None,
                         "share_blocks_empty": round(empty, 4)})
    return pd.DataFrame(rows)


def collection(root: Path) -> dict:
    import rasterio
    tiles = sorted((root / "tiles").glob("*.tif"))
    if not tiles:
        return {"n_tiles": 0}
    with rasterio.open(tiles[0]) as r:
        return {"n_tiles": len(tiles), "crs": str(r.crs), "res_m": r.res[0], "bands": list(r.descriptions),
                "vertical_datum": r.tags().get("vertical_datum", "VERIFY")}


def uncertainty(cfg: dict) -> str:
    p = cfg_path(cfg["inputs"]["second_reviewer"])
    if not p.exists():
        return "Uncertainty not measured. Second-reviewer labels from 6.3 are absent (" + str(p) + ")."
    return ("Second-reviewer labels exist at " + str(p) +
            ". Run _bench_validity_checks_9t.py --label-ceiling to compute the ceiling. The number is read from its JSON.")


def build(cfg: dict, root: Path) -> str:
    summ = json.loads((root / "_export_summary.json").read_text())
    comp = composition(root)
    col = collection(root)
    lic = cfg["licences"]
    off = {t: c.get("off_tile", 0) for t, c in summ["label_counts"].items()}
    touch = {t: c.get("hidden_touch", 0) for t, c in summ["label_counts"].items()}
    md = [f"# Datasheet {cfg['release_name']}", "",
          f"Status. {'PROVISIONAL. Not for release.' if summ['provisional'] else 'Candidate release.'}",
          "Evidence level (a) throughout. Labels are drawn terrain features. They are not wells.",
          f"Audit exclusion. {summ.get('audit_exclusion', 'not recorded. Export predates the label. Treat as none.')}",
          f"Scoring policy {summ.get('policy_version', 'not recorded')} (scoring_policy.json).", "",
          "## Motivation",
          "No public benchmark exists for lidar detection of terrain features linked to old oil and gas sites.",
          "The release lets others compare methods on the same tiles and the same scorer. Funding is VERIFY.", "",
          "## Composition", _md_table(comp) if len(comp) else "No blocks exported.", "",
          "## Collection",
          f"Tiles {col.get('n_tiles')}. CRS {col.get('crs', 'VERIFY')}. Resolution {col.get('res_m', 'VERIFY')} m.",
          f"Bands {', '.join(col.get('bands', []) or ['VERIFY'])}. Vertical datum {col.get('vertical_datum', 'VERIFY')}.",
          "Lidar project and flight dates are VERIFY. A publication date is not a flight date.", "",
          "## Label provenance",
          "One annotator drew polygons in QGIS from derivative views. The labels are one person's reading of terrain.",
          "The annotator did not see DEP well points while drawing (user, 2026-11-04). Other context seen is unrecorded.", "",
          "## Exclusions",
          f"Features with no block (off tile) per task {off}.",
          f"Features touching a hidden block, dropped from public files, per task {touch}.",
          f"Near-duplicate features across splits within 5 m {summ['near_duplicates_across_splits']}.", "",
          "## Spatial buffers",
          f"Roles {summ['roles']}. Buffer blocks ship tiles and no labels.", "",
          "## Uncertainty", uncertainty(cfg), "",
          "## Uses",
          "Intended. Compare terrain-feature detectors on pit and pad features in forested Appalachian lidar.",
          "Out of scope. Locating wells, regulatory or legal decisions, counting wells, safety decisions, other states.", "",
          "## Distribution and licences",
          f"Lidar {lic['lidar']}. Labels {lic['labels']}. Well context {lic['well_context']}.",
          "Host and DOI are VERIFY. Versioning follows the manifest. A change makes a new version.", ""]
    return "\n".join(md), comp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write the 7.3 datasheet from saved files.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--release", default=None, help="release folder (default from config)")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    root = Path(a.release) if a.release else cfg_path(cfg["release_root"]) / cfg["release_name"]
    if not (root / "_export_summary.json").exists():
        print(f"missing release export at {root}. Run _bench_export_release_9t.py first.", file=sys.stderr)
        return 2
    md, comp = build(cfg, root)
    (root / "DATASHEET.md").write_text(md, encoding="utf-8")
    write_manifest(root)
    tab = ek.sub("7.3", "results/tables")
    (tab / f"bench_card_{cfg['release_name']}.md").write_text(md, encoding="utf-8")
    comp.to_csv(tab / f"bench_composition_{cfg['release_name']}.csv", index=False)
    print(f"wrote {root / 'DATASHEET.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

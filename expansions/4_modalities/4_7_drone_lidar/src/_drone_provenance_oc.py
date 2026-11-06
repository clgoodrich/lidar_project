"""S1 of framework 4.7. Provenance check of the NETL drone delivery and the provenance write-up.

Purpose. Read the transcribed NETL reply (metadata JSON), the delivered LAS/LAZ headers and the site layer. Check
that every field the R2 request asked for is present, that the clouds agree on CRS and sit in EPSG:6346 (or say
which reprojection is needed), and that the site count matches. If sites were chosen by lidar visibility, or the
selection is unknown, every result is labelled "conditional on lidar-visible sites". The write-up is markdown.
Inputs.
  data/_source/drone_netl/netl_drone_metadata.json (assumed, schema in config_4_7.json)
  data/_source/drone_netl/*.las|*.laz (assumed)
  data/_source/drone_netl/netl_sites_oc.gpkg (assumed)
Outputs.
  expansions/4_modalities/4_7_drone_lidar/results/tables/drone_lidar_provenance_oc.md   (copy to docs/iterations/drone_lidar_provenance.md)
  expansions/4_modalities/4_7_drone_lidar/results/tables/drone_lidar_provenance_oc.json
Run.
  python expansions/4_modalities/4_7_drone_lidar/src/_drone_provenance_oc.py [--meta JSON] [--las-dir DIR] [--sites GPKG] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import _drone_kit_4_7 as dk

VISIBILITY_WORDS = ("lidar", "hillshade", "visible", "visual", "dem")


def conditional_label(selection: str | None) -> bool:
    """True when results must say 'conditional on lidar-visible sites'. Unknown selection also counts."""
    if not selection:
        return True
    s = selection.lower()
    return any(w in s for w in VISIBILITY_WORDS)


def check(meta: dict, infos: list[dict], n_sites_layer: int | None, crs: str) -> dict:
    schema = dk.load_cfg()["inputs"]["provenance"]["schema"]
    missing = [k for k in schema if meta.get(k) in (None, "")]
    epsgs = sorted({i["epsg"] for i in infos}, key=str)
    want = int(crs.split(":")[1])
    return {"missing_fields": missing, "n_clouds": len(infos), "epsg_found": epsgs,
            "crs_ok": epsgs == [want], "needs_reprojection": any(e != want for e in epsgs),
            "n_points": sum(i["n_points"] for i in infos), "n_ground": sum(i["n_ground"] for i in infos),
            "n_sites_meta": meta.get("n_sites"), "n_sites_layer": n_sites_layer,
            "sites_match": n_sites_layer is not None and meta.get("n_sites") == n_sites_layer,
            "conditional_on_visibility": conditional_label(meta.get("site_selection")),
            "evidence_level": "(d) for confirmed sites only, else (a)" if meta.get("sites_confirmed") else "(a)"}


def to_md(meta: dict, res: dict, infos: list[dict]) -> str:
    L = ["# Drone lidar provenance, Oil Creek", "",
         "Evidence level " + res["evidence_level"] + ". NETL sites are potential well sites found with lidar. They are not confirmed wells.", ""]
    if res["conditional_on_visibility"]:
        L += ["**Every result from this dataset is conditional on lidar-visible sites.**", ""]
    L += ["| Field | Value |", "|---|---|"] + [f"| {k} | {meta.get(k)} |" for k in sorted(meta)]
    L += ["", "| Cloud | LAS | Format | Points | Ground | EPSG |", "|---|---|---|---|---|---|"]
    L += [f"| {Path(i['path']).name} | {i['version']} | {i['point_format']} | {i['n_points']} | {i['n_ground']} | {i['epsg']} |" for i in infos]
    L += ["", f"Missing fields. {', '.join(res['missing_fields']) or 'none'}.",
          f"CRS check. {'EPSG:6346 throughout' if res['crs_ok'] else 'reprojection or a CRS fix is needed. Escalate to the user'}.",
          f"Sites. metadata {res['n_sites_meta']}, layer {res['n_sites_layer']}."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    cfg = dk.load_cfg()
    I = cfg["inputs"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--meta", default=None)
    ap.add_argument("--las-dir", default=None)
    ap.add_argument("--sites", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    mp = dk.need(Path(a.meta) if a.meta else dk.resolve(I["provenance"]), "NETL metadata JSON", I["provenance"])
    meta = json.loads(mp.read_text())
    ld = dk.need(Path(a.las_dir) if a.las_dir else dk.resolve(I["raw_las"]), "NETL point cloud folder", I["raw_las"])
    clouds = sorted(ld.glob(I["raw_las"]["glob"]))
    if not clouds:
        dk.need(ld / I["raw_las"]["glob"], "NETL point clouds", I["raw_las"])
    infos = [dk.las_info(p, cfg["ladder"]["ground_class"]) for p in clouds]
    sp = Path(a.sites) if a.sites else dk.resolve(I["sites"])
    n_sites = None
    if sp.exists():
        import geopandas as gpd
        n_sites = len(gpd.read_file(sp))
    res = check(meta, infos, n_sites, cfg["crs"])
    out = Path(a.out) if a.out else dk.resolve(cfg["outputs"]["tables"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "drone_lidar_provenance_oc.md").write_text(to_md(meta, res, infos), encoding="utf-8")
    (out / "drone_lidar_provenance_oc.json").write_text(json.dumps({"check": res, "clouds": infos}, indent=2), encoding="utf-8")
    dk.prov(out, "drone_provenance_oc", inputs=[mp, *clouds], outputs=[out / "drone_lidar_provenance_oc.json"], params=res)
    print(json.dumps(res, indent=2))
    if not res["crs_ok"]:
        print("ALERT: CRS is not EPSG:6346 in every cloud. Escalate before S2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

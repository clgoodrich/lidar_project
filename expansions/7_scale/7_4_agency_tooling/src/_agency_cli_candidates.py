"""Agency command-line tool. Candidate pits and pads from an agency's own lidar (7.4 section 6).

Purpose
    Subcommands
      check-env  interpreter, packages, PDAL binary and version, GPU, free disk, write test. Exit 3 if missing.
      version    tool version, input-contract version, code commit.
      manifest   hash every frozen checkpoint into the model manifest (results/tables/model_manifest_7_4.json).
      validate   input-validity checks only (_agency_las_validity.py).
      run        validate, build or read the 0.5 m derivative stack, predict with the frozen fold ensemble,
                 extract candidates at the frozen cutoff, rank, export GPKG/CSV/KML, coverage, trust statement,
                 provenance. Refused tiles produce no candidates and appear in coverage.gpkg.
      calibrate  local isotonic calibration from agency labels (_agency_trust_calibrate.py).
      report     summary of a finished run folder.
    Derivatives are built with the repo builder (notebooks/wellsight_v2/s1_build/_build_derivatives.py),
    which runs PDAL through the CLI binary by subprocess. The PDAL Python bindings are never imported.
    The tool refuses to run when a checkpoint hash differs from the manifest.
    Candidates are labelled "candidate". The tool never writes "confirmed" or "well found".
    Exit codes. 0 ok. 2 refused on validity. 3 environment or manifest problem. 4 internal error. 5 interrupted.

Inputs
    --lidar folder of LAS/LAZ (or --features a prebuilt 7-band 0.5 m stack), config_7_4.json,
    frozen checkpoints path_for("models") / pit/unet_cv5/fold{k}/best.pt and pad/unet_cv5_iso/fold{k}/best.pt (held),
    optional --known-wells (read-only, hashed), optional --calibration JSON
Outputs (<out>/<run_id>/)
    candidates.gpkg (pit, pad), candidates.csv, candidates.kml, validity_report.csv/.json, coverage.gpkg,
    trust_statement.md, _PROVENANCE.json, _RUN.md, _CONFIG.json, cache/ (per-class probability, for --resume),
    probability/ only with --keep-rasters

Run
    python expansions/7_scale/7_4_agency_tooling/src/_agency_cli_candidates.py check-env --out <folder>
    python expansions/7_scale/7_4_agency_tooling/src/_agency_cli_candidates.py run --lidar <laz folder> --out <folder>
"""
from __future__ import annotations

import argparse
import importlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _agency_export_formats as ex  # noqa: E402
import _agency_las_validity as va  # noqa: E402
import _agency_trust_calibrate as tc  # noqa: E402
from _agency_las_validity import CFG, cfg_path, ek, load_cfg  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "7_3_benchmark" / "src"))
import _bench_evaluate_recall_k as sc  # noqa: E402

PACKAGES = ["numpy", "pandas", "scipy", "rasterio", "geopandas", "shapely", "pyproj", "laspy", "torch", "sklearn"]


class Refused(Exception):
    pass


class EnvProblem(Exception):
    pass


# ----------------------------------------------------------------------------- env / version / manifest
def check_env(out: Path) -> dict:
    res = {"python": sys.version.split()[0], "python_ok": sys.version_info >= (3, 11), "packages": {}, "missing": []}
    for p in PACKAGES:
        try:
            m = importlib.import_module(p)
            res["packages"][p] = getattr(m, "__version__", "?")
        except Exception:  # noqa: BLE001
            res["missing"].append(p)
    pdal = shutil.which("pdal")
    res["pdal"] = pdal
    if pdal:
        r = subprocess.run([pdal, "--version"], capture_output=True, text=True)
        import re
        m = re.search(r"\d+\.\d+\.\d+\S*", (r.stdout or "") + (r.stderr or ""))
        res["pdal_version"] = m.group(0) if m else "unknown"
    else:
        res["missing"].append("pdal binary on PATH")
    try:
        import torch
        res["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        res["gpu"] = None
    out.mkdir(parents=True, exist_ok=True)
    res["free_disk_gb"] = round(shutil.disk_usage(out).free / 1e9, 1)
    try:
        (out / ".write_test").write_text("ok"); (out / ".write_test").unlink()
        res["write_ok"] = True
    except OSError:
        res["write_ok"] = False; res["missing"].append("write access to --out")
    if not res["python_ok"]:
        res["missing"].append("Python 3.11 or newer")
    return res


def checkpoint_paths(cfg: dict, cls: str) -> list[Path]:
    m = cfg["models"][cls]
    return [cfg_path({"key": c["key"], "rel": c["rel"].format(k=k)}) for c in m["checkpoints"] for k in m["folds"]]


def build_manifest(cfg: dict, classes=("pit", "pad")) -> dict:
    man = {"tool_version": cfg["tool_version"], "commit": ek._git_commit(), "models": {}}
    for cls in classes:
        man["models"][cls] = [{"path": str(p.relative_to(ek.REPO)) if p.is_relative_to(ek.REPO) else str(p),
                               "sha256": ek.sha256(p)} for p in checkpoint_paths(cfg, cls)]
    return man


def verify_manifest(cfg: dict, cls: str, manifest_path: Path) -> list[tuple[Path, str]]:
    if not manifest_path.exists():
        raise EnvProblem(f"model manifest missing at {manifest_path}. Run `manifest` first")
    man = json.loads(manifest_path.read_text())
    want = {e["path"]: e["sha256"] for e in man["models"].get(cls, [])}
    out = []
    for p in checkpoint_paths(cfg, cls):
        key = str(p.relative_to(ek.REPO)) if p.is_relative_to(ek.REPO) else str(p)
        if not p.exists():
            raise EnvProblem(f"checkpoint missing {p}")
        h = ek.sha256(p)
        if want.get(key) != h:
            raise EnvProblem(f"checkpoint hash differs from manifest for {key}. Refused")
        out.append((p, h))
    return out


# ----------------------------------------------------------------------------- features
def build_features(tiles: list[Path], out_dir: Path, cfg: dict, src_crs: str | None) -> Path:
    """Run the repo derivative builder on the admitted tiles, then stack the 7 channels."""
    import laspy
    import rasterio
    xs, ys = [], []
    for t in tiles:
        with laspy.open(t) as f:
            h = f.header
            xs += [h.mins[0], h.maxs[0]]; ys += [h.mins[1], h.maxs[1]]
    sfx = "agency_05"
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(tiles[0].parent / "*.la[sz]") if len({t.parent for t in tiles}) == 1 else str(tiles[0])
    cmd = [sys.executable, str(ek.REPO / cfg["derivative_builder"]), "--tiles", pattern,
           "--bbox", f"{min(xs)},{min(ys)},{max(xs)},{max(ys)}", "--suffix", sfx, "--res", str(cfg["resolution_m"]),
           "--out-dir", str(out_dir)]
    if src_crs:
        cmd += ["--src-crs", src_crs]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"derivative builder failed: {r.stderr[-1500:]}")
    stack = out_dir / f"features_{sfx}.tif"
    files = [out_dir / f"{ch}_{sfx}.tif" for ch in cfg["channels"]]
    missing = [f for f in files if not f.exists()]
    if missing:
        raise RuntimeError(f"builder did not write {missing[:3]}")
    with rasterio.open(files[0]) as r0:
        prof = r0.profile.copy()
    prof.update(count=len(files), dtype="float32", nodata=np.nan, compress="deflate")
    with rasterio.open(stack, "w", **prof) as o:
        for i, fp in enumerate(files, 1):
            with rasterio.open(fp) as r:
                a = r.read(1).astype(np.float32)
                if r.nodata is not None and np.isfinite(r.nodata):
                    a[a == r.nodata] = np.nan
            o.write(a, i)
            o.set_band_description(i, cfg["channels"][i - 1])
    return stack


def predict_class(cfg: dict, cls: str, ckpts, stack: Path, cache: Path, resume: bool):
    import rasterio
    import torch
    import _dl
    cache.mkdir(parents=True, exist_ok=True)
    cp = cache / f"{cls}_prob.tif"
    if resume and cp.exists():
        with rasterio.open(cp) as r:
            return r.read(1), r.transform, r.crs
    m = cfg["models"][cls]
    acc = None
    with rasterio.open(stack) as r:
        ek.assert_crs(r, r.crs)
        H, W, tf, crs = r.height, r.width, r.transform, r.crs
        if abs(r.res[0] - cfg["resolution_m"]) > 1e-6:
            raise Refused(f"feature stack resolution {r.res[0]} m, the tool needs {cfg['resolution_m']} m")
    for p, _ in ckpts:
        ck = torch.load(p, map_location="cpu", weights_only=False)
        if list(ck.get("channels", cfg["channels"])) != cfg["channels"]:
            raise EnvProblem(f"{p}: channel order differs from the input contract")
        net = _dl.UNet(in_ch=len(cfg["channels"]), n_classes=m["n_classes"])
        net.load_state_dict(ck["state_dict"])
        patch = min(int(ck.get("patch", m["patch"])), H, W) // 16 * 16
        prob, _, _ = _dl.predict_full_tile(net, stack, np.asarray(ck["mu"], np.float32), np.asarray(ck["sd"], np.float32),
                                            patch=patch, overlap=min(m["overlap"], patch // 2), n_classes=m["n_classes"])
        acc = prob[m["prob_class"]] if acc is None else acc + prob[m["prob_class"]]
    acc = (acc / len(ckpts)).astype(np.float32)
    with rasterio.open(cp, "w", driver="GTiff", width=W, height=H, count=1, dtype="float32", crs=crs, transform=tf,
                       nodata=-1, compress="deflate") as o:
        o.write(acc, 1)
    return acc, tf, crs


# ----------------------------------------------------------------------------- run
def tile_footprints(df, crs):
    import geopandas as gpd
    from shapely.geometry import box
    import laspy
    geoms = []
    for p in df["path"]:
        try:
            with laspy.open(p) as f:
                h = f.header
                geoms.append(box(h.mins[0], h.mins[1], h.maxs[0], h.maxs[1]))
        except Exception:  # noqa: BLE001
            geoms.append(None)
    return gpd.GeoDataFrame(df[["tile_id", "status", "reasons", "warnings"]].copy(), geometry=geoms, crs=crs)


def run(a, cfg: dict) -> Path:
    import geopandas as gpd
    from rasterio.features import rasterize
    params = {k: v for k, v in vars(a).items() if k not in ("out", "cmd", "resume", "config")}
    if a.res != cfg["resolution_m"]:
        raise Refused(f"--res {a.res} refused. The tool is fixed at {cfg['resolution_m']} m")
    rd = ek.new_run("7.4", "agency", {**params, "tool": cfg["tool_version"]}, base=Path(a.out),
                    why="Agency candidate run.")
    classes = ["pit", "pad"] if a.model == "both" else [a.model]
    manifest = Path(a.manifest) if a.manifest else cfg_path(cfg["manifest"])
    ckpts = {cls: verify_manifest(cfg, cls, manifest) for cls in classes}
    validity, coverage = {}, None
    if a.lidar:
        df = va.check_folder(Path(a.lidar), cfg, a.crs, a.strict)
        va.write_report(df, rd)
        if (df["status"] == "refuse").all():
            raise Refused("every tile refused. See validity_report.csv")
        crs_txt = next((c for c in df["crs"] if isinstance(c, str)), a.crs)
        coverage = tile_footprints(df, crs_txt)
        coverage.to_file(rd / "coverage.gpkg", driver="GPKG")
        validity = {t: (s if s != "warn" else "warn:" + w) for t, s, w in zip(df["tile_id"], df["status"], df["warnings"])}
        ok_tiles = [Path(p) for p, s in zip(df["path"], df["status"]) if s != "refuse"]
    if a.features:
        stack = Path(a.features)
    elif a.lidar:
        stack = build_features(ok_tiles, rd / "derived", cfg, a.crs if a.crs else None)
    else:
        raise Refused("give --lidar or --features")
    wells = None
    if a.known_wells:
        wells_path = Path(a.known_wells)
    cal_fn = None
    meta_cls = {}
    tables = {}
    for cls in classes:
        prob, tf, crs = predict_class(cfg, cls, ckpts[cls], stack, rd / "cache", a.resume)
        valid = np.isfinite(prob) & (prob >= 0)
        if coverage is not None:
            ok = coverage[coverage["status"] != "refuse"]
            valid &= rasterize([(g, 1) for g in ok.geometry if g is not None], out_shape=prob.shape, transform=tf,
                               fill=0).astype(bool)
        if a.aoi:
            aoi = gpd.read_file(a.aoi).to_crs(crs)          # any CRS, reprojected and logged in provenance
            valid &= rasterize([(g, 1) for g in aoi.geometry], out_shape=prob.shape, transform=tf, fill=0).astype(bool)
        cut = a.cutoff if a.cutoff is not None else cfg["frozen_cutoff"][cls]
        blobs = sc.extract_candidates(prob, tf, thr=cut, min_area_m2=cfg["min_area_m2"][cls], valid=valid, crs=crs)
        if coverage is not None and len(blobs):
            j = gpd.sjoin(gpd.GeoDataFrame(geometry=blobs.geometry.centroid, crs=crs),
                          coverage[["tile_id", "geometry"]], how="left", predicate="within")
            blobs["tile_id"] = j[~j.index.duplicated()]["tile_id"].fillna("unassigned").to_numpy()
        else:
            blobs["tile_id"] = Path(stack).stem
        area_km2 = float(valid.sum()) * abs(tf.a * tf.e) / 1e6
        if wells is None and a.known_wells:
            wells = ex.read_known_wells(wells_path, crs)
        if a.calibration:
            cal_fn = tc.apply_calibration(json.loads(Path(a.calibration).read_text()), ckpts[cls][0][1])
        sha = ek.config_hash({"ckpts": [h for _, h in ckpts[cls]]})
        meta = {"run_id": rd.name, "model_id": f"{cls}_{cfg['models'][cls]['method'].split()[0]}_ens{len(ckpts[cls])}",
                "model_sha256": ";".join(h for _, h in ckpts[cls]), "method": cfg["models"][cls]["method"]
                + (" (cutoff changed, flagged)" if a.cutoff is not None else "")}
        t = ex.build_table(blobs, cls, meta, area_km2, a.k_per_km2, wells, validity, cal_fn)
        if a.k_per_km2 is not None:
            t = t[t["within_review_budget"]].copy()
        tables[cls] = t
        meta_cls[cls] = {"area_km2": area_km2, "n": len(t), "ensemble_hash7": sha, "cutoff": cut}
        if a.keep_rasters:
            (rd / "probability").mkdir(exist_ok=True)
            shutil.copyfile(rd / "cache" / f"{cls}_prob.tif", rd / "probability" / f"{cls}_prob.tif")
    summ = ex.write_all(tables, rd, cfg["forbidden_words"])
    vs = {"scored": sum(1 for v in validity.values() if v == "ok"), "warned": sum(1 for v in validity.values() if v.startswith("warn")),
          "refused": sum(1 for v in validity.values() if v == "refuse")}
    sha_any = next(iter(ckpts.values()))[0][1]
    stmt = tc.trust_statement(cfg, sha_any, vs)
    ex.guard_text([stmt], cfg["forbidden_words"])
    (rd / "trust_statement.md").write_text(stmt, encoding="utf-8")
    inputs = [p for v in ckpts.values() for p, _ in v] + ([Path(a.known_wells)] if a.known_wells else [])
    if a.lidar:
        inputs += sorted([*Path(a.lidar).glob("*.la[sz]")])
    else:
        inputs.append(stack)
    ek.write_provenance(rd, inputs=inputs, outputs=[rd / "candidates.csv", rd / "candidates.gpkg"],
                        params={**params, "classes": meta_cls, "validity": vs, "summary": summ,
                                "tool_version": cfg["tool_version"], "contract": cfg["input_contract_version"],
                                "pdal": shutil.which("pdal"), "platform": platform.platform()},
                        seeds={"seed": a.seed}, hash_limit_mb=500)
    return rd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wells_cli", description="Candidate terrain features from agency lidar.")
    ap.add_argument("--config", default=str(CFG))
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("check-env"); e.add_argument("--out", default=".")
    sp.add_parser("version")
    m = sp.add_parser("manifest"); m.add_argument("--out", default=None)
    v = sp.add_parser("validate"); v.add_argument("--lidar", required=True); v.add_argument("--out", required=True)
    v.add_argument("--crs", default=None); v.add_argument("--strict", action="store_true")
    r = sp.add_parser("run")
    r.add_argument("--lidar", default=None); r.add_argument("--features", default=None); r.add_argument("--out", required=True)
    r.add_argument("--crs", default=None); r.add_argument("--aoi", default=None)
    r.add_argument("--model", choices=["pit", "pad", "both"], default="both")
    r.add_argument("--cutoff", type=float, default=None); r.add_argument("--k-per-km2", type=float, default=40.0)
    r.add_argument("--res", type=float, default=0.5); r.add_argument("--device", default="auto")
    r.add_argument("--strict", action="store_true"); r.add_argument("--calibration", default=None)
    r.add_argument("--seed", type=int, default=0); r.add_argument("--workers", type=int, default=1, help="reserved. Runs are single-process today")
    r.add_argument("--resume", action="store_true"); r.add_argument("--keep-rasters", action="store_true")
    r.add_argument("--known-wells", default=None); r.add_argument("--manifest", default=None)
    c = sp.add_parser("calibrate"); c.add_argument("--labels", required=True); c.add_argument("--model-sha256", required=True)
    c.add_argument("--out", required=True)
    p = sp.add_parser("report"); p.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    try:
        if a.cmd == "check-env":
            res = check_env(Path(a.out))
            print(json.dumps(res, indent=2))
            return 3 if res["missing"] else 0
        if a.cmd == "version":
            print(json.dumps({"tool_version": cfg["tool_version"], "input_contract": cfg["input_contract_version"],
                              "commit": ek._git_commit()}))
            return 0
        if a.cmd == "manifest":
            out = Path(a.out) if a.out else cfg_path(cfg["manifest"])
            out.write_text(json.dumps(build_manifest(cfg), indent=2), encoding="utf-8")
            print(f"wrote {out}")
            return 0
        if a.cmd == "validate":
            return va.main(["--config", a.config, "--lidar", a.lidar, "--out", a.out] + (["--crs", a.crs] if a.crs else [])
                           + (["--strict"] if a.strict else []))
        if a.cmd == "calibrate":
            return tc.main(["--config", a.config, "calibrate", "--labels", a.labels, "--model-sha256", a.model_sha256, "--out", a.out])
        if a.cmd == "report":
            rd = Path(a.run)
            prov = json.loads((rd / "_PROVENANCE.json").read_text())
            print(json.dumps({"run": rd.name, "summary": prov["params"].get("summary"), "validity": prov["params"].get("validity"),
                              "trust_statement": str(rd / "trust_statement.md")}, indent=2))
            return 0
        if a.device != "auto":
            import torch
            import _dl
            _dl.DEVICE = torch.device(a.device)
        rd = run(a, cfg)
        print(f"run folder {rd}")
        return 0
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except (EnvProblem, FileNotFoundError) as e:
        print(f"environment: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("interrupted. Rerun with --resume", file=sys.stderr)
        return 5
    except Exception as e:  # noqa: BLE001
        print(f"internal error: {type(e).__name__}: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())

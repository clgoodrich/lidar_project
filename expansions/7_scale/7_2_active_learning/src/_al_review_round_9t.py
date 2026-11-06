"""Blind pooled review package for one live round, and ingestion of the reviewed labels (7.2 S3 steps 2 and 3).

Purpose
    package
        Pool the batches of every policy. Deduplicate candidates whose centroids fall within 5 m in the
        same window. Shuffle item order with the round seed so policy order is hidden. Write a QGIS package
        that shows no score, no policy and no DEP record. The layout follows the repo pit review package
        (notebooks/wellsight_v2/s6_review/_build_pit_review_package.py). Its QML symbology and README
        text are imported from that module, not copied. The id map that links review ids to items and
        policies is written to data/interim/ and is never given to reviewers.
    ingest
        Run the repo diff (notebooks/wellsight_v2/s6_review/_pit_corrections_diff.py) on the edited
        package by subprocess. keep is a positive, reject a hard negative, unsure is excluded, added is a
        missed feature. Added features inside a discovery window are credited to that window. Minutes
        come from the timer. A shared item charges its measured minutes to every policy that selected it.

Inputs
    round folder with batch_<policy>.csv (from _al_policies_select_9t.py)
    data/interim/al_items_9t.gpkg item polygons (from _al_split_pool_stop_9t.py --build-items)
    timer minutes CSV (from _al_review_timer_minutes.py summarise)
Outputs
    <round>/review/review_pits_<tag>.gpkg (layer review), review_pits_<tag>_ORIGINAL.gpkg, review_pits_<tag>.qml,
    <round>/review/added_pits_<tag>.gpkg (layer added), windows_<tag>.gpkg (layer windows), README_EDIT.md
    data/interim/al_review_idmap_<tag>.csv   (private)
    <round>/labels.csv  item_id, review_id, policies, status, y, n_added
    <round>/minutes.csv policy, item_id, minutes

Run
    python expansions/7_scale/7_2_active_learning/src/_al_review_round_9t.py package --round 1
    python expansions/7_scale/7_2_active_learning/src/_al_review_round_9t.py ingest --round 1 --minutes minutes.csv
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _al_policies_select_9t import CFG, ek, load_cfg, need  # noqa: E402

REVIEW_DIR = ek.REPO / "notebooks" / "wellsight_v2" / "s6_review"


def interim_dir() -> Path:
    """Private folder for the review id map (gitignored, never handed to reviewers)."""
    return ek.sub("7.2", "data/interim")


def _pit_pkg():
    sys.path.insert(0, str(REVIEW_DIR))
    import _build_pit_review_package as pkg
    return pkg


def pool_batches(round_dir: Path, items_geo, dedupe_m: float, seed: int):
    bat = [pd.read_csv(p).assign(policy=p.stem.split("_", 1)[1]) for p in sorted(round_dir.glob("batch_*.csv"))]
    if not bat:
        raise FileNotFoundError(f"no batch_*.csv in {round_dir}")
    sel = pd.concat(bat, ignore_index=True)
    pol = sel.groupby("item_id")["policy"].apply(lambda s: ";".join(sorted(set(s)))).reset_index()
    g = items_geo.merge(pol, on="item_id", how="inner")
    ek.assert_rows(g, len(pol), "selected items found in the item polygons")
    # dedupe C items within dedupe_m in the same window (block)
    canon = {}
    C = g[g["type"] == "C"].sort_values("item_id")
    from scipy.spatial import cKDTree
    for b, gb in C.groupby("block_id"):
        xy = np.c_[gb.geometry.centroid.x, gb.geometry.centroid.y]
        ids = gb["item_id"].tolist()
        tree = cKDTree(xy)
        for i, iid in enumerate(ids):
            if iid in canon:
                continue
            for j in tree.query_ball_point(xy[i], dedupe_m):
                canon.setdefault(ids[j], iid)
    g["canonical"] = [canon.get(i, i) for i in g["item_id"]]
    rng = np.random.default_rng(seed)
    uniq = g.drop_duplicates("canonical")
    order = rng.permutation(len(uniq))
    rid = {c: f"R{k:05d}" for k, c in enumerate(uniq["canonical"].iloc[order])}
    g["review_id"] = g["canonical"].map(rid)
    g["review_num"] = g["review_id"].str[1:].astype(int)
    return g


def package(round_dir: Path, items_geo, cfg, rnd: int) -> Path:
    import pyogrio
    pkg = _pit_pkg()
    tag = f"al_r{rnd:02d}"
    g = pool_batches(round_dir, items_geo, cfg["dedupe_m"], ek.child_seed(cfg["master_seed"], rnd, 7))
    rev = round_dir / "review"
    rev.mkdir(parents=True, exist_ok=True)
    c = g[(g["type"] == "C")].drop_duplicates("review_id").sort_values("review_num")
    review = c[["review_num", "geometry"]].rename(columns={"review_num": "pit_inside_id"}).copy()
    review["status"] = "keep"
    review = review.set_geometry("geometry")
    rp = rev / f"review_pits_{tag}.gpkg"
    review.to_file(rp, layer="review", driver="GPKG")
    shutil.copyfile(rp, rev / f"review_pits_{tag}_ORIGINAL.gpkg")
    (rev / f"review_pits_{tag}.qml").write_text(pkg.QML, encoding="utf-8")
    w = g[g["type"] == "W"].drop_duplicates("review_id")[["review_id", "geometry"]]
    if len(w):
        w.to_file(rev / f"windows_{tag}.gpkg", layer="windows", driver="GPKG")
    import geopandas as gpd
    added = gpd.GeoDataFrame({"status": pd.Series([], dtype="object"), "note": pd.Series([], dtype="object")},
                             geometry=gpd.GeoSeries([], crs=items_geo.crs))
    pyogrio.write_dataframe(added, rev / f"added_pits_{tag}.gpkg", layer="added", geometry_type="Polygon")
    note = ("\n## Discovery windows\nEach polygon in `windows_" + tag + ".gpkg` is a block to annotate in full. "
            "Draw every pit inside it in `added_pits_" + tag + ".gpkg`.\nThe sheet shows no model score and no well record.\n")
    (rev / "README_EDIT.md").write_text(pkg.README.format(key=tag) + note, encoding="utf-8")
    idmap = interim_dir() / f"al_review_idmap_{tag}.csv"
    g.drop(columns="geometry").to_csv(idmap, index=False)
    return rev


def ingest(round_dir: Path, cfg, rnd: int, minutes_csv: Path | None) -> pd.DataFrame:
    import geopandas as gpd
    import pyogrio
    tag = f"al_r{rnd:02d}"
    rev = round_dir / "review"
    idmap = pd.read_csv(need(interim_dir() / f"al_review_idmap_{tag}.csv", "review id map"))
    out = rev / f"corrections_diff_pits_{tag}.gpkg"
    cmd = [sys.executable, str(REVIEW_DIR / "_pit_corrections_diff.py"), "--key", tag,
           "--original", str(rev / f"review_pits_{tag}_ORIGINAL.gpkg"), "--edited", str(rev / f"review_pits_{tag}.gpkg"),
           "--added", str(rev / f"added_pits_{tag}.gpkg"), "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pit corrections diff failed: {r.stderr[-800:]}")
    layers = {n for n, _ in pyogrio.list_layers(str(out))} if out.exists() else set()
    status = {}
    for st in ("keep", "reject", "unsure"):
        if st in layers:
            for pid in gpd.read_file(out, layer=st)["pit_inside_id"]:
                status[f"R{int(pid):05d}"] = st
    added = gpd.read_file(out, layer="added") if "added" in layers else gpd.GeoDataFrame(geometry=[])
    rows = []
    wins = idmap[idmap["type"] == "W"]
    for _, it in idmap.iterrows():
        if it["type"] == "C":
            st = status.get(it["review_id"], "missing")
            rows.append({"item_id": it["item_id"], "review_id": it["review_id"], "policies": it["policy"],
                         "status": st, "y": {"keep": 1, "reject": 0}.get(st), "n_added": 0})
    if len(wins):
        wg = gpd.read_file(rev / f"windows_{tag}.gpkg", layer="windows")
        for _, wr in wins.drop_duplicates("item_id").iterrows():
            poly = wg.loc[wg["review_id"] == wr["review_id"], "geometry"]
            n = int(added.geometry.centroid.within(poly.iloc[0]).sum()) if len(poly) and len(added) else 0
            rows.append({"item_id": wr["item_id"], "review_id": wr["review_id"], "policies": wr["policy"],
                         "status": "annotated", "y": None, "n_added": n})
    lab = pd.DataFrame(rows)
    if (lab["status"] == "missing").any():
        raise AssertionError("candidates missing from the diff output")
    lab.to_csv(round_dir / "labels.csv", index=False)
    if minutes_csv is not None:
        m = pd.read_csv(need(minutes_csv, "timer minutes"))
        per_review = m.groupby("item_id")["minutes"].sum()            # timer item ids are review ids
        mm = []
        for _, rr in lab.iterrows():
            for pol in str(rr["policies"]).split(";"):
                mm.append({"policy": pol, "item_id": rr["item_id"], "minutes": float(per_review.get(rr["review_id"], np.nan))})
        pd.DataFrame(mm).to_csv(round_dir / "minutes.csv", index=False)
    return lab


def main(argv=None) -> int:
    import geopandas as gpd
    ap = argparse.ArgumentParser(description="7.2 blind review package and label ingestion.")
    ap.add_argument("--config", default=str(CFG))
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("package", "ingest"):
        s = sp.add_parser(c)
        s.add_argument("--round", type=int, required=True)
        s.add_argument("--round-dir", default=None)
        if c == "package":
            s.add_argument("--items-geo", default=str(ek.sub("7.2", "data/interim") / "al_items_9t.gpkg"))
        else:
            s.add_argument("--minutes", default=None)
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    rd = Path(a.round_dir) if a.round_dir else ek.sub("7.2", f"results/live/round_{a.round:02d}")
    try:
        if a.cmd == "package":
            print(f"review package {package(rd, gpd.read_file(need(Path(a.items_geo), 'item polygons')), cfg, a.round)}")
        else:
            lab = ingest(rd, cfg, a.round, Path(a.minutes) if a.minutes else None)
            print(lab["status"].value_counts().to_dict())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Sampling frames and seeded draws for the three field arms, with inclusion probabilities (7.5 S1).

Purpose
    Arm A. Probability sample of drawn pits and pads in audit blocks or the reserved area. Strata are
           morphology x era proxy. Era proxy comes from the nearest DEP record within 50 m. A spud date
           before 1900 is early_dated, 1900 to 1929 transition_dated, 1930 on steel_dated. The 1800
           sentinel is its own stratum (unknown_sentinel) and never early era. No record is no_record.
           A dated historic mark (4.6) within the radius makes early_map. Allocation is proportional with
           a floor of 10 per stratum (capped at the stratum size). Stratified simple random sampling
           without replacement, so pi = n_h / N_h exactly.
    Arm B. Model candidates at the frozen K that lie inside the Arm A frame, cut into 5 equal-count score
           bands, equal allocation. The frame is the 5.4 density site table (site_id, max_score, cx, cy), so the
           density export can join on its site_id. Its sha256 is kept in the key (frame_sha256).
    Arm C. Random 250 m cells fully inside the reserved area, excluding cells within 50 m of an Arm A or
           B site. Each cell is searched in full. DEP wells inside a drawn cell are listed as seeded
           controls in the private key (search sensitivity, S4).
    Two files. The blind sample has no score, no record status and no stratum name that reveals either.
    The private key holds them for the analysis. Both are hashed.

Inputs (config_7_5.json)
    annotations (held), blocks (held), audit block list (P2, read with ek.require_audit, role audit only)
    and/or reserved area (assumed),
    frozen candidates (P2, assumed), DEP wells (held, read-only), historic marks (4.6, optional)
Outputs (expansions/7_scale/7_5_field_campaign/results/tables/)
    field_sample_blind_v1.csv     site_id, arm, x, y, lon, lat, cluster_id, pi, weight
    field_sample_key_v1.csv       site_id, arm, stratum, source_id, score, era, record ids (private)
    field_sample_v1.sha256        hashes of both, written once (frozen). A second draw is refused unless --force
    field_frame_counts_v1.csv     N and n per arm and stratum

Run
    python expansions/7_scale/7_5_field_campaign/src/_field_sample_draw_frames.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

HERE = Path(__file__).resolve().parent
CFG = HERE / "config_7_5.json"


def load_cfg(path: Path = CFG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cfg_path(entry: dict) -> Path:
    return ek.path_for(entry["key"]) / entry["rel"]


def need(path: Path, what: str) -> Path:
    if not Path(path).exists():
        raise FileNotFoundError(f"missing input for 7.5 ({what}): {path}. See config_7_5.json")
    return Path(path)


# ----------------------------------------------------------------------------- era proxy
def era_class(spud, rules: dict) -> str:
    if spud is None or (isinstance(spud, float) and np.isnan(spud)) or str(spud).strip() in ("", "None", "NaT"):
        return "no_date"
    s = str(spud)[:10]
    if s == rules["sentinel"]:
        return "unknown_sentinel"
    try:
        y = int(s[:4])
    except ValueError:
        return "no_date"
    if y < rules["early_before_year"]:
        return "early_dated"
    return "steel_dated" if y >= rules["steel_from_year"] else "transition_dated"


def attach_era(feat, wells, rules: dict, spud_col: str, id_col: str, marks=None):
    from scipy.spatial import cKDTree
    f = feat.copy()
    c = f.geometry.centroid
    f["era"] = "no_record"
    f["dep_id"] = None
    if wells is not None and len(wells):
        wc = wells.geometry.centroid
        d, j = cKDTree(np.c_[wc.x, wc.y]).query(np.c_[c.x, c.y])
        near = d <= rules["radius_m"]
        f.loc[near, "era"] = [era_class(wells.iloc[k][spud_col], rules) for k in j[near]]
        f.loc[near, "dep_id"] = [str(wells.iloc[k][id_col]) for k in j[near]]
        f.loc[f["era"] == "no_date", "era"] = "record_no_date"
    if marks is not None and len(marks):
        mc = marks.geometry.centroid
        d, _ = cKDTree(np.c_[mc.x, mc.y]).query(np.c_[c.x, c.y])
        upgrade = (d <= rules["radius_m"]) & f["era"].isin(["no_record", "unknown_sentinel", "record_no_date"])
        f.loc[upgrade, "era"] = "early_map"
    return f


# ----------------------------------------------------------------------------- allocation and draws
def allocate(sizes: dict, n: int, floor: int) -> dict:
    """Proportional allocation with a floor, capped at stratum size. Largest-remainder rounding."""
    N = sum(sizes.values())
    if n >= N:
        return dict(sizes)
    base = {h: min(Nh, floor) for h, Nh in sizes.items()}
    rest = n - sum(base.values())
    if rest < 0:
        raise AssertionError(f"n = {n} is below the floor total {sum(base.values())}. Raise n or lower the floor")
    room = {h: sizes[h] - base[h] for h in sizes}
    R = sum(room.values())
    raw = {h: rest * room[h] / R if R else 0 for h in sizes}
    add = {h: int(np.floor(v)) for h, v in raw.items()}
    for h in sorted(raw, key=lambda h: -(raw[h] - add[h]))[: rest - sum(add.values())]:
        add[h] += 1
    return {h: min(sizes[h], base[h] + add[h]) for h in sizes}


def stratified_draw(df: pd.DataFrame, strat_col: str, alloc: dict, seed: int) -> pd.DataFrame:
    out = []
    for i, (h, g) in enumerate(sorted(df.groupby(strat_col), key=lambda t: str(t[0]))):
        n_h = alloc.get(h, 0)
        rng = np.random.default_rng(ek.child_seed(seed, 0, i))
        pick = g.iloc[np.sort(rng.choice(len(g), n_h, replace=False))] if n_h else g.iloc[:0]
        out.append(pick.assign(pi=n_h / len(g), N_h=len(g), n_h=n_h))
    return pd.concat(out, ignore_index=True)


def arm_a(cfg, feats, wells, marks, frame_geom):
    import geopandas as gpd
    rules = cfg["era_rules"]
    dep = cfg["inputs"]["dep_wells"]
    f = feats[feats.geometry.centroid.within(frame_geom)].copy()
    if not len(f):
        raise AssertionError("no drawn features inside the Arm A frame")
    f = attach_era(f, wells, rules, dep["spud_col"], dep["id_col"], marks)
    f["stratum"] = f["morph"] + "|" + f["era"]
    alloc = allocate(f["stratum"].value_counts().to_dict(), cfg["arm_A"]["n"], cfg["arm_A"]["floor_per_stratum"])
    s = stratified_draw(f, "stratum", alloc, ek.child_seed(cfg["master_seed"], 0, 1))
    s["arm"] = "A"
    s["score"] = np.nan
    return gpd.GeoDataFrame(s, geometry="geometry", crs=feats.crs), f


def arm_b_frame(cands: pd.DataFrame) -> pd.DataFrame:
    """Normalise the Arm B frame. Two schemas are accepted.
    5.4 density site table (site_id, max_score, cx, cy). Its site_id is what 5.4 S3 joins on (review F16).
    Frozen candidate list (cand_id, score, cx, cy). It cannot feed the 5.4 export, which refuses it."""
    c = cands.copy()
    if "site_id" in c.columns:
        c["cand_id"] = c["site_id"].astype(int).astype(str)
        c["score"] = c["max_score"] if "max_score" in c.columns else c["score"]
        c["frame_schema"] = "density_sites_5_4"
    else:
        c["frame_schema"] = "candidates"
    miss = [k for k in ("cand_id", "score", "cx", "cy") if k not in c.columns]
    if miss:
        raise AssertionError(f"Arm B frame lacks columns {miss}")
    return c


def arm_b(cfg, cands: pd.DataFrame, frame_geom=None, frame_sha256: str = ""):
    """Score-stratified draw from the candidates that lie inside the Arm A frame (audit blocks or reserved area).
    Candidates outside the frame sit on ground the model may have trained on (review minor, 7.5 arm B)."""
    import geopandas as gpd
    nb = cfg["arm_B"]["n_bands"]
    c = arm_b_frame(cands)
    if frame_geom is not None:
        inside = gpd.points_from_xy(c["cx"], c["cy"]).within(frame_geom)
        c = c[np.asarray(inside)]
    if not len(c):
        raise AssertionError("no Arm B candidates inside the frame (audit blocks or reserved area)")
    c = c.sort_values(["score", "cand_id"], ascending=[False, True]).reset_index(drop=True)
    c["stratum"] = [f"band{b + 1}" for b in pd.qcut(np.arange(len(c)), nb, labels=False)]
    per = cfg["arm_B"]["n"] // nb
    alloc = {h: min(per, (c["stratum"] == h).sum()) for h in c["stratum"].unique()}
    s = stratified_draw(c, "stratum", alloc, ek.child_seed(cfg["master_seed"], 0, 2))
    s["arm"] = "B"
    s["frame_sha256"] = frame_sha256
    return gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s["cx"], s["cy"]), crs=cfg["crs"])


def arm_c(cfg, reserved, sites, wells):
    import geopandas as gpd
    from shapely.geometry import box
    cm = cfg["arm_C"]["cell_m"]
    x0, y0, x1, y1 = reserved.total_bounds
    cells = [box(x, y, x + cm, y + cm) for x in np.arange(np.floor(x0 / cm) * cm, x1, cm)
             for y in np.arange(np.floor(y0 / cm) * cm, y1, cm)]
    area = reserved.union_all()
    g = gpd.GeoDataFrame({"cell_id": [f"cell_{int(c.bounds[0])}_{int(c.bounds[1])}" for c in cells]}, geometry=cells, crs=reserved.crs)
    g = g[g.geometry.within(area)]
    if len(sites):
        near = sites.buffer(cfg["arm_C"]["buffer_m"]).union_all()
        g = g[~g.geometry.intersects(near)]
    N = len(g)
    n = min(cfg["arm_C"]["n_cells"], N)
    if N == 0:
        raise AssertionError("no eligible Arm C cells inside the reserved area")
    rng = np.random.default_rng(ek.child_seed(cfg["master_seed"], 0, 3))
    s = g.iloc[np.sort(rng.choice(N, n, replace=False))].copy()
    s["pi"], s["N_h"], s["n_h"], s["stratum"], s["arm"] = n / N, N, n, "cell", "C"
    s["controls"] = ""
    if wells is not None and len(wells):
        idc = cfg["inputs"]["dep_wells"]["id_col"]
        j = gpd.sjoin(wells[[idc, "geometry"]], s[["cell_id", "geometry"]], predicate="within")
        ctl = j.groupby("cell_id")[idc].apply(lambda v: ";".join(map(str, v)))
        s["controls"] = s["cell_id"].map(ctl).fillna("")
    return s


def assemble(a, b, c, crs) -> tuple[pd.DataFrame, pd.DataFrame]:
    import geopandas as gpd
    parts = []
    for arm, df, sid in (("A", a, "feature_id"), ("B", b, "cand_id"), ("C", c, "cell_id")):
        if df is None or not len(df):
            continue
        d = gpd.GeoDataFrame(df, geometry="geometry", crs=crs)
        cen = d.geometry.centroid
        parts.append(pd.DataFrame({"arm": arm, "source_id": d[sid].astype(str), "stratum": d["stratum"], "pi": d["pi"],
                                   "N_h": d["N_h"], "n_h": d["n_h"], "x": cen.x.round(2), "y": cen.y.round(2),
                                   "score": d.get("score", np.nan), "era": d.get("era", ""), "dep_id": d.get("dep_id", ""),
                                   "controls": d.get("controls", ""), "cluster_id": d.get("cluster_id", d[sid]).astype(str),
                                   "area_m2": d.geometry.area.round(1),
                                   "frame_schema": d.get("frame_schema", ""), "frame_sha256": d.get("frame_sha256", "")}))
    s = pd.concat(parts, ignore_index=True)
    s.insert(0, "site_id", [f"S{i:04d}" for i in range(len(s))])
    ll = gpd.GeoSeries(gpd.points_from_xy(s["x"], s["y"]), crs=crs).to_crs("EPSG:4326")
    s["lon"], s["lat"] = ll.x.round(7), ll.y.round(7)
    s["weight"] = 1.0 / s["pi"]
    ek.assert_unique(s, "site_id")
    blind = s[["site_id", "arm", "x", "y", "lon", "lat", "area_m2", "pi", "weight"]]
    key = s[["site_id", "arm", "stratum", "source_id", "score", "era", "dep_id", "controls", "cluster_id", "pi", "N_h", "n_h",
             "frame_schema", "frame_sha256"]]
    return blind, key


def cluster_ids(feats, wells, cfg):
    """Cluster on the DEP pad id of the nearest record within the radius, else the feature itself."""
    from scipy.spatial import cKDTree
    pad_col = cfg["inputs"]["dep_wells"]["pad_col"]
    out = feats["feature_id"].astype(str).copy()
    if wells is not None and len(wells) and pad_col in wells.columns:
        wc = wells.geometry.centroid
        c = feats.geometry.centroid
        d, j = cKDTree(np.c_[wc.x, wc.y]).query(np.c_[c.x, c.y])
        pads = wells[pad_col].to_numpy()
        for i in np.nonzero(d <= cfg["era_rules"]["radius_m"])[0]:
            if pd.notna(pads[j[i]]) and str(pads[j[i]]).strip():
                out.iloc[i] = f"pad_{pads[j[i]]}"
    return out


def draw(cfg: dict, out: Path, force: bool = False) -> dict:
    import geopandas as gpd
    sys.path.insert(0, str(ek.REPO / "notebooks" / "wellsight_v2"))
    from _common import read_layer
    lock = out / "field_sample_v1.sha256"
    if lock.exists() and not force:
        raise PermissionError(f"the sample is frozen ({lock}). A redraw needs a new version")
    inp = cfg["inputs"]
    ann = need(cfg_path(inp["truth"]), "annotations")
    feats = []
    for cls, layer in inp["truth"]["layers"].items():
        g = read_layer(ann, layer).to_crs(cfg["crs"])
        mcol = inp["morphology"]["col"]
        g["morph"] = g[mcol].astype(str) if mcol in g.columns else f"{cls}_{inp['morphology']['default']}"
        g["feature_id"] = [f"{cls}_{i:05d}" for i in range(len(g))]
        feats.append(g[["feature_id", "morph", "geometry"]])
    feats = gpd.GeoDataFrame(pd.concat(feats, ignore_index=True), geometry="geometry", crs=cfg["crs"])
    wells = gpd.read_file(need(cfg_path(inp["dep_wells"]), "DEP wells")).to_crs(cfg["crs"])
    mp = cfg_path(inp["historic_marks"])
    marks = gpd.read_file(mp).to_crs(cfg["crs"]) if mp.exists() else None
    feats["cluster_id"] = cluster_ids(feats, wells, cfg)
    frames = []
    rp = cfg_path(inp["reserved_area"])
    reserved = gpd.read_file(rp).to_crs(cfg["crs"]) if rp.exists() else None
    ap_ = cfg_path(inp["audit_blocks"])
    # P2 audit CSV has # header lines and a sha256 sidecar. Only the P2 reader may parse it (review F05).
    # A missing file is allowed only because the reserved area is a declared alternative frame. It is recorded.
    audit = ek.require_audit(ap_, allow_missing=True)
    frame_sources = []
    if audit is not None:
        blocks = gpd.read_file(need(cfg_path(inp["blocks"]), "blocks"))
        ids = ek.audit_ids(audit, roles=("audit",))           # sealed test blocks only, not the buffer margin
        frames.append(blocks[blocks["block_id"].astype(int).isin(ids)].union_all())
        frame_sources.append(f"P2 audit blocks {sorted(ids)} sha256 {audit.attrs.get('sha256', '')[:12]}")
    if reserved is not None:
        frames.append(reserved.union_all())
        frame_sources.append("reserved area")
    if not frames:
        raise FileNotFoundError(f"no Arm A frame. Need the P2 audit list ({ap_}) or the reserved area ({rp})")
    if audit is None:
        frame_sources.append("no audit exclusion. P2 audit set missing, frame is the reserved area only")
    from shapely.ops import unary_union
    frame_geom = unary_union(frames)
    a, frame_all = arm_a(cfg, feats, wells, marks, frame_geom)
    cp = cfg_path(inp["candidates_frozen"])
    b = arm_b(cfg, pd.read_csv(cp), frame_geom, ek.sha256(cp)) if cp.exists() else None
    sites = pd.concat([x.geometry for x in (a, b) if x is not None])
    c = arm_c(cfg, reserved, gpd.GeoSeries(sites, crs=cfg["crs"]), wells) if reserved is not None else None
    blind, key = assemble(a, b, c, cfg["crs"])
    out.mkdir(parents=True, exist_ok=True)
    blind.to_csv(out / "field_sample_blind_v1.csv", index=False)
    key.to_csv(out / "field_sample_key_v1.csv", index=False)
    counts = key.groupby(["arm", "stratum"]).agg(N_h=("N_h", "first"), n_h=("n_h", "first")).reset_index()
    counts.to_csv(out / "field_frame_counts_v1.csv", index=False)
    lock.write_text(f"{ek.sha256(out / 'field_sample_blind_v1.csv')}  field_sample_blind_v1.csv\n"
                    f"{ek.sha256(out / 'field_sample_key_v1.csv')}  field_sample_key_v1.csv\n", encoding="utf-8")
    ek.write_provenance(out, inputs=[ann, cfg_path(inp["dep_wells"])], outputs=[out / "field_sample_blind_v1.csv"],
                        params={k: cfg[k] for k in ("arm_A", "arm_B", "arm_C", "era_rules")},
                        seeds={"master": cfg["master_seed"]})
    return {"n_sites": len(blind), "by_arm": blind["arm"].value_counts().to_dict(), "frame_sources": frame_sources,
            "missing_arms": [n for n, x in (("B", b), ("C", c)) if x is None]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 S1 sampling frames and draws.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--out", default=str(ek.sub("7.5", "results/tables")))
    ap.add_argument("--force", action="store_true", help="overwrite the frozen sample. Record the reason in decisions_7_5.md")
    a = ap.parse_args(argv)
    try:
        print(json.dumps(draw(load_cfg(Path(a.config)), Path(a.out), a.force)))
    except (FileNotFoundError, PermissionError) as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

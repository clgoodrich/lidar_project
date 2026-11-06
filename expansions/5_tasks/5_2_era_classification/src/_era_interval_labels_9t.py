"""S2 interval labels and identity links for 5.2 era classification (fw_5_2 section 7 S2).

Purpose
    Build a construction-year interval [lo, hi] per independently dated well and link it to annotated features.
    - A valid DEP spud year y gives [y, y], source dep_spud.
    - An identity-resolved 4.6 mark on a map dated D gives [first_oil_year, D], source map:<map_id> (left-censored).
    - Absence from a map gives no label.
    - Several sources. The tightest interval wins. The others go to check_intervals. Non-overlap sets conflict.
    - Position-only marks are linked to the nearest well within pos_error_m (or the pad radius) and flagged
      link_flag = position_only. They are excluded from the primary fit.
    - Each labelled well is linked to the nearest annotated pad (plat) and pit floor (pit_inside) within the
      configured radii. One row per well-feature pair. The well keeps one fold through its block.
    The sentinel never produces a label. assert_no_sentinel runs on the output.

Inputs (config_5_2.json)
    dep_wells        @dep_wells/venango_wells_all.gpkg (read-only)
    historic_marks   @results_9t/historic/historic_well_marks_9t.gpkg (ASSUMED, 4.6 S4). Required unless --records-only.
    annotations      @truth/annotations_proj.gpkg layers plat, pit_inside
Outputs
    labels_csv   @exp:5.2/results/tables/era_interval_labels_9t.csv
    run folder   @exp:5.2/results/<YYYYMMDD>_era_labels_<hash>/
Evidence level
    (a) drawn feature with era as an attribute. Dates are (b) historical.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_interval_labels_9t.py
    python expansions/5_tasks/5_2_era_classification/src/_era_interval_labels_9t.py --records-only   (exploratory, no 4.6)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _era_core_tools as ec  # noqa: E402
from _era_strata_wells_9t import build_strata, load_marks  # noqa: E402

ek = th.ek


def link_features(xy: np.ndarray, feats, radius: float, id_col: str):
    """Nearest feature polygon within radius for each point. Returns (ids, dist) with NaN where none."""
    from shapely import STRtree, points
    ids = np.full(len(xy), np.nan)
    dist = np.full(len(xy), np.nan)
    if feats is None or not len(feats) or not len(xy):
        return ids, dist
    tree = STRtree(feats.geometry.values)
    pts = points(xy)
    pi, fi = tree.query_nearest(pts, max_distance=radius, return_distance=False, all_matches=False)
    g = feats.geometry.values
    for p, f in zip(pi, fi):
        ids[p] = feats[id_col].iloc[f]
        dist[p] = pts[p].distance(g[f])
    return ids, dist


def build_labels(strata: pd.DataFrame, marks, cfg: dict, pads=None, pits=None) -> pd.DataFrame:
    first = cfg["dates"]["first_oil_year"]
    classes = cfg["era_classes"]
    src: dict[str, list] = {}
    for r in strata[strata["stratum"] == "dated_record"].itertuples():
        src.setdefault(str(r.permit), []).append((r.spud_year, r.spud_year, "dep_spud", str(int(r.spud_year)),
                                                   "record", 0.0))
    if marks is not None:
        mk = marks.copy()
        mk["permit"] = mk["permit"].astype(object)
        # Position-only marks: nearest well within its stated error
        po = mk["identity_basis"] == "position_only"
        if po.any():
            t = cKDTree(np.c_[strata.x.values, strata.y.values])
            mxy = np.c_[mk.geometry.x.values, mk.geometry.y.values]
            rad = mk["pos_error_m"].fillna(cfg["link"]["pad_radius_m"]).to_numpy()
            d, j = t.query(mxy)
            near = po.to_numpy() & (d <= rad)
            mk.loc[near, "permit"] = strata["permit"].to_numpy()[j[near]]
        for r in mk[mk["permit"].notna() & mk["map_year"].notna()].itertuples():
            src.setdefault(str(r.permit), []).append((float(first), float(r.map_year), f"map:{r.map_id}",
                                                       str(int(r.map_year)), r.identity_basis,
                                                       float(r.pos_error_m) if pd.notna(r.pos_error_m) else np.nan))
    rows = []
    st = strata.set_index(strata["permit"].astype(str))
    for permit, ivs in src.items():
        if permit not in st.index:
            continue
        s = st.loc[permit]
        best, conflict = ec.tightest(ivs)
        others = [f"{a:.0f}-{b:.0f}:{c}" for a, b, c, *_ in ivs if (a, b, c) != best[:3]]
        lo, hi = best[0], best[1]
        # The label decides the stratum of a labelled well. The record stratum (possibly sentinel) is kept apart.
        lab_stratum = "dated_record" if best[2] == "dep_spud" else (
            "dated_map_position_only" if best[4] == "position_only" else "dated_map")
        rows.append(dict(permit=permit, stratum=lab_stratum, record_stratum=s["stratum"], x=s["x"], y=s["y"], lo=lo, hi=hi, source=best[2],
                         source_date=best[3], identity_basis=best[4], pos_error_m=best[5],
                         link_flag="position_only" if best[4] == "position_only" else "identity",
                         check_intervals=";".join(others), interval_conflict=conflict,
                         era_class=ec.era_class(lo, hi, classes), early=ec.early_label(lo, hi, classes)))
    lab = pd.DataFrame(rows, columns=["permit", "stratum", "record_stratum", "x", "y", "lo", "hi", "source", "source_date",
                                      "identity_basis", "pos_error_m", "link_flag", "check_intervals",
                                      "interval_conflict", "era_class", "early"])
    xy = np.c_[lab.x.values, lab.y.values] if len(lab) else np.zeros((0, 2))
    lab["pad_id"], lab["pad_dist_m"] = link_features(xy, pads, cfg["link"]["pad_radius_m"], "pad_id")
    lab["pit_id"], lab["pit_dist_m"] = link_features(xy, pits, cfg["link"]["pit_radius_m"], "pit_inside_id")
    lab["primary"] = (lab["link_flag"] == "identity") & ~lab["interval_conflict"]
    ec.assert_no_sentinel(lab)
    lab = th.tag(lab, "a", "exploratory")
    lab["era_basis"] = "interval"
    return lab


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    ap.add_argument("--records-only", action="store_true", help="exploratory labels from DEP spud dates only")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    dep_p = th.inp(cfg, "dep_wells")
    marks = None
    if not a.records_only:
        th.inp(cfg, "historic_marks")  # fails with MissingInput naming 4.6 when absent
        marks = load_marks(cfg)
    w = th.load_dep(dep_p, bbox=cfg["bbox_9t"])
    strata = build_strata(w, marks, cfg)
    ann = th.inp(cfg, "annotations")
    pads = th.read_vector(ann, "plat")
    pits = th.read_vector(ann, "pit_inside")
    lab = build_labels(strata, marks, cfg, pads, pits)
    if a.records_only:
        lab["analysis"] = "exploratory_records_only"
    csv = th.outp(cfg, "labels_csv")
    lab.to_csv(csv, index=False)
    run = ek.new_run("5.2", "era_labels", {"link": cfg["link"], "classes": cfg["era_classes"], "records_only": a.records_only},
                     base=th.resolve(cfg["outputs"]["runs"]), why="S2 interval labels.")
    ins = [dep_p, ann] + ([th.inp(cfg, "historic_marks")] if marks is not None else [])
    ek.write_provenance(run, inputs=ins, outputs=[csv], params={"link": cfg["link"]})
    print(lab["era_class"].value_counts().to_string())
    print(f"labelled wells {len(lab)}, with pad {int(lab.pad_id.notna().sum())}, primary {int(lab.primary.sum())}")
    print(csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())

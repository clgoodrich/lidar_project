"""5.6 S1 to S3. Corrected record association on 9t, three analyses, positive control and power.

Purpose
    Replaces the withdrawn notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py (left untouched). Changes,
    following protocol section 4.
    1. Reads the full detector output from S0 (matched + unmatched), never the unmatched leftovers.
    2. Each modality uses its own footprint (pit blocks with n_pits > 0, pad blocks with n_pads > 0), or a declared
       intersection (open_decisions.footprint). Observed and shifted records use the same eligibility rule.
    3. Observed rates per status group and radius. Pits by distance to the nearest detection centroid. Pads inside or
       within r of a polygon (many records may share a pad).
    4. Null. The whole record set of a group is translated as one, 200 to 500 m in a random direction, 300 shifts.
       Shifts losing more than 10% of records are redrawn. Each shift's retained count is saved.
    5. Proposals. Global one-to-one Hungarian across all statuses (default) or per-status competing proposals.
    6. Normalised excess association with a null-based interval. Not link PPV. Minimum detectable excess (power).
    Three analyses. full (headline), novel (unmatched only, labelled), annotated (agreement with drawings, not a
    detector test). All exploratory, since the withdrawn run existed. Evidence level (a) throughout. A pad centroid
    is not a borehole. A proposal is not a corrected coordinate.

Inputs (config_5_6.json)
    full_pit, full_pad   S0 outputs in expansions/5_tasks/5_6_record_association/data/processed/
    annotations          @truth/annotations_proj.gpkg (pit_inside, plat) for the annotated analysis
    pit_blocks, pad_blocks, dep_wells
Outputs (run folder expansions/5_tasks/5_6_record_association/results/<YYYYMMDD>_recassoc_<hash7>/)
    rates.csv            one row per modality x detector set x group x radius
    null_retained.csv    retained record count of every accepted shift
    proposals.csv        pit-level one-to-one proposals and pad-level containment proposals
    summary.json         settings, counts, positive control verdict, primary per group, power
    records_assoc_rates_9t.png   observed (blue circles) against null mean (grey squares) and 95% band
    _CONFIG.json, _RUN.md, _PROVENANCE.json
Run
    python expansions/5_tasks/5_6_record_association/src/_records_assoc_v2_9t.py [--n-shift 300] [--assignment per_status]
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402

ek = th.ek
SETS = ("full", "novel", "annotated")


def footprint_cells(blocks, count_col: str, origin, size) -> set:
    b = blocks[blocks[count_col] > 0]
    c = b.geometry.centroid
    ij = th.block_cells(np.c_[c.x, c.y], origin, size)
    return set(map(tuple, ij.tolist()))


def make_eligible(cells: set, bbox, origin, size):
    x0, y0, x1, y1 = bbox

    def f(xy):
        xy = np.atleast_2d(xy)
        inb = (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1)
        return inb & th.in_cells(xy, cells, origin, size)
    return f


def load_inputs(cfg):
    pit = th.read_vector(th.inp(cfg, "full_pit"))
    pad = th.read_vector(th.inp(cfg, "full_pad"))
    ann = th.inp(cfg, "annotations")
    ann_pit = th.read_vector(ann, layer="pit_inside")
    ann_pad = th.read_vector(ann, layer="plat")
    ann_pad["geometry"] = ann_pad.geometry.buffer(0)
    pit_blocks = th.read_vector(th.inp(cfg, "pit_blocks"), layer="blocks")
    pad_blocks = th.read_vector(th.inp(cfg, "pad_blocks"), layer="blocks")
    dep = th.load_dep(th.inp(cfg, "dep_wells"), bbox=cfg["tile_bbox"])
    return pit, pad, ann_pit, ann_pad, pit_blocks, pad_blocks, dep


def detector_sets(pit, pad, ann_pit, ann_pad):
    c = ann_pit.geometry.centroid
    return {
        "pit": {"full": np.c_[pit["cx"].to_numpy(), pit["cy"].to_numpy()],
                "novel": np.c_[pit.loc[pit.novel == 1, "cx"].to_numpy(), pit.loc[pit.novel == 1, "cy"].to_numpy()],
                "annotated": np.c_[c.x.to_numpy(), c.y.to_numpy()]},
        "pad": {"full": pad.geometry.values, "novel": pad.loc[pad.novel == 1].geometry.values,
                "annotated": ann_pad[~ann_pad.geometry.is_empty].geometry.values},
    }


def analyse(cfg, rec_xy_by_group: dict, dets: dict, elig: dict, n_shift: int):
    """Observed, null and excess for every modality x set x group x radius."""
    rows, retained = [], []
    nl = cfg["null"]
    master = int(cfg["seed"])
    for mi, mod in enumerate(("pit", "pad")):
        radii = cfg[mod]["radii_m"]
        for si, s in enumerate(SETS):
            det = dets[mod][s]
            rate_fn = core.pit_rate_fn(det, radii) if mod == "pit" else core.pad_rate_fn(det, radii)
            for gi, (g, xy_all) in enumerate(rec_xy_by_group.items()):
                xy = xy_all[elig[mod](xy_all)] if len(xy_all) else xy_all.reshape(0, 2)
                obs = rate_fn(xy)
                seed = ek.child_seed(master, fold=mi * 10 + si, arm=gi)
                max_loss = nl["max_loss"] if cfg["open_decisions"]["null_redraw"] == "reject_and_redraw" else 1.0
                nul = core.shift_null(xy, elig[mod], rate_fn, n_shift=n_shift, dmin=nl["shift_min_m"],
                                      dmax=nl["shift_max_m"], max_loss=max_loss,
                                      rng=np.random.default_rng(seed), max_tries=nl["max_tries"])
                for k, rk in enumerate(nul["retained"]):
                    retained.append(dict(modality=mod, detector_set=s, group=g, shift=k, retained=rk, n_records=len(xy)))
                for r in radii:
                    v = [d[r] for d in nul["draws"]]
                    e = core.excess(obs[r], v)
                    rows.append(dict(modality=mod, detector_set=s, group=g, radius_m=r, n_records=len(xy),
                                     n_detections=len(det), primary=int(r == cfg[mod]["primary_radius_m"]),
                                     **{k: (round(x, 5) if isinstance(x, float) else x) for k, x in e.items()},
                                     mde=round(core.mde(len(xy), v), 5), shifts_rejected=nul["rejected"],
                                     null_status="ok" if len(v) else "unattainable_under_loss_rule",
                                     seed=seed))
    R = pd.DataFrame(rows)
    R["evidence_level"] = "a"
    R["analysis"] = np.where(R.detector_set == "annotated", "exploratory_agreement_with_drawings",
                             np.where(R.detector_set == "novel", "exploratory_novel_only", "exploratory_full_output"))
    return R, pd.DataFrame(retained)


def proposals(cfg, dep_el, groups, pit, pad, mode: str):
    """Pit one-to-one (global or per status) and pad containment proposals. Proposed, not corrected."""
    rec_xy = np.c_[dep_el.x.to_numpy(), dep_el.y.to_numpy()]
    det_xy = np.c_[pit["cx"].to_numpy(), pit["cy"].to_numpy()]
    rows = core.assign(rec_xy, groups, det_xy, cfg["pit"]["gate_m"], mode)
    P = pd.DataFrame(rows)
    out = []
    if len(P):
        r = dep_el.iloc[P.rec_idx.to_numpy()]
        d = pit.iloc[P.det_idx.to_numpy()]
        out.append(pd.DataFrame(dict(level="pit", permit=r.PERMIT_NUM.values, status=r.WELL_STATU.values,
                                     group=P.group.values, rec_x=r.x.values, rec_y=r.y.values,
                                     det_id=d.det_id.values, det_source=d.source.values, det_score=d.score.values,
                                     det_x=d["cx"].values, det_y=d["cy"].values, dist_m=P.dist_m.round(1).values,
                                     proposal_type=P.proposal_type.values)))
    import geopandas as gpd
    pts = gpd.GeoDataFrame(dep_el[["PERMIT_NUM", "WELL_STATU", "x", "y"]].assign(group=groups),
                           geometry=gpd.points_from_xy(dep_el.x, dep_el.y), crs=th.CRS)
    j = gpd.sjoin(pts, pad[["det_id", "source", "score", "cx", "cy", "geometry"]], predicate="within")
    if len(j):
        out.append(pd.DataFrame(dict(level="pad", permit=j.PERMIT_NUM.values, status=j.WELL_STATU.values,
                                     group=j.group.values, rec_x=j.x.values, rec_y=j.y.values, det_id=j.det_id.values,
                                     det_source=j.source.values, det_score=j.score.values, det_x=j["cx"].values,
                                     det_y=j["cy"].values,
                                     dist_m=np.hypot(j.x.values - j["cx"].values, j.y.values - j["cy"].values).round(1),
                                     proposal_type="pad_contains_record_many_to_one")))
    Q = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(Q):
        Q.insert(0, "link_id", np.arange(len(Q)))
        Q["evidence_level"] = "a"
        Q["note"] = "proposed association, not a corrected coordinate; a pad centroid is not a borehole"
        pit_q = Q[(Q.level == "pit") & (Q.proposal_type == "global_one_to_one")]
        if len(pit_q):
            ek.assert_unique(pit_q, "det_id")       # global assignment: at most one record per detection
            ek.assert_unique(pit_q, "permit")
    return Q


def figure(R, cfg, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # Palette: observed ek.PALETTE blue #1F5FA8, null grey #8E959B (fw_00 section 7; worst pair from the
    # lost/found palette validation, dE 21.1 deutan, dataviz validator --pairs all). Second encoding: marker
    # shape (circle observed, square null) and line style.
    blue, grey = ek.PALETTE["blue"], ek.PALETTE["grey"]
    groups = list(cfg["status_groups"])
    fig, ax = plt.subplots(2, len(groups), figsize=(4.2 * len(groups), 7), sharey="row", squeeze=False)
    for row, mod in enumerate(("pit", "pad")):
        for col, g in enumerate(groups):
            a = ax[row, col]
            s = R[(R.modality == mod) & (R.group == g) & (R.detector_set == "full")]
            if not len(s):
                continue
            a.fill_between(s.radius_m, s.null_lo, s.null_hi, color=grey, alpha=0.3, label="shifted records, 95%")
            a.plot(s.radius_m, s.null_mean, color=grey, ls="--", marker="s", label="shifted records, mean")
            a.plot(s.radius_m, s.observed, color=blue, ls="-", marker="o", label="DEP records")
            a.set_title(f"{mod}, {g.replace('_', ' ')} (n={int(s.n_records.iloc[0])})", fontsize=9)
            a.set_xlabel("distance (m), 0 = inside pad" if mod == "pad" else "distance to detection centroid (m)")
    ax[0, 0].set_ylabel("share of records with a feature")
    ax[1, 0].set_ylabel("share of records with a feature")
    ax[0, 0].legend(fontsize=7, loc="upper left")
    fig.suptitle("Records against the full detector output, 9t, exploratory, evidence level (a)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--n-shift", type=int)
    ap.add_argument("--assignment", choices=("global", "per_status"))
    ap.add_argument("--footprint", choices=("per_modality", "intersection"))
    ap.add_argument("--null-redraw", choices=("reject_and_redraw", "report_retained"))
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    if a.assignment:
        cfg["open_decisions"]["assignment"] = a.assignment
    if a.footprint:
        cfg["open_decisions"]["footprint"] = a.footprint
    if a.null_redraw:
        cfg["open_decisions"]["null_redraw"] = a.null_redraw
    n_shift = a.n_shift or cfg["null"]["n_shift"]
    org, size, bbox = cfg["block_origin"], cfg["block_m"], cfg["tile_bbox"]

    pit, pad, ann_pit, ann_pad, pit_blocks, pad_blocks, dep = load_inputs(cfg)
    cp = footprint_cells(pit_blocks, "n_pits", org, size)
    cd = footprint_cells(pad_blocks, "n_pads", org, size)
    if cfg["open_decisions"]["footprint"] == "intersection":
        cp = cd = cp & cd
    elig = {"pit": make_eligible(cp, bbox, org, size), "pad": make_eligible(cd, bbox, org, size)}
    dep["group"] = th.status_group(dep.WELL_STATU, cfg["status_groups"])
    dep = dep[dep.group != "other"].reset_index(drop=True)
    by_group = {g: np.c_[dep.loc[dep.group == g, "x"].to_numpy(), dep.loc[dep.group == g, "y"].to_numpy()]
                for g in cfg["status_groups"]}
    dets = detector_sets(pit, pad, ann_pit, ann_pad)

    run_cfg = {k: v for k, v in copy.deepcopy(cfg).items() if not k.startswith("_")}
    run_cfg["n_shift_used"] = n_shift
    run = ek.new_run("5.6", "recassoc", run_cfg, base=th.resolve(cfg["outputs"]["runs"]),
                     why="Corrected association, full detector output, per-modality footprints, shifted null.")
    R, ret = analyse(cfg, by_group, dets, elig, n_shift)
    dep_el = dep[elig["pit"](np.c_[dep.x, dep.y]) | elig["pad"](np.c_[dep.x, dep.y])].reset_index(drop=True)
    Q = proposals(cfg, dep_el, dep_el.group.to_numpy(), pit, pad, cfg["open_decisions"]["assignment"])

    pc = cfg["positive_control"]
    pcr = R[(R.modality == pc["level"]) & (R.group == pc["group"]) & (R.radius_m == pc["radius_m"]) &
            (R.detector_set == pc["detector_set"])]
    pc_pass = bool(len(pcr) and pcr.norm_lo.iloc[0] > 0)
    prim = R[R.primary == 1][["modality", "detector_set", "group", "radius_m", "n_records", "observed", "null_mean",
                               "norm_excess", "norm_lo", "norm_hi", "mde"]]
    summary = dict(
        evidence_level="a", analysis="exploratory",
        statistic="normalised excess association = (observed - null mean) / (1 - null mean). Not link PPV.",
        counts=dict(pit_detections=len(pit), pit_novel=int(pit.novel.sum()), pad_detections=len(pad),
                    pad_novel=int(pad.novel.sum()), pit_footprint_blocks=len(cp), pad_footprint_blocks=len(cd),
                    records_by_group={g: int(len(v)) for g, v in by_group.items()},
                    proposals_by_level=Q.level.value_counts().to_dict() if len(Q) else {}),
        open_decisions=cfg["open_decisions"], n_shift=n_shift,
        positive_control=dict(spec=pc, passed=pc_pass,
                              row=pcr.iloc[0].to_dict() if len(pcr) else None,
                              rule="lower bound of normalised excess above 0. If it fails the target-group result cannot be interpreted."),
        primary=prim.to_dict(orient="records"),
        null_unattainable=R.loc[R.null_status != "ok", ["modality", "detector_set", "group"]].drop_duplicates().to_dict(orient="records"),
        null_conditions="Whole record set translated as one. Keeps record count and clustering. Gradients in oil development and road density only partly preserved.",
        caveat="Annotators did not see DEP points (user, 2026-11-04). Other annotation context is unrecorded.")
    files = {"rates": run / "rates.csv", "ret": run / "null_retained.csv", "prop": run / "proposals.csv",
             "sum": run / "summary.json", "fig": run / "records_assoc_rates_9t.png"}
    R.to_csv(files["rates"], index=False)
    ret.to_csv(files["ret"], index=False)
    Q.to_csv(files["prop"], index=False)
    th.write_json(files["sum"], summary)
    figure(R, cfg, files["fig"])
    ek.write_provenance(run, inputs=[th.inp(cfg, k) for k in ("full_pit", "full_pad", "annotations", "pit_blocks",
                                                             "pad_blocks", "dep_wells")],
                        outputs=list(files.values()), params=run_cfg, seeds={"master": cfg["seed"]})
    print(prim.to_string(index=False))
    print("positive control passed:", pc_pass)
    print("run folder", run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

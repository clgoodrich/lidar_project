"""Field outcomes exported in the exact schemas that 5.4 S3 reads (7.5 to 5.4 handoff, review F16).

Purpose
    5.4 S3 (_density_field_bounds_9t.py) reads two files from this expansion's data/processed/ folder.
        arm_b_candidate_outcomes.csv   site_id, identity, weight, frame_sha256
            One row per sampled Arm B site, inaccessible sites included as ambiguous. site_id is the 5.4
            density site id, so the Arm B frame must be the 5.4 site table (density_distinct_sites_9t.csv).
            weight = 1 / pi. frame_sha256 is the hash the draw recorded. The export refuses when the frame
            file on disk no longer has that hash, or when the frame was a plain candidate list.
        arm_c_search_outcomes.csv      area_id, well_id, detected, search_round
            One row per confirmed well per search round, from the child well table. A round-2 find of the
            same well keeps its well_id. Controls (known DEP wells found on search) count as wells.
            detected = 1 when a frame site lies within detector_link_m of the well's GNSS position.
    5.4's arm_c schema has no row for a cell with no well, so two companion files keep what it cannot hold.
        arm_c_search_areas.csv   one row per sampled cell, zero-well and inaccessible cells included.
                                 pi, weight, outcome, access, searched, well counts, controls, frame hashes.
        arm_c_well_links.csv     one row per found well with its nearest frame site and the distance.
                                 This is the explicit detector link behind detected.
    Ambiguous well finds stay in the companion files only. 5.4's recall counts confirmed wells.

Inputs
    results/tables/field_results_clean_v1.csv, field_wells_clean_v1.csv, field_sample_key_v1.csv (7.5 S5, S1)
    the Arm B frame (config inputs.candidates_frozen, the 5.4 site table)
Outputs (expansions/7_scale/7_5_field_campaign/data/processed/, gitignored)
    arm_b_candidate_outcomes.csv, arm_c_search_outcomes.csv, arm_c_search_areas.csv, arm_c_well_links.csv,
    _PROVENANCE_density_export.json
    The 5.4 config already points at the first two (@exp:7.5/data/processed/...). No copy is needed.

Run
    python expansions/7_scale/7_5_field_campaign/src/_field_density_export.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_sample_draw_frames import CFG, cfg_path, ek, load_cfg, need  # noqa: E402

ARM_B_COLS = ["site_id", "identity", "weight", "frame_sha256"]       # config_5_4.json inputs.arm_b.schema
ARM_C_COLS = ["area_id", "well_id", "detected", "search_round"]      # config_5_4.json inputs.arm_c.schema


def _frame_sites(frame: pd.DataFrame) -> pd.DataFrame:
    if "site_id" not in frame.columns:
        raise AssertionError("the Arm B frame has no 5.4 site_id. 5.4 S3 needs the density site table as the frame")
    return frame[["site_id", "cx", "cy"]].astype({"site_id": int})


def export(clean: pd.DataFrame, wells: pd.DataFrame, key: pd.DataFrame, frame_path: Path, cfg: dict,
           out: Path) -> dict:
    de = cfg["density_export"]
    frame_path = Path(frame_path)
    frame = _frame_sites(pd.read_csv(frame_path))
    sha_now = ek.sha256(frame_path)
    df = clean.merge(key, on=["site_id", "arm"], how="left", validate="one_to_one")
    ek.assert_rows(df, len(clean), "clean x key")
    ek.assert_no_nan(df["pi"], "pi")
    out.mkdir(parents=True, exist_ok=True)
    res = {"out": str(out), "frame": str(frame_path), "frame_sha256": sha_now}

    # ---------------------------------------------------------------- arm B
    b = df[df["arm"] == "B"]
    if len(b):
        if set(b["frame_schema"].astype(str)) != {"density_sites_5_4"}:
            raise AssertionError("Arm B was drawn from a frame without 5.4 site ids. Redraw from the 5.4 site table")
        drawn = set(b["frame_sha256"].astype(str))
        if drawn != {sha_now}:
            raise AssertionError(f"Arm B frame changed since the draw. Drawn {sorted(drawn)}, file now {sha_now}")
        ab = pd.DataFrame({"site_id": b["source_id"].astype(int).to_numpy(), "identity": b["identity"].to_numpy(),
                           "weight": 1.0 / b["pi"].to_numpy(float), "frame_sha256": b["frame_sha256"].to_numpy()})
        missing = set(ab["site_id"]) - set(frame["site_id"])
        if missing:
            raise AssertionError(f"Arm B site ids not in the frame {sorted(missing)[:5]}")
        ab[ARM_B_COLS].to_csv(out / "arm_b_candidate_outcomes.csv", index=False)
        res["arm_b_rows"] = int(len(ab))

    # ---------------------------------------------------------------- arm C
    c = df[df["arm"] == "C"].copy()
    if len(c):
        from scipy.spatial import cKDTree
        w = wells[wells["site_id"].isin(c["site_id"]) & (wells["status"] != "superseded")].copy()
        w["tied_record_id"] = w["tied_record_id"].fillna("").astype(str)
        tree = cKDTree(frame[["cx", "cy"]].to_numpy(float))
        if len(w):
            d, j = tree.query(w[["gnss_x", "gnss_y"]].to_numpy(float))
            w["nearest_frame_site_id"] = frame["site_id"].to_numpy()[j]
            w["link_m"] = np.round(d, 2)
        else:
            w["nearest_frame_site_id"], w["link_m"] = [], []
        w["detected"] = (w["link_m"] <= de["detector_link_m"]).astype(int)
        w["area_id"] = w["site_id"].map(c.set_index("site_id")["source_id"])
        # one detected value per distinct well, from its round-1 position (positions differ between rounds)
        w = w.sort_values(["well_id", "search_round"])
        w["detected"] = w.groupby("well_id")["detected"].transform(lambda s: int(s.iloc[0]) if len(s) else 0)
        links = w.sort_values(["area_id", "well_id", "search_round"])
        links[["area_id", "site_id", "visit_id", "search_round", "well_id", "identity", "tied_record_id",
               "gnss_x", "gnss_y", "nearest_frame_site_id", "link_m", "detected"]].to_csv(out / "arm_c_well_links.csv", index=False)
        conf = links[links["identity"] == "confirmed_well"]
        conf[ARM_C_COLS].to_csv(out / "arm_c_search_outcomes.csv", index=False)
        prim = w[w["status"] == "primary"]
        ctl = c[["site_id", "controls"]].assign(control_id=c["controls"].fillna("").astype(str).str.split(";")).explode("control_id")
        ctl = ctl[ctl["control_id"].astype(str).str.strip().ne("") & ctl["control_id"].astype(str).ne("nan")]
        found = set(zip(prim.loc[prim["identity"] == "confirmed_well", "site_id"], prim.loc[prim["identity"] == "confirmed_well", "tied_record_id"]))
        ctl["found"] = [(s, str(k)) in found for s, k in zip(ctl["site_id"], ctl["control_id"])]
        cnt = lambda m: prim[m].groupby("site_id").size().reindex(c["site_id"], fill_value=0).to_numpy()  # noqa: E731
        areas = pd.DataFrame({
            "area_id": c["source_id"].to_numpy(), "site_id": c["site_id"].to_numpy(),
            "pi": c["pi"].to_numpy(float), "weight": 1.0 / c["pi"].to_numpy(float),
            "N_h": c["N_h"].to_numpy(), "n_h": c["n_h"].to_numpy(),
            "outcome": c["outcome"].to_numpy(), "access": c["access"].to_numpy(),
            "searched": (c["outcome"] != "inaccessible").astype(int).to_numpy(),
            "n_wells_confirmed_r1": cnt(prim["identity"] == "confirmed_well"),
            "n_wells_undocumented_r1": cnt((prim["identity"] == "confirmed_well") & prim["tied_record_id"].eq("")),
            "n_wells_ambiguous_r1": cnt(prim["identity"] == "ambiguous"),
            "n_controls_listed": ctl.groupby("site_id").size().reindex(c["site_id"], fill_value=0).to_numpy(),
            "n_controls_found": ctl.groupby("site_id")["found"].sum().reindex(c["site_id"], fill_value=0).astype(int).to_numpy(),
            "repeat_searched": c["site_id"].isin(w.loc[w["search_round"] >= 2, "site_id"]).astype(int).to_numpy(),
            "frame_sha256": sha_now, "detector_link_m": de["detector_link_m"]})
        areas.to_csv(out / "arm_c_search_areas.csv", index=False)
        res.update(arm_c_well_rows=int(len(conf)), arm_c_distinct_wells=int(conf["well_id"].nunique()),
                   arm_c_areas=int(len(areas)), arm_c_areas_without_wells=int((areas["n_wells_confirmed_r1"] == 0).sum()))
    written = [out / f for f in ("arm_b_candidate_outcomes.csv", "arm_c_search_outcomes.csv", "arm_c_search_areas.csv",
                                 "arm_c_well_links.csv") if (out / f).exists()]
    ek.write_provenance(out, inputs=[frame_path], outputs=written, params=de, name="density_export")
    res["written"] = [str(p) for p in written]
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 export of field outcomes for 5.4 S3.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--tables", default=str(ek.sub("7.5", "results/tables")))
    ap.add_argument("--out", default=None, help="default data/processed/ of this expansion")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    t = Path(a.tables)
    try:
        clean = pd.read_csv(need(t / "field_results_clean_v1.csv", "clean field results (run the ingest)"))
        wells = pd.read_csv(need(t / "field_wells_clean_v1.csv", "clean well rows (run the ingest)"),
                            dtype={"tied_record_id": str})
        key = pd.read_csv(need(t / "field_sample_key_v1.csv", "sample key"), dtype={"frame_sha256": str})
        frame = need(cfg_path(cfg["inputs"]["candidates_frozen"]), "Arm B frame (5.4 site table)")
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else ek.sub("7.5", cfg["density_export"]["out_rel"])
    print(json.dumps(export(clean, wells, key, frame, cfg, out), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

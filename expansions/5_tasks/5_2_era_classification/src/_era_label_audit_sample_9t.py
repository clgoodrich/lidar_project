"""S3 blind label audit for 5.2 era classification (fw_5_2 section 7 S3).

Purpose
    draw   Draw a probability sample of labels (60 by default, or all if fewer), stratified by era class with
           proportional allocation and at least one per class. Write a blank sheet that hides morphology and
           model output. The second person fills audit_source_ok, audit_date_ok, audit_link_ok with yes or no.
    score  Read the filled sheet. Agreement is all three checks yes. Link error is audit_link_ok == no.
           Clopper-Pearson intervals (unweighted counts) and a weighted point estimate. Disputed labels are
           marked audited = disputed in a copy of the labels for the drop-disputed sensitivity run.

Inputs (config_5_2.json)
    labels               @exp:5.2/results/tables/era_interval_labels_9t.csv (S2)
    label_audit_filled   @exp:5.2/data/interim/era_label_audit_filled_9t.csv (ASSUMED, filled by a second person)
Outputs
    audit_sheet_csv      @exp:5.2/data/interim/era_label_audit_sample_9t.csv     (draw)
    audit_score_json     @exp:5.2/results/tables/era_label_audit_score_9t.json   (score)
    labels_audited_csv   @exp:5.2/results/tables/era_labels_audited_9t.csv       (score)
Evidence level
    (b) historical, audit of labels.
Run
    python expansions/5_tasks/5_2_era_classification/src/_era_label_audit_sample_9t.py draw
    python expansions/5_tasks/5_2_era_classification/src/_era_label_audit_sample_9t.py score
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _era_core_tools as ec  # noqa: E402

ek = th.ek
SHEET_COLS = ["permit", "source", "source_date", "identity_basis", "pos_error_m", "x", "y", "era_class",
              "incl_prob", "weight"]
AUDIT_COLS = ["audit_source_ok", "audit_date_ok", "audit_link_ok", "auditor", "audit_note"]


def draw(lab: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    la = cfg["label_audit"]
    one = lab.drop_duplicates("permit")
    s = ec.stratified_sample(one, la["strata_col"], la["n_sample"], ek.child_seed(cfg["master_seed"], 0, 3))
    s = s[SHEET_COLS].copy()
    for c in AUDIT_COLS:
        s[c] = ""
    return s.sort_values("permit").reset_index(drop=True)


def score(sheet: pd.DataFrame) -> dict:
    th.require_columns(sheet, ["permit", "audit_source_ok", "audit_date_ok", "audit_link_ok", "weight", "era_class"],
                       "label_audit_filled")
    yes = lambda c: sheet[c].astype(str).str.strip().str.lower().eq("yes")  # noqa: E731
    filled = sheet[["audit_source_ok", "audit_date_ok", "audit_link_ok"]].astype(str).apply(
        lambda c: c.str.strip().str.lower().isin(["yes", "no"])).all(axis=1)
    s = sheet[filled].copy()
    if not len(s):
        raise SystemExit("label_audit_filled has no completed rows (yes or no in all three audit columns)")
    agree = yes("audit_source_ok")[filled] & yes("audit_date_ok")[filled] & yes("audit_link_ok")[filled]
    link_err = ~yes("audit_link_ok")[filled]
    w = s["weight"].astype(float)
    out = dict(n_rows=int(len(sheet)), n_completed=int(len(s)))
    for name, m in (("agreement", agree), ("link_error", link_err)):
        k, n = int(m.sum()), int(len(m))
        p, lo, hi = ek.clopper_pearson(k, n)
        out[name] = dict(k=k, n=n, share=p, cp95=[lo, hi], weighted_share=float((w * m).sum() / w.sum()))
    out["by_class"] = {c: dict(n=int(g.shape[0]), agreement=float(agree[g.index].mean()))
                       for c, g in s.groupby("era_class")}
    out["disputed_permits"] = s.loc[~agree, "permit"].astype(str).tolist()
    out["evidence_level"] = "b"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["draw", "score"])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    lab = pd.read_csv(th.inp(cfg, "labels"))
    if a.mode == "draw":
        s = draw(lab, cfg)
        p = th.outp(cfg, "audit_sheet_csv")
        if p.exists():
            raise SystemExit(f"{p} exists. A drawn sample is not redrawn. Delete it on purpose to redraw.")
        s.to_csv(p, index=False)
        print(f"sample {len(s)} of {lab.permit.nunique()} labelled wells -> {p}")
        print("Copy it to the label_audit_filled path once a second person fills the audit columns.")
        return 0
    sheet = pd.read_csv(th.inp(cfg, "label_audit_filled"))
    res = score(sheet)
    js = th.write_json(th.outp(cfg, "audit_score_json"), res)
    lab["audited"] = np.where(lab["permit"].astype(str).isin(res["disputed_permits"]), "disputed",
                              np.where(lab["permit"].astype(str).isin(sheet["permit"].astype(str)), "agreed", "not_sampled"))
    p2 = th.outp(cfg, "labels_audited_csv")
    lab.to_csv(p2, index=False)
    print(js, p2, sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""5.6 S1 step 6. Draw a blinded adjudication sample of proposed links, then score link PPV from the filled sheet.

Purpose
    Normalised excess is not link precision. Link PPV needs blinded identity adjudication of a probability sample
    of accepted links, with ambiguous outcomes kept and inclusion weights (protocol section 4 rule 5).
    --draw   stratified random sample of pit-level proposals by distance band (config adjudication.distance_strata_m),
             equal allocation, weight = stratum size / stratum sample. The sheet hides model score and source so
             the adjudicator is blind to detector output.
    --score  reads the filled sheet (outcome correct | wrong | ambiguous) and reports PPV lower and upper bounds
             with sampling intervals, overall and per status group, plus the deployment decision against the
             crew minimum (adjudication.field_use_min_ppv, a user decision). Success if the lower interval bound
             is above the minimum. Failure if the upper interval bound is below it. Else inconclusive.

Inputs
    --proposals   proposals.csv from a _records_assoc_v2_9t.py run folder (default: newest run)
    adjudication_filled   assumed, expansions/5_tasks/5_6_record_association/data/raw/records_link_adjudication_filled_9t.csv
Outputs
    expansions/5_tasks/5_6_record_association/data/interim/records_link_adjudication_sheet_9t.csv   (--draw)
    expansions/5_tasks/5_6_record_association/results/tables/records_link_ppv_9t.json             (--score)
Run
    python expansions/5_tasks/5_6_record_association/src/_records_link_ppv_sample_9t.py --draw
    python expansions/5_tasks/5_6_record_association/src/_records_link_ppv_sample_9t.py --score
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _task5_helpers as th  # noqa: E402
import _records_assoc_core as core  # noqa: E402

ek = th.ek
BLIND_DROP = ["det_score", "det_source", "proposal_type"]


def newest_proposals(cfg) -> Path:
    runs = sorted(th.resolve(cfg["outputs"]["runs"]).glob("*_recassoc_*/proposals.csv"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise th.MissingInput("proposals.csv", th.resolve(cfg["outputs"]["runs"]),
                              "Run _records_assoc_v2_9t.py first.")
    return runs[-1]


def draw(P: pd.DataFrame, edges, n_total: int, seed: int) -> pd.DataFrame:
    P = P[P.level == "pit"].copy()
    P["stratum"] = pd.cut(P.dist_m, bins=list(edges) + [np.inf], right=False, labels=False)
    strata = sorted(P.stratum.dropna().unique())
    size = {s: int((P.stratum == s).sum()) for s in strata}
    alloc = {s: 0 for s in strata}
    left = n_total
    while left > 0 and any(alloc[s] < size[s] for s in strata):   # equal allocation, slack moves to larger strata
        for s in strata:
            if left and alloc[s] < size[s]:
                alloc[s] += 1
                left -= 1
    rng = np.random.default_rng(seed)
    parts = []
    for s in strata:
        g = P[P.stratum == s]
        k = alloc[s]
        if k == 0:
            continue
        pick = g.iloc[rng.choice(len(g), k, replace=False)].copy()
        pick["weight"] = len(g) / k
        parts.append(pick)
    S = pd.concat(parts, ignore_index=True)
    S = S.drop(columns=[c for c in BLIND_DROP if c in S.columns])
    S["outcome"] = ""
    S["adjudicator"] = ""
    return S.sample(frac=1, random_state=seed).reset_index(drop=True)


def score(F: pd.DataFrame, min_ppv) -> dict:
    th.require_columns(F, ["link_id", "outcome", "weight", "group"], "adjudication sheet")
    F = F[F.outcome.astype(str).str.len() > 0]
    out = {"overall": core.link_ppv_bounds(F.outcome.to_numpy(), F.weight.to_numpy())}
    for g, x in F.groupby("group"):
        out[str(g)] = core.link_ppv_bounds(x.outcome.to_numpy(), x.weight.to_numpy())
    for k, v in out.items():
        if min_ppv is None or v.get("n", 0) == 0:
            v["decision"] = "no crew minimum set (user decision)" if min_ppv is None else "no data"
        elif v["ppv_lower_ci_lo"] > min_ppv:
            v["decision"] = "success"
        elif v["ppv_upper_ci_hi"] < min_ppv:
            v["decision"] = "failure"
        else:
            v["decision"] = "inconclusive"
    out["_note"] = "Ambiguous and inaccessible links sit between the bounds. Evidence level of a correct link is set by the adjudication method."
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config")
    ap.add_argument("--proposals")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draw", action="store_true")
    g.add_argument("--score", action="store_true")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    adj = cfg["adjudication"]
    if a.draw:
        src = Path(a.proposals) if a.proposals else newest_proposals(cfg)
        S = draw(pd.read_csv(src), adj["distance_strata_m"], adj["n_sample"], int(cfg["seed"]) + 31)
        out = th.outp(cfg, "adjudication_sheet")
        S.to_csv(out, index=False)
        print(f"drew {len(S)} links from {src}\nwrote {out}")
        return 0
    F = pd.read_csv(th.inp(cfg, "adjudication_filled"))
    res = score(F, adj["field_use_min_ppv"])
    out = th.write_json(th.outp(cfg, "ppv_summary"), res)
    print(res["overall"], "\nwrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

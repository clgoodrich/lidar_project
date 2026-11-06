"""S6 of framework 4.6. Verdict per source and date from the S1 to S4 products, plus descriptive S5 counts.

Purpose. Apply the section 9 gate. Readiness uses provenance, date, coverage, positional accuracy and two-digitiser
agreement only. It never uses agreement with lidar or DEP (review revision 2, 2026-11-04). The S5 counts (marks
with no record and no feature) are printed beside the verdict as association, not as a test.
  usable here     date and rights known, cover share at least min_coverage_share, check-point RMSE within the limit
                  with enough points, at least one mark, agreement lower bound above the preregistered level
  unusable here   RMSE over the limit, or both digitisers found no symbols (one sheet never generalises)
  inconclusive    anything else
Inputs (per source id, all from this expansion's results/tables unless noted).
  hist_source_search_9t.csv (S0), data/_source/historic_topo_probe/<source>_crop_9t.json (S1),
  hist_georef_<source>_9t.json (S3), hist_marks_agreement_<source>_9t.json (S4), hist_marks_compare_<source>_9t.csv (S5, optional)
Outputs.
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_source_verdicts_9t.csv
  expansions/4_modalities/4_6_historic_maps_aerials/results/tables/hist_source_verdicts_9t.md
  (copy the .md into docs/iterations/historic_imagery_probe_9t.md when the lead logs the pass)
Run.
  python expansions/4_modalities/4_6_historic_maps_aerials/src/_hist_source_verdicts_9t.py --sources oil_city_1922 [more ids] [--tables DIR] [--crops DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _hist_kit_4_6 as hk


def _load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def verdict_one(sid: str, meta: dict | None, crop: dict | None, geo: dict | None, agr: dict | None, pr: dict) -> dict:
    why = []
    share = crop["cover_share_9t"] if crop else None
    if geo and geo.get("verdict", "").startswith("unusable"):
        v = "unusable here"
        why.append(f"RMSE {geo['rmse_m']:.1f} m over limit {pr['rmse_limit_m']} m")
    elif agr and agr["n_marks"] == 0:
        v = "unusable here"
        why.append("no interpretable symbols from either digitiser (this source and date only)")
    else:
        ok = True
        if not meta or pd.isna(meta.get("date")) or pd.isna(meta.get("rights")):
            ok = False; why.append("date or rights unknown")
        if share is None or share < pr["min_coverage_share"]:
            ok = False; why.append(f"cover share {share} below {pr['min_coverage_share']}")
        if not geo or geo.get("verdict") != "within limit":
            ok = False; why.append("no accuracy within limit on enough points" if geo else "S3 not run")
        if not agr or not agr.get("agreement_passes"):
            ok = False; why.append("agreement not above level" if agr else "S4 not run")
        v = "usable here" if ok else "inconclusive"
    return {"source_id": sid, "date": (meta or {}).get("date"), "kind": (meta or {}).get("kind"),
            "cover_share_9t": share, "rmse_m": geo["rmse_m"] if geo else None,
            "rmse_hi": geo["rmse_hi"] if geo else None, "agreement": agr["agreement"] if agr else None,
            "agreement_lo": agr["agreement_lo"] if agr else None, "n_marks": agr["n_marks"] if agr else None,
            "verdict": v, "why": "; ".join(why) or "all readiness checks met"}


def main(argv=None) -> int:
    cfg = hk.load_cfg()
    pr = cfg["prereg"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--tables", default=None)
    ap.add_argument("--crops", default=None)
    a = ap.parse_args(argv)
    tables = Path(a.tables) if a.tables else hk.resolve(cfg["outputs"]["tables"])
    crops = Path(a.crops) if a.crops else hk.resolve(cfg["outputs"]["crops"])
    search = tables / "hist_source_search_9t.csv"
    meta_all = pd.read_csv(search).set_index("source_id").to_dict("index") if search.exists() else {}
    rows = []
    for sid in a.sources:
        r = verdict_one(sid, meta_all.get(sid), _load(crops / f"{sid}_crop_9t.json"),
                        _load(tables / f"hist_georef_{sid}_9t.json"), _load(tables / f"hist_marks_agreement_{sid}_9t.json"), pr)
        cmp_f = tables / f"hist_marks_compare_{sid}_9t.csv"
        if cmp_f.exists():
            c = pd.read_csv(cmp_f)
            r["marks_no_feature_200m"] = int(((c.dist_pit_m > 200) & (c.dist_pad_m > 200)).sum())
        rows.append(r)
    df = pd.DataFrame(rows)
    hk.ek.assert_rows(df, len(a.sources), "verdict rows")
    df.to_csv(tables / "hist_source_verdicts_9t.csv", index=False)
    md = ["# Historic imagery probe, tile 9t", "", "Evidence level (b) historical. Readiness only. Association with lidar or DEP is a later, separate outcome.", "",
          "| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    md += ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    md += ["", "One failed sheet is not a verdict on a source family. Test several dates."]
    (tables / "hist_source_verdicts_9t.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    hk.prov(tables, "hist_source_verdicts_9t", inputs=[search], outputs=[tables / "hist_source_verdicts_9t.csv"], params=pr)
    print(df[["source_id", "verdict", "why"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

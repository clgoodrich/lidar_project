"""6.1 S3. Limits sheet and summary, written from saved numbers only.

Purpose
    Write the partner summary in a fixed order. Limits first, then coverage, then candidates, then records.
    No result appears before the limits. Every number is read from the S1 summary JSON, the S2 layer JSON and
    the S4 counts CSV. A hypothetical partner is stated at the top and the bottom.
Inputs (run folder)
    screen_eligible_summary_9t.json, screening_layers_9t.json, screening_counts_9t.csv
Outputs (run folder)
    screening_summary_9t.md (hydrogen: screening_summary_h2_9t.md)
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_screen_summary_9t.py --out RUN_DIR [--profile co2]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import _co2_screen_lib as L


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 100 else f"{v:.0f}"
    return str(v)


def write_summary(cfg: dict, prof: dict, out_dir: Path) -> Path:
    area = cfg["area"]
    s1 = json.loads((out_dir / f"screen_eligible_summary_{area}.json").read_text(encoding="utf-8"))
    s2 = json.loads((out_dir / L.fname("screening_layers", prof, area, "json")).read_text(encoding="utf-8"))
    cpath = out_dir / L.fname("screening_counts", prof, area, "csv")
    if not cpath.exists():
        raise L.MissingInput(f"{cpath} missing. Run _co2_screen_counts_9t.py first.")
    c = pd.read_csv(cpath).set_index("metric")
    hyp = cfg["decisions"]["partner"] == "hypothetical"
    banner = ("This package was built for a declared hypothetical partner. No real partner has read it."
              if hyp else f"Partner {cfg['decisions']['partner']}.")
    title = "Hydrogen storage screening package" if prof["name"] == "hydrogen" else "CO2 and geothermal screening package"
    lines = [f"# {title} ({area})", "", banner, "",
             "## What this package cannot tell you", ""]
    lines += [f"{i + 1}. {t}" for i, t in enumerate(prof["limits"])]
    lines += ["", "## Coverage", "",
              f"- Blocks screened {s1['n_blocks']}. Eligible {s1['n_eligible']}. Blind zones {s1['n_blind']}.",
              f"- Eligible area {_fmt(s1['eligible_km2'])} km2 of {_fmt(s1['total_km2'])} km2.",
              f"- Eligibility rule. Ground density at least {s1['rule']['min_ground_density_pts_m2']} points per m2 "
              f"and void fraction at most {s1['rule']['max_void_frac']}. {s1['rule_note']}",
              "", "## Candidates (evidence level a)", "",
              f"- Candidate sites in the area {int(c.loc['candidates_in_area', 'value'])}.",
              f"- Candidates inside the review budget of {cfg['params']['k_per_km2']} per km2 "
              f"{int(c.loc['candidates_within_K', 'value'])}.",
              f"- Candidates with no record within {cfg['params']['link_radius_m']} m "
              f"{int(c.filter(like='candidates_no_record', axis=0)['value'].iloc[0])}. This is review burden, not a count of wells.",
              "- The share of candidates that are wells is unmeasured.",
              "", "## Records (evidence level b)", "",
              f"- Records in the area {int(c.loc['records_in_area', 'value'])}. "
              f"With a depth {int(c.loc['records_with_depth', 'value'])}. "
              f"With a plugging date {int(c.loc['records_with_plug_date', 'value'])}. "
              f"Spud year 1800 sentinel {int(c.loc['records_spud_sentinel_1800', 'value'])}.",
              f"- Records with no candidate within {cfg['params']['link_radius_m']} m "
              f"{int(c.filter(like='records_no_candidate', axis=0)['value'].iloc[0])}. This is association, not recall."]
    sr = c.filter(like="share_records_with_candidate", axis=0)
    if len(sr):
        r = sr.iloc[0]
        lines.append(f"- Share of records with a candidate nearby {_fmt(r.value)} (95% block interval "
                     f"{_fmt(r.lo95)} to {_fmt(r.hi95)}). Association only.")
    extra = [m for m in c.index if m.startswith("h2_")]
    if extra:
        lines += ["", "## Record fields for the storage zone (evidence level b, from records only)", ""]
        lines += [f"- {m[3:].replace('_', ' ')} {_fmt(c.loc[m, 'value'])}. {c.loc[m, 'note'] if isinstance(c.loc[m, 'note'], str) else ''}"
                  for m in extra]
    lines += ["", "## Layers", ""]
    lines += [f"- {k} {v} rows." for k, v in s2["rows"].items()]
    lines += [f"- {k} absent. {v}." for k, v in s2["absent"].items()]
    lines += ["", banner, ""]
    out = out_dir / L.fname("screening_summary", prof, area, "md")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out = write_summary(cfg, prof, Path(a.out))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

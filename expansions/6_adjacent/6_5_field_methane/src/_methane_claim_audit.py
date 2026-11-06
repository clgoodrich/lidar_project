"""6.5 S3. Claim audit of methane outputs and reports.

Purpose
    Search the per-site table, the summary and any listed report for banned phrases (whole word, case-insensitive),
    such as "no leak", "leak-free", "emission rate", "flux" and "kg/h". The fixed disclaimer sentences are
    stripped first because they name what a reading is not. Every summary must contain the word "screening".
    Zero hits required before release with 7.5.
Inputs
    data/9t/results/field/field_methane_by_site.csv, field_methane_summary.json, plus --docs files
Outputs
    data/9t/results/field/methane_claim_audit_9t.csv (one row per hit, or one PASS row)
Run
    python expansions/6_adjacent/6_5_field_methane/src/_methane_claim_audit.py [--out DIR] [--docs report.md]
Exit code 1 on any hit.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

import _methane_sheet_check as SC
from _methane_field_table import DISCLAIMER


def audit_texts(cfg: dict, texts: dict[str, str]) -> list[dict]:
    allowed = [s.strip() + "." for s in DISCLAIMER.split(".") if s.strip()] + [DISCLAIMER]
    pats = [(ph, re.compile(r"(?<![\w-])" + re.escape(ph) + r"(?![\w-])", re.IGNORECASE)) for ph in cfg["banned_phrases"]]
    hits = []
    for src, text in texts.items():
        t = text
        for a in sorted(allowed, key=len, reverse=True):
            t = t.replace(a, "")
        for ln, line in enumerate(t.splitlines(), 1):
            for ph, rx in pats:
                if rx.search(line):
                    hits.append({"source": src, "where": f"line {ln}", "phrase": ph, "context": line.strip()[:160]})
        if src.endswith(".json") or "summary" in src:
            for w in cfg["required_words"]:
                if w.lower() not in text.lower():
                    hits.append({"source": src, "where": "", "phrase": f"missing required word '{w}'", "context": ""})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--docs", nargs="*", default=[])
    a = ap.parse_args()
    cfg = SC.load_config(a.config)
    out = Path(a.out) if a.out else SC.resolve(cfg["outputs"]["results"])
    files = [out / "field_methane_by_site.csv", out / "field_methane_summary.json"] + [Path(d) for d in a.docs]
    miss = [f for f in files if not f.exists()]
    if miss:
        raise FileNotFoundError(f"missing {miss}. Run _methane_field_table.py first.")
    hits = audit_texts(cfg, {f.name: f.read_text(encoding="utf-8") for f in files})
    df = pd.DataFrame(hits) if hits else pd.DataFrame([{"source": "all", "where": "", "phrase": "", "context": "PASS zero hits"}])
    p = out / f"methane_claim_audit_{cfg['area']}.csv"
    df.to_csv(p, index=False)
    print(f"{'PASS' if not hits else 'FAIL'} {len(hits)} hits. wrote {p}")
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())

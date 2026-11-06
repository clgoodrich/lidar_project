"""6.1 S5a. Automated claim audit of the summary, the layer attributes and any listed docs.

Purpose
    Search for banned phrases (profile banned_phrases, whole-word, case-insensitive). The fixed limits sentences
    are stripped first, because they name what is unknown. On level (a) rows of L2_candidates the words
    "confirmed" and "confirmed well" are also banned. The package passes only with zero hits.
Inputs (run folder)
    screening_summary_9t.md, screening_package_9t.gpkg, plus any --docs files
Outputs (run folder)
    screen_claim_audit_9t.csv (hydrogen: screen_claim_audit_h2_9t.csv). One row per hit, or one PASS row.
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_claim_audit_9t.py --out RUN_DIR [--profile co2] [--docs a.md b.md]
Exit code 1 when any hit is found.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pyogrio

import _co2_screen_lib as L


def _patterns(phrases):
    return [(ph, re.compile(r"\b" + re.escape(ph) + r"\b", re.IGNORECASE)) for ph in phrases]


def strip_allowed(text: str, allowed: list[str]) -> str:
    for a in sorted(allowed, key=len, reverse=True):
        text = text.replace(a, "")
    return text


def audit_text(text: str, source: str, phrases, allowed) -> list[dict]:
    hits = []
    for ln, line in enumerate(strip_allowed(text, allowed).splitlines(), 1):
        for ph, rx in _patterns(phrases):
            if rx.search(line):
                hits.append({"source": source, "where": f"line {ln}", "phrase": ph, "context": line.strip()[:160]})
    return hits


def audit(cfg: dict, prof: dict, out_dir: Path, docs: list[Path] | None = None) -> tuple[Path, int]:
    area = cfg["area"]
    allowed = list(prof["limits"]) + [q["text"] for q in prof.get("reader_questions", {}).values()]
    hits = []
    summ = out_dir / L.fname("screening_summary", prof, area, "md")
    if not summ.exists():
        raise L.MissingInput(f"{summ} missing. Run _co2_screen_summary_9t.py first.")
    hits += audit_text(summ.read_text(encoding="utf-8"), summ.name, prof["banned_phrases"], allowed)
    gpkg = out_dir / L.fname("screening_package", prof, area, "gpkg")
    for lname, _ in pyogrio.list_layers(gpkg):
        if lname == "L0_limits":
            continue
        df = pyogrio.read_dataframe(gpkg, layer=lname, read_geometry=False)
        phrases = list(prof["banned_phrases"]) + (prof["banned_on_level_a"] if lname == "L2_candidates" else [])
        pats = _patterns(phrases)
        for col in df.columns:
            if df[col].dtype != object:
                continue
            for i, v in df[col].dropna().astype(str).items():
                v2 = strip_allowed(v, allowed)
                for ph, rx in pats:
                    if rx.search(v2):
                        hits.append({"source": f"{gpkg.name}:{lname}", "where": f"row {i} col {col}",
                                     "phrase": ph, "context": v[:160]})
    for d in docs or []:
        hits += audit_text(Path(d).read_text(encoding="utf-8"), str(d), prof["banned_phrases"], allowed)
    df = pd.DataFrame(hits) if hits else pd.DataFrame([{"source": "all", "where": "", "phrase": "", "context": "PASS zero hits"}])
    out = out_dir / L.fname("screen_claim_audit", prof, area, "csv")
    df.to_csv(out, index=False)
    return out, len(hits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--docs", nargs="*", default=[])
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    out, n = audit(cfg, prof, Path(a.out), [Path(x) for x in a.docs])
    print(f"{'PASS' if n == 0 else 'FAIL'} {n} hits. wrote {out}")
    return 0 if n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

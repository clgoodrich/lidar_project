"""When was each script last actually RUN? Read the analysis log, not the code.

`docs/analysis_log.md` is the project's append-only record: 137 dated entries
from 2026-04-30 to 2026-08-06, newest at top, one per processing pass, naming
the scripts run and the parameters used. It is first-party evidence of what
executed and WHEN.

Every static audit I built before this ignored it, on the grounds that a
historical log cannot prove current use. That was the wrong call. It cannot
prove a script is wired to an entry point -- but "wired" was never the question.
The question is whether the thing is still part of the work, and a dated log
answers that directly in a way an import graph cannot.

Two sources are combined, both first-party and both dated:

    LOG    the date of the newest analysis_log.md entry naming the script
    GIT    the date of the last commit that touched the file

They mean different things. LOG is when it last RAN. GIT is when it was last
EDITED. A script with a recent GIT date and an old LOG date was refactored, not
used -- which is exactly the state most of this repository was left in by the
2026-08-12 reorganisation, so GIT alone would mark everything as fresh.

Outputs:
    docs/script_last_used.md
    docs/script_last_used.csv

Reproduce:
  python tools/script_last_used.py
  ... --stale-days 45
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "analysis_log.md"
OUT_MD = ROOT / "docs" / "script_last_used.md"
OUT_CSV = ROOT / "docs" / "script_last_used.csv"
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache"}
DATE_RE = re.compile(r"^##\s+(\d{4})-(\d{2})-(\d{2})")


def log_mentions(files: list[Path]) -> tuple[dict[str, date], dict[str, date],
                                             set[str]]:
    """Newest log date per script, by PATH and (separately) by basename.

    39 basenames exist in both notebooks/wellsight and wellsight_v2. Matching on
    the basename alone credits the dead v1 copy with the v2 script's run -- the
    v1 `_prep_road_1m.py` appeared to have run on 2026-08-06 when what actually
    ran was the v2 one. So path matches and basename matches are kept apart, and
    a basename match is only trusted when that name is unique in the repo.
    """
    from collections import Counter
    name_count = Counter(p.name for p in files)
    rels = {p.relative_to(ROOT).as_posix() for p in files}
    by_path: dict[str, date] = {}
    by_name: dict[str, date] = {}
    ambiguous: set[str] = set()
    cur: date | None = None
    for line in LOG.read_text(encoding="utf8", errors="replace").splitlines():
        m = DATE_RE.match(line)
        if m:
            cur = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            continue
        if cur is None:
            continue
        norm = line.replace("\\", "/")
        for rel in rels:                       # full-path mention: unambiguous
            if rel in norm:
                if rel not in by_path or cur > by_path[rel]:
                    by_path[rel] = cur
        for nm in re.findall(r"([A-Za-z0-9_\-]+\.py)", norm):
            if name_count.get(nm, 0) > 1:
                ambiguous.add(nm)
                continue                       # cannot tell which tree
            if nm not in by_name or cur > by_name[nm]:
                by_name[nm] = cur
    return by_path, by_name, ambiguous


def git_dates(paths: list[Path]) -> dict[str, date]:
    out: dict[str, date] = {}
    for p in paths:
        rel = p.relative_to(ROOT).as_posix()
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ad", "--date=short", "--follow", "--", rel],
            cwd=ROOT, capture_output=True, text=True)
        s = r.stdout.strip()
        if s:
            y, mo, d = s.split("-")
            out[rel] = date(int(y), int(mo), int(d))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-days", type=int, default=45)
    a = ap.parse_args()

    files = sorted(p for t in ("notebooks", "ui", "roads_studio", "tools", "tests")
                   for p in (ROOT / t).rglob("*.py")
                   if not any(s in p.parts for s in SKIP))
    by_path, by_name, ambiguous = log_mentions(files)
    print(f"analysis_log: {len(by_path)} scripts named by FULL PATH, "
          f"{len(by_name)} by unique basename, "
          f"{len(ambiguous)} basenames too ambiguous to attribute")
    gits = git_dates(files)
    today = date(2026, 8, 12)

    rows = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        lg = by_path.get(rel) or by_name.get(p.name)
        how = "path" if rel in by_path else ("name" if p.name in by_name else "")
        gt = gits.get(rel)
        rows.append(dict(
            path=rel, tree=rel.split("/")[1] if rel.startswith("notebooks/") else rel.split("/")[0],
            last_run=lg.isoformat() if lg else "",
            days_since_run=(today - lg).days if lg else "",
            matched_by=how,
            ambiguous=int(p.name in ambiguous and not how),
            last_edit=gt.isoformat() if gt else "",
        ))
    with open(OUT_CSV, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    never = [r for r in rows if not r["last_run"]]
    ran = [r for r in rows if r["last_run"]]
    fresh = [r for r in ran if r["days_since_run"] <= a.stale_days]
    stale = [r for r in ran if r["days_since_run"] > a.stale_days]

    L = ["# When was each script last actually run?", "",
         "Source: `docs/analysis_log.md`, 137 dated entries from 2026-04-30 to "
         "2026-08-06. `last_run` is the newest entry naming the script; "
         "`last_edit` is the last commit that touched it.", "",
         "**They are not the same thing.** A recent `last_edit` with an old "
         "`last_run` means the file was refactored, not used — which is the "
         "state the 2026-08-12 reorganisation left most of the repo in.", "",
         f"| Bucket | Scripts |", "|---|---:|",
         f"| run within {a.stale_days} days | {len(fresh)} |",
         f"| run, but longer ago | {len(stale)} |",
         f"| **never named in the log** | **{len(never)}** |", ""]

    by_tree = defaultdict(lambda: [0, 0, 0])
    for r in rows:
        b = by_tree[r["tree"]]
        if not r["last_run"]:
            b[2] += 1
        elif r["days_since_run"] <= a.stale_days:
            b[0] += 1
        else:
            b[1] += 1
    L += ["## By tree", "",
          f"| Tree | run <={a.stale_days}d | run older | never in log |",
          "|---|---:|---:|---:|"]
    for k in sorted(by_tree):
        f_, s_, n_ = by_tree[k]
        L.append(f"| `{k}` | {f_} | {s_} | {n_} |")
    L += ["", f"## Run within {a.stale_days} days", ""]
    for r in sorted(fresh, key=lambda r: r["last_run"], reverse=True):
        L.append(f"- `{r['path']}` — last run **{r['last_run']}**")
    L += ["", "## Run, but longer ago", ""]
    for r in sorted(stale, key=lambda r: r["last_run"], reverse=True):
        L.append(f"- `{r['path']}` — last run {r['last_run']} "
                 f"({r['days_since_run']} days)")
    L += ["", "## Never named in the log", "",
          "The log started 2026-04-30. Anything older than that, or run without "
          "being logged, lands here. Absence is weak evidence, not proof.", ""]
    for r in sorted(never, key=lambda r: r["path"]):
        L.append(f"- `{r['path']}`")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf8")

    print(f"  run within {a.stale_days}d : {len(fresh)}")
    print(f"  run, older        : {len(stale)}")
    print(f"  never in the log  : {len(never)}")
    print(f"wrote {OUT_MD}\nwrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

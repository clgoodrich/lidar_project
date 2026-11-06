"""Leaderboard rules, submission scoring and leaderboard writer (7.3 S6).

Purpose
    rules   Write RULES.md into the release from config_7_3.json.
    submit  Score one submission on the hidden test once. Enforce the cap (3 per team per 90 days).
            Refuse a submission whose prediction hash was already scored. Compute the paired
            block-bootstrap difference from the plain U-Net baseline on the same hidden blocks.
            Store only aggregate scores in the public table. Test labels never leave the maintainer.
    render  Write LEADERBOARD_<release>.md. Ranks carry intervals. Entries whose difference interval
            from the entry above spans 0 are listed as tied. Maintainer entries are marked.

Inputs
    hidden-test labels and blocks (maintainer only, paths given on the command line)
    baseline candidates, blocks CSV and score JSON scored on the same hidden blocks (from the scorer).
    The submission is scored with sc.load_policy(task) and must share the baseline's policy (ek.assert_same_policy).
    submission prediction rasters (float, 0.5 m, EPSG:6346) and a one-page method note
Outputs
    <release>/RULES.md, <release>/LEADERBOARD_<release>.md
    expansions/7_scale/7_3_benchmark/results/tables/bench_submissions_terrain_v1.csv   (public aggregates)
    expansions/7_scale/7_3_benchmark/data/interim/submissions/<sub_id>/   (private candidates, gitignored)

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_leaderboard_submit_9t.py rules
    python expansions/7_scale/7_3_benchmark/src/_bench_leaderboard_submit_9t.py submit --team T --track A \
        --note note.md --pred p1.tif p2.tif --task pit_floor --test-labels hidden.gpkg --test-blocks hidden_blocks.gpkg \
        --baseline baseline_cands.csv baseline_blocks.csv baseline_score.json --date 2026-11-05
    python expansions/7_scale/7_3_benchmark/src/_bench_leaderboard_submit_9t.py render
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bench_evaluate_recall_k as sc  # noqa: E402
from _bench_export_release_9t import CFG, cfg_path, load_cfg  # noqa: E402
from _bench_validity_checks_9t import paired_diff  # noqa: E402

RULES = """# Rules ({name})

1. Submit one probability raster per hidden-test tile. Float, 0.5 m, EPSG:6346. Add a one-page method note and the track.
2. Track A trains only on the released training data. Track B may use any extra data and declares every dataset.
3. Extra unlabelled data is declared in both tracks. Hidden-test tiles are never used for training, self-training or normalisation.
4. Transductive use is declared and listed apart.
5. Candidates are extracted by the official scorer only. K is fixed at {k} candidates per km2.
6. At most {cap} submissions per team per {days} days. Each submission is scored once.
7. Test labels are never returned. Only aggregate scores are published.
8. Each entry reports its difference from the plain U-Net baseline with a paired block-bootstrap interval.
9. Ranks are shown only with intervals. Two entries whose difference interval spans 0 are listed as tied.
10. Entries from the maintainers are marked.
11. After v1 closes the test labels may be released as v2 with a fresh hidden set. A released test set is never reused as hidden.
12. Every label is a drawn terrain feature. No entry may be described as finding wells.
"""


def table_path() -> Path:
    return ek.sub("7.3", "results/tables") / "bench_submissions_terrain_v1.csv"


def load_table() -> pd.DataFrame:
    p = table_path()
    return pd.read_csv(p) if p.exists() else pd.DataFrame(
        columns=["sub_id", "team", "track", "date", "maintainer", "transductive", "pred_sha256", "recall", "lo",
                 "hi", "diff_vs_baseline", "diff_lo", "diff_hi", "n_blocks", "policy_hash"])


def pred_hash(paths) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: Path(x).name):
        h.update(Path(p).name.encode()); h.update(ek.sha256(Path(p)).encode())
    return h.hexdigest()


def check_cap(tab: pd.DataFrame, team: str, date: dt.date, cap: int, days: int) -> None:
    if not len(tab):
        return
    t = tab[tab["team"] == team]
    recent = [d for d in pd.to_datetime(t["date"]).dt.date if (date - d).days < days]
    if len(recent) >= cap:
        raise PermissionError(f"team {team!r} has {len(recent)} submissions in the last {days} days (cap {cap})")


def submit(a, cfg) -> dict:
    import geopandas as gpd
    lb = cfg["leaderboard"]
    tab = load_table()
    date = dt.date.fromisoformat(a.date)
    check_cap(tab, a.team, date, lb["max_submissions"], lb["window_days"])
    h = pred_hash(a.pred)
    if len(tab) and h in set(tab["pred_sha256"]):
        raise PermissionError("this prediction set was already scored once")
    if not Path(a.note).exists():
        raise FileNotFoundError(f"method note missing: {a.note}")
    sub_id = f"{date:%Y%m%d}_{a.team}_{h[:7]}"
    d = ek.sub("7.3", f"data/interim/submissions/{sub_id}")
    sp = cfg["scorer"]
    policy = sc.load_policy(a.task, sp.get("mode", "primary"))       # review 7.3-01: one policy, never 0.10
    base_policy = json.loads(Path(a.baseline[2]).read_text(encoding="utf-8")).get("policy")
    if base_policy is None:
        raise PermissionError(f"baseline score {a.baseline[2]} carries no scoring policy. Rescore the baseline.")
    ek.assert_same_policy(policy, base_policy)
    s, cands = sc.evaluate([(p, None) for p in a.pred], gpd.read_file(a.test_labels, layer=a.layer or a.task),
                           gpd.read_file(a.test_blocks), policy=policy, B=a.B, seed=sp["seed"])
    cands.to_csv(d / "cands.csv", index=False)
    s["_blocks"].to_csv(d / "blocks.csv", index=False)
    sc.write_json(s, d / "score.json")
    diff = paired_diff((cands, s["_blocks"]), (pd.read_csv(a.baseline[0]), pd.read_csv(a.baseline[1])),
                       policy["k_per_km2"], a.B, sp["seed"])
    row = {"sub_id": sub_id, "team": a.team, "track": a.track, "date": a.date, "maintainer": a.maintainer,
           "transductive": a.transductive, "pred_sha256": h, "recall": s["recall"], "lo": s["ci95"][0],
           "hi": s["ci95"][1], "diff_vs_baseline": diff["point"], "diff_lo": diff["lo"], "diff_hi": diff["hi"],
           "n_blocks": s["n_blocks"], "policy_hash": policy["policy_hash"]}
    tab = pd.concat([tab, pd.DataFrame([row])], ignore_index=True)
    tab.to_csv(table_path(), index=False)
    ek.write_provenance(d, inputs=[Path(p) for p in a.pred] + [Path(a.note)], outputs=[d / "score.json"],
                        params={"track": a.track, **sp, "policy": policy})
    return row


def render(tab: pd.DataFrame, name: str) -> str:
    """Ranks by recall within track. Tied when the paired-difference intervals from baseline overlap the entry above."""
    lines = [f"# Leaderboard {name}", "", "Evidence level (a). Recall of drawn terrain features at K = 40 per km2.",
             "Entries whose difference intervals overlap the entry above are tied (same rank).", ""]
    for track, g in tab.groupby("track"):
        g = g.sort_values(["recall", "date"], ascending=[False, True]).reset_index(drop=True)
        lines += [f"## Track {track}", "", "| Rank | Team | Recall (95% CI) | Diff vs U-Net (95% CI) | Notes |",
                  "|---|---|---|---|---|"]
        rank = 0
        prev = None
        for i, r in g.iterrows():
            if prev is None or r["diff_hi"] < prev["diff_lo"]:
                rank = i + 1
            notes = ", ".join(x for x, f in (("maintainer", r["maintainer"]), ("transductive", r["transductive"])) if bool(f))
            lines.append(f"| {rank} | {r['team']} | {r['recall']:.3f} ({r['lo']:.3f} to {r['hi']:.3f}) | "
                         f"{r['diff_vs_baseline']:+.3f} ({r['diff_lo']:+.3f} to {r['diff_hi']:+.3f}) | {notes} |")
            prev = r
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Leaderboard rules, submissions and rendering (7.3 S6).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--release", default=None)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("rules")
    s = sp.add_parser("submit")
    s.add_argument("--team", required=True)
    s.add_argument("--track", choices=["A", "B"], required=True)
    s.add_argument("--note", required=True)
    s.add_argument("--pred", nargs="+", required=True)
    s.add_argument("--test-labels", required=True)
    s.add_argument("--task", required=True, choices=sc.TASKS)
    s.add_argument("--layer", default=None, help="default: the task name")
    s.add_argument("--test-blocks", required=True)
    s.add_argument("--baseline", nargs=3, required=True, metavar=("CANDS", "BLOCKS", "SCORE_JSON"))
    s.add_argument("--date", default=dt.date.today().isoformat())
    s.add_argument("--maintainer", action="store_true")
    s.add_argument("--transductive", action="store_true")
    s.add_argument("--B", type=int, default=2000)
    sp.add_parser("render")
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    root = Path(a.release) if a.release else cfg_path(cfg["release_root"]) / cfg["release_name"]
    if a.cmd == "rules":
        root.mkdir(parents=True, exist_ok=True)
        lb = cfg["leaderboard"]
        (root / "RULES.md").write_text(RULES.format(name=cfg["release_name"], k=int(ek.PROPOSAL_POLICY["k_per_km2"]),
                                                    cap=lb["max_submissions"], days=lb["window_days"]), encoding="utf-8")
        print(f"wrote {root / 'RULES.md'}")
    elif a.cmd == "submit":
        for p in [a.test_labels, a.test_blocks, *a.baseline, *a.pred]:
            if not Path(p).exists():
                print(f"missing input: {p}", file=sys.stderr)
                return 2
        try:
            print(json.dumps(submit(a, cfg), indent=2, default=str))
        except PermissionError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 3
    else:
        root.mkdir(parents=True, exist_ok=True)
        out = root / f"LEADERBOARD_{cfg['release_name']}.md"
        out.write_text(render(load_table(), cfg["release_name"]), encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

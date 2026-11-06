"""Reviewer timer. Logs per-item events and turns them into effort minutes (7.2 assumption 5, QC 7).

Purpose
    Effort is measured reviewer-minutes per item, never label count. A reviewer (or the review tool)
    appends start and stop events. Minutes per item are the summed start-to-stop intervals, with any
    single gap longer than 5 minutes cut to 5 (idle time is not effort). Items under 10 seconds or over
    30 minutes are flagged for review. An open start with no stop is flagged and not counted.

Inputs
    event log CSV, columns timestamp (ISO 8601), reviewer, item_id, event in {start, stop}
Outputs
    --log  the event log (append with the `start` and `stop` subcommands)
    minutes CSV (`summarise`), columns item_id, reviewer, minutes, n_sessions, flag

Run
    python expansions/7_scale/7_2_active_learning/src/_al_review_timer_minutes.py start --item C123 --reviewer r1
    python expansions/7_scale/7_2_active_learning/src/_al_review_timer_minutes.py stop --item C123 --reviewer r1
    python expansions/7_scale/7_2_active_learning/src/_al_review_timer_minutes.py summarise --out minutes.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _al_policies_select_9t import CFG, ek, load_cfg  # noqa: E402

DEFAULT_LOG = "review_events.csv"


def append(log: Path, reviewer: str, item: str, event: str, when: str | None = None) -> None:
    row = pd.DataFrame([{"timestamp": when or dt.datetime.now().isoformat(timespec="seconds"),
                         "reviewer": reviewer, "item_id": item, "event": event}])
    row.to_csv(log, mode="a", header=not log.exists(), index=False)


def minutes(events: pd.DataFrame, idle_gap_min: float = 5.0, flag_short_s: float = 10.0,
            flag_long_min: float = 30.0) -> pd.DataFrame:
    e = events.copy()
    e["t"] = pd.to_datetime(e["timestamp"])
    e = e.sort_values(["reviewer", "item_id", "t"], kind="stable")
    rows = []
    for (rev, item), g in e.groupby(["reviewer", "item_id"]):
        total, n, open_t, flag = 0.0, 0, None, []
        for _, r in g.iterrows():
            if r["event"] == "start":
                if open_t is not None:
                    flag.append("double_start")
                open_t = r["t"]
            elif r["event"] == "stop" and open_t is not None:
                total += min((r["t"] - open_t).total_seconds() / 60, idle_gap_min)
                n += 1
                open_t = None
        if open_t is not None:
            flag.append("open_start")
        if n and total * 60 < flag_short_s:
            flag.append("under_10s")
        if total > flag_long_min:
            flag.append("over_30min")
        rows.append({"item_id": item, "reviewer": rev, "minutes": round(total, 4), "n_sessions": n,
                     "flag": ";".join(flag)})
    return pd.DataFrame(rows, columns=["item_id", "reviewer", "minutes", "n_sessions", "flag"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.2 reviewer timer.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--log", default=str(ek.sub("7.2", "data/interim") / DEFAULT_LOG))
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("start", "stop"):
        s = sp.add_parser(c)
        s.add_argument("--item", required=True)
        s.add_argument("--reviewer", required=True)
        s.add_argument("--when", default=None)
    s = sp.add_parser("summarise")
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    log = Path(a.log)
    if a.cmd in ("start", "stop"):
        append(log, a.reviewer, a.item, a.cmd, a.when)
        return 0
    if not log.exists():
        print(f"missing event log {log}", file=sys.stderr)
        return 2
    t = load_cfg(Path(a.config))["timer"]
    m = minutes(pd.read_csv(log), t["idle_gap_min"], t["flag_short_s"], t["flag_long_min"])
    m.to_csv(a.out, index=False)
    print(f"{len(m)} items, {int((m['flag'] != '').sum())} flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())

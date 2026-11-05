"""Download the recommended 3DEP lidar tiles listed in lidar_win_download_list_us.csv. Resumable, tracked, polite.
Run     python notebooks/wellsight_v2/s1_build/_fetch_lidar_windows_us.py [--window-prefix Pennsylvania] [--dest F:\\lidar_project_data\\lidar_us_windows] [--delay 2] [--max-gb N]
Status  <dest>\\download_status.csv  one row per tile (url, window, project, file, expected_bytes, got_bytes, status, attempts, updated, note)
        status is done, partial, failed or pending. Rewritten after every tile. Safe to stop (Ctrl+C) and rerun. Done tiles are skipped.
Log     <dest>\\download_log.txt
Rules   One connection at a time. Honest User-Agent that names the tool. A 429 or 503 waits (Retry-After if given, else growing backoff)
        and retries. A finished file is checked against the server's Content-Length. Nothing is overwritten. Files are written as .part
        then renamed.
"""
import argparse
import csv
import datetime as dt
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIST = ROOT / "data/_source/reference/lidar_catalogue/lidar_win_download_list_us.csv"
UA = "lidar-project-tile-fetch/1.0 (academic orphan-well research)"
FIELDS = ["url", "window", "project", "file", "expected_bytes", "got_bytes", "status", "attempts", "updated", "note"]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def load_status(p):
    if not p.exists():
        return {}
    with open(p, newline="") as f:
        return {r["url"]: r for r in csv.DictReader(f)}


def save_status(p, st):
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(st.values())
    tmp.replace(p)


def fetch(url, part, log):
    """Return (ok, bytes_on_disk, note). Resumes from .part. Waits on 429/5xx."""
    wait = 30
    for attempt in range(1, 13):
        have = part.stat().st_size if part.exists() else 0
        hdr = {"User-Agent": UA}
        if have:
            hdr["Range"] = f"bytes={have}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=90) as r:
                code = r.status
                total = int(r.headers.get("Content-Length", 0)) + (have if code == 206 else 0)
                with open(part, "ab" if code == 206 else "wb") as f:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        f.write(b)
            got = part.stat().st_size
            if total and got != total:
                log(f"short read {got}/{total}, retrying")
                continue
            return True, got, ""
        except urllib.error.HTTPError as e:
            if e.code == 416:
                return True, have, "already complete"
            if e.code in (429, 500, 502, 503, 504):
                ra = e.headers.get("Retry-After")
                s = int(ra) if ra and ra.isdigit() else wait
                log(f"HTTP {e.code}, waiting {s}s (attempt {attempt})")
                time.sleep(s)
                wait = min(wait * 2, 600)
                continue
            return False, have, f"HTTP {e.code}"
        except Exception as e:
            log(f"{type(e).__name__}: {e}, waiting {wait}s (attempt {attempt})")
            time.sleep(wait)
            wait = min(wait * 2, 600)
    return False, (part.stat().st_size if part.exists() else 0), "gave up after 12 attempts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-prefix", default="")
    ap.add_argument("--dest", default=r"F:\lidar_project_data\lidar_us_windows")
    ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--max-gb", type=float, default=0, help="stop after this many GB this run (0 = no limit)")
    a = ap.parse_args()
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    logf = open(dest / "download_log.txt", "a", encoding="utf-8")

    def log(m):
        line = f"{now()} {m}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    with open(LIST, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["window"].lower().startswith(a.window_prefix.lower())]
    sp = dest / "download_status.csv"
    st = load_status(sp)
    for r in rows:
        st.setdefault(r["url"], dict(url=r["url"], window=r["window"], project=r["project"], file=r["url"].rsplit("/", 1)[-1],
                                     expected_bytes=int(float(r["gb"]) * 1e9), got_bytes=0, status="pending", attempts=0,
                                     updated=now(), note=""))
    todo = []
    for r in rows:
        s = st[r["url"]]
        if s["status"] == "done" and (dest / s["project"] / s["file"]).exists():
            continue
        todo.append(r)
    log(f"{len(rows)} tiles selected, {len(rows) - len(todo)} done, {len(todo)} to fetch -> {dest}")
    got_run, t0 = 0, time.time()
    try:
        for i, r in enumerate(todo, 1):
            s = st[r["url"]]
            d = dest / s["project"]
            d.mkdir(exist_ok=True)
            final, part = d / s["file"], d / (s["file"] + ".part")
            if final.exists():
                s.update(status="done", got_bytes=final.stat().st_size, updated=now(), note="present")
                continue
            log(f"[{i}/{len(todo)}] {s['window']} {s['file']}")
            s["attempts"] = int(s["attempts"]) + 1
            ok, n, note = fetch(r["url"], part, log)
            if ok:
                part.replace(final)
                s.update(status="done", got_bytes=n, updated=now(), note=note)
                got_run += n
            else:
                s.update(status="partial" if n else "failed", got_bytes=n, updated=now(), note=note)
                log(f"FAILED {s['file']}: {note}")
            save_status(sp, st)
            if i % 25 == 0 or not ok:
                done = sum(1 for v in st.values() if v["status"] == "done")
                log(f"progress: {done}/{len(st)} tiles done, this run {got_run / 1e9:.2f} GB in {(time.time() - t0) / 60:.1f} min")
            if a.max_gb and got_run >= a.max_gb * 1e9:
                log("max-gb reached, stopping")
                break
            time.sleep(a.delay)
    except KeyboardInterrupt:
        log("interrupted, status saved")
    save_status(sp, st)
    c = {}
    for v in st.values():
        c[v["status"]] = c.get(v["status"], 0) + 1
    log(f"summary {c}. status file: {sp}")


if __name__ == "__main__":
    main()

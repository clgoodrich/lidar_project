"""Record what lives on a backup mirror but NOT in the local repo.

Backups use `robocopy /E /XO`, which never deletes. So every file that was moved,
renamed or removed locally stays on the mirror. This script lists them, so the
mirror can be trusted as a rollback point and nobody has to rediscover what is
only there.

Compares relative paths only (existence), not content. Metadata only, so it
takes a minute or two, not hours. Read-only on both sides.

Outputs (default target label T7):
    docs/backup_only_inventory.md             summary by folder, newest run first
    docs/_ledgers/backup_only_files_<tag>.csv one row per file: relpath,size_bytes,mtime

Run:
    python tools/backup_only_inventory.py --mirror H:/Colton/_BACKUPS/lidar_project_MIRROR --tag T7
"""
import argparse, csv, datetime as dt, os, sys
from collections import defaultdict

SKIP_TOP = {"_BACKUP_MANIFEST.txt"}


def walk(root):
    """yield (relpath with /, size, mtime) for every file; no junction following."""
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError as e:
            print(f"[warn] cannot read {d}: {e}", file=sys.stderr)
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name == ".git" and d == root:
                            continue
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat()
                        rel = os.path.relpath(e.path, root).replace("\\", "/")
                        yield rel, st.st_size, st.st_mtime
                except OSError:
                    continue


def gb(n):
    return f"{n / 1e9:.2f} GB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--mirror", required=True)
    ap.add_argument("--tag", default="T7")
    ap.add_argument("--depth", type=int, default=3, help="folder depth for the summary")
    a = ap.parse_args()

    if not os.path.isdir(a.mirror):
        sys.exit(f"mirror not found: {a.mirror}")

    local = {rel for rel, _, _ in walk(a.src)}
    only = [(r, s, m) for r, s, m in walk(a.mirror) if r not in local and r not in SKIP_TOP]
    only.sort()

    docs = os.path.join(a.src, "docs")
    csv_path = os.path.join(docs, "_ledgers", f"backup_only_files_{a.tag}.csv")
    md_path = os.path.join(docs, "backup_only_inventory.md")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["relpath", "size_bytes", "mtime"])
        for r, s, m in only:
            w.writerow([r, s, dt.datetime.fromtimestamp(m).strftime("%Y-%m-%d %H:%M")])

    groups = defaultdict(lambda: [0, 0, 0.0, 0.0])  # n, bytes, min mtime, max mtime
    for r, s, m in only:
        parts = r.split("/")
        key = "/".join(parts[:a.depth]) if len(parts) > a.depth else "/".join(parts[:-1]) or "(root)"
        g = groups[key]
        g[0] += 1
        g[1] += s
        g[2] = m if g[2] == 0 else min(g[2], m)
        g[3] = max(g[3], m)
    total = sum(s for _, s, _ in only)

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Files on the backup but not in the local repo",
        "",
        f"Generated {now} by `tools/backup_only_inventory.py`.",
        f"Mirror `{a.mirror}` (tag {a.tag}). Local `{a.src}`.",
        "",
        "Backups never delete (`robocopy /E /XO`). So anything moved, renamed or deleted locally",
        "stays on the mirror. These files exist **only** on the backup. Do not delete the mirror",
        "without reading this list first.",
        "",
        f"**{len(only):,} files, {gb(total)}** across {len(groups)} folders (existence by relative path, not content).",
        "",
        f"Full list: `docs/_ledgers/backup_only_files_{a.tag}.csv` (columns relpath, size_bytes, mtime).",
        "",
        "Two causes, not separated here. (1) Data deleted locally to free space on C:. For these the",
        "mirror holds the only copy. (2) Files renamed or moved locally. They show here under the old",
        "path and in the repo under the new one, so a second copy exists. `docs/MOVES.csv` maps old to new.",
        "To tell them apart, check whether the file name appears elsewhere in the repo before deleting",
        "anything from the mirror.",
        "",
        f"## By folder (depth {a.depth}), largest first",
        "",
        "| folder | files | size | oldest file | newest file |",
        "|---|---|---|---|---|",
    ]
    for k, (n, b, lo, hi) in sorted(groups.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"| `{k}` | {n:,} | {gb(b)} | {dt.datetime.fromtimestamp(lo):%Y-%m-%d} | {dt.datetime.fromtimestamp(hi):%Y-%m-%d} |")
    lines += ["", "## Largest 25 files", "", "| file | size |", "|---|---|"]
    for r, s, _ in sorted(only, key=lambda t: -t[1])[:25]:
        lines.append(f"| `{r}` | {gb(s)} |")
    lines += [
        "",
        "## Refresh",
        "",
        "```",
        f"python tools/backup_only_inventory.py --mirror {a.mirror} --tag {a.tag}",
        "```",
        "Run it after every backup. The CSV is overwritten, so diff it in git to see what changed.",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"{len(only):,} files, {gb(total)} -> {md_path}")
    print(f"csv -> {csv_path}")


if __name__ == "__main__":
    main()

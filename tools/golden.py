"""Prove a refactor changed nothing, by watching the filesystem, not the code.

Static analysis of "what does this script output" failed twice this session
(`map_scripts.py`, `check_archived_still_used.py`) because these scripts build
output paths inside `main()` from CLI arguments — there is no module-level
constant to inspect. This tool sidesteps that by observing reality directly:
snapshot the tree, run the command, snapshot again, hash whatever changed.

    python tools/golden.py record <name> -- <command...>
    python tools/golden.py verify <name> -- <command...>

`record` walks the watched directories, runs the command, walks again, and
SHA-256-hashes every path that is new or whose size/mtime changed. That set —
not a guess — is the script's output. Written to `docs/golden/<name>.json`.

`verify` re-runs the same command and compares the new hashes against the
record. Any difference is a real change in behaviour and exits non-zero.

WHY THIS MATTERS FOR THIS REPO SPECIFICALLY
Every number in docs/iterations/LEADERBOARD.md came from a specific script run.
A refactor (renaming a function, moving it into core/, changing an import) that
shifts an output by even one row invalidates a published number silently. This
is the same discipline that caught an accidental overwrite of the trained-on
feature stack earlier in this project — hash before, hash after, compare.

NOT EVERYTHING IS DETERMINISTIC
Training scripts do not produce bit-identical weights on CUDA. Figure-drawing
scripts can embed timestamps. Golden-verifying those will show spurious
failures — that is itself useful information (recorded to
docs/golden/NON_DETERMINISTIC.md by convention, not automatically), and the
fix is to golden-verify their INPUTS instead of their outputs for those cases
(hash the feature stack / label raster / manifest going in, not the weights
coming out).

WATCHED DIRECTORIES
data/derivatives/, docs/, qgis/ — everywhere this project's scripts write.
Not the whole repo: walking 100k+ files (data/external, .git, .venv) on every
record/verify would be slow and mostly noise.

GEOPACKAGE FILES ARE NOT BYTE-STABLE — HASH THEIR CONTENT INSTEAD
Confirmed empirically: running `_prep_annotations.py` twice in a row with zero
code or data changes produces two `.gpkg` files with different SHA-256 sums,
even though every one of the 7 layers is row-for-row, geometry-for-geometry
identical between the runs. GDAL/OGR's GeoPackage driver writes a `last_change`
timestamp into the `gpkg_contents` table on every save — the spec requires it —
so the raw bytes churn regardless of the data. 5 of the first 11 Tier-1 scripts
tripped this. A golden check that hashes `.gpkg` bytes directly is a false-alarm
generator, not a safety net, so `.gpkg` outputs are hashed by CONTENT: for each
layer, in the order the driver reports it, hash the column names, dtypes, and
each row's non-geometry values plus geometry WKB. This still catches a real
content change (different row count, different geometry, different attribute,
different layer, different row order) — it only ignores what GeoPackage embeds
independent of content. Requires geopandas + pyogrio, hence a run under
`C:\\Python313\\python.exe` alongside this project's other scripts, not the
lighter `.venv` interpreter that lacks it.

Same problem, second source: this project's `_style_heldout_gpkg.py` convention
(see its docstring — "Make the held-out GeoPackages self-styling in QGIS") writes
a QGIS `layer_styles` system table with an `update_time` column that is SUPPOSED
to change on every save; it is styling metadata, not pipeline output. Confirmed
on `_heldout_rim_containment_9t.py`: all 5 real data layers were byte-identical
across two runs, `layer_styles.update_time` was the only difference. That table
is skipped entirely rather than hashed.

IGNORED (changes every run by construction, proves nothing)
*.log, *.aux.xml, *_tmp_*, docs/golden/*, backup_to_*_last_run.log,
__pycache__, *.gpkg-wal, *.gpkg-shm, verify_paths_report.md,
verify_backup_report.md (this tool's own siblings' scratch output).

Exit code 0 on a clean record or a clean verify. Non-zero on any verify
mismatch, or if the command itself fails.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "docs" / "golden"
WATCH_DIRS = ["data/derivatives", "docs", "qgis"]
IGNORE_GLOBS = [
    "*.log", "*.aux.xml", "*_tmp_*", "docs/golden/*",
    "backup_to_*_last_run.log", "*/__pycache__/*", "*.gpkg-wal", "*.gpkg-shm",
    "*/verify_paths_report.md", "*/verify_backup_report.md",
    "*/script_usage_audit.*", "*/script_map.md", "*/reference_index*.md",
    "*/reference_index.csv", "*/duplicates_report.md",
    "*/duplicates_proposed_moves.csv", "*/MOVES.csv",
]


def is_ignored(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in IGNORE_GLOBS)


def snapshot() -> dict[str, tuple[int, int]]:
    """rel path -> (size, mtime_ns) for every file under the watched dirs."""
    out = {}
    for d in WATCH_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if is_ignored(rel):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            out[rel] = (st.st_size, st.st_mtime_ns)
    return out


def sha(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def gpkg_content_hash(p: Path) -> str:
    """Hash a GeoPackage by DATA, not bytes -- see the GEOPACKAGE note above.

    Falls back to a raw byte hash (with a printed warning) if geopandas is not
    importable in whatever interpreter is running golden.py, rather than
    crashing the whole record/verify pass.
    """
    try:
        import geopandas as gpd
        import pyogrio
    except ImportError:
        print(f"  WARNING: geopandas unavailable, hashing {p.name} as raw bytes "
              f"-- this WILL show false mismatches on every run. Use "
              f"C:\\Python313\\python.exe to run golden.py.")
        return sha(p)

    h = hashlib.sha256()
    for layer_name, _ in pyogrio.list_layers(p):
        if layer_name == "layer_styles":
            continue    # QGIS styling metadata; update_time changes by design
        h.update(f"::layer::{layer_name}".encode())
        g = gpd.read_file(p, layer=layer_name)
        h.update(str(list(g.columns)).encode())
        h.update(str([str(dt) for dt in g.dtypes]).encode())
        geom_col = g.geometry.name if hasattr(g, "geometry") else None
        for _, row in g.iterrows():
            for col in g.columns:
                if col == geom_col:
                    geom = row[col]
                    h.update(geom.wkb if geom is not None else b"<null-geom>")
                else:
                    h.update(str(row[col]).encode("utf8", "replace"))
        h.update(b"::end-layer::")
    return h.hexdigest()


def content_hash(p: Path) -> str:
    return gpkg_content_hash(p) if p.suffix.lower() == ".gpkg" else sha(p)


def diff_new_or_changed(before: dict, after: dict) -> list[str]:
    out = []
    for rel, (size, mtime) in after.items():
        prev = before.get(rel)
        if prev is None or prev != (size, mtime):
            out.append(rel)
    return out


def run_command(cmd: list[str]) -> None:
    print(f"  running: {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"command failed (exit {r.returncode}): {' '.join(cmd)}")


def record(name: str, cmd: list[str]) -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    t0 = time.time()
    run_command(cmd)
    elapsed = time.time() - t0
    after = snapshot()
    changed = diff_new_or_changed(before, after)

    outputs = {}
    for rel in sorted(changed):
        p = ROOT / rel
        if not p.exists():
            continue
        outputs[rel] = {"sha256": content_hash(p), "bytes": p.stat().st_size}

    record_obj = {
        "name": name,
        "command": cmd,
        "recorded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(elapsed, 1),
        "n_outputs": len(outputs),
        "outputs": outputs,
    }
    out_path = GOLDEN_DIR / f"{name}.json"
    out_path.write_text(json.dumps(record_obj, indent=2), encoding="utf8")

    print(f"  {len(outputs)} output file(s) recorded in {elapsed:.1f}s")
    for rel in sorted(outputs):
        print(f"    {rel}  ({outputs[rel]['bytes']:,} bytes)")
    print(f"wrote {out_path}")
    return 0


def verify(name: str, cmd: list[str]) -> int:
    record_path = GOLDEN_DIR / f"{name}.json"
    if not record_path.exists():
        print(f"no golden record for '{name}' — run `record` first")
        return 1
    prev = json.loads(record_path.read_text(encoding="utf8"))
    if cmd and cmd != prev["command"]:
        print(f"  WARNING: command differs from the recorded one")
        print(f"    recorded: {' '.join(prev['command'])}")
        print(f"    now     : {' '.join(cmd)}")
    use_cmd = cmd or prev["command"]

    before = snapshot()
    run_command(use_cmd)
    after = snapshot()
    changed = diff_new_or_changed(before, after)

    new_outputs = {}
    for rel in sorted(set(changed) | set(prev["outputs"])):
        p = ROOT / rel
        new_outputs[rel] = {"sha256": content_hash(p), "bytes": p.stat().st_size} \
            if p.exists() else None

    missing, mismatched, extra, ok = [], [], [], []
    for rel, old in prev["outputs"].items():
        new = new_outputs.get(rel)
        if new is None:
            missing.append(rel)
        elif new["sha256"] != old["sha256"]:
            mismatched.append(rel)
        else:
            ok.append(rel)
    for rel in changed:
        if rel not in prev["outputs"] and new_outputs.get(rel) is not None:
            extra.append(rel)

    print(f"  {len(ok)} unchanged, {len(mismatched)} MISMATCHED, "
          f"{len(missing)} MISSING, {len(extra)} new/extra")
    for rel in mismatched:
        print(f"    MISMATCH  {rel}")
    for rel in missing:
        print(f"    MISSING   {rel}")
    for rel in extra:
        print(f"    EXTRA     {rel}")

    if mismatched or missing:
        print(f"\nFAIL: '{name}' produced different output than the golden record")
        return 1
    print(f"\nPASS: '{name}' output is unchanged")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["record", "verify"])
    ap.add_argument("name")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- <command...> (omit on verify to reuse the recorded command)")
    a = ap.parse_args()
    cmd = a.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if a.mode == "record":
        if not cmd:
            ap.error("record requires -- <command...>")
        return record(a.name, cmd)
    return verify(a.name, cmd)


if __name__ == "__main__":
    sys.exit(main())

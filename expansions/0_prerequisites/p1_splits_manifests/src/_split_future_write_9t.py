"""P1 S2. Write the immutable future split file for the 9t pit and pad CV, or verify an existing one.

Purpose
    Build the deterministic split (P1 S2 algorithm) and save it as one JSON with explicit block lists per
    task, fold and role. Held-out lists come from the historical assign_folds and seed, so they do not
    change. Inner validation is drawn from `sorted(int ids not held out)` with
    `np.random.default_rng(seed + 1000 * k)` and the 20% rule. The file also records the seed, the dropped
    NaN row counts, the manifest SHA-256 and a SHA-256 of every list. A file that exists is never
    overwritten. A new version gets a new name (`--version 2`).
    Buffer (review P1-02). The derived buffer per task is read from the P1 S4 buffer JSON through
    `ek.read_buffer`. In `block` mode (default) every train block that overlaps held-out ground dilated by
    the buffer moves to role `buffer` in that fold. The count per fold is saved as `buffer_removed_by_fold`.
    In `window` mode the lists stay and the sampler must reject windows. A missing buffer stops the
    writer unless `--no-buffer` is given (exploratory, saved as buffer_m null).
    `--verify FILE` recomputes everything from the manifests and checks the file. It compares every field
    (seed, inner fraction, list hashes, counts, buffer, lists). Declared exclusions are re-derived from
    the audit file they name, and its sha256 must match. It fails on any difference, also after a rehash.

QC (fail closed)
    No NaN id, no block in two roles within a fold, union of roles (with `buffer`) equals the block set,
    held-out lists equal the exporter lists in data/9t/results/splits/cv_split_blocks_<task>_9t.csv.

Inputs
    data/9t/derived/05/pit_dataset_manifest.csv, pad_dataset_manifest.csv (through the trainers)
    data/9t/results/splits/cv_split_blocks_{pit,pad}_9t.csv (exporter, held-out lists only)
    data/9t/results/splits/buffer_derivation_9t.json (--buffer-json, P1 S4) and pit/pad_blocks_9t.gpkg

Outputs
    <out-dir>/cv_splits_future_9t_v<version>.json
    Default out-dir C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/splits/
    Run record under expansions/0_prerequisites/p1_splits_manifests/results/<run_id>/

Run
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_future_write_9t.py [--buffer-json FILE] [--buffer-mode block] [--out-dir DIR] [--version 1]
    python expansions/0_prerequisites/p1_splits_manifests/src/_split_future_write_9t.py --verify data/9t/results/splits/cv_splits_future_9t_v1.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split_core_lib_9t as sc  # noqa: E402
ek = sc.ek

K = 5
BUFFER_MODES = ("block", "window")
# 2026-11-06. User accepted the default buffer mode `window` ("take defaults"). Train blocks keep their role and
# the sampler rejects windows within the buffer of held-out ground. Change freely.
DEFAULT_BUFFER_MODE = "window"
PATH_KEYS = ("manifest", "blocks")        # path strings are not compared by verify. Their hashes are.


def _p2():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "p2_audit_set" / "src"))
    import _audit_guard_lib as ag
    return ag


def audit_exclusion(path: Path, allow_unfrozen: bool = False) -> tuple[set[int], dict]:
    """Audit and buffer block ids of a P2 audit file, and the traceable source record {path, sha256}."""
    aud = _p2().load_audit(path, allow_unfrozen=allow_unfrozen)
    return set(aud.block_id.astype(int)), {"path": str(path), "sha256": aud.attrs["sha256"]}


def buffer_spec(task: str, path: Path) -> dict:
    """Derived buffer for one task from the P1 S4 buffer JSON (through ek.read_buffer). Raises if absent."""
    return {"buffer_m": float(ek.read_buffer(task, path)), "path": str(path), "sha256": ek.sha256(path)}


def build(manifests: dict[str, Path | None] | None = None, exporter_dir: Path | None = None,
          check_exporter: bool = True, exclude: set[int] | None = None, exclude_source: dict | None = None,
          buffers: dict[str, dict | None] | None = None, blocks: dict[str, Path | None] | None = None,
          buffer_mode: str = DEFAULT_BUFFER_MODE) -> dict:
    """The split document for every task. Raises on any QC problem.

    exclude      block ids (P2 audit and buffer rows) removed from every role after the historical fold
                 assignment. Held-out lists then become subsets of the historical ones. Fold assignment is
                 not redone, so the folds stay comparable with the historical models. exclude_source is
                 {path, sha256} of the audit file, so verify() can re-derive the set.
    buffers      {task: buffer_spec(...) or None}. A task without an entry gets no buffer, recorded as null.
    buffer_mode  block   train blocks overlapping held-out ground dilated by the buffer move to role 'buffer'
                 window  lists unchanged. The near blocks are counted and the sampler must reject windows
    """
    if buffer_mode not in BUFFER_MODES:
        raise ValueError(f"buffer_mode {buffer_mode} not in {BUFFER_MODES}")
    exclude = set(exclude or ())
    if exclude and not (isinstance(exclude_source, dict) and exclude_source.get("sha256")):
        raise ValueError("exclusions need a traceable exclude_source {path, sha256} (review P1-05)")
    manifests = manifests or {t: None for t in sc.TASKS}
    buffers = buffers or {}
    blocks = blocks or {}
    doc = {"schema": "wellsight.cv_splits.v2", "tile": "9t", "k": K, "label": "future",
           "note": "Immutable once committed. A new version gets a new file. Held-out lists equal the "
                   "historical ones. Inner lists are new and were never used by the historical models. "
                   "Role 'buffer' (block mode) holds train blocks within the derived buffer of held-out ground.",
           "tasks": {}}
    for task, mpath in manifests.items():
        p = sc.task_params(task)
        mp = Path(mpath) if mpath else p["manifest"]
        man = sc.load_manifest(task, mp)
        n_nan = int(man.block_id.isna().sum())
        splits = sc.make_splits(man, K, p["seed"], p["inner_val_frac"], p["assign_folds"], "fixed")
        all_blocks = set(int(b) for b in man.block_id.dropna().astype(int).unique())
        removed = sorted(all_blocks & exclude)
        if exclude:
            splits = {f: {r: [b for b in v if b not in exclude] for r, v in roles.items()} for f, roles in splits.items()}
        kept = all_blocks - exclude
        buf = buffers.get(task)
        rec_buf = {"buffer_m": None, "buffer_mode": None, "buffer_source": None, "blocks": None,
                   "blocks_sha256": None, "buffer_removed_by_fold": None, "near_held_out_by_fold": None}
        if buf is not None:
            bp = Path(blocks.get(task) or p["blocks"])
            import geopandas as gpd
            gdf = gpd.read_file(bp, layer="blocks")
            ek.assert_crs(gdf)
            if buffer_mode == "block":
                splits, near = sc.apply_block_buffer(splits, gdf, buf["buffer_m"])
            else:
                near = sc.near_held_out(splits, gdf, buf["buffer_m"])
            rec_buf = {"buffer_m": buf["buffer_m"], "buffer_mode": buffer_mode,
                       "buffer_source": {"path": buf["path"], "sha256": buf["sha256"]},
                       "blocks": str(bp), "blocks_sha256": ek.sha256(bp),
                       "buffer_removed_by_fold": ({str(f): len(v) for f, v in near.items()}
                                                  if buffer_mode == "block" else None),
                       "near_held_out_by_fold": {str(f): len(v) for f, v in near.items()}}
        probs = sc.check_roles(splits, kept)
        if check_exporter:
            ed = exporter_dir or (ek.path_for("results_9t") / "splits")
            exp = ed / f"cv_split_blocks_{task}_9t.csv"
            if not exp.exists():
                probs.append(f"exporter list missing at {exp}")
            else:
                import pandas as pd
                e = pd.read_csv(exp)
                for f in range(K):
                    eh = sorted(e[(e.fold == f) & (e.role == "held_out")].block_id.astype(int))
                    eh = [b for b in eh if b not in exclude]
                    if eh != splits[f]["held_out"]:
                        probs.append(f"{task} fold {f}: held-out differs from exporter")
        if probs:
            raise AssertionError(f"{task} split QC failed: " + "; ".join(probs))
        roles_out = sc.ROLES + ((sc.BUFFER_ROLE,) if sc.BUFFER_ROLE in splits[0] else ())
        doc["tasks"][task] = {
            "manifest": str(mp), "manifest_sha256": ek.sha256(mp), "manifest_rows": int(len(man)),
            "rows_without_block_dropped": n_nan, "n_blocks": len(kept), "seed": p["seed"],
            "excluded_audit_blocks": removed, "exclude_source": exclude_source if exclude else None,
            "inner_val_frac": p["inner_val_frac"], "child_seed_rule": "seed + 1000 * fold",
            **rec_buf,
            "folds": {str(f): {r: splits[f][r] for r in roles_out} for f in range(K)},
            "list_sha256": {str(f): v for f, v in sc.fold_hashes(splits).items()},
        }
    doc["content_sha256"] = sc.lists_hash(doc["tasks"])
    return doc


def write_split(doc: dict, dst: Path) -> Path:
    """Write a split document. Never overwrites (a new split gets a new version)."""
    dst = Path(dst)
    if dst.exists():
        raise FileExistsError(f"{dst} exists and is immutable. Use a new version for a new split.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc = {**doc, "written": dt.datetime.now().isoformat(timespec="seconds")}
    dst.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return dst


def verify(path: Path, manifests=None, exporter_dir=None, check_exporter=True, blocks=None) -> list[str]:
    """Recompute everything and compare. Returns a list of problems (empty means pass).

    Seed, inner fraction, list hashes, block counts and every list are recomputed from the trainers and
    compared with the file. Declared exclusions are re-derived from the audit file they name (its sha256
    must match), and the buffer is re-read from the buffer JSON it names (sha256 must match). A file that
    was edited and then rehashed therefore fails (review P1-05)."""
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    probs = []
    if sc.lists_hash(saved["tasks"]) != saved.get("content_sha256"):
        probs.append("content_sha256 does not match the file's own lists (file edited by hand?)")
    tasks = saved["tasks"]
    mans = manifests or {t: Path(tasks[t]["manifest"]) for t in tasks}
    excl, src = set(), None
    declared = [t for t, v in tasks.items() if v.get("excluded_audit_blocks") or v.get("exclude_source")]
    if declared:
        srcs = {json.dumps(tasks[t].get("exclude_source"), sort_keys=True) for t in tasks}
        if len(srcs) != 1:
            return probs + ["tasks name different exclusion sources"]
        src = tasks[declared[0]].get("exclude_source")
        if not (isinstance(src, dict) and src.get("path") and src.get("sha256")):
            return probs + [f"declared exclusions cannot be traced to an audit file (exclude_source {src!r})"]
        try:
            excl, src_now = audit_exclusion(Path(src["path"]), allow_unfrozen=True)
        except (FileNotFoundError, AssertionError) as e:
            return probs + [f"exclusion source unreadable: {e}"]
        if src_now["sha256"] != src["sha256"]:
            return probs + [f"audit file {src['path']} changed since the split was written"]
    modes = {v.get("buffer_mode") for v in tasks.values() if v.get("buffer_mode")}
    if len(modes) > 1:
        return probs + [f"tasks use different buffer modes {modes}"]
    bufs, blks = {}, dict(blocks or {})
    for t, v in tasks.items():
        bs = v.get("buffer_source")
        if not bs:
            bufs[t] = None
            continue
        try:
            bufs[t] = buffer_spec(t, Path(bs["path"]))
        except (FileNotFoundError, KeyError, TypeError) as e:
            return probs + [f"{t}: buffer source unreadable: {e}"]
        bufs[t]["path"] = bs["path"]
        if bufs[t]["sha256"] != bs.get("sha256"):
            probs.append(f"{t}: buffer JSON changed since the split was written")
        blks.setdefault(t, Path(v["blocks"]))
    try:
        now = build(mans, exporter_dir, check_exporter, exclude=excl, exclude_source=src, buffers=bufs,
                    blocks=blks, buffer_mode=next(iter(modes)) if modes else DEFAULT_BUFFER_MODE)
    except (AssertionError, ValueError) as e:
        return probs + [str(e)]
    for t in tasks:
        a, b = tasks[t], now["tasks"].get(t)
        if b is None:
            probs.append(f"{t}: missing on recompute")
            continue
        if a.get("manifest_sha256") != b["manifest_sha256"]:
            probs.append(f"{t}: manifest hash changed since the split file was written")
        if a.get("folds") != b["folds"]:
            probs.append(f"{t}: recomputed lists differ")
        for key in sorted(set(a) | set(b)):
            if key in PATH_KEYS or key in ("folds", "manifest_sha256"):
                continue
            if a.get(key) != b.get(key):
                probs.append(f"{t}: field '{key}' differs from the recompute (file {a.get(key)!r}, now {b.get(key)!r})")
    for key in ("schema", "k", "tile"):
        if saved.get(key) != now.get(key):
            probs.append(f"top-level '{key}' differs from the recompute")
    return probs


def split_file_for(task: str, path: Path) -> dict:
    """Reader used by trainers. Returns {fold(int): {role: [ids]}} and checks the file's own hash."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if sc.lists_hash(doc["tasks"]) != doc.get("content_sha256"):
        raise AssertionError(f"{path}: content hash mismatch")
    return {int(f): v for f, v in doc["tasks"][task]["folds"].items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P1 S2 write or verify the future split file")
    ap.add_argument("--out-dir", type=Path, default=None, help="default data/9t/results/splits/")
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--verify", type=Path, default=None)
    ap.add_argument("--no-exporter-check", action="store_true")
    ap.add_argument("--exclude-audit", type=Path, default=None,
                    help="frozen P2 audit file. Its audit and buffer blocks leave every role (write v2 or later)")
    ap.add_argument("--buffer-json", type=Path, default=None,
                    help="P1 S4 buffer_derivation_9t.json. Default ek.default_buffer_path()")
    ap.add_argument("--buffer-mode", choices=BUFFER_MODES, default=DEFAULT_BUFFER_MODE,
                    help="window (default) keeps the lists and the sampler rejects windows within the buffer. "
                         "block moves train blocks within the buffer of held-out ground to role 'buffer'")
    ap.add_argument("--no-buffer", action="store_true",
                    help="exploratory only. Write the split with no buffer (recorded as buffer_m null)")
    a = ap.parse_args(argv)
    if a.verify:
        probs = verify(a.verify, check_exporter=not a.no_exporter_check)
        print("PASS" if not probs else "FAIL\n  " + "\n  ".join(probs))
        return 0 if not probs else 1
    out = a.out_dir or (ek.path_for("results_9t") / "splits")
    dst = out / f"cv_splits_future_9t_v{a.version}.json"
    if dst.exists():
        raise SystemExit(f"{dst} exists and is immutable. Use --version {a.version + 1} for a new split.")
    buffers = {}
    if not a.no_buffer:
        bj = a.buffer_json or ek.default_buffer_path()
        if not Path(bj).exists():
            raise SystemExit(f"buffer JSON missing: {bj}. Run _split_buffer_derive_9t.py (P1 S4), pass "
                             "--buffer-json, or pass --no-buffer for an exploratory split.")
        for t in sc.TASKS:
            try:
                buffers[t] = buffer_spec(t, Path(bj))
            except KeyError as e:
                raise SystemExit(f"{e}. Pass --no-buffer for an exploratory split.")
    excl, src = set(), None
    if a.exclude_audit:
        excl, src = audit_exclusion(a.exclude_audit)
    doc = build(check_exporter=not a.no_exporter_check, exclude=excl, exclude_source=src, buffers=buffers,
                buffer_mode=a.buffer_mode)
    write_split(doc, dst)
    run = ek.new_run("p1", "split_future", {"version": a.version, "out": str(out), "buffer_mode": a.buffer_mode,
                                            "no_buffer": a.no_buffer},
                     why="S2 write the immutable future split file.")
    ek.write_provenance(run, inputs=[Path(v["manifest"]) for v in doc["tasks"].values()], outputs=[dst],
                        params={"content_sha256": doc["content_sha256"]})
    for t, v in doc["tasks"].items():
        sizes = {f: tuple(len(r[x]) for x in sc.ROLES) for f, r in v["folds"].items()}
        print(f"{t}: {v['n_blocks']} blocks, {v['rows_without_block_dropped']} rows without block dropped, "
              f"(held, val, train) per fold {sizes}, buffer {v['buffer_m']} m {v['buffer_mode']}, "
              f"train blocks moved to buffer per fold {v['buffer_removed_by_fold']}")
    print(f"content_sha256 {doc['content_sha256']}\nfile sha256 {ek.sha256(dst)}\nwrote {dst}\nrun record {run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

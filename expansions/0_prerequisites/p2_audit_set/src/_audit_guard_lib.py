"""P2 S2. Audit guard. Refuse any training, calibration, mining or selection list that touches an audit block.

Purpose
    `load_audit(path)` reads a frozen audit file and refuses it unless its SHA-256 equals the frozen hash.
    The frozen hash is read from the sidecar `<file>.sha256` written at freeze time, and, when the file is
    tracked in git, also from the committed blob at HEAD. A file with neither is refused unless
    `allow_unfrozen=True` (dry runs and tests only).
    `assert_no_audit(items, audit)` raises on any intersection. Items are block ids, or shapely geometries
    (training windows). Windows are tested against the audit block polygons dilated by the audit file's
    `buffer_m` (positive-area overlap), so a window 1 m from audit ground fails at a 100 m buffer.
    An audit id with no polygon in `blocks` raises. It never passes as "far away" (review P2-03).
    The CLI checks every train, inner-validation and held-out list of a P1 split file. Audit blocks must
    not reach calibration or scoring folds either.
    Scope. The 9t draw frame is the pit-bearing blocks, so the file declares `tasks=pit` in its header.
    `load_audit(path, task="pad")` refuses a file whose header does not name the task. Every task may still
    exclude the blocks from training, which is conservative. Files without a `tasks` key are pit only.

Audit file schema (written by `_audit_draw_blocks_9t.py` and `_audit_reserve_warren.py`)
    Leading `#` comment lines state the use rule. Columns block_id (int), role (`audit` or `buffer`),
    stratum, area. Audit and buffer rows are both forbidden for training.

Inputs
    an audit CSV (data/9t/results/splits/audit_blocks_9t_v1.csv or data/warren/results/transfer/audit_blocks_warren_v1.csv)
    optionally a P1 split file and a blocks GeoPackage (layer `blocks`) for window checks

Outputs
    None from the library. The CLI prints PASS or the violations and exits 1 on any.

Run
    python expansions/0_prerequisites/p2_audit_set/src/_audit_guard_lib.py --audit data/9t/results/splits/audit_blocks_9t_v1.csv --splits data/9t/results/splits/cv_splits_future_9t_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402


class AuditViolation(AssertionError):
    """Raised when a list or window touches an audit block, or the audit file is not the frozen one."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def committed_hash(path: Path) -> str | None:
    """SHA-256 of the file's content at git HEAD, or None if untracked or git is unavailable."""
    try:
        rel = Path(path).resolve().relative_to(ek.REPO)
    except ValueError:
        return None
    try:
        r = subprocess.run(["git", "-C", str(ek.REPO), "show", f"HEAD:{rel.as_posix()}"], capture_output=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):        # git not installed, not runnable, or timed out
        return None
    return _sha(r.stdout) if r.returncode == 0 else None


def frozen_hashes(path: Path) -> dict:
    side = Path(str(path) + ".sha256")
    out = {"sidecar": side.read_text().split()[0] if side.exists() else None, "git_head": committed_hash(path)}
    return out


def audit_tasks(header: dict) -> set[str]:
    """Tasks the audit set was drawn for. A header without `tasks` is the pit-only 9t draw."""
    return set(str(header.get("tasks", "pit")).split(","))


def load_audit(path: Path, allow_unfrozen: bool = False, task: str | None = None) -> pd.DataFrame:
    """Hash-checked audit set. task, when given, must be named in the header `tasks` (draw scope)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"audit file not found: {path}")
    raw = path.read_bytes()
    h = _sha(raw)
    fz = frozen_hashes(path)
    known = [v for v in fz.values() if v]
    if not known and not allow_unfrozen:
        raise AuditViolation(f"{path} has no frozen hash (no .sha256 sidecar, not in git). Refusing.")
    bad = {k: v for k, v in fz.items() if v and v != h}
    if bad:
        raise AuditViolation(f"{path} sha256 {h[:12]} differs from frozen {bad}. Refusing.")
    df = pd.read_csv(io.BytesIO(raw), comment="#")
    if "block_id" not in df.columns:
        raise AuditViolation(f"{path} has no block_id column")
    df["block_id"] = df["block_id"].astype(int)
    df.attrs["sha256"] = h
    df.attrs["header"] = header_values(raw)
    if task is not None:
        key = "pit" if task.startswith("pit") else task
        if key not in audit_tasks(df.attrs["header"]):
            raise AuditViolation(f"{path} was drawn for tasks {sorted(audit_tasks(df.attrs['header']))}, not '{task}'. "
                                 "A separate draw is needed to score that task on held-back ground.")
    return df


def header_values(raw: bytes) -> dict:
    """key=value pairs from the leading # comment lines (seed, share, buffer_m, buffer_mode, written)."""
    out = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.startswith("#"):
            break
        for tok in line[1:].split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    out[k] = float(v) if k in ("share", "buffer_m") else (int(v) if k == "seed" else v)
                except ValueError:
                    out[k] = v
    return out


def assert_no_audit(items, audit: pd.DataFrame, label: str = "", blocks=None, buffer_m: float | None = None) -> None:
    """Raise AuditViolation if any block id, or any geometry, touches an audit or buffer block.

    Geometries are tested against the audit polygons dilated by buffer_m. The default is the audit file's
    header buffer_m. A smaller explicit value is refused."""
    items = list(items)
    if not items:
        return
    ids = set(audit.block_id.astype(int))
    if hasattr(items[0], "geom_type"):
        if blocks is None:
            raise ValueError("geometry items need the blocks GeoDataFrame")
        import shapely
        from shapely.strtree import STRtree
        need = float(audit.attrs.get("header", {}).get("buffer_m", 0.0) or 0.0)
        buf = need if buffer_m is None else float(buffer_m)
        if buf < need:
            raise AuditViolation(f"{label}: window buffer {buf} m is below the audit file's {need} m")
        have = set(blocks.block_id.astype(int))
        missing = sorted(ids - have)
        if missing:
            raise AuditViolation(f"{label}: audit blocks {missing[:10]} have no polygon in the blocks layer. "
                                 "Cannot check windows against them")
        polys = list(blocks[blocks.block_id.astype(int).isin(ids)].geometry)
        if buf > 0:
            polys = [g.buffer(buf, join_style="mitre") for g in polys]
        tree = STRtree(polys)
        shr = shapely.buffer(items, -1e-6, join_style="mitre")
        hit = tree.query(shr, predicate="intersects")
        if hit.size:
            raise AuditViolation(f"{label}: {len(set(hit[0]))} windows within {buf} m of audit ground")
        return
    clean = [int(b) for b in items if b is not None and b == b]
    inter = sorted(set(clean) & ids)
    if inter:
        raise AuditViolation(f"{label}: audit blocks in list {inter[:10]}{' ...' if len(inter) > 10 else ''}")


def check_split_file(split_path: Path, audit: pd.DataFrame, roles=("train", "inner_val", "held_out")) -> list[str]:
    """Every listed role of every task and fold. Returns violations as strings.

    held_out is checked too. Held-out folds feed calibration and scoring, which the audit set must not reach."""
    doc = json.loads(Path(split_path).read_text(encoding="utf-8"))
    out = []
    for task, t in doc["tasks"].items():
        for f, r in t["folds"].items():
            for role in roles:
                try:
                    assert_no_audit(r.get(role, []), audit, f"{task} fold {f} {role}")
                except AuditViolation as e:
                    out.append(str(e))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P2 audit guard check")
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--splits", type=Path, required=True, help="P1 split file")
    ap.add_argument("--allow-unfrozen", action="store_true", help="dry runs only")
    a = ap.parse_args(argv)
    audit = load_audit(a.audit, a.allow_unfrozen)
    v = check_split_file(a.splits, audit)
    print("PASS" if not v else "FAIL\n  " + "\n  ".join(v))
    return 0 if not v else 1


if __name__ == "__main__":
    sys.exit(main())

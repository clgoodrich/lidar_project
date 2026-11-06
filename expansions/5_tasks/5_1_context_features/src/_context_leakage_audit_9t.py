"""5.1 S6. Leakage audit for context stacking (tile 9t).

Purpose
    Fail the run unless every upstream model that fed outer fold k excluded fold k's blocks from its training and
    selection. That holds for stage-2 training inputs and test inputs alike (fw_5_1 section 3, protocol section 8).
    The audit reads the usage log S4 wrote (one entry per outer fold, block group, role and raster) and the
    training block set of each model that produced a value.
        shared-scheme rasters  training_blocks.json beside the raster ({train, val, held_out}). train + val count
                               as seen, because validation chose the checkpoint.
        historical pit mosaic  per block, the pit-scheme fold model that scored it trained on every other pit fold
        historical pad fold f  trained on every pad-scheme block outside fold f
        historical road        in-sample on 9t with no fold file. Every block counts as seen
    A second check (nested mode) asserts that a training row's own block fold was also excluded.

Inputs (config_5_1.json)
    outputs.stage2_usage  -> expansions/5_tasks/5_1_context_features/data/processed/stage2_upstream_usage_9t.json (S4)
    inputs.pit_assign, inputs.pad_assign  historical fold assignments (data/9t/models/.../*_fold_assignment_9t.csv)
    inputs.pit_blocks     block grid (all 144 blocks, for the in-sample road model)
Outputs
    outputs.leakage_audit -> expansions/5_tasks/5_1_context_features/results/tables/context_leakage_audit_9t.json
    Exit code 1 when the audit fails. S5 reads the JSON and voids its result on failure.
Run
    python expansions/5_tasks/5_1_context_features/src/_context_leakage_audit_9t.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "5_6_record_association" / "src"))
import _task5_helpers as th  # noqa: E402

ek = th.ek


def repo_rel(p) -> str:
    """Repo-relative POSIX path for outputs. Never an absolute path."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ek.REPO.resolve()).as_posix()
    except ValueError:
        return p.name


def _fold_map(csv: Path) -> dict[int, int]:
    d = pd.read_csv(csv).dropna(subset=["block_id", "fold"]).astype({"block_id": int, "fold": int})
    return dict(d.drop_duplicates("block_id")[["block_id", "fold"]].itertuples(index=False, name=None))


class Seen:
    """Training block set of the model that produced a value for a given usage entry and block."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._pit = self._pad = None
        self._all = None

    def pit_map(self):
        if self._pit is None:
            self._pit = _fold_map(th.inp(self.cfg, "pit_assign"))
        return self._pit

    def pad_map(self):
        if self._pad is None:
            self._pad = _fold_map(th.inp(self.cfg, "pad_assign"))
        return self._pad

    def all_blocks(self):
        if self._all is None:
            b = th.read_vector(th.inp(self.cfg, "pit_blocks"), layer="blocks")
            self._all = set(b.block_id.astype(int))
        return self._all

    def for_block(self, u: dict, block: int) -> set[int]:
        if u["kind"] != "historical":
            r = Path(u["raster"])
            log = (r if r.is_absolute() else ek.REPO / r).parent / "training_blocks.json"
            if not log.exists():
                raise th.MissingInput("shared_training_log", log, "the shared-scheme trainer must write it (S3)")
            j = json.loads(log.read_text())
            return {int(x) for x in j.get("train", []) + j.get("val", [])}
        if u["role"] == "pit":
            m = self.pit_map()
            if block not in m:
                return self.all_blocks()     # no pit fold for this block. Unknown, so treat as seen
            return {b for b, f in m.items() if f != m[block]}
        if u["role"] == "pad":
            m = self.pad_map()
            return {b for b, f in m.items() if f != u.get("pad_fold")} if u.get("pad_fold") is not None else self.all_blocks()
        return self.all_blocks()             # road: in-sample, no fold file


def audit(usage_doc: dict, seen: Seen, nested: bool) -> dict:
    b2f = {int(b): int(f) for b, f in usage_doc["block_to_fold"].items()}
    k_n = max(b2f.values()) + 1
    fold_blocks = {k: {b for b, f in b2f.items() if f == k} for k in range(k_n)}
    entries, n_bad = [], 0
    for u in usage_doc["usage"]:
        k = int(u["outer_fold"])
        blocks = u.get("blocks") or sorted(b for b, f in b2f.items() if f == u["block_fold"])
        viol, own = set(), set()
        cache: dict[frozenset, set] = {}
        for b in blocks:
            s = seen.for_block(u, int(b))
            key = frozenset(s)
            if key not in cache:
                cache[key] = s & fold_blocks[k]
            viol |= cache[key]
            if nested and u["block_fold"] != k:
                own |= s & fold_blocks[u["block_fold"]]
        ok = not viol and not own
        n_bad += not ok
        entries.append(dict(outer_fold=k, block_fold=u["block_fold"], role=u["role"], kind=u["kind"], raster=repo_rel(u["raster"]),
                            n_blocks=len(blocks), n_outer_blocks_seen=len(viol), example_seen=sorted(viol)[:5],
                            n_own_fold_seen=len(own), passed=ok))
    return dict(passed=n_bad == 0, n_entries=len(entries), n_failed=n_bad, mode=usage_doc.get("mode"),
                rule="every upstream model feeding outer fold k excluded fold k (train and val)", entries=entries)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    cfg = th.load_cfg(__file__, a.config)
    up = th.resolve(cfg["outputs"]["stage2_usage"])
    if not up.exists():
        raise th.MissingInput("stage2_usage", up, "run _context_stage2_features_9t.py first")
    doc = json.loads(up.read_text())
    res = audit(doc, Seen(cfg), nested=doc.get("mode") == "nested")
    res["usage_file"], res["usage_sha256"] = repo_rel(up), ek.sha256(up)
    out = th.outp(cfg, "leakage_audit")
    th.write_json(out, res)
    summ = pd.DataFrame(res["entries"]).groupby("role").agg(entries=("passed", "size"), failed=("passed", lambda s: int((~s).sum())))
    print(summ.to_string())
    print(f"audit {'PASSED' if res['passed'] else 'FAILED'}  wrote {out}")
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except th.MissingInput as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(2)

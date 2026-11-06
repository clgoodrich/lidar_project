"""Fresh-checkout reproduction test of the release (7.3 S5).

Purpose
    Copy the release into an empty temporary folder, verify the manifest, rerun evaluate.py with the
    exact shipped baseline commands in a separate interpreter (no repo on its path, no expkit), and
    compare every output byte for byte with the shipped baseline files. The gate needs exact equality.
    Tiles are not needed to rescore and are skipped unless --with-tiles is given.

Inputs
    <release>/manifest.csv, evaluate.py, labels/, blocks/, baselines/ (from the export and baseline scripts)
Outputs
    expansions/7_scale/7_3_benchmark/results/tables/bench_fresh_checkout_terrain_v1.json
    Exit code 0 when every baseline reproduces exactly, 1 otherwise, 2 when inputs are missing.

Run
    python expansions/7_scale/7_3_benchmark/src/_bench_fresh_checkout_test.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bench_export_release_9t import CFG, cfg_path, load_cfg, verify_manifest  # noqa: E402


def fresh_check(root: Path, with_tiles: bool = False) -> dict:
    res = {"release": str(root), "manifest_problems": verify_manifest(root), "baselines": {}}
    cmds = json.loads((root / "baselines" / "baseline_commands.json").read_text())
    with tempfile.TemporaryDirectory(prefix="bench_fresh_") as td:
        dst = Path(td) / root.name
        ignore = None if with_tiles else shutil.ignore_patterns("tiles")
        shutil.copytree(root, dst, ignore=ignore)
        for name, argv in cmds.items():
            outs = [argv[i + 1] for i, t in enumerate(argv) if t in ("--out", "--candidates-out", "--blocks-out")]
            for o in outs:
                (dst / o).unlink(missing_ok=True)
            # -I isolates from user site and the repo. Fall back to plain python, where the
            # project packages live in user site (fw_00 section 3).
            r = subprocess.run([sys.executable, "-I", "evaluate.py", *argv], cwd=dst, capture_output=True, text=True)
            if r.returncode != 0:
                r = subprocess.run([sys.executable, "evaluate.py", *argv], cwd=dst, capture_output=True, text=True)
            same = {o: (dst / o).exists() and (dst / o).read_bytes() == (root / o).read_bytes() for o in outs}
            res["baselines"][name] = {"rc": r.returncode, "identical": same, "stderr_tail": r.stderr[-400:]}
    res["pass"] = (not res["manifest_problems"]) and all(
        b["rc"] == 0 and all(b["identical"].values()) for b in res["baselines"].values()) and bool(cmds)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fresh-checkout reproduction test (7.3 S5).")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--release", default=None)
    ap.add_argument("--with-tiles", action="store_true")
    ap.add_argument("--out", default=str(ek.sub("7.3", "results/tables") / "bench_fresh_checkout_terrain_v1.json"))
    a = ap.parse_args(argv)
    cfg = load_cfg(Path(a.config))
    root = Path(a.release) if a.release else cfg_path(cfg["release_root"]) / cfg["release_name"]
    if not (root / "baselines" / "baseline_commands.json").exists():
        print(f"missing baselines under {root}. Run _bench_baselines_score_9t.py first.", file=sys.stderr)
        return 2
    res = fresh_check(root, a.with_tiles)
    Path(a.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({"pass": res["pass"], "manifest_problems": res["manifest_problems"][:5]}, indent=2))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

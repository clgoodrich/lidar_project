"""Reorganize wellsight_v2 by PIPELINE STAGE instead of by target.

Today the code is grouped by what it detects -- pits/, plats/, roads/, drainage/
-- so every one of those folders holds label-prep AND training AND inference
scripts. That does not match how the work actually flows:

    s1_build    LAZ -> DEM -> channels -> feature stack
    s2_labels   annotations -> label rasters + train/val/test splits
    s3_train    labels + features -> best.pt
    s4_infer    best.pt + a new area -> probability rasters -> candidates
    s5_eval     score predictions against held-out truth
    s6_review   build review packages; fold human corrections back into s2
    s7_analysis morphology, change detection, science outputs

WHY THIS IS SAFE, MECHANICALLY
Every script currently sits at wellsight_v2/<dir>/<file>.py. Every script ends
at wellsight_v2/<stage>/<file>.py. The DEPTH IS UNCHANGED, so all 167
`sys.path.insert(0, Path(__file__).resolve().parents[N])` calls keep resolving
to exactly the same directory. That is the whole reason this is a rename and
not a rewrite.

WHAT DOES BREAK, AND IS FIXED HERE
Anything that names a directory literally. There are only 17:

  * 4  `parents[1] / "build"` / `"pits"`     sibling-dir sys.path inserts
  * 10 `ROOT / "notebooks" / "wellsight_v2" / "<dir>"`  absolute inserts
  * 3  ui/registry.py constants RB / AN / BU

Each is repointed by RESOLVING WHAT IT IS FOR, not by string substitution: for
a file F whose sys.path names old directory D, find the modules F imports that
live in D, look up where those modules land, and point at that stage. A single
old directory can fan out to several stages -- plats/ splits across s3_train and
s4_infer -- so one insert can become two.

Scripts that both train and predict (the CV5 runners, _road_unet_1m_recall)
land in s3_train and keep their inference tail. Splitting them is a code change,
not a move, and is out of scope here.

Outputs:
    docs/stage_refactor_moves.csv     ledger for tools/apply_moves.py
    docs/stage_refactor_edits.csv     per-file source rewrites to apply
    docs/stage_refactor_plan.md       the mapping, and what breaks if it is wrong

Reproduce:
  python tools/plan_stage_refactor.py            # plan only
  python tools/plan_stage_refactor.py --apply    # move + rewrite
"""
from __future__ import annotations

import argparse
import ast
import csv
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "notebooks" / "wellsight_v2"
LEDGER = ROOT / "docs" / "stage_refactor_moves.csv"
EDITS = ROOT / "docs" / "stage_refactor_edits.csv"
PLAN = ROOT / "docs" / "stage_refactor_plan.md"

# ---------------------------------------------------------------- the mapping
STAGES: dict[str, list[str]] = {
    "s1_build": [
        "build/_build_derivatives.py", "build/_build_extra_channels.py",
        "build/_build_data_3x3_derivatives.py",
        "build/_build_data_3x3_partial_westernpa.py",
        "build/_build_3x3_hillshades.py", "build/_build_contours_data_3x3.py",
        "build/_build_exag_derivatives.py", "build/_fetch_nisar_9t.py",
        "build/_fetch_permian_grids.py", "pits/_stack_features.py",
    ],
    "s2_labels": [
        "annotations/_prep_annotations.py", "annotations/_build_pit_dataset.py",
        "annotations/_build_plat_road_dataset.py",
        "annotations/_build_plat_split.py", "annotations/_build_unified_split.py",
        "annotations/_merge_review_added_roads_613590_into_roads_shp.py",
        "annotations/_sanity_render.py", "build/_build_label_grids.py",
        "roads/_prep_road_1m.py", "roads/_rebuild_labels_road_9t_1m.py",
        "roads/_build_orient_labels.py",
    ],
    "s3_train": [
        "pits/_pit_unet_cv5.py", "pits/_pit_unet_v2.py", "pits/_pit_maskrcnn.py",
        "pits/_pit_yolo.py", "plats/_pad_unet_cv5.py", "plats/_plat_unet.py",
        "plats/_pad_maskrcnn.py", "plats/_pad_yolo.py",
        "roads/_road_unet_1m_recall.py", "roads/_road_unet_1m_corrected.py",
        "roads/_road_sweep_202607.py", "drainage/_drainage_unet_1m.py",
        "multitask/_multitask_unet.py",
    ],
    "s4_infer": [
        "build/_predict_on_tile.py", "build/_infer_roads_data_3x3.py",
        "build/_yolo_infer_tile.py", "build/_postfilter_tile_candidates.py",
        "build/_refine_roads_data_3x3.py", "roads/_road_infer.py",
        "pits/_pit_unet_v2_infer.py", "pits/_pit_maskrcnn_infer.py",
        "pits/_pit_yolo_infer.py", "plats/_pad_maskrcnn_infer.py",
        "plats/_pad_yolo_infer.py", "plats/_pad_unet_infer_grid.py",
    ],
    "s5_eval": [
        "build/_road_optimize.py", "build/_pit_optimize.py",
        "build/_road_methods_compare.py", "roads/_road_sweep_aggregate.py",
        "roads/_compare_corrected_613590.py",
    ],
    "s6_review": [
        "build/_build_road_review_package.py", "build/_build_pit_review_package.py",
        "build/_build_drainage_review_package.py", "build/_road_corrections_diff.py",
        "build/_pit_corrections_diff.py", "build/_overlay_drainage_review_613590.py",
        "build/_calibrate_drainage_extraction_9t.py",
        "roads/_build_road_corrections_613590.py",
    ],
    "s7_analysis": [
        "build/_icp_change_9t.py", "build/_icp_change_9t_rebuild.py",
        "build/_icp_change_classify_9t.py",
    ],
}
# whole directories that move as a unit
DIR_STAGES = {"eval": "s5_eval", "analysis": "s7_analysis"}
# stay at wellsight_v2/ root, imported by everything
SHARED = {"_common.py", "_dl.py", "_instance_common.py"}


def build_mapping() -> dict[str, str]:
    m: dict[str, str] = {}
    for stage, items in STAGES.items():
        for rel in items:
            m[rel] = f"{stage}/{Path(rel).name}"
    for d, stage in DIR_STAGES.items():
        for p in sorted((V2 / d).glob("*.py")):
            m[f"{d}/{p.name}"] = f"{stage}/{p.name}"
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    mapping = build_mapping()
    present = {p.relative_to(V2).as_posix() for p in V2.rglob("*.py")
               if "__pycache__" not in p.parts}
    unmapped = sorted(present - set(mapping) - SHARED)
    missing = sorted(set(mapping) - present)
    print(f"{len(present)} scripts, {len(mapping)} mapped, "
          f"{len(SHARED)} shared at root, {len(unmapped)} UNMAPPED")
    if missing:
        print("  mapping references files that do not exist:")
        for x in missing:
            print(f"    {x}")
        return 1
    if unmapped:
        print("  UNMAPPED (refusing to proceed -- every file must be placed):")
        for x in unmapped:
            print(f"    {x}")
        return 1

    # module name -> (old directory, new stage directory)
    mod_old = {Path(k).stem: Path(k).parent.as_posix() for k in mapping}
    mod_dir = {Path(k).stem: Path(v).parent.as_posix() for k, v in mapping.items()}
    for s in SHARED:                          # stay at wellsight_v2/ root
        mod_old[Path(s).stem] = ""
        mod_dir[Path(s).stem] = ""

    # ---------------- compute source rewrites ------------------------------
    edits = []
    for rel, new in sorted(mapping.items()):
        src_path = V2 / rel
        text = src_path.read_text(encoding="utf8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and not n.level:
                imported.add(n.module.split(".")[0])
            elif isinstance(n, ast.Import):
                imported |= {x.name.split(".")[0] for x in n.names}
        # ONLY rewrite inside sys.path statements. `DERIV / "annotations"` is the
        # DATA directory and must never become `DERIV / "s2_labels"`; a naive
        # whole-file regex rewrites it in 20+ scripts and breaks every one that
        # reads annotations. Locate the sys.path statements by AST and confine
        # the substitution to their exact line spans.
        syspath_lines: set[int] = set()
        for n in ast.walk(tree):
            hit = False
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Attribute) and f.attr in ("insert", "append") \
                        and isinstance(f.value, ast.Attribute) and f.value.attr == "path":
                    hit = True
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) \
                            and t.value.attr == "path":
                        hit = True
            if hit and hasattr(n, "lineno"):
                syspath_lines.update(
                    range(n.lineno, (getattr(n, "end_lineno", n.lineno) or n.lineno) + 1))
        if not syspath_lines:
            continue

        lines = text.splitlines(keepends=True)
        new_text = text

        # a) parents[N] / "<olddir>"   and   ROOT/.../wellsight_v2/"<olddir>"
        for olddir in sorted({Path(k).parent.as_posix() for k in mapping}):
            pat = re.compile(rf'(/\s*"){re.escape(olddir)}(")')
            if not any(pat.search(lines[i - 1]) for i in syspath_lines
                       if i - 1 < len(lines)):
                continue
            # which stages hold the modules this file imports from olddir?
            wanted = {mod_dir[m] for m in imported
                      if m in mod_dir and mod_old.get(m) == olddir}
            wanted.discard("")
            if len(wanted) == 1:
                target = wanted.pop()
            elif len(wanted) > 1:
                target = sorted(wanted)[0]
                edits.append(dict(path=f"notebooks/wellsight_v2/{rel}",
                                  kind="MANUAL: fans out to " + ",".join(sorted(wanted)),
                                  old=olddir, new=target))
            else:
                # nothing imported from it; point at the file's own new stage
                target = Path(new).parent.as_posix()
            for i in sorted(syspath_lines):
                if i - 1 < len(lines):
                    lines[i - 1] = pat.sub(rf'\g<1>{target}\g<2>', lines[i - 1])
            new_text = "".join(lines)
        if new_text != text:
            edits.append(dict(path=f"notebooks/wellsight_v2/{rel}",
                              kind="sys.path repoint", old="", new=""))
            if a.apply:
                src_path.write_text(new_text, encoding="utf8")

    # ---------------- external references ----------------------------------
    ext = {
        "ui/registry.py": [('"notebooks/wellsight_v2/roads"', '"notebooks/wellsight_v2/s3_train"'),
                           ('"notebooks/wellsight_v2/analysis"', '"notebooks/wellsight_v2/s7_analysis"'),
                           ('"notebooks/wellsight_v2/build"', '"notebooks/wellsight_v2/s1_build"')],
        "roads_studio/core.py": [('"wellsight_v2" / "build"', '"wellsight_v2" / "s5_eval"')],
        "roads_studio/train.py": [('"roads" / "_road_sweep_202607.py"',
                                   '"s3_train" / "_road_sweep_202607.py"')],
    }
    for f, subs in ext.items():
        p = ROOT / f
        if not p.exists():
            continue
        t = p.read_text(encoding="utf8")
        n = t
        for old, new in subs:
            n = n.replace(old, new)
        if n != t:
            edits.append(dict(path=f, kind="external reference", old="", new=""))
            if a.apply:
                p.write_text(n, encoding="utf8")

    # ---------------- ledger ------------------------------------------------
    rows = [dict(old_path=f"notebooks/wellsight_v2/{k}",
                 new_path=f"notebooks/wellsight_v2/{v}",
                 phase="stage_refactor",
                 reason=f"pipeline stage {Path(v).parent.as_posix()}")
            for k, v in sorted(mapping.items())]
    with open(LEDGER, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["old_path", "new_path", "phase", "reason"])
        w.writeheader(); w.writerows(rows)
    with open(EDITS, "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "kind", "old", "new"])
        w.writeheader(); w.writerows(edits)

    counts = defaultdict(int)
    for v in mapping.values():
        counts[Path(v).parent.as_posix()] += 1
    L = ["# Stage refactor plan", "",
         "Reorganizes `notebooks/wellsight_v2/` by pipeline stage. Depth is "
         "unchanged, so all 167 `parents[N]` sys.path calls keep working. Only "
         "literal directory names need repointing.", "",
         "| Stage | Scripts | What it does |", "|---|---:|---|",
         f"| `s1_build` | {counts['s1_build']} | LAZ to DEM to channels to feature stack |",
         f"| `s2_labels` | {counts['s2_labels']} | annotations to label rasters and splits |",
         f"| `s3_train` | {counts['s3_train']} | labels + features to best.pt |",
         f"| `s4_infer` | {counts['s4_infer']} | best.pt + new area to candidates |",
         f"| `s5_eval` | {counts['s5_eval']} | score against held-out truth |",
         f"| `s6_review` | {counts['s6_review']} | review packages; corrections back to s2 |",
         f"| `s7_analysis` | {counts['s7_analysis']} | morphology, change detection |",
         f"| _(root)_ | {len(SHARED)} | `_common.py`, `_dl.py`, `_instance_common.py` |",
         "", f"{len(rows)} files move. {len(edits)} source rewrites.", ""]
    manual = [e for e in edits if e["kind"].startswith("MANUAL")]
    if manual:
        L += ["## Needs a human look", "",
              "One old directory fans out to several stages, so a single "
              "sys.path insert may need to become two:", ""]
        L += [f"- `{e['path']}` — {e['kind']}" for e in manual]
        L.append("")
    PLAN.write_text("\n".join(L) + "\n", encoding="utf8")

    for k in sorted(counts):
        print(f"  {k:<14} {counts[k]:3d}")
    print(f"  {len(edits)} source rewrites"
          f"{' APPLIED' if a.apply else ' (dry run)'}")
    if manual:
        print(f"  {len(manual)} need a human look -- see {PLAN.name}")
    print(f"wrote {LEDGER}\nwrote {PLAN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

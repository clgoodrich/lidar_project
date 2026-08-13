"""Declarative catalog of runnable tasks. Pages auto-generate forms from this.

Each Task maps form widgets -> a CLI arg list for its script. Adding a script to
the UI is one Task entry. `build` turns the collected widget values into
(script_path, args_list, gpu, output_dir_note); `requires` lists input files
whose absence disables Run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from paths import (ANNOT, DERIV, DERIV_9T, ROOT, SWEEP, path_for, block_features,
                   list_blocks, list_road_models)

# One constant per pipeline stage. The old per-target constants (RB=roads,
# AN=analysis, BU=build) collapsed on 2026-08-12 when the stage refactor sent
# scripts from a single old folder to four different stages -- `roads/` split
# across s2_labels, s3_train, s4_infer and s5_eval. A per-target constant can no
# longer name a directory correctly, so these are per-stage.
S1 = "notebooks/wellsight_v2/s1_build"
S2 = "notebooks/wellsight_v2/s2_labels"
S3 = "notebooks/wellsight_v2/s3_train"
S4 = "notebooks/wellsight_v2/s4_infer"
S5 = "notebooks/wellsight_v2/s5_eval"
S7 = "notebooks/wellsight_v2/s7_analysis"
STATS_1M = DERIV_9T / "feature_stats_1m.json"
UI_INFER = path_for("experiments") / "ui_infer"


@dataclass
class Inp:
    kind: str                     # radio|select|multiselect|int|flag|slider
    name: str
    label: str
    choices: Callable[[], list] | list | None = None
    default: object = None
    help: str = ""
    minv: float = 0
    maxv: float = 1
    step: float = 1
    flag: str = ""                # for kind==flag: the CLI flag emitted when True

    def options(self) -> list:
        return self.choices() if callable(self.choices) else (self.choices or [])


@dataclass
class Task:
    id: str
    label: str
    group: str                    # page name
    script: str
    gpu: bool
    inputs: list[Inp]
    build: Callable[[dict], list[str]]
    requires: Callable[[dict], list[Path]] = lambda v: []
    outputs: Callable[[dict], list[Path]] = lambda v: []
    docs: str = ""
    note: str = ""

    @property
    def script_abs(self) -> Path:
        return ROOT / self.script


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _infer_build(v: dict) -> list[str]:
    models = list_road_models()
    ckpt = models[v["model"]]
    block = v["block"]
    outdir = UI_INFER / block.replace("/", "__") / v["model"].replace(
        ":", "_").replace(" ", "_").replace("(", "").replace(")", "")
    return ["--checkpoint", str(ckpt), "--features", str(block_features(block)),
            "--stats", str(STATS_1M), "--outdir", str(outdir),
            "--patch", str(int(v.get("patch", 256))),
            "--overlap", str(int(v.get("overlap", 64)))]


def _infer_out(v: dict) -> list[Path]:
    block = v["block"]
    outdir = UI_INFER / block.replace("/", "__") / v["model"].replace(
        ":", "_").replace(" ", "_").replace("(", "").replace(")", "")
    return [outdir / "road_prob.tif"]


def _sweep_build(v: dict) -> list[str]:
    args = ["--variant", v["variant"]]
    if v.get("epochs"):
        args += ["--epochs", str(int(v["epochs"]))]
    if v.get("eval_only"):
        args.append("--eval-only")
    return args


# --------------------------------------------------------------------------
# catalog
# --------------------------------------------------------------------------
TASKS: dict[str, Task] = {}


def _add(t: Task):
    TASKS[t.id] = t


_add(Task(
    id="roads.infer", label="Run road inference on a block", group="Roads",
    script=f"{S4}/_road_infer.py", gpu=True,
    inputs=[
        Inp("radio", "model", "Model", choices=lambda: list(list_road_models()),
            help="Trained road checkpoints found on disk."),
        Inp("select", "block", "Target block", choices=list_blocks,
            default="9t"),
        Inp("int", "patch", "Patch px", default=256, minv=128, maxv=512),
        Inp("int", "overlap", "Overlap px", default=64, minv=0, maxv=256),
    ],
    build=_infer_build,
    requires=lambda v: [block_features(v["block"]),
                        list_road_models().get(v.get("model", ""), Path("x"))],
    outputs=_infer_out,
    docs="docs/iterations/road_unet_1m_corrected.md",
    note="Writes road/drainage prob + argmax to data/derivatives/experiments/"
         "ui_infer/. Does NOT deploy over block rasters."))

_add(Task(
    id="roads.sweep", label="Train a sweep variant", group="Roads",
    script=f"{S3}/_road_sweep_202607.py", gpu=True,
    inputs=[
        Inp("radio", "variant", "Variant",
            choices=["cldice", "alpha078", "boundary", "orient", "res05"]),
        Inp("int", "epochs", "Epochs (blank=default)", default=0,
            minv=0, maxv=60, help="0 = the variant's built-in epoch count."),
        Inp("flag", "eval_only", "Eval only (skip training)", flag="--eval-only"),
    ],
    build=_sweep_build,
    outputs=lambda v: [SWEEP / v["variant"] / "road_prob.tif"],
    docs="docs/handoff/ROAD_SWEEP_HANDOFF.md",
    note="One of the 5 optimization variants. GPU-serialized."))

_add(Task(
    id="roads.sweep.aggregate", label="Aggregate sweep leaderboard",
    group="Roads", script=f"{S5}/_road_sweep_aggregate.py", gpu=False,
    inputs=[], build=lambda v: [],
    outputs=lambda v: [SWEEP / "leaderboard.md"],
    note="Reads every variant's test_metrics.json + baselines -> leaderboard."))

_add(Task(
    id="roads.orient_labels", label="Build orientation labels", group="Roads",
    script=f"{S2}/_build_orient_labels.py", gpu=False, inputs=[],
    build=lambda v: [], note="Prerequisite for the orient sweep variant."))

_add(Task(
    id="analysis.provenance", label="Well provenance flags (Venango+McKean)",
    group="Analysis", script=f"{S7}/_well_provenance_flags.py", gpu=False,
    inputs=[], build=lambda v: [],
    outputs=lambda v: [path_for("experiments") / "well_provenance" /
                       "well_provenance_venango.gpkg"],
    docs="docs/analysis_log.md"))

_add(Task(
    id="analysis.age", label="Well age vs morphology", group="Analysis",
    script=f"{S7}/_well_age_morphology.py", gpu=False, inputs=[],
    build=lambda v: [],
    outputs=lambda v: [path_for("experiments") / "well_age_morphology" /
                       "summary_stats.json"],
    docs="docs/iterations/well_age_morphology.md"))

_add(Task(
    id="analysis.padbins", label="Pad morphology bins", group="Analysis",
    script=f"{S7}/_pad_morphology_bins.py", gpu=False,
    inputs=[Inp("radio", "k", "Clusters (k)", choices=["", "2", "3"],
                default="", help="blank = silhouette-selected k")],
    build=lambda v: (["--k", v["k"]] if v.get("k") else []),
    outputs=lambda v: [path_for("experiments") / "pad_morphology_bins"],
    docs="docs/iterations/pad_morphology_bins.md"))

_add(Task(
    id="analysis.photos", label="Well photo source locations", group="Analysis",
    script=f"{S7}/_photo_source_locations.py", gpu=False, inputs=[],
    build=lambda v: [],
    outputs=lambda v: [path_for("experiments") / "well_photo_locations" /
                       "well_photo_locations.gpkg"]))


def by_group(group: str) -> list[Task]:
    return [t for t in TASKS.values() if t.group == group]


GROUPS = ["Roads", "Analysis"]

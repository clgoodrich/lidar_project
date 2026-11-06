"""Give every expansion project its own standard directory under expansions/.

Layout follows common data-science project practice (one folder per project,
same skeleton everywhere, docs / code / data / models / results kept apart,
raw data immutable, heavy files never in git, a README at every level).

    expansions/
      README.md                      index: id, project, tier, status, folder
      _shared/fw_00_common.md        machinery every framework inherits
      _template/                     the skeleton, copy it for a new expansion
      <group>/<id>_<slug>/
        README.md                    status, gate, next step, where outputs go
        docs/  plan_*.md  fw_*.md  decisions_<id>.md
        src/                         scripts for this expansion
        data/raw/        (ignored)   inputs as received. never edited
        data/interim/    (ignored)   intermediate products
        data/processed/  (ignored)   model-ready inputs
        models/          (ignored)   weights and checkpoints
        results/figures/             small tracked figures
        results/tables/              small tracked tables and JSON

Area products for a new study area still go to data/<area>/ (area-major rule
in STRUCTURE.md). The expansion's own data/ is for inputs and intermediates
that belong to the expansion and not to an area.

Steps (each safe to rerun):
    python tools/scaffold_expansions.py ledger      # write move ledger
    python tools/apply_moves.py --ledger docs/_ledgers/expansions_moves.csv --execute
    python tools/scaffold_expansions.py scaffold    # skeleton + READMEs
    python tools/scaffold_expansions.py links       # rewrite links to new paths
"""
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "expansions"
PLANS = "docs/plans"
FWD = "docs/plans/frameworks"
LEDGER = ROOT / "docs/_ledgers/expansions_moves.csv"

GROUPS = {"p": "0_prerequisites", "3": "3_geography", "4": "4_modalities",
          "5": "5_tasks", "6": "6_adjacent", "7": "7_scale"}

# id, folder slug, title, plan file, framework file
P = [
    ("p1", "splits_manifests", "Reproducible splits and manifests", "plan_prereq_splits_manifests.md", "fw_p1_splits_manifests.md"),
    ("p2", "audit_set", "Audit set and training history", "plan_prereq_audit_set.md", "fw_p2_audit_set.md"),
    ("3.0", "transfer_protocol", "Transfer protocol", "plan_geo_transfer_protocol.md", "fw_3_0_transfer_protocol.md"),
    ("3.1", "warren_forest_mckean", "Warren, Forest and McKean transfer", "plan_geo_warren_forest.md", "fw_3_1_warren_forest_mckean.md"),
    ("3.2", "appalachian_states", "Ohio, West Virginia, New York, Kentucky", "plan_geo_appalachian_states.md", "fw_3_2_appalachian_states.md"),
    ("3.3", "low_relief_slope", "Low-relief sensitivity", "plan_geo_low_relief_midwest.md", "fw_3_3_low_relief_slope.md"),
    ("3.4", "gulf_texas", "Gulf Coast and Texas", "plan_geo_gulf_east_texas.md", "fw_3_4_gulf_texas.md"),
    ("3.5", "oklahoma_kansas", "Oklahoma and Kansas", "plan_geo_oklahoma_kansas.md", "fw_3_5_oklahoma_kansas.md"),
    ("3.6", "california", "California", "plan_geo_california.md", "fw_3_6_california.md"),
    ("3.7", "canada", "Canada", "plan_geo_canada.md", "fw_3_7_canada.md"),
    ("3.8", "alaska", "Alaska", "plan_geo_alaska.md", "fw_3_8_alaska.md"),
    ("4.1", "magnetometry", "Magnetometry pilot", "plan_mod_magnetometry.md", "fw_4_1_magnetometry.md"),
    ("4.2", "thermal", "Thermal", "plan_mod_thermal.md", "fw_4_2_thermal.md"),
    ("4.3", "vegetation_stress", "Vegetation stress", "plan_mod_vegetation_stress.md", "fw_4_3_vegetation_stress.md"),
    ("4.4", "methane_plumes", "Methane plumes", "plan_mod_methane_plumes.md", "fw_4_4_methane_plumes.md"),
    ("4.5", "multitemporal_lidar", "Multitemporal lidar at plugged wells", "plan_mod_multitemporal_lidar.md", "fw_4_5_multitemporal_lidar.md"),
    ("4.6", "historic_maps_aerials", "Historic maps and aerials", "plan_mod_historic_maps_aerials.md", "fw_4_6_historic_maps_aerials.md"),
    ("4.7", "drone_lidar", "Drone lidar density ladder", "plan_mod_drone_lidar.md", "fw_4_7_drone_lidar.md"),
    ("4.8", "leafoff_optical", "Leaf-off optical imagery", "plan_mod_leafoff_optical.md", "fw_4_8_leafoff_optical.md"),
    ("4.9", "more_radar", "More radar", "plan_mod_more_radar.md", "fw_4_9_more_radar.md"),
    ("5.1", "context_features", "Context features (second-stage model)", "plan_task_context_features.md", "fw_5_1_context_features.md"),
    ("5.2", "era_classification", "Era classification", "plan_task_era_classification.md", "fw_5_2_era_classification.md"),
    ("5.3", "risk_ranking", "Risk ranking", "plan_task_risk_ranking.md", "fw_5_3_risk_ranking.md"),
    ("5.4", "undocumented_density", "Undocumented well density", "plan_task_undocumented_density.md", "fw_5_4_undocumented_density.md"),
    ("5.5", "polygon_area_cost", "Polygon area and cost", "plan_task_polygon_area_cost.md", "fw_5_5_polygon_area_cost.md"),
    ("5.6", "record_association", "Record association", "plan_task_record_association.md", "fw_5_6_record_association.md"),
    ("6.1", "co2_geothermal", "CO2 storage and geothermal screening", "plan_adj_co2_geothermal.md", "fw_6_1_co2_geothermal.md"),
    ("6.2", "coal_features", "Coal and mine features", "plan_adj_coal_features.md", "fw_6_2_coal_features.md"),
    ("6.3", "confuser_classes", "Confuser classes and negative-class training", "plan_adj_negative_classes.md", "fw_6_3_confuser_classes.md"),
    ("6.4", "hydrogen", "Hydrogen storage screening", "plan_adj_hydrogen.md", "fw_6_4_hydrogen.md"),
    ("6.5", "field_methane", "Field methane screening", "plan_adj_field_methane.md", "fw_6_5_field_methane.md"),
    ("6.6", "sar_viewshed", "Search and rescue viewshed", "plan_adj_sar_viewshed.md", "fw_6_6_sar_viewshed.md"),
    ("7.1", "pretraining", "Self-supervised pretraining", "plan_scale_pretraining.md", "fw_7_1_pretraining.md"),
    ("7.2", "active_learning", "Active learning", "plan_scale_active_learning.md", "fw_7_2_active_learning.md"),
    ("7.3", "benchmark", "Terrain-feature benchmark", "plan_scale_benchmark.md", "fw_7_3_benchmark.md"),
    ("7.4", "agency_tooling", "Agency tooling", "plan_scale_agency_tooling.md", "fw_7_4_agency_tooling.md"),
    ("7.5", "field_campaign", "Field campaign", "plan_scale_field_campaign.md", "fw_7_5_field_campaign.md"),
]

SKELETON = ["docs", "src", "data/raw", "data/interim", "data/processed", "models",
            "results/figures", "results/tables"]


def folder(pid, slug):
    return f"expansions/{GROUPS[pid[0]]}/{pid.replace('.', '_')}_{slug}"


def new_paths():
    """old repo-relative path -> new repo-relative path, for every moved doc."""
    m = {f"{FWD}/fw_00_common.md": "expansions/_shared/fw_00_common.md",
         f"{FWD}/README.md": "expansions/README.md"}
    for pid, slug, _, plan, fw in P:
        d = folder(pid, slug)
        m[f"{PLANS}/{plan}"] = f"{d}/docs/{plan}"
        m[f"{FWD}/{fw}"] = f"{d}/docs/{fw}"
    return m


def ledger():
    rows = []
    for old, new in new_paths().items():
        p = ROOT / old
        if not p.exists():
            continue
        rows.append(dict(ts="", phase="expansions", old_path=old, new_path=new,
                         size_bytes=p.stat().st_size, reason="one standard directory per expansion"))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["ts", "phase", "old_path", "new_path", "size_bytes", "reason"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} moves -> {LEDGER}")


def status_line(fw_path):
    """First Tier line of the framework, used as the status in the README."""
    try:
        for line in fw_path.read_text(encoding="utf-8").splitlines()[:6]:
            if line.startswith("**Tier"):
                return line.strip("*").split("**")[0].strip().rstrip(".")
    except OSError:
        pass
    return "plan only"


README = """# {pid}. {title}

**Status.** Plan only. Nothing here has been run. {tier}.
**Plan.** [docs/{plan}](docs/{plan})
**Framework.** [docs/{fw}](docs/{fw}) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_{tag}.md](docs/decisions_{tag}.md)
**Shared rules.** [fw_00_common.md](../../_shared/fw_00_common.md) and [protocol_gates_and_metrics.md](../../../docs/plans/protocol_gates_and_metrics.md). The protocol wins on any conflict.

## Folders

| Folder | Holds | In git |
|---|---|---|
| `docs/` | plan, framework, decisions log | yes |
| `src/` | scripts for this expansion | yes |
| `data/raw/` | inputs as received. Never edited | no |
| `data/interim/` | intermediate products | no |
| `data/processed/` | model-ready inputs | no |
| `models/` | weights and checkpoints | no |
| `results/figures/` | small figures | yes |
| `results/tables/` | small tables and JSON | yes |

Products for a new study area go to `data/<area>/` as everywhere else, not here.
Scripts resolve paths with `path_for("expansions")` (key in `config/paths.toml`). Add the import path with
`sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "notebooks/wellsight_v2"))`.
Anything at or above 100 MB goes under an ignored folder. Every run gets an entry in `docs/analysis_log.md`.
"""

DECISIONS = """# {pid} decisions

Newest first. One line per decision, with the date and who made it.

"""


def scaffold():
    for sub in SKELETON:
        d = EXP / "_template" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()
    (EXP / "_shared").mkdir(parents=True, exist_ok=True)
    for pid, slug, title, plan, fw in P:
        d = ROOT / folder(pid, slug)
        for sub in SKELETON:
            (d / sub).mkdir(parents=True, exist_ok=True)
            k = d / sub / ".gitkeep"
            if not any(p.name != ".gitkeep" for p in (d / sub).iterdir()):
                k.touch()
        tag = pid.replace(".", "_")
        r = d / "README.md"
        if not r.exists():
            r.write_text(README.format(pid=pid.upper(), title=title, plan=plan, fw=fw, tag=tag,
                                       tier=status_line(d / "docs" / fw)), encoding="utf-8")
        dec = d / "docs" / f"decisions_{tag}.md"
        if not dec.exists():
            dec.write_text(DECISIONS.format(pid=pid.upper()), encoding="utf-8")
    print(f"scaffolded {len(P)} expansions under {EXP}")


LINK = re.compile(r"\]\(([^)#\s]+)(#[^)]*)?\)")


def links():
    """Rewrite markdown links and plain path mentions to the new locations."""
    moves = new_paths()
    by_name = {Path(o).name: n for o, n in moves.items() if Path(o).name != "README.md"}
    # files that may link to moved docs
    targets = set(moves.values()) | {f"{PLANS}/{n}" for n in os.listdir(ROOT / PLANS) if n.endswith(".md")}
    targets |= {"literature/CITATIONS.md", "notebooks/wellsight_v2/s3_train/_save_cv_split_manifests_9t.py",
                "STRUCTURE.md"}
    changed = 0
    for rel in sorted(targets):
        p = ROOT / rel
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        here = p.parent

        def fix(mt):
            href, frag = mt.group(1), mt.group(2) or ""
            if href.startswith(("http", "mailto:")):
                return mt.group(0)
            # resolve against the file's ORIGINAL directory
            orig = next((o for o, n in moves.items() if n == rel), rel)
            src = (ROOT / orig).parent / href
            try:
                key = src.resolve().relative_to(ROOT.resolve()).as_posix()
            except ValueError:
                return mt.group(0)
            dest = moves.get(key)
            if dest is None:
                if (ROOT / key).exists():
                    dest = key
                elif Path(href).name in by_name:
                    dest = by_name[Path(href).name]
                else:
                    return mt.group(0)
            new = os.path.relpath(ROOT / dest, here).replace("\\", "/")
            return f"]({new}{frag})"

        out = LINK.sub(fix, txt)
        # plain repo-relative mentions in code spans and prose
        for o, n in moves.items():
            out = out.replace(o, n)
        if out != txt:
            p.write_text(out, encoding="utf-8")
            changed += 1
    print(f"links rewritten in {changed} files")


if __name__ == "__main__":
    {"ledger": ledger, "scaffold": scaffold, "links": links}[sys.argv[1]]()

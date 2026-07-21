# WellSight Control Panel (Phase 1)

A local browser app to run the project's pipeline scripts by picking options,
instead of running them by hand. Built per `docs/ui/UI_PLAN.md`.

## Launch

Double-click **`wellsight_ui.bat`** (repo root), or:

```bash
python -m streamlit run ui/app.py
```

A tab opens at <http://localhost:8501>. Left nav: **Dashboard · Roads ·
Analysis · Jobs**. The window must stay open to *watch* progress — but jobs run
as detached subprocesses and keep going (and survive a UI restart, which
re-attaches to them).

## What Phase 1 does

- **Roads**: run road inference on any block with any trained checkpoint
  (recall / corrected / sweep variants); train a sweep variant; aggregate the
  sweep leaderboard; build orientation labels.
- **Analysis** (CPU, safe during GPU training): well provenance flags, well-age
  morphology, pad morphology bins, photo-source locations.
- **Jobs**: queue table, live log tail with an epoch progress bar, cancel,
  per-job command + git commit provenance.

GPU jobs run one at a time (8 GB card); CPU jobs run up to 2 in parallel.
Inference writes to `data/derivatives/experiments/ui_infer/<block>/<model>/` and
never overwrites deployed block rasters. Every output panel shows its path for
drag-into-QGIS.

## How it's wired

- `registry.py` — the task catalog; each entry maps form widgets to a CLI. Add a
  script to the UI in ~10 lines here.
- `jobs.py` — JobManager: spawn/queue/cancel subprocesses, log files,
  jobs.jsonl ledger, restart re-attach.
- `paths.py` — wraps `_common.py` so UI and scripts share one truth for paths.
- `pages/` — Streamlit pages, auto-generated forms via `widgets.render_task`.

Transient state (`runs/`, `jobs.jsonl`, `settings.json`) is gitignored.

## Not yet built (later phases — see the plan)

Pits/Pads tabs, Data Builder, Pipelines, Reports, Models family tree,
deploy/rollback manager, dependency-staleness DAG, training forms with channel
masks, ETA priors. Phase 1 is the runnable core.

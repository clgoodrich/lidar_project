# WellSight Documentation

Durable, prose record of everything done in this project. If a piece of work matters, it should land here as readable English — not buried in commit messages, code comments, or chat logs that disappear.

This file is the index. Start here.

## Where things live

```
docs/
├── README.md                            ← you are here
├── iterations/                          ← model iteration write-ups
│   ├── README.md                        ← iterations index + methodology
│   ├── LEADERBOARD.md                   ← live test-set comparison table
│   ├── iter_01_tta_miou.md
│   ├── iter_02_smp_pretrained.md
│   └── iter_03_multiscale_feats.md
├── pipelines/                           ← data + feature pipelines
│   ├── annotations.md                   ← shapefile → reprojected GeoPackage
│   ├── pit_dataset.md                   ← polygons → label rasters + splits
│   └── feature_stack.md                 ← terrain rasters → 7- and 11-band input
├── articles/                            ← outside-paper summaries (lab notebook)
│   ├── ramachandran_explained.md
│   ├── barlow_dissertation_explained.md
│   └── kang_2014_explained.md
└── handoff/                             ← machine-to-machine handoff notes
    └── RAMACHANDRAN_LAPTOP_RESUME.md
```

## Quick links

- **Want the latest pit-model numbers?** → [LEADERBOARD](iterations/LEADERBOARD.md)
- **Want to start a new pit iteration?** → [iterations/README — How to add an iteration](iterations/README.md#how-to-add-an-iteration)
- **Want to understand the train/val/test discipline?** → [pit_dataset.md](pipelines/pit_dataset.md)
- **Want to add a new input channel to the feature stack?** → [feature_stack.md — How to add a new channel](pipelines/feature_stack.md#how-to-add-a-new-channel)
- **Want to understand what a paper actually says?** → `docs/articles/`

## Documentation policy

Every meaningful piece of work in this project must be documented as durable prose — not just code + commit messages. See the **Extensive documentation (mandatory)** section in `CLAUDE.md`. In short:

1. Every iteration gets a write-up under `docs/iterations/iter_XX_<name>.md`.
2. The [LEADERBOARD](iterations/LEADERBOARD.md) is updated each iteration. Always show all prior iterations.
3. Every new data pipeline, feature-build, or annotation-prep workflow gets a doc under `docs/pipelines/`.
4. Decision logs: when a non-trivial choice is made, the *reasoning* is recorded — not just the outcome.
5. Honest tradeoffs: if an iteration regressed on something, the doc says so explicitly. No celebrating wins while hiding losses.

If you are reading this six months from now and the docs are out of date or missing, the discipline broke down. Fix it before adding new iterations.

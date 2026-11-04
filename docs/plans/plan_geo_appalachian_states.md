# 3.2 Ohio, West Virginia, New York, Kentucky

**Problem.** Other Appalachian oil states have orphaned wells in similar terrain. Their records, status definitions and lidar differ. It is unknown how much of the model carries over.

**Why it matters.** It shows how far the approach reaches and which state programs could use it.

**Evidence level produced.** (a) per county. Treat results as case studies. One county per state cannot separate a state effect from county differences.

**Inputs.** State well inventories and lidar programs. Coverage and access are **unverified** for each state.

**Architecture.**
1. `docs/iterations/state_data_inventory.md`. One table row per state with record source, status definitions, coordinate method, lidar program, acquisition dates, access route.
2. One county per state, chosen by data availability and well density, recorded in a prereg per county.
3. Reuse plan 3.0 scripts per county.
4. `data/<county>/results/transfer/` for outputs.

**Method outline.** Harmonise status labels into one table before comparison. Record survey dates and coordinate accuracy. Keep eligibility rules identical across counties.

**Acceptance test.** A harmonised status table exists. Each county has a committed prereg before scoring.

**Risks and unknowns.** Record schemas differ. Some inventories may be restricted. Lidar leaf-off timing varies.

**Depends on.** 3.0, 3.1.

**Executor notes.** One county at a time. Do not pool counties into one statistic.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Desk inventory table only (record source, status definitions, coordinate method, lidar program, dates, access). One county per state cannot separate state from county effects, so report case studies, never a between-state variance.

**Downloads and requests.** D14 gated on the inventory.

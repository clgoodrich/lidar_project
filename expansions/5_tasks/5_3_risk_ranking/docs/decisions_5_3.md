# 5.3 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Build outputs stay inside `expansions/5_tasks/5_3_risk_ranking/` instead of `data/9t/results/risk/`. Made by the build agent, change freely.
- 2026-11-05. Sites are DEP records in the 9t bbox minus "Operator Reported Not Drilled" and "Proposed But Never Materialized", plus 5.6 S0 candidates. Made by the build agent, change freely.
- 2026-11-05. A candidate that is the nearest within 50 m of a record merges into that record site as surface evidence. It is a proposed association. Made by the build agent, change freely.
- 2026-11-05. P for candidates is the K-rank tercile band (K1, K2, K3, below_K) at K = 40 per km2 of the 115 pit blocks. Band values 0.75, 0.5, 0.25, 0 are ordinal codes, not probabilities. Made by the build agent, change freely.
- 2026-11-05. A missing assumed receptor layer is skipped and listed in `missing_components`. `--strict` fails instead. Made by the build agent, change freely.
- 2026-11-05. TIGER roads enter E as a human-presence and access proxy (count within 100 m). Made by the build agent, change freely.
- 2026-11-05. H and E are means of percentile ranks of the components a site has. Missing components are skipped per site. Made by the build agent, change freely.
- 2026-11-05. Status scores are orphan or abandoned 3, plugged unverified 2, active 1, plugged 0, undocumented candidate 3. Age scores are pre-1956 3, sentinel 2, 1956 to 1984 2, 1985 on 1. Made by the build agent, change freely.
- 2026-11-05. Optional H columns enter only at 50% missing or less. Depth and formation are 100% missing on 9t, so they are dropped. Made by the build agent, change freely.
- 2026-11-05. Top N is min(50, 5% of eligible sites). It is 50 on 9t. Made by the build agent, change freely.
- 2026-11-05. The weighted-sum base is equal weights. The grid sweeps one weight while the other two share the rest equally. Dirichlet(1, 1, 1) with 2000 draws. Made by the build agent, change freely.
- 2026-11-05. Bootstrap jitter is isotropic normal with RMS radial error 30 m for records and 10 m for candidates. Both are assumptions to VERIFY. Made by the build agent, change freely.
- 2026-11-05. Bootstrap imputation stays inside one p_source group. A candidate's missing plugging record is structural and is not imputed. Made by the build agent, change freely.
- 2026-11-05. S6 enforces order with the prereg hash stamped by S3 and a ledger written the first time the endpoint is opened. Made by the build agent, change freely.
- 2026-11-05. The enrichment decision uses superiority on enrichment minus 1 against delta_enrich_gain. Made by the build agent, change freely.
- 2026-11-05. Primary scenario is A (exposure first) as a placeholder until the agency names one. Made by the build agent, change freely.

# 5.3 decisions

Newest first. One line per decision, with the date and who made it.

## Needs user decision

- Imputation rule for candidate H. A candidate has no plugging record by construction. Options are an imputed prior value declared in `index_missing.H.impute`, a coverage minimum below 1 in `index_missing.H.min_coverage`, or leaving candidates unrankable in H (today's default). Added 2026-11-06.
- Coverage minimum for E once more receptor layers arrive (`index_missing.E.min_coverage`, default 1.0). Added 2026-11-06.
- Whether a declared share of undefined bootstrap draws is acceptable for S6 enrichment (`max_undefined` in the preregistration, default 0). Added 2026-11-06.
- Detector coverage of the 29 zero-pit blocks of 9t. K now uses all 144 blocks (20.25 km2). Those 29 blocks have no out-of-fold detector output, so the area that K counts is larger than the area the detector scored. An out-of-fold prediction for them is needed upstream. Added 2026-11-06.

## Log

- 2026-11-06. Review fix 5.3-01. A missing H or E component is no longer skipped per site. The default rule `unrankable` gives a site no index when it lacks any component. `impute` needs a declared value per column. Both rules are stamped into the S2 and S3 summaries. Made by the review-fix agent.
- 2026-11-06. Review fix 5.3-02. E must have at least 2 components and top N + 1 distinct values. Otherwise E is NaN, and scenarios A and D are unrankable with the reason in `e_status`. A later key that is absent for every site is dropped, so B ranks by H alone and C by documented status alone. Made by the review-fix agent.
- 2026-11-06. Ties share a competition rank and are reported (`tie_<scenario>`, `scenario_report`). Row order never breaks a tie. A top-N set keeps every site tied at the cutoff. Made by the review-fix agent.
- 2026-11-06. rank01 uses mid-ranks, (rank - 0.5) / n. The lowest site no longer gets 0, which used to zero the scenario D product. Made by the review-fix agent.
- 2026-11-06. The weighted-sum variant no longer fills a missing component with 0. A site missing a component with nonzero weight is unrankable. Jaccard of two empty top sets is NaN, not 1. Made by the review-fix agent.
- 2026-11-06. Every candidate within 50 m of a record merges into its nearest record, not only each record's single nearest candidate. Records carry `n_assoc_cand`. Made by the review-fix agent.
- 2026-11-06. K uses every block of the grid (144 blocks, 20.25 km2, K = 810), not the 115 blocks with pits. Made by the review-fix agent.
- 2026-11-06. The endpoint rule reads `top_decile_fallback`. A rate cutoff of null falls back to the top decile when the flag is true and fails otherwise. S6 reports the undefined share of enrichment draws. Made by the review-fix agent.
- 2026-11-06. The S0 audit table writes repo-relative paths. Figures are saved through a temp file and a rename. Made by the review-fix agent.
- 2026-11-06. The 5.6 detector output is now read by column only. Its det_id is a seeded permutation, so 5.3 never relies on det_id order. Made by the review-fix agent.


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

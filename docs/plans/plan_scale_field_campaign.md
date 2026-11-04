# 7.5 Field campaign

**Problem.** Everything so far is lidar and records. Only field visits can say whether candidates are wells and whether the detector misses any.

**Why it matters.** It is the highest-value evidence and unlocks precision, recall, association and density work.

**Evidence level produced.** (d) confirmed well, plus (c) steel anomalies where magnetometry is used.

**Inputs.** A partner (agency or university), site access, instruments (4.1, 6.5), a sample frame of candidates.

**Architecture.**
1. `docs/iterations/field_campaign_design.md` defines the sampling plan. Strata by score and geography. Record inclusion probabilities and access failures. Blind assessors. Several evidence types.
2. `_field_sample_draw.py` draws the sample with a saved seed to `data/<area>/results/field/field_sample.csv`.
3. Data sheets and a field database schema.
4. Candidate sampling estimates precision. Independent searches of sampled areas are needed to estimate missed wells and recall.
5. Analysis plan with weighting, clustering, inaccessible sites and unresolved evidence.

**Method outline.** Size the primary estimate first. For n = 1.96 squared times 0.25 over d squared, about 43 sites gives plus or minus 15 points, 96 gives 10, and 24 gives 20, under simple random sampling per estimate. Forty total sites cannot give plus or minus 15 in each of five score bins.

**Acceptance test.** Design document approved by the partner and a drawn sample.

**Risks and unknowns.** Partner dependence. Access. Weather.

**Depends on.** Partner. P2 for a frozen sample frame.

**Executor notes.** Record every non-visit and why.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign, highest value.

- Three arms. (A) Probability sample of drawn features, to measure what share are wells. (B) Score-stratified sample of model candidates, for precision. (C) Probability-sampled areas searched independently, to bound missed wells.
- Outcomes. Confirmed, steel only, nothing found, unresolved, inaccessible. Report bounds with unresolved counted both ways. If search sensitivity cannot be bounded, report conditional recall only.
- Era strata for magnetometry. Wooden or removed casing is invisible.
- Sample sizes of 43, 96 and 24 sites per estimate give plus or minus 15, 10 and 20 points under simple random sampling. Forty sites in total cannot support five score bins.

**Downloads and requests.** R3, R4.

## Review revision 2 (third review, 2026-11-04)
Identity status is separate from outcome. Lower bound is confirmed-well weight over total sampled weight. Upper bound is one minus definite-non-well weight over total. Ambiguous and inaccessible sites sit in the gap. Use inference suited to a weighted, clustered sample.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

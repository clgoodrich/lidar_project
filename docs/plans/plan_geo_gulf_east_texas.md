# 3.4 Gulf Coast and East Texas

**Problem.** Wetland, vegetation and ground-return conditions differ. Lidar may have poor ground coverage under dense or flooded cover.

**Why it matters.** Texas has a documented orphan well layer, the Railroad Commission layer 2. It is a source of confirmed locations.

**Evidence level produced.** (a) and (d) where RRC records give confirmed locations. Association is separate.

**Inputs.** RRC orphan layer (documented). Public lidar for chosen counties (**unverified**). Frozen checkpoints.

**Architecture.**
1. Measure ground-return density and void fraction per block into `data/<area>/results/transfer/ground_density_by_block.csv` before any scoring.
2. Zero-shot baseline with unchanged preprocessing, using plan 3.0.
3. Separate adaptation arm with relief-normalised channels, written as its own experiment.
4. Stratify results by wetland and by void fraction.
5. An exclusion arm for wetland blocks is reported as a different target population.

**Method outline.** Keep the unchanged baseline in every table. Do not mix arms.

**Acceptance test.** Baseline and adaptation arm both reported with block-bootstrap intervals and stratum tables.

**Risks and unknowns.** Only about 35% of RRC orphans sit within 100 m of an optical pad detection in earlier work, so records and visible features agree weakly.

**Depends on.** 3.0.

**Executor notes.** Measure density first. Do not infer from file size.

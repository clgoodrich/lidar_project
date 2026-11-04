# 5.2 Era classification

**Problem.** Wells from different eras leave different surface marks. A classifier that estimates era from morphology could help date features and prioritise.

**Why it matters.** Older wells are more likely to be undocumented. Era would sharpen risk ranking.

**Evidence level produced.** (a) with era as an attribute.

**Inputs.** Dated wells from the DEP export. An earlier note found a weak era signal in morphology and no dated well before 1956. Valid dates are the limit.

**Architecture.**
1. `docs/iterations/era_label_audit.md` lists which wells have trustworthy dates. About 92% of the DEP orphan-list spud dates are the 1800 sentinel, so they are not usable.
2. Historical maps give an upper bound on construction date. Absence on a map is censored, not evidence of later construction. Record map coverage and visibility.
3. `_era_model.py` fits an ordinal or interval-censored model on morphology features. Output `data/9t/results/era/era_predictions_9t.csv`.

**Method outline.** Treat dates as bounds. Use censored methods. Report ordinal accuracy only on dated wells.

**Acceptance test.** Accuracy and calibration on dated held-out wells with intervals.

**Risks and unknowns.** Few valid dates. Deferred until dates are valid.

**Depends on.** 4.6 for historic bounds.

**Executor notes.** Do not treat missing historical presence as proof of a later date.

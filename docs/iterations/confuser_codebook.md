# Confuser codebook (A1)

**Purpose.** Label detections that the model scores high but that may not be well features. The output feeds negative classes for retraining. Unmatched is not negative. A detection with no drawn feature may be a real undocumented well.

## Classes
| Code | Class | Rule of thumb |
|---|---|---|
| P | Well pit or pad (feature) | Circular or rectangular depression or level clearing, with an access trace, in a plausible oil-field setting |
| C | Charcoal hearth or mill platform | Round, flat, 8 to 15 m, no depression, no access trace to a pad group |
| Q | Quarry or borrow pit | Larger, angular, with spoil bank |
| K | Coal or mine feature | Portal, subsidence, spoil. Check mine inventory |
| R | Road cut, landing or log deck | Linear or one-sided, tied to a road |
| H | Hydrology | Beaver pond, stream meander, sink along a channel |
| B | Building or foundation | Rectilinear, small, near a road or driveway |
| X | Other known cause | Name it in the notes |
| U | Uncertain | Use freely. Never force a class |

## Procedure
1. Sample from detections at the frozen cutoff, stratified by score band. Record inclusion probabilities.
2. Each reviewer sees a neutral contact sheet. Hillshade, slope, local relief, and an aerial chip when one exists. No model score, no well record, no class from the other reviewer.
3. Each reviewer assigns one code and one confidence (high, medium, low).
4. Disagreements go to adjudication by a third look. Kept as U if still unresolved.
5. A frozen audit subset is set aside before any error mining. It is never used for training or selection.

## Budget
About 2 hours per 20 candidates per reviewer, not including adjudication. 150 candidates with two reviewers is about 30 hours of review in total.

## Reporting
- Counts by class and score band, with population weights.
- Agreement as raw percent and kappa. Kappa is not the acceptance criterion.
- Retrain acceptance rule. Confuser false positives fall and recall on drawn features drops by no more than the margin set in the preregistration.
- One failed retrain does not retire the idea.

## Outputs
- `data/9t/results/confusers/confuser_sample_9t.csv` (sampled candidates, score band, inclusion probability)
- `data/9t/results/confusers/confuser_labels_9t.csv` (one row per reviewer per candidate)
- Contact sheets in `data/9t/results/confusers/sheets/`

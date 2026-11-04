# Warren County transfer pre-registration (draft, A7)

**Status:** draft. Fill the bracketed fields and commit before looking at any Warren output. Follows `transfer_prereg_template.md`.

## 1. Question
Does the tile 9t pit and pad model keep its ranking and recall at fixed K in Warren County, a neighbouring county with different lidar.

## 2. Population and unit
- Target. Pits and pads, scored separately.
- Unit. One detection per pit.
- Scored footprint. [Complete evaluation blocks chosen before any scores are viewed. Path.]
- Edge rule. Blocks touching the area edge are dropped for both observed and null data.

## 3. Data
- Lidar. Seven Warren LAZ files are on disk. Their paths, acquisition dates and measured ground density go here before scoring. [Fill.]
- Forest County readiness is not verified. It is out of scope until measured.
- Labels. Drawn features by [annotators] on the adaptation and test areas. Evidence level (a). Agency records are a separate association analysis.
- Hashes of the checkpoint (`data/9t/models/pit/unet_cv5`, `pad` equivalents) and every input, recorded in `data/warren/results/_PROVENANCE.json`.

## 4. Frozen
Weights, preprocessing, proposal extraction and cutoff. The cutoffs are those fixed on 9t cross-validation. No retuning on the test area.

## 5. Areas
- Adaptation area. [Blocks.] Used only for calibration.
- Test area. [Blocks.] At least 500 m from the adaptation area.
- Audit blocks. [Blocks.] Excluded from every later training step.

## 6. Primary analysis
- Metric. Recall at fixed K, K equal to the number of annotated features in the scored footprint.
- Reference from 9t. Held-out recall 0.928 (F2 cutoff). The 613590 transfer gave 0.911 on 153 annotated floors.
- Uncertainty. Block bootstrap, 2,000 resamples, seed 20261104.
- Calibration reported separately by Brier score, log loss and calibration error. Platt scaling does not change recall at fixed K.

## 7. Decision rule
- Non-inferiority margin on the recall difference against 9t. [Set before scoring, e.g. 0.10.]
- Met when the lower bound of the 95% interval for the difference is above minus the margin.
- If met, proceed to adaptation-area calibration and Phase B. If not met, keep the result, run the error review, and do not claim transfer.
- If the test area has too few features for the interval to be narrower than the margin, report inconclusive.

## 8. Reporting
Detection of terrain features and association with agency records are reported separately. Precision of wells is not claimed from lidar interpretation alone.

## 9. Amendments
[None yet.]

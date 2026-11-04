# 4.6 Historic maps and aerials

**Problem.** Old maps and aerial photos may show wells or derricks that no record lists. Whether they are usable here is unknown.

**Why it matters.** They give evidence level (b) independent of lidar and could supply labels that the lidar model misses.

**Evidence level produced.** (b) historical evidence.

**Inputs.** USGS historic topographic sheets (31 sheets cover tile 9t, 1922 to 1967, **listing verified, content not**). Aerial archives (USGS EarthExplorer, Penn State historical aerials). State oil-field maps (**unverified**). One earlier look at one 1922 sheet showed no well symbols in the mapped part, so topo sheets look low-yield.

**Architecture.**
1. `docs/iterations/historic_imagery_probe_9t.md` records, per source, scale, date, georeferencing method and a verdict of usable here, unusable here or inconclusive.
2. Probe design. Several dates and scales. Use known well locations as positive checks. Use independent check points to measure georeferencing error.
3. If usable, `_historic_label_extract.py` digitises symbols into `data/9t/results/historic/historic_well_marks_9t.gpkg` with a source, date and positional accuracy column.
4. Historical positives are kept even when lidar scores are low.

**Method outline.** An index entry does not guarantee a usable scan. One failed frame cannot establish general unavailability.

**Acceptance test.** A probe table covering several sources and dates with a verdict for each.

**Risks and unknowns.** Georeferencing quality. Symbol ambiguity.

**Depends on.** None.

**Executor notes.** Judge labels by interpretability and positional accuracy, not by agreement with the model.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Proceed as a probe, elevated.

- It is the only plausible independent evidence for pre-1880 wells, the stratum magnetometry misses.
- The probed 1922 sheet showed no well symbols. Probe higher-yield sources first. 1870s and 1880s oil-region maps, 1860s atlases and 1937 to 1942 aerials. Their existence over 9t is unverified.
- Each source gets a verdict. Usable here, unusable here or inconclusive. Test several dates.
- The null is the shifted-set null inside the oil field. Radius from measured georeferencing RMSE on independent check points.
- Keep historical positives when the lidar score is low.

**Downloads and requests.** D5, D6 (search), D7 (index), then D8 and D9.

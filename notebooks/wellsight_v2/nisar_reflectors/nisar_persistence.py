"""Stage 4: short-record stability with visible support and sensitivity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .nisar_contracts import Artifact, EvidenceTable, Metric
from .nisar_measurements import MeasurementResult
from .nisar_provenance import Manifest
from .nisar_quality import QualityReport


@dataclass(frozen=True)
class PersistenceSummary:
    run_id: str
    seed_id: str
    track: int
    polarization: str
    cohort_id: str
    scheduled_acquisition_ids: tuple[str, ...]
    used_acquisition_ids: tuple[str, ...]
    metrics: tuple[Metric, ...]
    # LOO ranges, date splits, and processing-cohort comparisons are recorded
    # separately from genuine confidence intervals.
    sensitivity: tuple[Metric, ...]
    phase_model: Artifact | None
    limitations: tuple[str, ...]


class PersistenceEstimator(Protocol):
    def summarize(
        self, manifest: Manifest, quality: QualityReport,
        measurements: MeasurementResult, persistence_policy: Artifact,
    ) -> EvidenceTable:
        """Return per-seed/track/polarization/cohort summaries and support IDs.

        Specify dispersion convention, handle missing dates, retain LOO ranges,
        and check calibration cohorts. Phase requires a passed QC capability
        and an explicit phase model/reference; no raw temporal phase averaging.
        This stage does not return a probability of steel.
        """
        ...

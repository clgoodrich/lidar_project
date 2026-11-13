"""Stage 3: native-chip measurements, retaining complex source evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .nisar_contracts import Artifact, EvidenceTable, Metric, Position
from .nisar_provenance import Manifest
from .nisar_quality import QualityReport


@dataclass(frozen=True)
class TargetMeasurement:
    run_id: str
    seed_id: str
    acquisition_id: str
    track: int
    polarization: str
    position: Position
    native_range_sample: float | None
    native_azimuth_sample: float | None
    valid: bool
    exclusion_reason: str | None
    # Named metrics: peak_power, aperture_power, background_power, contrast_db,
    # excess_energy, range/azimuth_width, PSLR, ISLR; RCS only if QC permits.
    metrics: tuple[Metric, ...]
    chip: Artifact
    aperture_and_background_masks: Artifact
    flags: tuple[str, ...]


@dataclass(frozen=True)
class MeasurementResult:
    run_id: str
    measurements: EvidenceTable
    # Includes all proposed seeds and explicit reasons for rejecting any seed.
    seed_ledger: EvidenceTable
    footprint_table: EvidenceTable


class ChipMeasurer(Protocol):
    def measure(
        self, manifest: Manifest, quality: QualityReport,
        seeds: EvidenceTable, measurement_policy: Artifact,
    ) -> MeasurementResult:
        """Fit/measure HH and HV using explicit native validity and PSF support.

        Preserve source chips and aperture definitions. Missing values are not
        zeros. Never combine extrema from different pixels into one target row.
        A policy identifies proposal/discovery dates to expose selection bias.
        """
        ...

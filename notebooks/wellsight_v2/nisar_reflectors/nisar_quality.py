"""Stage 2: measurement evidence and claim-specific gates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .nisar_contracts import Artifact, Capability, EvidenceTable, Metric
from .nisar_provenance import Manifest


@dataclass(frozen=True)
class QualityCheck:
    check_id: str
    acquisition_ids: tuple[str, ...]
    status: Literal["pass", "fail", "unknown"]
    metrics: tuple[Metric, ...]
    evidence: tuple[Artifact, ...]
    reason: str


@dataclass(frozen=True)
class CapabilityDecision:
    capability: Capability
    acquisition_ids: tuple[str, ...]
    allowed: bool
    required_check_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class QualityReport:
    run_id: str
    checks: tuple[QualityCheck, ...]
    decisions: tuple[CapabilityDecision, ...]
    spatial_residuals: EvidenceTable
    diagnostic_chips: tuple[Artifact, ...]


class MeasurementVerifier(Protocol):
    def verify(
        self, manifest: Manifest, independent_targets: EvidenceTable,
        acceptance_policy: Artifact,
    ) -> QualityReport:
        """Validate geometry, support, calibration and point impulse responses.

        Keep internal registration and independent absolute errors separate.
        Unknown required checks block their capability. Tolerances and reference
        target uncertainty come from the policy, not hidden hard-coded defaults.
        """
        ...

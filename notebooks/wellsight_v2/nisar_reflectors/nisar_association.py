"""Stage 5: uncertainty-aware object matching and separate arrangement analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .nisar_contracts import Artifact, EvidenceTable, Metric
from .nisar_measurements import MeasurementResult
from .nisar_provenance import Manifest
from .nisar_quality import QualityReport


@dataclass(frozen=True)
class AssociationEdge:
    left_seed_id: str
    right_seed_id: str
    status: Literal["accepted", "rejected", "ambiguous"]
    metrics: tuple[Metric, ...]
    assumed_height_interval_m: tuple[float, float] | None
    height_datum: str | None
    reason: str


@dataclass(frozen=True)
class AssociationResult:
    run_id: str
    edges: EvidenceTable
    members: EvidenceTable
    groups: EvidenceTable
    unmatched: EvidenceTable
    arrangements: EvidenceTable


class TrackAssociator(Protocol):
    def associate(
        self, manifest: Manifest, quality: QualityReport,
        measurements: MeasurementResult, persistence: EvidenceTable,
        association_policy: Artifact,
    ) -> AssociationResult:
        """Match with explicit CRS/epoch, LOS, height and error assumptions.

        At most one seed per track in each object; require pairwise compatibility,
        preserve ambiguous alternatives and prevent transitive distance chaining.
        Describe multi-object arrangements separately. Do not collapse nearby
        same-track returns without an impulse-response/sidelobe assessment.
        """
        ...

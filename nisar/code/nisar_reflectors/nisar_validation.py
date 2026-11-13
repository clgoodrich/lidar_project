"""Stage 6: independent equipment validation and matched well association."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .nisar_association import AssociationResult
from .nisar_contracts import Artifact, EvidenceTable, Metric, Position
from .nisar_provenance import Manifest
from .nisar_quality import QualityReport


@dataclass(frozen=True)
class ReferenceTarget:
    reference_id: str
    position: Position
    observed_utc: str
    equipment_presence: Literal["present", "absent", "unknown"]
    material: str | None
    equipment_class: str | None
    source: Artifact
    spatial_block_id: str
    split: Literal["development", "validation", "heldout"]
    dep_status: str | None


@dataclass(frozen=True)
class ValidationResult:
    run_id: str
    endpoint: Literal["equipment_detection", "well_association"]
    metrics: tuple[Metric, ...]
    uncertainty: tuple[Metric, ...]
    match_ledger: EvidenceTable
    exclusions: EvidenceTable
    split_table: EvidenceTable
    limitations: tuple[str, ...]


class ReflectorValidator(Protocol):
    def evaluate_equipment(
        self, manifest: Manifest, quality: QualityReport,
        targets: AssociationResult, reference_targets: EvidenceTable,
        evaluation_policy: Artifact,
    ) -> ValidationResult:
        """Use independent held-out truth, one-to-one matches and shared support.

        Report unknown labels, reviewed detections and sampled nondetections;
        account for review sampling weights and spatially dependent uncertainty.
        """
        ...

    def evaluate_well_association(
        self, manifest: Manifest, quality: QualityReport,
        targets: AssociationResult, wells: EvidenceTable,
        matched_controls: EvidenceTable, evaluation_policy: Artifact,
    ) -> ValidationResult:
        """Preserve matched sets, opportunity masks, spatial blocks and exclusions.

        Export all controls and their selection probabilities. No pooling of
        unequal sets as independent replicates; no equipment labels from status.
        """
        ...

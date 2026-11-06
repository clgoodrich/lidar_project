"""Stage 1: explicit selection, lineage and immutable run identity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .nisar_contracts import Artifact, EvidenceTable, StackState


@dataclass(frozen=True)
class Acquisition:
    acquisition_id: str
    product_id: str
    product_version: str
    collection: str
    acquired_utc: str
    track: int
    frame: int
    direction: Literal["A", "D"]
    frequency: str
    polarizations: tuple[str, ...]
    raster: Artifact
    # Include native RSLC, orbit, calibration, noise and source validity assets
    # when available. Missing dependencies must also appear in the QC report.
    dependencies: tuple[Artifact, ...]
    metadata: Artifact
    included: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class Manifest:
    schema_version: str
    run_id: str
    area: str
    stack_state: StackState
    acquisitions: tuple[Acquisition, ...]
    config: Artifact
    code_snapshot: tuple[Artifact, ...]
    # DEM, geoid, date/track offsets and transform/epoch specification.
    geometry_dependencies: tuple[Artifact, ...]
    selection_ledger: EvidenceTable


@dataclass(frozen=True)
class FreezeRequest:
    area: str
    stack_state: StackState
    index_paths: tuple[str, ...]
    selection_config_path: str
    geometry_paths: tuple[str, ...]
    source_code_paths: tuple[str, ...]
    output_root: str


class ManifestBuilder(Protocol):
    def freeze(self, request: FreezeRequest) -> Manifest:
        """Resolve and hash inputs, validate lineage, persist to a new run folder.

        Reject incomplete identity and overwrite. Never discover stack state
        from global argv/environment. Persist explicit exclusion reasons.
        """
        ...

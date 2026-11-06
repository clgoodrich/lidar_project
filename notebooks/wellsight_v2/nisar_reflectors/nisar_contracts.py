"""Shared immutable records; backends must supply runtime validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StackState = Literal["gslc", "lidar_placed", "date_coreg", "absolute_coreg"]
Capability = Literal[
    "relative_contrast", "cross_date_amplitude", "absolute_location",
    "calibrated_rcs", "phase_analysis",
]


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    path: str
    sha256: str
    role: str


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None
    unit: str
    method: str
    # Unknown, censored, and failed estimates must have an explanatory flag.
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Position:
    x_m: float
    y_m: float
    crs: str
    coordinate_epoch: float | None
    # Covariance is in projected metres squared; None means unknown.
    covariance_xx_xy_yy: tuple[float, float, float] | None
    height_m: float | None
    height_datum: str | None


@dataclass(frozen=True)
class EvidenceTable:
    """Reference to a future persisted table, never an implicit in-memory result.

    Field names describe its schema; readers must validate types, units, foreign
    keys and uniqueness against the versioned schema before consuming the table.
    """

    artifact: Artifact
    schema_version: str
    primary_key: tuple[str, ...]
    fields: tuple[str, ...]
    row_count: int

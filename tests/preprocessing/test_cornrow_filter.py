"""Unit tests for ``notebooks.wellsight.preprocessing.cornrow_filter``.

Most tests use a small synthetic LAZ fixture built once per session by
``cornrow_fixture_laz``. The fixture is deterministic: 100 points laid out
on a regular grid, with controlled values for ``scan_angle_rank`` and the
``Withheld`` flag, so the expected post-filter counts are exact.

Tests that actually exercise the PDAL CLI are skipped automatically if the
``pdal`` binary is not on PATH; the input-validation and mocked-failure
tests do not require PDAL.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# Import path is bootstrapped by tests/conftest.py.
from notebooks.wellsight.preprocessing.cornrow_filter import (
    filter_cornrow_artifacts,
)

PDAL_AVAILABLE = shutil.which("pdal") is not None
needs_pdal = pytest.mark.skipif(
    not PDAL_AVAILABLE, reason="PDAL CLI not on PATH"
)

# Fixture composition:
#   - 60 points at scan_angle_rank=0  (nadir, kept by any sane limit)
#   - 20 points at scan_angle_rank=25 (swath-edge, dropped at limit<25)
#   - 20 points at scan_angle_rank=5, Withheld=1 (dropped when withheld is on)
N_NADIR = 60
N_EDGE = 20
N_WITHHELD = 20
N_TOTAL = N_NADIR + N_EDGE + N_WITHHELD  # 100


@pytest.fixture(scope="session")
def cornrow_fixture_laz(tmp_path_factory) -> Path:
    """Build a deterministic synthetic LAZ for filter tests."""
    import laspy

    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    # Stored as .las (uncompressed) so the fixture builds without a LAZ
    # backend; PDAL reads either format identically.
    out = fixture_dir / "cornrow_test_tile.las"

    # Use LAS 1.2 PF1 — native int8 scan_angle_rank in raw degrees, simpler
    # than PF6's int16*0.006 scaling. PDAL exposes ScanAngleRank identically
    # on both, so the filter logic is unchanged.
    header = laspy.LasHeader(version="1.2", point_format=1)
    header.scales = np.array([0.01, 0.01, 0.01])
    header.offsets = np.array([0.0, 0.0, 0.0])

    las = laspy.LasData(header)
    # 100 points on a 10x10 grid in the unit square, z=0.
    xs, ys = np.meshgrid(np.arange(10), np.arange(10))
    las.x = xs.ravel().astype(np.float64)
    las.y = ys.ravel().astype(np.float64)
    las.z = np.zeros(N_TOTAL, dtype=np.float64)
    las.classification = np.full(N_TOTAL, 2, dtype=np.uint8)  # ground

    sar = np.zeros(N_TOTAL, dtype=np.int8)
    sar[N_NADIR:N_NADIR + N_EDGE] = 25            # edge
    sar[N_NADIR + N_EDGE:] = 5                    # near-nadir but withheld
    las.scan_angle_rank = sar

    wh = np.zeros(N_TOTAL, dtype=bool)
    wh[N_NADIR + N_EDGE:] = True                  # last 20 withheld
    las.withheld = wh

    las.write(str(out))
    return out


@pytest.fixture
def tmp_output(tmp_path) -> Path:
    return tmp_path / "filtered.laz"


# ---------------------------------------------------------------------------
# Input validation (no PDAL required)
# ---------------------------------------------------------------------------


def test_input_validation_missing_file(tmp_path):
    out = tmp_path / "out.laz"
    with pytest.raises(FileNotFoundError, match="not found"):
        filter_cornrow_artifacts(tmp_path / "does_not_exist.laz", out)


@pytest.mark.parametrize("bad_value", [0, -5, 100, "fifteen", 15.5, True])
def test_input_validation_invalid_scan_angle(
    cornrow_fixture_laz, tmp_output, bad_value
):
    with pytest.raises(ValueError, match="scan_angle_limit"):
        filter_cornrow_artifacts(
            cornrow_fixture_laz, tmp_output, scan_angle_limit=bad_value
        )


# ---------------------------------------------------------------------------
# Filter semantics (require PDAL)
# ---------------------------------------------------------------------------


@needs_pdal
def test_filter_retains_nadir_points(cornrow_fixture_laz, tmp_output):
    """Points with |scan_angle_rank| <= limit and Withheld=0 must survive."""
    stats = filter_cornrow_artifacts(
        cornrow_fixture_laz, tmp_output, scan_angle_limit=15
    )
    # Expected survivors: the 60 nadir points only.
    # (Edge points fail the angle gate; withheld points fail the withheld gate.)
    assert stats["output_points"] == N_NADIR


@needs_pdal
def test_filter_drops_swath_edge_points(cornrow_fixture_laz, tmp_output):
    """Points with |scan_angle_rank| > limit must be dropped."""
    # Disable the withheld filter to isolate the scan-angle behavior.
    stats = filter_cornrow_artifacts(
        cornrow_fixture_laz, tmp_output,
        scan_angle_limit=15, drop_withheld=False,
    )
    # Survivors: 60 nadir + 20 withheld-but-near-nadir = 80.
    assert stats["output_points"] == N_NADIR + N_WITHHELD
    assert stats["scan_angle_dropped"] == N_EDGE


@needs_pdal
def test_filter_drops_withheld_points(cornrow_fixture_laz, tmp_output):
    """Points with Withheld=1 must be dropped when drop_withheld=True."""
    # Use a permissive angle so the only filter exercised is Withheld.
    stats = filter_cornrow_artifacts(
        cornrow_fixture_laz, tmp_output,
        scan_angle_limit=30, drop_withheld=True,
    )
    # Survivors: 60 nadir + 20 edge = 80 (the 20 withheld are dropped).
    assert stats["output_points"] == N_NADIR + N_EDGE
    assert stats["withheld_dropped"] == N_WITHHELD


@needs_pdal
def test_return_dict_structure(cornrow_fixture_laz, tmp_output):
    stats = filter_cornrow_artifacts(
        cornrow_fixture_laz, tmp_output, scan_angle_limit=15
    )
    expected_keys = {
        "input_points", "output_points", "withheld_dropped",
        "scan_angle_dropped", "retention_pct", "scan_angle_limit_deg",
        "input_path", "output_path",
    }
    assert set(stats.keys()) == expected_keys
    assert isinstance(stats["input_points"], int)
    assert isinstance(stats["output_points"], int)
    assert isinstance(stats["withheld_dropped"], int)
    assert isinstance(stats["scan_angle_dropped"], int)
    assert isinstance(stats["retention_pct"], float)
    assert isinstance(stats["scan_angle_limit_deg"], int)
    assert isinstance(stats["input_path"], str)
    assert isinstance(stats["output_path"], str)
    assert stats["input_points"] == N_TOTAL
    assert 0.0 <= stats["retention_pct"] <= 100.0
    assert stats["scan_angle_limit_deg"] == 15


# ---------------------------------------------------------------------------
# PDAL failure path (mocked — no PDAL required)
# ---------------------------------------------------------------------------


def test_pdal_failure_raises_runtimeerror(cornrow_fixture_laz, tmp_output):
    """Non-zero PDAL exit must surface as RuntimeError carrying stderr."""
    fake_stderr = "PDAL stderr: synthetic failure for test"

    class FakeCompleted:
        def __init__(self):
            self.returncode = 1
            self.stderr = fake_stderr
            self.stdout = ""

    with patch(
        "notebooks.wellsight.preprocessing.cornrow_filter.subprocess.run",
        return_value=FakeCompleted(),
    ):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            filter_cornrow_artifacts(
                cornrow_fixture_laz, tmp_output, scan_angle_limit=15
            )

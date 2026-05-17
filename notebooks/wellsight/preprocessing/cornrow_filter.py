"""Tier-1 scan-geometry filter for WellSight LiDAR tiles.

Removes provider-flagged Withheld points and swath-edge points beyond a
caller-specified absolute scan-angle limit, mitigating the cornrow / corduroy
artifact pattern visible in low-relief terrain derivatives. See
``docs/preprocessing/cornrow_mitigation_spec.md`` for full rationale.

PDAL is invoked via the established WellSight subprocess-pipeline pattern
(JSON pipeline written to a temp file, ``pdal pipeline`` executed via
``subprocess.run``). PDAL Python bindings are intentionally not used.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

logger = logging.getLogger(__name__)


def _pdal_binary() -> str:
    """Return the PDAL CLI binary path, falling back to the literal name."""
    return shutil.which("pdal") or "pdal"


def filter_cornrow_artifacts(
    input_path: PathLike,
    output_path: PathLike,
    scan_angle_limit: int = 15,
    drop_withheld: bool = True,
    verbose: bool = True,
    timeout: int = 3600,
) -> dict:
    """Drop swath-edge and withheld points from a LAS/LAZ tile.

    The function applies two ``filters.range`` predicates in sequence via a
    single PDAL pipeline:

    1. ``Withheld[0:0]`` — drop any point whose ASPRS Withheld bit is set
       (optional, controlled by ``drop_withheld``).
    2. ``ScanAngleRank[-N:N]`` — drop points whose absolute scan angle (in
       degrees) exceeds ``scan_angle_limit``. PDAL exposes ``ScanAngleRank``
       as a degrees-valued dimension regardless of whether the source file is
       LAS 1.4 PF6+ (native int16 × 0.006°) or an older format storing raw
       degrees, side-stepping the unit-conversion landmine documented in
       ``docs/development_history.md`` §2.

    Args:
        input_path: Source LAS or LAZ file (must exist).
        output_path: Destination LAS or LAZ file. Parent directory must
            already exist. The file extension determines the writer format
            (``.laz`` → compressed, ``.las`` → uncompressed). LAS header,
            VLRs, and SRS are forwarded via PDAL's ``forward=all``.
        scan_angle_limit: Maximum allowed absolute scan angle in **degrees**.
            Must be an integer in ``[1, 30]``. Default 15 (see spec §4).
        drop_withheld: When True (default) the Withheld filter is included.
            When False, only the scan-angle filter is applied; this exists
            primarily for testing.
        verbose: When True (default), emit an INFO-level summary line on
            completion. Independent of the module logger configuration.
        timeout: PDAL subprocess timeout in seconds. Default 3600 (1 hour)
            covers a full ~85 M-point merged 9-tile mosaic on commodity
            hardware.

    Returns:
        A dictionary with keys:

        - ``input_points`` (int): point count read from the input header.
        - ``output_points`` (int): point count read from the output header.
        - ``withheld_dropped`` (int): count of points with Withheld=1 in the
          input (0 if ``drop_withheld=False``, since none were removed).
        - ``scan_angle_dropped`` (int): count of points with
          ``|ScanAngleRank| > scan_angle_limit`` in the input.
        - ``retention_pct`` (float): ``100 * output_points / input_points``.
        - ``scan_angle_limit_deg`` (int): the limit actually applied.
        - ``input_path`` (str): absolute path of the input file.
        - ``output_path`` (str): absolute path of the output file.

        Note: ``withheld_dropped`` and ``scan_angle_dropped`` are pre-filter
        counts on the input. They overlap (a point may be both withheld and
        beyond the angle limit), so summing them and subtracting from
        ``input_points`` will NOT in general equal ``output_points``.

    Raises:
        FileNotFoundError: ``input_path`` does not exist.
        ValueError: ``scan_angle_limit`` is not an int in ``[1, 30]``.
        RuntimeError: PDAL pipeline returned a non-zero exit code; the
            exception message contains the tail of PDAL's stderr.

    Example:
        >>> from notebooks.wellsight.preprocessing import filter_cornrow_artifacts
        >>> stats = filter_cornrow_artifacts(
        ...     "data/files/9t_merged.las",
        ...     "data/derivatives/9t_filtered.laz",
        ...     scan_angle_limit=15,
        ... )
        >>> print(f"Retained {stats['retention_pct']:.1f}% of points")
    """
    # ----- input validation ----------------------------------------------
    # Validate scan_angle_limit first so type errors surface before any I/O.
    # Reject booleans explicitly: bool is a subclass of int in Python, so a
    # caller passing `True` would otherwise sneak past the int() check as 1.
    if isinstance(scan_angle_limit, bool) or not isinstance(scan_angle_limit, int):
        raise ValueError(
            f"scan_angle_limit must be an integer in [1, 30], got "
            f"{type(scan_angle_limit).__name__}={scan_angle_limit!r}"
        )
    if not (1 <= scan_angle_limit <= 30):
        raise ValueError(
            f"scan_angle_limit must be an integer in [1, 30], got "
            f"{scan_angle_limit}"
        )

    in_path = Path(input_path)
    out_path = Path(output_path)

    if not in_path.exists():
        raise FileNotFoundError(f"Input LAS/LAZ not found: {in_path}")
    if not out_path.parent.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {out_path.parent}"
        )

    logger.info(
        "filter_cornrow_artifacts: input=%s output=%s limit=±%d° withheld=%s",
        in_path, out_path, scan_angle_limit, drop_withheld,
    )

    # ----- pre-filter point accounting -----------------------------------
    # Count input points, withheld points, and high-scan-angle points by
    # streaming through laspy. This is the source of truth for the return
    # dict; PDAL's own counts come from the output header post-filter.
    pre = _count_pre_filter(in_path, scan_angle_limit)
    logger.debug("pre-filter counts: %s", pre)

    # ----- build the PDAL pipeline ---------------------------------------
    # Filters are applied in declaration order. Withheld first (cheap bit
    # test on most points), ScanAngleRank second (a range comparison on a
    # signed integer dimension). Both use filters.range (not
    # filters.expression) to avoid version-fragile equality parsing.
    pipeline_stages: list = [
        {"type": "readers.las", "filename": str(in_path)},
    ]
    if drop_withheld:
        # Withheld is a single bit (0 or 1); the range [0:0] keeps only the
        # not-withheld points. ASPRS LAS 1.4-R15 §"Point Data Record Format".
        pipeline_stages.append(
            {"type": "filters.range", "limits": "Withheld[0:0]"}
        )
    # ScanAngleRank is PDAL's degrees-valued dimension. PDAL synthesises this
    # from the native ScanAngle field on LAS 1.4 PF6+ inputs (int16 × 0.006°
    # native storage), so the same range expression is correct on PF0–5 and
    # PF6+ source files.
    pipeline_stages.append({
        "type": "filters.range",
        "limits": f"ScanAngleRank[-{scan_angle_limit}:{scan_angle_limit}]",
    })
    # forward=all preserves SRS / VLRs / scales / offsets. PDAL recomputes
    # point counts and the bbox header on write, which is the desired
    # behavior post-filter.
    pipeline_stages.append({
        "type": "writers.las",
        "filename": str(out_path),
        "forward": "all",
    })

    pipeline = {"pipeline": pipeline_stages}

    # ----- run PDAL ------------------------------------------------------
    tmp_json = out_path.parent / f"_tmp_cornrow_pipeline_{int(time.time()*1000)}.json"
    tmp_json.write_text(json.dumps(pipeline, indent=2))
    logger.debug("wrote pipeline JSON: %s", tmp_json)

    t0 = time.time()
    try:
        result = subprocess.run(
            [_pdal_binary(), "pipeline", str(tmp_json)],
            capture_output=True, text=True, timeout=timeout,
        )
    finally:
        # Always clean up the temp pipeline JSON, even on PDAL failure.
        tmp_json.unlink(missing_ok=True)
    elapsed = time.time() - t0

    if result.returncode != 0:
        # Per the established WellSight pattern, raise with the stderr tail.
        # Truncate to the last 4 KB to keep tracebacks readable in notebooks.
        raise RuntimeError(
            "PDAL pipeline failed (rc="
            f"{result.returncode}) for {in_path.name}:\n"
            f"{result.stderr[-4096:]}"
        )

    # ----- post-filter accounting ----------------------------------------
    out_pts = _count_points(out_path)
    retention = 100.0 * out_pts / pre["input_points"] if pre["input_points"] else 0.0

    stats = {
        "input_points":         pre["input_points"],
        "output_points":        out_pts,
        "withheld_dropped":     pre["withheld_dropped"] if drop_withheld else 0,
        "scan_angle_dropped":   pre["scan_angle_dropped"],
        "retention_pct":        retention,
        "scan_angle_limit_deg": scan_angle_limit,
        "input_path":           str(in_path.resolve()),
        "output_path":          str(out_path.resolve()),
    }

    if verbose:
        logger.info(
            "filter_cornrow_artifacts done in %.1fs: kept %d / %d pts (%.2f%%)",
            elapsed, out_pts, pre["input_points"], retention,
        )

    return stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_pre_filter(path: Path, scan_angle_limit: int) -> dict:
    """Stream the input via laspy and tally withheld + high-scan-angle counts.

    Separated for testability (the test suite monkey-patches this when
    exercising the PDAL-failure path).
    """
    import numpy as np
    import laspy

    with laspy.open(str(path)) as r:
        las = r.read()

    n = int(las.header.point_count)

    if "withheld" in las.point_format.dimension_names:
        wh_count = int(np.asarray(las.withheld, dtype=bool).sum())
    else:
        wh_count = 0

    # Prefer scan_angle_rank when present (PF0-5); fall back to scan_angle
    # (PF6+) with the canonical 0.006° scale factor. This mirrors what PDAL's
    # ScanAngleRank dimension reports.
    # Note: laspy's point_format.dimension_names is a *generator* — calling
    # `in` on it consumes the iterator, so materialise to a set first.
    dim_names = set(las.point_format.dimension_names)
    if "scan_angle_rank" in dim_names:
        sa_deg = np.asarray(las.scan_angle_rank, dtype=np.float32)
    elif "scan_angle" in dim_names:
        sa_deg = np.asarray(las.scan_angle, dtype=np.float32) * 0.006
    else:
        sa_deg = np.zeros(n, dtype=np.float32)

    sa_drop = int((np.abs(sa_deg) > scan_angle_limit).sum())

    return {
        "input_points":       n,
        "withheld_dropped":   wh_count,
        "scan_angle_dropped": sa_drop,
    }


def _count_points(path: Path) -> int:
    """Return ``header.point_count`` of a LAS/LAZ file."""
    import laspy
    with laspy.open(str(path)) as r:
        return int(r.header.point_count)

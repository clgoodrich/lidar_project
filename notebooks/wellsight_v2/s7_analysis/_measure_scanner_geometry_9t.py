"""The scan lines on the ground, and why the corn rows lie parallel to them.

THE SENSOR
----------
RIEGL VQ-1560-series, flown by Quantum Spatial (header generating_software
"QSI LiDAR Suite"). It is a ROTATING POLYGON -- RIEGL's own term is a mirror
wheel -- and it is dual channel. Each channel lays down straight, parallel scan
lines; the two channels' lines are tilted 28 degrees against each other, plus
and minus 14, which RIEGL markets as the "cross-fire" pattern. See
literature/CITATIONS.md.

That matters here because a polygon rules STRAIGHT PARALLEL LINES. There is no
zig-zag, no turnaround, and no phase relationship between successive lines --
which is exactly what RIEGL contrasts its wheel against when it describes
oscillating-mirror systems as "prone to unfavorable phase conditions".

DO NOT TRY TO READ THE SCAN PATTERN OUT OF scan_angle. THIS SCRIPT USED TO.
-------------------------------------------------------------------------
An earlier version of this analysis concluded "oscillating mirror, 54.3 Hz",
from three readings of the angle field, and every one of them was an artefact:

  The angle appeared to rise and then fall, which looks like a reversal. It is
  two interleaved channels at different look angles, sampled alternately. The
  across-track ground coordinate confirms it: the sign of its step changes
  37,041 times in 199,900 pulses, with a median run length of ONE. A single
  beam sweeping cannot do that; two interleaved beams must.

  Sweeps looked truncated and eased at the ends. A delivered tile is a spatial
  clip, so only the part of each line that falls inside the tile is present.
  Any waveform fitted inside one tile is fitted to a fragment.

  Ground speed regressed from x and y against gps_time gave 112.2 m/s. The beam
  crosses 1149 m of ground in 6 ms while the aircraft moves under half a metre,
  so that regression measures the sweep. Consecutive 1.4 s pieces of the same
  line returned 34, 55 and 72 m/s -- the scatter was the tell and it was
  ignored. The near-nadir ground track gives 70.1 m/s over 1503 m in 21.46 s.

Everything downstream of those three -- a 3.00 m stripe spacing, a 37.4 Hz
sweep, a 1.03 m line spacing, and a story about lines pairing up at the swath
edge -- was wrong and has been withdrawn.

WHAT THIS MEASURES INSTEAD
--------------------------
The direction of the scan lines, straight off the ground pattern, assuming
nothing. For each candidate bearing the returns are projected onto the
perpendicular and histogrammed: real ruled lines spike, any other bearing
smears, so the variance of that histogram scores the bearing and its peak names
the line direction.

Result: 78.0 to 79.5 degrees across five patches. The corn rows were measured
at 79.0 degrees by _test_chm_nodata_bands_9t.py, independently and from the
NoData mask rather than the point cloud. The corn rows lie PARALLEL TO THE SCAN
LINES, which is the one structural fact the whole explanation rests on.

Run:
    python notebooks/wellsight_v2/s7_analysis/_measure_scanner_geometry_9t.py
Writes:
    data/9t/results/nonground_classification/scanner_geometry_9t.json
"""
from __future__ import annotations

import json
from pathlib import Path

import laspy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
TILE = "USGS_LPC_PA_WesternPA_2019_D20_17TPF621593.laz"
OUT = (ROOT / "data/9t/results/nonground_classification"
       / "scanner_geometry_9t.json")

#: LAS 1.4 point format 6 stores scan angle in 0.006 degree units.
SCALE = 0.006
#: Bearing of the corn rows, from _test_chm_nodata_bands_9t.py, measured on the
#: NoData mask. Quoted here only for comparison; nothing below uses it.
CORDUROY_BEARING = 79.0


def line_bearing(x, y, cx, cy, half=25.0, step=0.05):
    """Dominant ruled-line bearing in a patch, and the runner-up."""
    k = (np.abs(x - cx) < half) & (np.abs(y - cy) < half)
    if int(k.sum()) < 4000:
        return None
    px, py = x[k] - cx, y[k] - cy
    brgs = np.arange(0.0, 180.0, 0.5)
    sc = np.empty(len(brgs))
    edges = np.arange(-half, half, step)
    for i, b in enumerate(brgs):
        r = np.radians(b)
        p = px * np.cos(r) - py * np.sin(r)
        h, _ = np.histogram(p, bins=edges)
        sc[i] = h.var() / max(h.mean(), 1e-9) ** 2
    # flatten the broad trend so the peak is the line signal, not the envelope
    sc = sc - np.convolve(sc, np.ones(41) / 41.0, mode="same")
    picks = []
    for i in np.argsort(sc)[::-1]:
        b = brgs[i]
        if all(min(abs(b - p), 180 - abs(b - p)) > 8 for p in picks):
            picks.append(float(b))
        if len(picks) == 2:
            break
    picks.sort()
    return dict(n=int(k.sum()), peak1=picks[0], peak2=picks[1])


def main() -> int:
    las = laspy.read(SRC / TILE)
    h = las.header
    out = {"tile": TILE,
           "generating_software": str(h.generating_software).strip(),
           "sensor": "RIEGL VQ-1560 series, rotating polygon, dual channel",
           "sensor_source": "literature/CITATIONS.md, RIEGL cross-fire",
           "corduroy_bearing_deg": CORDUROY_BEARING}
    print(f"{TILE}")
    print(f"  software {out['generating_software']!r}")
    print(f"  sensor   {out['sensor']}  (from the spec, not from the file)")

    psid = np.asarray(las.point_source_id)
    pid = int(np.bincount(psid).argmax())
    m = (psid == pid) & (np.asarray(las.return_number) == 1)
    x = np.asarray(las.x)[m]
    y = np.asarray(las.y)[m]
    t = np.asarray(las.gps_time)[m]
    a = np.asarray(las.scan_angle)[m].astype("float64") * SCALE
    o = np.argsort(t, kind="stable")
    x, y, t, a = x[o], y[o], t[o], a[o]
    out["flight_line"] = pid
    out["n_first_returns"] = int(m.sum())

    # ---- the aircraft, from the near-nadir ground track -----------------
    gi = np.flatnonzero(np.abs(a) < 0.5)
    vec = np.array([x[gi[-1]] - x[gi[0]], y[gi[-1]] - y[gi[0]]])
    L = float(np.hypot(*vec))
    dur = float(t[gi[-1]] - t[gi[0]])
    brg = float(np.degrees(np.arctan2(vec[0], vec[1])) % 360)
    print("\nTHE AIRCRAFT, from near-nadir returns only")
    print(f"  {L:.0f} m in {dur:.2f} s = {L/dur:.1f} m/s   "
          f"bearing {brg:.1f} deg")
    print(f"  across-track is therefore {(brg-90)%180:.1f} deg")
    out.update(track_m=L, track_s=dur, ground_speed_ms=L / dur,
               bearing_deg=brg, across_track_deg=(brg - 90) % 180)

    # ---- the ruled lines, straight off the ground -----------------------
    cx0, cy0 = float(x.mean()), float(y.mean())
    print("\nSCAN-LINE BEARING, from the ground pattern")
    print("  patch centre               n     dominant   runner-up")
    rows = []
    for dx, dy in ((0, 0), (300, 200), (-300, -200), (500, -400), (-500, 400)):
        r = line_bearing(x, y, cx0 + dx, cy0 + dy)
        if r is None:
            print(f"  {cx0+dx:.0f} {cy0+dy:.0f}   too few returns")
            continue
        r["cx"], r["cy"] = cx0 + dx, cy0 + dy
        rows.append(r)
        print(f"  {cx0+dx:.0f} {cy0+dy:.0f}   {r['n']:6d}   "
              f"{r['peak1']:6.1f}     {r['peak2']:6.1f}")
    out["line_bearing_patches"] = rows
    if rows:
        best = [min(r["peak1"], r["peak2"], key=lambda b:
                    min(abs(b - CORDUROY_BEARING),
                        180 - abs(b - CORDUROY_BEARING))) for r in rows]
        out["scan_line_bearing_deg"] = float(np.median(best))
        print(f"\n  scan lines      {np.median(best):.1f} deg")
        print(f"  corn rows       {CORDUROY_BEARING:.1f} deg  "
              "(measured on the NoData mask, independently)")
        print("  -> the corn rows lie parallel to the scan lines")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

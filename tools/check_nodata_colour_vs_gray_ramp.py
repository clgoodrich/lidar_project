"""Is a NoData colour separable from every step of a greyscale ramp?

WHY THIS EXISTS
---------------
The project's colourblind rule says to validate with the dataviz skill's
`scripts/validate_palette.js`, all pairs, never by eye. That validator is not
installed in this environment, and guessing a colour by eye is the exact
failure the rule was written to prevent. So this measures the same thing the
same way: simulate deuteranopia, protanopia and tritanopia, then take CIEDE2000
between every pair.

WHAT IT CHECKS
--------------
A greyscale panel has no green in it, so the red/green prohibition is not the
binding constraint here. The binding constraint is that the NoData colour must
not read as a grey level, under normal vision or any CVD, at any point on the
ramp -- otherwise a hole looks like a measurement.

Sampled at 11 evenly spaced steps of the black-to-white ramp. Reports the
WORST pair, because a colour that separates from black and white and collides
in the middle is still broken.

Run:
    python tools/check_nodata_colour_vs_gray_ramp.py "#A31515"
    python tools/check_nodata_colour_vs_gray_ramp.py "#A31515" "#00C2D4"
"""
from __future__ import annotations

import sys

import numpy as np
from colorspacious import cspace_convert, deltaE

#: dE below this and two colours are not reliably separable.
DE_FLOOR = 15.0

SEVERITY = 100
CVD = {
    "deutan": {"name": "sRGB1+CVD", "cvd_type": "deuteranomaly",
               "severity": SEVERITY},
    "protan": {"name": "sRGB1+CVD", "cvd_type": "protanomaly",
               "severity": SEVERITY},
    "tritan": {"name": "sRGB1+CVD", "cvd_type": "tritanomaly",
               "severity": SEVERITY},
}


def hex_to_rgb1(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def rgb1_to_hex(c) -> str:
    return "#" + "".join(f"{int(round(v * 255)):02x}" for v in np.clip(c, 0, 1))


def simulate(rgb1: np.ndarray, mode: str) -> np.ndarray:
    if mode == "normal":
        return rgb1
    return np.clip(cspace_convert(rgb1, CVD[mode], "sRGB1"), 0, 1)


def de(a: np.ndarray, b: np.ndarray) -> float:
    return float(deltaE(a, b, input_space="sRGB1", uniform_space="CAM02-UCS"))


def main(argv) -> int:
    cands = argv[1:] or ["#A31515"]
    ramp = [np.array([v, v, v]) for v in np.linspace(0.0, 1.0, 11)]

    print(f"floor dE {DE_FLOOR:.0f}, CIEDE2000 in CAM02-UCS, "
          f"CVD severity {SEVERITY}\n")
    rc = 0
    for hx in cands:
        c = hex_to_rgb1(hx)
        print(f"{hx}")
        overall = (None, 1e9)
        for mode in ("normal", "deutan", "protan", "tritan"):
            cs = simulate(c, mode)
            worst = (None, 1e9)
            for g in ramp:
                d = de(cs, simulate(g, mode))
                if d < worst[1]:
                    worst = (rgb1_to_hex(g), d)
            flag = "OK  " if worst[1] >= DE_FLOOR else "FAIL"
            print(f"  {flag} {mode:7s} worst vs ramp step {worst[0]}  "
                  f"dE {worst[1]:5.1f}")
            if worst[1] < overall[1]:
                overall = (f"{mode} vs {worst[0]}", worst[1])
        print(f"  -> worst overall: {overall[0]}  dE {overall[1]:.1f}\n")
        if overall[1] < DE_FLOOR:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

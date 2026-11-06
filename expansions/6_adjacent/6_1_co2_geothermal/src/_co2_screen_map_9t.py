"""6.1 deliverable figure. Screening map with candidates, records and blind zones.

Purpose
    Candidates are orange triangles, records are blue circles, blind zones are hatched grey. Shape and hatching
    carry meaning as well as colour (colourblind rule). Palette from ek.PALETTE (lost/found palette, worst pair
    dE 21.1 deutan per CLAUDE.md, dataviz validator --pairs all. Grey is the classification-palette neutral).
    A footer states the evidence levels and the hypothetical partner.
Inputs (run folder)
    screening_package_9t.gpkg
Outputs (run folder)
    screening_map_9t.png (hydrogen: screening_map_h2_9t.png)
Run
    python expansions/6_adjacent/6_1_co2_geothermal/src/_co2_screen_map_9t.py --out RUN_DIR [--profile co2]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import _co2_screen_lib as L
from _co2_screen_lib import ek


def render(cfg: dict, prof: dict, out_dir: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    area = cfg["area"]
    gpkg = out_dir / L.fname("screening_package", prof, area, "gpkg")
    elig = L.read_vector(gpkg, cfg["crs"], layer="L4_eligible")
    rec = L.read_vector(gpkg, cfg["crs"], layer="L1_records")
    cand = L.read_vector(gpkg, cfg["crs"], layer="L2_candidates")
    poly = L.read_vector(gpkg, cfg["crs"], layer=prof["screen_layer"])
    blind = elig[~elig["eligible"].astype(str).isin(["True", "true", "1"])]
    fig, ax = plt.subplots(figsize=(8, 8))
    poly.boundary.plot(ax=ax, color=ek.PALETTE["charcoal"], linewidth=1.0)
    if len(blind):
        blind.plot(ax=ax, facecolor="none", edgecolor=ek.PALETTE["grey"], hatch="///", linewidth=0.3)
    if len(rec):
        rec.plot(ax=ax, color=ek.PALETTE["blue"], marker="o", markersize=6, label="record (level b)")
    if len(cand):
        cand.plot(ax=ax, color=ek.PALETTE["orange"], marker="^", markersize=14, label="candidate (level a)")
    from matplotlib.patches import Patch
    h, lab = ax.get_legend_handles_labels()
    h.append(Patch(facecolor="none", edgecolor=ek.PALETTE["grey"], hatch="///", label="blind zone"))
    ax.legend(handles=h, loc="upper right", frameon=True)
    ax.set_axis_off()
    who = "declared hypothetical partner" if cfg["decisions"]["partner"] == "hypothetical" else cfg["decisions"]["partner"]
    fig.text(0.01, 0.01, f"Candidates are possible wells (level a). Records are level b. Blind zones are not evidence "
                         f"of absence. {who}.", fontsize=7)
    out = out_dir / L.fname("screening_map", prof, area, "png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    ap.add_argument("--profile", default="co2")
    ap.add_argument("--profile-file", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = L.load_config(a.config)
    prof = L.load_profile(cfg, a.profile, a.profile_file)
    print(f"wrote {render(cfg, prof, Path(a.out))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

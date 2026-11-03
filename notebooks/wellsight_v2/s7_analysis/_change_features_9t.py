"""What changed at the mapped pads, roads and pits between the 2006-2008 and 2019 lidar (9t)?

For every pad, road segment and pit outline that lies inside the change raster, measure the high-passed 2019-minus-2006/08
elevation change inside the outline, and compare it with the same outline moved to 40 random ordinary spots 150 to 800 m away.
A feature is called CHANGED when its share of cells beyond the noise threshold (0.235 m, 3 sigma of the field) beats 97.5% of its own
moved copies AND covers at least 20% of the outline. Then the type is read from the sign: fill, cut, or both (regrade).

Pits are reported but flagged as unassessable. The 2006-2008 survey is about 7 times sparser and resolves only about 72% of a pit's depth
(docs/iterations/icp_change_9t.md, Part 3). But the pit flags did not go away when the 2019 points were thinned to near the 2006 density
(129 of 436 flagged, 2026-11-03), so sparse sampling alone does not explain them. Cause not established.

Output: data/9t/results/change/change_features_9t.gpkg (layers pad, road, pit) and change_features_summary_9t.json

Changes 2026-11-03 after an outside review.
  1. Controls are matched on slope (mean slope within 3 degrees of the feature). Noise in the change field rises steeply with slope.
  2. Placebo rate. Each feature's own controls are flagged by the same rule against the other controls (leave one out). The share
     flagged is the measured false-alarm rate. It replaces 0.025 x n, which was an assumption (the review measured 4.7%, not 2.5%).
  3. --field lineadj runs on the per-pass-corrected surface. Default is the surface the published flags came from (singleicp).

Run:
  python notebooks/wellsight_v2/s7_analysis/_change_features_9t.py [--field singleicp|lineadj]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely import affinity

ROOT = Path(__file__).resolve().parents[3]
ICP = ROOT / "data/_experiments/icp/change_9t"
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"
OUT = ROOT / "data/9t/results/change"
THR = 0.235          # 3 sigma of the high-passed field, docs/iterations/icp_change_9t.md Part 4
N_CTRL = 40
MIN_COVER = 0.20
P_CUT = 0.975
RNG = np.random.default_rng(20261102)


FIELDS = {"singleicp": (ICP / "dod_9t_singleicp_highpass_2m.tif", ""),
          "lineadj": (ROOT / "data/9t/derived/lidar_2006_2008/dod_lineadj_highpass_9t_2m.tif", "_lineadj"),
          "v2": (ROOT / "data/9t/derived/lidar_2006_2008/dod_v2_highpass_9t_2m.tif", "_v2")}
SLOPE_TOL = 3.0


def main(field="singleicp"):
    OUT.mkdir(parents=True, exist_ok=True)
    src, tag = FIELDS[field]
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _change_lineadj_9t as LA
    ref = LA.dem2019()
    gy_, gx_ = np.gradient(np.nan_to_num(ref, nan=np.nanmean(ref)), 2.0)
    slope = np.degrees(np.arctan(np.hypot(gx_, gy_)))
    with rasterio.open(src) as s:
        f = s.read(1).astype(float)
        T, B = s.transform, s.bounds
    ok = np.isfinite(f)
    layers = {"pad": gpd.read_file(G, layer="pad"), "road": gpd.read_file(G, layer="roads"), "pit": gpd.read_file(G, layer="pit_full")}
    layers["road"]["geometry"] = layers["road"].geometry.buffer(3.0)  # roads carry no width in the annotations
    from rasterio.features import rasterize
    from scipy import ndimage as ndi
    feat = rasterize([g for L in layers.values() for g in L.geometry], out_shape=f.shape, transform=T, fill=0, default_value=1, all_touched=True).astype(bool)
    excl = ndi.binary_dilation(feat, iterations=20)  # 40 m clear of every mapped feature

    def stats(geom, clear=False):
        x0, y0, x1, y1 = geom.bounds
        if x0 < B.left or y0 < B.bottom or x1 > B.right or y1 > B.top:
            return None
        c0, r0 = int((x0 - B.left) // 2), int((B.top - y1) // 2)
        c1, r1 = int(np.ceil((x1 - B.left) / 2)), int(np.ceil((B.top - y0) / 2))
        sub = f[r0:r1, c0:c1]
        tr = rasterio.transform.from_origin(B.left + c0 * 2, B.top - r0 * 2, 2, 2)
        m = ~geometry_mask([geom], out_shape=sub.shape, transform=tr, all_touched=False)
        if clear and (m & excl[r0:r1, c0:c1]).any():
            return None
        m &= np.isfinite(sub)
        if m.sum() < 8:
            return None
        v = sub[m]
        return dict(n=int(m.sum()), med=float(np.median(v)), cut=float((v < -THR).mean()), fill=float((v > THR).mean()),
                    slope=float(slope[r0:r1, c0:c1][m].mean()))

    def ctrl_stats(geom, n, slope0):
        out, tries = [], 0
        while len(out) < n and tries < 600:
            tries += 1
            a, d = RNG.uniform(0, 2 * np.pi), RNG.uniform(150, 800)
            c = stats(affinity.translate(geom, d * np.cos(a), d * np.sin(a)), clear=True)
            if c and abs(c["slope"] - slope0) <= SLOPE_TOL:
                out.append(c)
        return out

    summary = {}
    outs = {}
    for name, L in layers.items():
        rows = []
        for idx, row in L.iterrows():
            s0 = stats(row.geometry)
            if s0 is None:
                continue
            cs = ctrl_stats(row.geometry, N_CTRL, s0["slope"])
            if len(cs) < 10:
                continue
            tot = s0["cut"] + s0["fill"]
            ct = np.array([c["cut"] + c["fill"] for c in cs])
            p = float((ct >= tot).mean())
            q975 = float(np.quantile(ct, P_CUT))
            # placebo: flag each control against the others with the same rule
            fl = [ct[i] > np.quantile(np.delete(ct, i), P_CUT) and ct[i] >= MIN_COVER for i in range(len(ct))]
            placebo = float(np.mean(fl))
            changed = bool(tot > q975 and tot >= MIN_COVER)
            kind = "none"
            if changed:
                kind = "fill" if s0["fill"] > 2 * s0["cut"] else "cut" if s0["cut"] > 2 * s0["fill"] else "cut_and_fill"
            rows.append(dict(idx=idx, geometry=row.geometry, n_px=s0["n"], med_dz_m=round(s0["med"], 3), frac_cut=round(s0["cut"], 3),
                             frac_fill=round(s0["fill"], 3), frac_changed=round(tot, 3), ctrl_q975=round(q975, 3), p_ctrl=round(p, 3), changed=changed, kind=kind, slope_deg=round(s0["slope"], 1), n_ctrl=len(cs), placebo_rate=round(placebo, 3)))
            if len(rows) % 100 == 0:
                print(name, len(rows), flush=True)
        D = gpd.GeoDataFrame(rows, geometry="geometry", crs=6346)
        key = {"pad": "pad_id", "road": "id", "pit": "pit_full_id"}[name]
        D[key] = [L.loc[i, key] for i in D["idx"]]
        D = D.drop(columns="idx")
        outs[name] = D
        summary[name] = dict(n_measured=int(len(D)), n_changed=int(D.changed.sum()), share=round(float(D.changed.mean()), 3),
                             kinds=D[D.changed].kind.value_counts().to_dict(), expected_false_assumed=round(0.025 * len(D), 1),
                             placebo_rate=round(float(D.placebo_rate.mean()), 4), expected_false_measured=round(float(D.placebo_rate.sum()), 1),
                             median_n_ctrl=float(D.n_ctrl.median()))
        print(name, summary[name], flush=True)
    gp = OUT / f"change_features{tag}_9t.gpkg"
    if gp.exists():
        gp.unlink()
    for name, D in outs.items():
        D.to_file(gp, layer=name, driver="GPKG")
    (OUT / f"change_features_summary{tag}_9t.json").write_text(json.dumps(summary, indent=2))
    print(gp)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", choices=sorted(FIELDS), default="singleicp")
    main(ap.parse_args().field)

"""Steel screen anchored to lidar pad polygons instead of DEP points. Set 2026-11-25.

Why
  DEP well points sit a median 36 m from the nearest lidar pad on 9t, and only 25% fall inside one
  (nisar/results/9t/nisar_dep_well_pad_distance_9t.gpkg). A 6 m circle on a DEP point mostly samples
  ground beside the well. A lidar pad is where the equipment actually stands, to lidar accuracy.

Test
  * Steady bright pixels (SBT): the same rule and dates as _nisar_steel_9t.py (D_A < 0.25 and
    brightness >= 3 robust SD above the 250 m median, per track).
  * Site = lidar pad polygon + 5 m buffer. Hit = any SBT pixel centre inside it, per track.
  * Control polygons: each pad's own shape, shifted 150-600 m in a random direction, every pixel
    >= 60 m from any DEP well and >= 30 m from any pad, mean canopy cover within 0.15 of the pad's.
    5 per pad. Same shape and size, so a bigger pad has no area advantage over its controls.
  * Fisher's exact test, pads vs controls: all pads, by canopy (open < 0.30), by pad size tercile,
    and by DEP status of wells inside the pad (any active / plugged or abandoned only / no DEP well).
  * Also: brightness-rule and steadiness-rule pass rates on their own (review point), and the whole
    test on summer (leaf-on) dates only, so leaf drop cannot fail a real under-canopy target.

Outputs
  nisar/results/9t/nisar_steel_pads_summary_9t_slc.json   (_9t without --slc = NASA placement)
  nisar/results/9t/nisar_steel_pads_sites_9t_slc.gpkg   (pads with hits per track and status class)

Run
  python nisar/code/s5_eval/_nisar_steel_pads_9t.py --slc    (lidar-placed stack; the published one)
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize, geometry_mask
from rasterio.windows import from_bounds, Window
from scipy.stats import fisher_exact
from shapely.affinity import translate

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _nisar_steel_9t as S  # noqa: E402

BUF_M, N_CTRL, SEED = 5.0, 5, 20261125
OUT = S.OUT


def pix(geom, tf, shape):
    """Row, col arrays of pixels whose centre lies inside geom."""
    x0, y0, x1, y1 = geom.bounds
    c0, c1 = int(np.floor((x0 - tf.c) / tf.a)), int(np.ceil((x1 - tf.c) / tf.a))
    r0, r1 = int(np.floor((y1 - tf.f) / tf.e)), int(np.ceil((y0 - tf.f) / tf.e))
    if c0 < 0 or r0 < 0 or c1 > shape[1] or r1 > shape[0]:
        return None
    sub = tf * tf.translation(c0, r0)
    m = geometry_mask([geom], out_shape=(r1 - r0, c1 - c0), transform=sub, invert=True)
    rr, cc = np.nonzero(m)
    if not len(rr):
        return None
    return rr + r0, cc + c0


def test(maps, sites, ctrls, label):
    """Hit rates and Fisher per class. sites/ctrls: DataFrames with per-track hit columns."""
    tr = [f"t{t}" for t in maps]

    def rate(df):
        n = (df[tr] > 0).sum(1)
        return (n >= 1), (n >= 2)
    out = []
    classes = [("all", sites.index, ctrls.index)]
    for col in ("cover_cls", "size_cls", "status_cls"):
        for v in sorted(sites[col].unique()):
            s = sites.index[sites[col] == v]
            classes.append((f"{col}={v}", s, ctrls.index[ctrls.site.isin(s)]))
    for name, si, ci in classes:
        a1, a2 = rate(sites.loc[si]); b1, b2 = rate(ctrls.loc[ci])
        o, p = fisher_exact([[a1.sum(), (~a1).sum()], [b1.sum(), (~b1).sum()]])
        o2, p2 = fisher_exact([[a2.sum(), (~a2).sum()], [b2.sum(), (~b2).sum()]])
        out.append(dict(dates=label, cls=name, n_pads=len(si), n_ctrl=len(ci),
                        pads_hit_any=round(a1.mean(), 3), ctrl_hit_any=round(b1.mean(), 3),
                        odds_any=round(o, 2), p_any=float(f"{p:.2g}"),
                        pads_hit_2plus=round(a2.mean(), 3), ctrl_hit_2plus=round(b2.mean(), 3),
                        p_2plus=float(f"{p2:.2g}")))
    return out


def main():
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = S.ifg.load_complex()
    cover = S.st.canopy_cover(tf, shape)

    runs = {"all_post_june": idx}
    m = pd.to_datetime(idx.date.astype(str).str[:10]).dt.month
    runs["summer_leaf_on"] = idx[(m >= 6) & (m <= 9)]

    x0, y1 = tf.c, tf.f
    x1, y0 = x0 + shape[1] * 5, y1 - shape[0] * 5
    pads = S.read_layer(S.ANN, "plat").pipe(S.AREA.to_radar).cx[x0:x1, y0:y1].reset_index(drop=True)
    wells = gpd.read_file(S.WELLS).pipe(S.AREA.to_radar).cx[x0 - 100:x1 + 100, y0 - 100:y1 + 100]
    grp = {v: k for k, vs in S.GROUPS.items() for v in vs}
    wells["group"] = wells.WELL_STATU.map(grp)

    results, rates, site_out = [], {}, None
    for label, sub in runs.items():
        maps = S.sbt_maps(sub, stack, shape)
        valid = np.isfinite(cover) & np.all([mm["ok"] for mm in maps.values()], axis=0)
        # separate pass rates for the two rules
        rates[label] = {int(t): dict(n_dates=mm["n"], cut_db=S.BRIGHT_DB[int(t)],
                                     bright_pass=round(float((mm["bright"][mm["ok"]] >= S.BRIGHT_DB[int(t)]).mean()), 5),
                                     steady_pass=round(float((mm["da"][mm["ok"]] < S.DA_MAX).mean()), 5),
                                     both_pass=round(float(mm["sbt"][mm["ok"]].mean()), 5))
                        for t, mm in maps.items()}
        away = rasterize([(g, 1) for g in list(wells.buffer(60)) + list(pads.buffer(30))],
                         out_shape=shape, transform=tf, fill=0, dtype="uint8") == 0
        away &= valid

        srows, crows = [], []
        for i, p in pads.iterrows():
            g = p.geometry.buffer(BUF_M)
            px = pix(g, tf, shape)
            if px is None or not valid[px].all():
                continue
            cv = float(np.nanmean(cover[px]))
            inside = wells[wells.within(g)]
            gs = set(inside.group.dropna())
            status = "active" if "active" in gs else ("plugged_or_abandoned" if gs & {"plugged", "abandoned"}
                                                     else "no_dep_well")
            row = dict(site=i, cover=cv, area=g.area, n_dep=len(inside), status_cls=status,
                       **{f"t{t}": int(mm["sbt"][px].any()) for t, mm in maps.items()})
            srows.append(row)
            cx, cy = g.centroid.x, g.centroid.y
            got = tries = 0
            while got < N_CTRL and tries < 400:
                tries += 1
                a, r = rng.uniform(0, 2 * np.pi), rng.uniform(150, 600)
                h = translate(g, r * np.cos(a), r * np.sin(a))
                q = pix(h, tf, shape)
                if q is None or not away[q].all() or abs(np.nanmean(cover[q]) - cv) > 0.15:
                    continue
                crows.append(dict(site=i, **{f"t{t}": int(mm["sbt"][q].any()) for t, mm in maps.items()}))
                got += 1
        sites = pd.DataFrame(srows).set_index("site", drop=False)
        sites["cover_cls"] = np.where(sites.cover < 0.30, "open", "canopy")
        sites["size_cls"] = pd.qcut(sites.area, 3, labels=["small", "mid", "large"]).astype(str)
        ctrls = pd.DataFrame(crows)
        print(label, len(sites), "pads,", len(ctrls), "controls")
        results += test(maps, sites, ctrls, label)
        if label == "all_post_june":
            site_out = pads.loc[sites.index].assign(**{c: sites[c].values for c in sites.columns if c != "site"})

    res = pd.DataFrame(results)
    print(res.to_string(index=False))
    json.dump(dict(params=dict(buffer_m=BUF_M, n_ctrl=N_CTRL, seed=SEED, da_max=S.DA_MAX,
                               bright_sd=S.BRIGHT_SD, bg_m=S.BG_M, ctrl_shift_m=[150, 600],
                               ctrl_clear_of_wells_m=60, ctrl_clear_of_pads_m=30, canopy_match=0.15),
                   pass_rates=rates, tests=results),
              open(OUT / f"nisar_steel_pads_summary_{S.OTAG}.json", "w"), indent=2, default=float)
    site_out.to_file(OUT / f"nisar_steel_pads_sites_{S.OTAG}.gpkg", driver="GPKG")
    print("wrote", OUT / f"nisar_steel_pads_summary_{S.OTAG}.json")


if __name__ == "__main__":
    main()

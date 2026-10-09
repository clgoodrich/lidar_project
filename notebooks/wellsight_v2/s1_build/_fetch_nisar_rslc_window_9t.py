"""Stage 1 of docs/iterations/nisar_regeocode_plan_9t.md: fetch the 9t piece of each NISAR RSLC.

RSLC is the radar image before NASA places it on a map (zero-Doppler radar geometry, HH and HV,
about 54,700 x 53,000 complex samples). It sits in the ASF cloud, chunked 512 x 512, so h5py
reads only the chunks over 9t through HTTPS range requests, like the GSLC fetch.

One RSLC per GSLC already held: matched on cycle, track and frame from
data/9t/derived/nisar_gslc_5m/nisar_gslc_window_index_9t_5m.csv. On track 026 that keeps the frame
the GSLC index kept. Other RSLC granules are listed in the log and skipped. When a date has several
RSLC versions (_001, _002), the one whose version matches the GSLC's is kept.

Radar window per granule:
  * The RSLC's own metadata/geolocationGrid maps (height, zero-Doppler time, slant range) to map
    x, y. Near 9t the inverse is fitted as a plane per height layer (least squares on the grid
    nodes within 3 km), and the 9t box plus MARGIN_M is sent through it at the two height
    layers that bracket 9t.
  * Min and max time and range over those corners, padded by PAD samples for the interpolator.

Saved per granule (HDF5):
  /HH, /HV                 complex64 window
  /row0, /col0             window offset in the full RSLC
  /zeroDopplerTime         window times (units attribute copied exactly)
  /slantRange              window ranges (m)
  /geolocationGrid/...     every cube cut to the window's time and range span plus 2 nodes
  /orbit, /attitude, /processingInformation/parameters, /identification   copied whole
                           (small; Doppler centroid and timing tables live in parameters)

Run (about 1 minute per granule):
  python notebooks/wellsight_v2/s1_build/_fetch_nisar_rslc_window_9t.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import fsspec
import h5py
import numpy as np
import pandas as pd
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fetch_nisar_gslc_window_9t as gfetch  # noqa: E402

D9 = gfetch.path_for("data") / "9t"
OUT = D9 / "derived" / "nisar_rslc_window"
GINDEX = D9 / "derived" / "nisar_gslc_5m" / "nisar_gslc_window_index_9t_5m.csv"
COLLECTIONS = ["NISAR_L1_RSLC_BETA_V1", "NISAR_L1_RSLC_PROVISIONAL_V1"]
ROOT_GRP = "science/LSAR/RSLC"
MARGIN_M = 200.0
FIT_M = 3000.0
PAD = 64
COPY = ["metadata/orbit", "metadata/attitude", "metadata/processingInformation/parameters"]


def query() -> pd.DataFrame:
    gfetch.COLLECTIONS = COLLECTIONS        # same CMR query and name parsing as the GSLC fetch
    return gfetch.query()


def plane_inverse(gx, gy, t, r, box):
    """Fit time and range as planes in (x, y) on nodes near 9t; return them at the box corners."""
    x0, y0, x1, y1 = box
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    near = np.hypot(gx - xc, gy - yc) < FIT_M
    if near.sum() < 6:
        raise RuntimeError(f"only {near.sum()} geolocation nodes near 9t")
    A = np.c_[gx[near] - xc, gy[near] - yc, np.ones(near.sum())]
    ct, *_ = np.linalg.lstsq(A, t[near], rcond=None)
    cr, *_ = np.linalg.lstsq(A, r[near], rcond=None)
    cx = np.array([x0, x1, x0, x1]) - xc
    cy = np.array([y0, y0, y1, y1]) - yc
    C = np.c_[cx, cy, np.ones(4)]
    # residual of the plane fit at the nodes, in seconds and metres
    res_t = np.abs(A @ ct - t[near]).max()
    res_r = np.abs(A @ cr - r[near]).max()
    return C @ ct, C @ cr, res_t, res_r


def fetch_one(url, box, path):
    f = fsspec.filesystem("http").open(gfetch.signed_url(url), block_size=8 * 2**20, cache_type="blockcache")
    with h5py.File(f, "r") as h:
        R = h[ROOT_GRP]
        sw = R["swaths"]
        zt_ds, sr_ds = sw["zeroDopplerTime"], sw["frequencyA/slantRange"]
        zt, sr = zt_ds[:], sr_ds[:]
        gg = R["metadata/geolocationGrid"]
        epsg = int(gg["epsg"][()])
        gt, gr, gh = gg["zeroDopplerTime"][:], gg["slantRange"][:], gg["heightAboveEllipsoid"][:]
        if dict(gg["zeroDopplerTime"].attrs).get("units") != dict(zt_ds.attrs).get("units"):
            raise RuntimeError("geolocation grid and swath time units differ")
        tf = Transformer.from_crs(f"EPSG:{epsg}", gfetch.CRS, always_xy=True)
        # 9t ellipsoid heights are about 300-500 m; take the layers bracketing 0-800 m
        layers = [int(np.searchsorted(gh, 0) - 1), int(np.searchsorted(gh, 800))]
        layers = [int(np.clip(k, 0, len(gh) - 1)) for k in layers]
        T, Rg = np.meshgrid(gt, gr, indexing="ij")
        ts, rs, fit = [], [], []
        for k in layers:
            X, Y = tf.transform(gg["coordinateX"][k], gg["coordinateY"][k])
            ct, cr, et, er = plane_inverse(X.ravel(), Y.ravel(), T.ravel(), Rg.ravel(), box)
            ts += list(ct); rs += list(cr); fit.append((et, er))
        dt, dr = zt[1] - zt[0], sr[1] - sr[0]
        r0 = int(np.floor((min(ts) - zt[0]) / dt)) - PAD
        r1 = int(np.ceil((max(ts) - zt[0]) / dt)) + PAD
        c0 = int(np.floor((min(rs) - sr[0]) / dr)) - PAD
        c1 = int(np.ceil((max(rs) - sr[0]) / dr)) + PAD
        if r0 < 0 or c0 < 0 or r1 > len(zt) or c1 > len(sr):
            raise RuntimeError(f"window {r0}:{r1}, {c0}:{c1} leaves the swath {len(zt)} x {len(sr)}")
        hh = sw["frequencyA/HH"][r0:r1, c0:c1]
        hv = sw["frequencyA/HV"][r0:r1, c0:c1]
        # geolocation cubes cut to the window plus 2 nodes each way
        ti = np.where((gt >= zt[r0]) & (gt <= zt[r1 - 1]))[0]
        ri = np.where((gr >= sr[c0]) & (gr <= sr[c1 - 1]))[0]
        ta = max((ti[0] if len(ti) else np.searchsorted(gt, zt[r0])) - 2, 0)
        tb = min((ti[-1] if len(ti) else np.searchsorted(gt, zt[r1 - 1])) + 3, len(gt))
        ra = max((ri[0] if len(ri) else np.searchsorted(gr, sr[c0])) - 2, 0)
        rb = min((ri[-1] if len(ri) else np.searchsorted(gr, sr[c1 - 1])) + 3, len(gr))
        with h5py.File(path, "w") as o:
            o["HH"], o["HV"] = hh, hv
            o["row0"], o["col0"] = r0, c0
            o.create_dataset("zeroDopplerTime", data=zt[r0:r1])
            o.create_dataset("slantRange", data=sr[c0:c1])
            for src_ds, name in ((zt_ds, "zeroDopplerTime"), (sr_ds, "slantRange")):
                for a, v in src_ds.attrs.items():
                    o[name].attrs[a] = v
            og = o.create_group("geolocationGrid")
            for name, ds in gg.items():
                if ds.ndim == 3:
                    og[name] = ds[:, ta:tb, ra:rb]
                elif name == "zeroDopplerTime":
                    og[name] = ds[ta:tb]
                elif name == "slantRange":
                    og[name] = ds[ra:rb]
                else:
                    og[name] = ds[()]
                for a, v in ds.attrs.items():
                    og[name].attrs[a] = v
            for p in COPY:
                if p in R:
                    R.copy(R[p], o, name=p.split("/")[-1])
            h.copy(h["science/LSAR/identification"], o, name="identification")
            o.attrs["slant_range_spacing_m"] = float(dr)
            o.attrs["zero_doppler_time_spacing_s"] = float(dt)
            o.attrs["full_shape"] = (len(zt), len(sr))
            o.attrs["window_box_epsg32617"] = box
            o.attrs["plane_fit_max_residual_s_m"] = np.array(fit).ravel()
    return dict(row0=r0, col0=c0, nrows=r1 - r0, ncols=c1 - c0,
                fit_res_time_s=max(e[0] for e in fit), fit_res_range_m=max(e[1] for e in fit),
                hh_valid_fraction=float(np.mean(np.abs(hh) > 0)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gi = pd.read_csv(GINDEX)
    q = query()
    q["key"] = list(zip(q.cycle, q.track, q.frame))
    keep = set(zip(gi.cycle, gi.track, gi.frame))
    skip = q[~q.key.isin(keep)]
    print(f"{len(q)} RSLC granules; {len(skip)} have no matching GSLC in the index and are skipped:")
    for g in skip.granule:
        print("  skip", g)
    q = q[q.key.isin(keep)].copy()
    # a date can have several RSLC versions (..._001, ..._002). Keep the one whose version suffix
    # matches the GSLC we hold, else the latest.
    gver = {(r.cycle, r.track, r.frame): r.granule.rsplit("_", 1)[1] for r in gi.itertuples()}
    q["ver"] = q.granule.str.rsplit("_", n=1).str[1]
    q["match"] = [v == gver[k] for v, k in zip(q.ver, q.key)]
    q = q.sort_values(["match", "ver"]).groupby("key").tail(1)
    q = q.sort_values(["date", "track"]).reset_index(drop=True)
    x0, y0, x1, y1 = gfetch.window_bounds()
    box = (x0, y0, x1, y1)     # already includes the GSLC fetch's 200 m margin
    idx_path = OUT / "nisar_rslc_window_index_9t.csv"
    done = pd.read_csv(idx_path) if idx_path.exists() else pd.DataFrame(columns=["file"])
    rows = done.to_dict("records")
    for _, g in q.iterrows():
        name = f"nisar_rslc_window_{g.date.replace('-', '')}_t{g.track:03d}{g.direction}_9t.h5"
        if name in set(done.file):
            print("have", name)
            continue
        t = time.time()
        try:
            info = fetch_one(g.url, box, OUT / name)
        except Exception as e:  # keep going; the log shows which failed
            print("FAIL", g.granule, repr(e))
            continue
        rows.append(dict(file=name, date=g.date, collection=g.collection, cycle=g.cycle, track=g.track,
                         direction=g.direction, frame=g.frame, granule=g.granule, **info,
                         size_mb=round((OUT / name).stat().st_size / 2**20, 1)))
        pd.DataFrame(rows).to_csv(idx_path, index=False)
        print(f"wrote {name}  {info['nrows']} x {info['ncols']}  {time.time() - t:.0f} s", flush=True)
    print("index", idx_path, len(rows), "files")


if __name__ == "__main__":
    main()

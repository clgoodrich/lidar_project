"""Are steady bright targets that repeat across tracks more than chance? (9t)

Each track is an independent set of dates and a different look. A bright steady point that shows up
on two tracks within MERGE_M is hard to put down to speckle. Null: shift one track's points by a
random vector, wrapped around the tile edge (toroidal), and count coincidences again. The shift keeps
the point count and the overall density, and breaks any real alignment. 10,000 shifts, one-sided.

Per track pair: observed coincidences (points of track a with a track-b point within MERGE_M),
the shifted-null mean, and p = (1 + #null >= observed) / (1 + N).

  python notebooks/wellsight_v2/s5_eval/_nisar_bright_coincidence_9t.py --slc
"""
import importlib
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
bt = importlib.import_module("_nisar_bright_targets_9t")
steel, ifg = bt.steel, bt.ifg
N_SHIFT, SEED, R = 10000, 20261021, bt.MERGE_M


def main():
    rng = np.random.default_rng(SEED)
    idx, stack, tf, shape = ifg.load_complex()
    maps = steel.sbt_maps(idx, stack, shape)
    p = bt.track_points(maps, tf)
    W, H = shape[1] * 5.0, shape[0] * 5.0
    ox, oy = tf.c, tf.f - H
    xy = {t: ((g.x.values - ox), (g.y.values - oy)) for t, g in p.groupby("track")}
    print({t: len(v[0]) for t, v in xy.items()})

    def coinc(a, b, dx=0.0, dy=0.0):
        bx, by = (b[0] + dx) % W, (b[1] + dy) % H
        d, _ = cKDTree(np.c_[bx, by]).query(np.c_[a[0], a[1]], distance_upper_bound=R)
        return int(np.isfinite(d).sum())

    rows = []
    for ta, tb in itertools.combinations(sorted(xy), 2):
        a, b = xy[ta], xy[tb]
        obs = coinc(a, b)
        null = np.array([coinc(a, b, rng.uniform(0, W), rng.uniform(0, H)) for _ in range(N_SHIFT)])
        rows.append(dict(track_a=ta, track_b=tb, n_a=len(a[0]), n_b=len(b[0]), observed=obs,
                         null_mean=round(float(null.mean()), 2), null_p99=float(np.percentile(null, 99)),
                         ratio=round(obs / max(null.mean(), 1e-9), 1),
                         p=float((1 + (null >= obs).sum()) / (1 + N_SHIFT))))
    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    stem = "nisar_bright_coincidence"
    res.to_csv(bt.OUT / f"{stem}_by_track_pair_{bt.AREA.TAG}.csv", index=False)
    json.dump(dict(merge_m=R, n_shift=N_SHIFT, seed=SEED, pairs=rows),
              open(bt.OUT / f"{stem}_summary_{bt.AREA.TAG}.json", "w"), indent=2)


if __name__ == "__main__":
    main()

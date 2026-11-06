"""S3 (3.6). Blind label packs per complete block, and the double-label subset.

Purpose
    For each complete block write one PNG chip each of imagery (NAIP RGB), hillshade and the
    above-ground height raster (nDSM, clipped 0 to 12 m), plus a manifest. No status, no well points,
    no model output. The manifest records only these three layer names, and the script asserts that no
    forbidden field name reaches it (QC check 3). A seeded draw marks double_label_share of blocks for two
    annotators. Blocks are fixed by the saved draw before any labelling (QC check 5).
    Agreement is computed afterwards with the core: _geo_transfer_core.py agree --exp 3.6 --area ca1 --a .. --b ..
Inputs
    data/<area>/results/transfer/xfer_blocks_roles_<area>.gpkg (core 'blocks')
    NAIP, hillshade and nDSM rasters (config inputs naip, hillshade, ndsm)
Outputs
    data/<area>/derived/ca_label_packs_<area>/<block_id>_{naip,hillshade,ndsm}.png
    data/<area>/derived/ca_label_packs_<area>/ca_label_pack_manifest_<area>.csv
Run
    python expansions/3_geography/3_6_california/src/_ca_label_packs.py --area ca1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.6"
LAYERS = ("naip", "hillshade", "ndsm")
FORBIDDEN = ("status", "api", "well", "prob", "score", "candidate", "operator")


def double_label_draw(block_ids: list[str], share: float, seed: int) -> set:
    rng = np.random.default_rng(seed)
    n = int(round(share * len(block_ids)))
    return set(rng.choice(sorted(block_ids), n, replace=False).tolist()) if n else set()


def assert_blind(columns) -> None:
    bad = [c for c in columns if any(f in c.lower() for f in FORBIDDEN)]
    if bad:
        raise AssertionError(f"label pack manifest carries forbidden fields {bad}")


def to_uint8(a: np.ndarray, lo=None, hi=None) -> np.ndarray:
    a = a.astype(np.float32)
    lo = np.nanpercentile(a, 2) if lo is None else lo
    hi = np.nanpercentile(a, 98) if hi is None else hi
    return (np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1) * 255).astype(np.uint8)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--area", required=True)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    import geopandas as gpd
    import rasterio
    from PIL import Image
    from rasterio.windows import from_bounds
    try:
        blocks = gpd.read_file(gt.require_input(gt.area_transfer_dir(a.area) / f"xfer_blocks_roles_{a.area}.gpkg",
                                                "block roles", "core 'blocks'"))
        srcs = {k: gt.config_input(cfg, k, EXP, area=a.area) for k in LAYERS}
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    blocks = blocks[blocks["eligible"]]
    dbl = double_label_draw(list(blocks["block_id"]), cfg["prereg"]["double_label_share"],
                            int(cfg["prereg"]["master_seed"]))
    out_d = ek.area_dir(a.area) / "derived" / f"ca_label_packs_{a.area}"
    out_d.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, b in blocks.iterrows():
        rec = {"block_id": b.block_id, "double_label": b.block_id in dbl}
        for k, p in srcs.items():
            with rasterio.open(p) as r:
                bb = gpd.GeoSeries([b.geometry], crs=blocks.crs).to_crs(r.crs).total_bounds
                w = from_bounds(*bb, r.transform).round_offsets().round_lengths()
                if k == "naip":
                    img = np.dstack([to_uint8(r.read(i, window=w)) for i in (1, 2, 3)])
                elif k == "ndsm":
                    img = to_uint8(r.read(1, window=w), 0.0, 12.0)
                else:
                    img = r.read(1, window=w).astype(np.uint8)
            fp = out_d / f"{b.block_id}_{k}.png"
            Image.fromarray(img).save(fp)
            rec[f"{k}_png"] = fp.name
        rows.append(rec)
    man = pd.DataFrame(rows)
    assert_blind(man.columns)
    mp = out_d / f"ca_label_pack_manifest_{a.area}.csv"
    man.to_csv(mp, index=False)
    ek.write_provenance(out_d, inputs=list(srcs.values()), outputs=[mp], params={"double": sorted(dbl)})
    print(f"{len(man)} blocks, {len(dbl)} double-labelled -> {mp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

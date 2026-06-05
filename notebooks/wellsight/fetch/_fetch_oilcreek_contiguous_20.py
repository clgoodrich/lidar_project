"""Download 20 LAZ tiles from PA_WesternPA_2019_D20 that grow a contiguous
patch starting from the two we already have on disk (17TPF610597 + 610599).

Greedy edge-adjacent expansion: at each step pick the unselected tile that
(a) is 4-adjacent to the current selected set (within 1500 m + tolerance of
some already-selected centroid) and (b) is closest to the seed-pair centroid.
Repeat 20 times.

CLI:
  python notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py            # plan + download
  python notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py --list     # plan only
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT

API = "https://tnmaccess.nationalmap.gov/api/v1/products"
BBOX_LL = (-79.72, 41.50, -79.62, 41.66)  # Oil Creek SP, roughly
TILE_M = 1500.0
ADJ_TOL = 50.0
EXISTING = {
    "USGS_LPC_PA_WesternPA_2019_D20_17TPF610597.laz",
    "USGS_LPC_PA_WesternPA_2019_D20_17TPF610599.laz",
}
DEST = ROOT / "data" / "files"


def tnm_list_d20() -> list[dict]:
    qs = urllib.parse.urlencode({
        "datasets": "Lidar Point Cloud (LPC)",
        "bbox": ",".join(f"{v:.4f}" for v in BBOX_LL),
        "prodFormats": "LAS,LAZ",
        "max": 1000, "offset": 0,
    })
    url = f"{API}?{qs}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
            break
        except Exception as e:
            print(f"  TNM attempt {attempt+1}: {e}", file=sys.stderr)
            time.sleep(8 * (attempt + 1))
    else:
        raise SystemExit("TNM API not responding")
    return [it for it in j.get("items", [])
            if "PA_WesternPA_2019_D20" in (it.get("title") or "")]


def utm_centroid(item: dict, t: Transformer) -> tuple[float, float]:
    bb = item.get("boundingBox", {}) or {}
    cx_ll = 0.5 * (bb["minX"] + bb["maxX"])
    cy_ll = 0.5 * (bb["minY"] + bb["maxY"])
    return t.transform(cx_ll, cy_ll)


def name_of(item: dict) -> str:
    u = item.get("downloadURL") or ""
    return u.rsplit("/", 1)[-1]


def is_adjacent(cx: float, cy: float, selected: list[tuple[float, float]]) -> bool:
    """4-connectivity: within TILE_M (with tolerance) of an already-selected tile."""
    for sx, sy in selected:
        dx = abs(cx - sx); dy = abs(cy - sy)
        if (dx <= TILE_M + ADJ_TOL and dy <= ADJ_TOL) or \
           (dy <= TILE_M + ADJ_TOL and dx <= ADJ_TOL):
            return True
    return False


def download_one(url: str, dest: Path, expected: int) -> tuple[str, str]:
    if dest.exists() and (expected == 0 or dest.stat().st_size == expected):
        return ("skip", dest.name)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
            while True:
                buf = r.read(1 << 20)
                if not buf: break
                f.write(buf)
        tmp.rename(dest)
        return ("ok", dest.name)
    except Exception as e:
        return ("err", f"{dest.name}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="plan only, no download")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--n", type=int, default=20, help="new tiles to add")
    args = ap.parse_args()

    items = tnm_list_d20()
    print(f"TNM returned {len(items)} D20 tiles for Oil Creek SP bbox")

    t = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    by_name: dict[str, dict] = {}
    centroids: dict[str, tuple[float, float]] = {}
    for it in items:
        nm = name_of(it)
        if not nm: continue
        by_name[nm] = it
        centroids[nm] = utm_centroid(it, t)

    seed_names = sorted(EXISTING & set(by_name))
    if len(seed_names) < 1:
        print("ERROR: seed tiles not in TNM result set", file=sys.stderr)
        return 1
    seed_centroids = [centroids[n] for n in seed_names]
    seed_cx = sum(c[0] for c in seed_centroids) / len(seed_centroids)
    seed_cy = sum(c[1] for c in seed_centroids) / len(seed_centroids)
    print(f"seed: {len(seed_names)} tile(s)  centroid UTM17N = ({seed_cx:.0f}, {seed_cy:.0f})")
    for n in seed_names: print(f"  seed  {n}  cx,cy = {centroids[n]}")

    selected_names: list[str] = list(seed_names)
    selected_centroids: list[tuple[float, float]] = list(seed_centroids)
    new_picks: list[str] = []
    while len(new_picks) < args.n:
        candidates = []
        for nm, c in centroids.items():
            if nm in selected_names: continue
            if not is_adjacent(c[0], c[1], selected_centroids): continue
            d2 = (c[0] - seed_cx) ** 2 + (c[1] - seed_cy) ** 2
            candidates.append((d2, nm, c))
        if not candidates:
            print(f"  no more adjacent candidates after {len(new_picks)} picks")
            break
        candidates.sort(key=lambda kv: kv[0])
        d2, nm, c = candidates[0]
        new_picks.append(nm)
        selected_names.append(nm); selected_centroids.append(c)
        d = d2 ** 0.5
        print(f"  +{len(new_picks):2d}  {nm}  d_seed_centroid={d:6.0f} m")

    total_bytes = sum(int(by_name[n].get("sizeInBytes", 0) or 0) for n in new_picks)
    print(f"\n{len(new_picks)} new tiles  {total_bytes/1e9:.2f} GB")
    print(f"final patch size: {len(selected_names)} tiles "
          f"({len(seed_names)} seed + {len(new_picks)} new)")

    # Write the plan files
    out_dir = ROOT / "data" / "external" / "oil_creek"
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_txt = out_dir / "contiguous_20_plan.txt"
    plan_txt.write_text("\n".join(by_name[n]["downloadURL"] for n in new_picks) + "\n")
    print(f"wrote {plan_txt}")

    if args.list:
        return 0

    print(f"\ndownloading to {DEST} ...")
    DEST.mkdir(parents=True, exist_ok=True)
    jobs = []
    for n in new_picks:
        it = by_name[n]
        url = it.get("downloadURL")
        if not url: continue
        sz = int(it.get("sizeInBytes", 0) or 0)
        jobs.append((url, DEST / n, sz))
    ok = skip = err = 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(download_one, u, d, s) for u, d, s in jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            status, msg = fut.result()
            if status == "ok": ok += 1
            elif status == "skip": skip += 1
            else: err += 1; print(f"  ERR {msg}")
            if i % 4 == 0 or i == len(futs):
                print(f"  [{i}/{len(futs)}]  ok={ok} skip={skip} err={err}  "
                      f"elapsed={time.time()-t0:.0f}s")
    print(f"\nDONE  ok={ok} skip={skip} err={err}  in {time.time()-t0:.0f}s")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""Fetch USGS 3DEP LAZ tiles covering the McKean (mkf/mk5) and 9-tile (9t)
study areas in Pennsylvania.

Source projects (verified against existing build scripts):
  mkf / mk5  → PA_Northcentral_2019_B19
  9t         → PA_WesternPA_2019_D20

Total: ~6.1 GB across 128 tiles.

Idempotent: skips files already present at the destination with matching size.
"""
import argparse
import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import ROOT

OUT_BASE = ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz"
OUT_BASE.mkdir(parents=True, exist_ok=True)

API = "https://tnmaccess.nationalmap.gov/api/v1/products"

TARGETS = {
    "mkf": dict(
        bbox=(-78.6359, 41.9326, -78.5119, 42.0201),
        wanted_project="PA_Northcentral_2019_B19",
    ),
    "9t": dict(
        bbox=(-79.5687, 41.4797, -79.5139, 41.5195),
        wanted_project="PA_WesternPA_2019_D20",
    ),
}


def list_tiles(bbox, wanted_project):
    url = (f"{API}?datasets=Lidar%20Point%20Cloud%20(LPC)"
           f"&bbox={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
           f"&prodFormats=LAS,LAZ&max=500&offset=0")
    d = json.load(urllib.request.urlopen(url, timeout=60))
    pat = re.compile(r"USGS Lidar Point Cloud (\S+)")
    keep = []
    for it in d["items"]:
        m = pat.search(it.get("title", ""))
        if not m or m.group(1) != wanted_project:
            continue
        keep.append({
            "title": it.get("title"),
            "url": it.get("downloadURL"),
            "size": int(it.get("sizeInBytes", 0)),
        })
    return keep


def download_one(url, dest, expected_size, retries=5, chunk=1 << 20):
    if dest.exists() and dest.stat().st_size == expected_size and expected_size > 0:
        return ("skip", dest.name)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    buf = r.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
            tmp.rename(dest)
            return ("ok", dest.name)
        except Exception as e:
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    return ("err", f"{dest.name}: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--targets", nargs="+", default=list(TARGETS.keys()))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = []
    for key in args.targets:
        spec = TARGETS[key]
        tiles = list_tiles(spec["bbox"], spec["wanted_project"])
        dest_dir = OUT_BASE / spec["wanted_project"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        total = sum(t["size"] for t in tiles)
        print(f"[{key}] {spec['wanted_project']}: {len(tiles)} tiles  {total/1e9:.2f} GB"
              f"  -> {dest_dir}", flush=True)
        for t in tiles:
            fname = t["url"].rsplit("/", 1)[-1]
            jobs.append((t["url"], dest_dir / fname, t["size"]))

    grand = sum(s for _, _, s in jobs)
    print(f"\nTotal jobs: {len(jobs)}  ({grand/1e9:.2f} GB)", flush=True)

    if args.dry_run:
        for url, dest, sz in jobs[:5]:
            print(f"  would fetch: {dest.name}  ({sz/1e6:.0f} MB)")
        print("  ... (dry-run)")
        return

    t0 = time.time()
    n_ok = n_skip = n_err = 0
    done_bytes = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(download_one, u, d, s) for u, d, s in jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            status, msg = fut.result()
            if status == "ok":
                n_ok += 1
            elif status == "skip":
                n_skip += 1
            else:
                n_err += 1
                print(f"  ERR {msg}", flush=True)
            # rough progress: by job index, not by bytes
            if i % 10 == 0 or i == len(futs):
                el = time.time() - t0
                print(f"  [{i:4d}/{len(futs)}]  ok={n_ok} skip={n_skip} err={n_err}  "
                      f"elapsed={el:.0f}s", flush=True)
    print(f"\nDone: ok={n_ok} skip={n_skip} err={n_err}  in {(time.time()-t0):.0f}s")


if __name__ == "__main__":
    main()

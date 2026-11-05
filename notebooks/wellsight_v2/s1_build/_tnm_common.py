"""Shared helper for the USGS TNM Access API (3DEP lidar point cloud listing). METADATA ONLY.

query_all() pages through every result and reports an honest status.
  ok          every reported item was retrieved and the total was above zero
  empty       the call succeeded and the API reported zero items
  failed      a page failed after all retries (items retrieved so far are kept, never treated as empty)
  incomplete  the API reported more items than were retrieved
Fixes from the third review (2026-11-04). The old helpers capped each query at 200 items, turned repeated failure into an
empty result, and gave no way to tell either case from a true zero.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

API = "https://tnmaccess.nationalmap.gov/api/v1/products"
UA = {"User-Agent": "lidar-well-research/1.0"}
DS = "Lidar Point Cloud (LPC)"
PAGE = 200


def _get(params, tries=4):
    q = urllib.parse.urlencode(params)
    err = ""
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=90) as r:
                return json.loads(r.read()), ""
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (k + 1))
    return None, err


def query_all(bbox: str, q: str | None = None, dataset: str = DS, pause: float = 0.25):
    """Return dict(status, total, retrieved, pages, error, items). Pages with offset until all items are retrieved."""
    items, total, pages, err = [], None, 0, ""
    offset = 0
    while True:
        p = dict(datasets=dataset, bbox=bbox, max=PAGE, offset=offset, outputFormat="JSON")
        if q:
            p["q"] = q
        r, err = _get(p)
        if r is None:
            return dict(status="failed", total=total, retrieved=len(items), pages=pages, error=err, items=items)
        pages += 1
        total = r.get("total", 0)
        got = r.get("items", [])
        items += got
        offset += len(got)
        if not got or offset >= total:
            break
        time.sleep(pause)
    if total == 0:
        status = "empty"
    elif len(items) < total:
        status = "incomplete"
    else:
        status = "ok"
    return dict(status=status, total=total, retrieved=len(items), pages=pages, error="", items=items)

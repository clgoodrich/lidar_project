"""Repoint QGIS layer datasources without opening QGIS.

A `.qgz` is a ZIP holding one `.qgs` XML file. 57 of the 59 layers in
`qgis/wellsight.qgz` bind by RELATIVE path into `data/derivatives/`, so any data
move silently orphans them -- QGIS only complains the next time a human opens the
project. This rewrites those bindings from a mapping and repacks the archive.

    tools/rewrite_qgis_paths.py --map docs/qgis_repoint.csv          # dry run
    tools/rewrite_qgis_paths.py --map docs/qgis_repoint.csv --execute
    tools/rewrite_qgis_paths.py --audit          # just list every datasource

The map is CSV with `old_datasource,new_datasource`. Matching is on the datasource
text BEFORE the `|layername=` suffix, so a layer selector is preserved.

The original archive is copied to `wellsight_<stamp>.qgz.bak` before any write.
Nothing is deleted.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QGIS = ROOT / "qgis"
DS_RE = re.compile(r"(<datasource>)(.*?)(</datasource>)", re.S)


def load_map(p: Path) -> dict[str, str]:
    with open(p, encoding="utf8") as f:
        return {r["old_datasource"].strip(): r["new_datasource"].strip()
                for r in csv.DictReader(f)}


def process(qgz: Path, mapping: dict, execute: bool) -> int:
    with zipfile.ZipFile(qgz) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}
    qgs = [n for n in names if n.lower().endswith(".qgs")]
    if not qgs:
        print(f"  {qgz.name}: no .qgs inside")
        return 0
    key = qgs[0]
    xml = blobs[key].decode("utf8", errors="replace")

    hits = [0]

    def sub(m):
        head, body, tail = m.groups()
        raw = body.strip()
        base, sep, layer = raw.partition("|")
        base = base.strip()
        if base in mapping:
            hits[0] += 1
            new = mapping[base] + (sep + layer if sep else "")
            print(f"    {base}\n      -> {mapping[base]}")
            return head + new + tail
        return m.group(0)

    new_xml = DS_RE.sub(sub, xml)
    if not hits[0]:
        print(f"  {qgz.name}: no datasource matched the map")
        return 0
    if not execute:
        print(f"  {qgz.name}: {hits[0]} would change (dry run)")
        return hits[0]

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    bak = qgz.with_suffix(f".qgz.{stamp}.bak")
    shutil.copy2(qgz, bak)
    blobs[key] = new_xml.encode("utf8")
    tmp = qgz.with_suffix(".qgz.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.writestr(n, blobs[n])
    tmp.replace(qgz)
    print(f"  {qgz.name}: {hits[0]} rewritten, backup at {bak.name}")
    return hits[0]


def audit() -> None:
    for qgz in sorted(QGIS.glob("*.qgz")):
        with zipfile.ZipFile(qgz) as z:
            n = [x for x in z.namelist() if x.lower().endswith(".qgs")][0]
            xml = z.read(n).decode("utf8", errors="replace")
        print(f"\n=== {qgz.name} ===")
        for i, m in enumerate(DS_RE.finditer(xml), 1):
            raw = m.group(2).strip()
            base = raw.partition("|")[0].strip()
            if not base or base.lower().startswith(("crs=", "http", "type=")):
                continue
            target = (qgz.parent / base).resolve()
            inside = ROOT in target.parents
            ok = target.exists()
            flag = "OK " if ok else "MISSING"
            scope = "" if inside else "  <-- OUTSIDE REPO"
            print(f"  [{flag}] {base}{scope}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", type=Path)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()
    if a.audit:
        audit()
        return 0
    if not a.map:
        ap.error("--map is required unless --audit")
    mapping = load_map(a.map)
    print(f"{len(mapping)} repoint rules "
          f"({'EXECUTE' if a.execute else 'DRY RUN'})")
    total = 0
    for qgz in sorted(QGIS.glob("*.qgz")):
        print(f"  {qgz.name}")
        total += process(qgz, mapping, a.execute)
    print(f"\n{total} datasources {'rewritten' if a.execute else 'would change'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

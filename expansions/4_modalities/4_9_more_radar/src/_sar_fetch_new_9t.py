"""S2 of framework 4.9. Resumable, logged fetch of approved SAR products from a manifest. Run only after the user approves cost.

Purpose. For each manifest row, download url to data/_source/sar_new/<sensor>/<filename> with HTTP Range resume
(a .part file grows until complete), check size and SHA-256 when the manifest gives them, and append to a fetch log.
A complete file whose hash matches is skipped. Each source has its own folder. Downloaded files are data. No script
from a download is ever run. --dry-run lists what would be fetched and stops. Vendor portals that need a login are
fetched by the user. Put those files in the folder and the script verifies them.
Inputs.
  expansions/4_modalities/4_9_more_radar/data/raw/sar_fetch_manifest.csv (assumed, schema in config_4_9.json)
Outputs.
  data/_source/sar_new/<sensor>/<filename>  (ignored by data/_source/**)
  data/_source/sar_new/sar_fetch_log.csv    one row per attempt (time, file, status, bytes, sha256)
Run.
  python expansions/4_modalities/4_9_more_radar/src/_sar_fetch_new_9t.py [--manifest CSV] [--dest DIR] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

import _sar_kit_4_9 as sk


def verify(path: Path, sha: str | None, nbytes) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if nbytes is not None and not pd.isna(nbytes) and path.stat().st_size != int(nbytes):
        return False, f"size {path.stat().st_size} != {int(nbytes)}"
    h = sk.ek.sha256(path)
    if sha and not pd.isna(sha) and h != str(sha).lower():
        return False, "sha256 mismatch"
    return True, h


def download(url: str, dst: Path, chunk: int = 1 << 20, timeout: int = 120) -> None:
    import requests
    part = dst.with_suffix(dst.suffix + ".part")
    have = part.stat().st_size if part.exists() else 0
    hdr = {"Range": f"bytes={have}-"} if have else {}
    with requests.get(url, headers=hdr, stream=True, timeout=timeout) as r:
        if r.status_code == 200 and have:
            have = 0                       # server ignored Range, start over
        r.raise_for_status()
        with open(part, "ab" if have else "wb") as f:
            for b in r.iter_content(chunk):
                f.write(b)
    part.replace(dst)


def main(argv=None) -> int:
    cfg = sk.load_cfg()
    spec = cfg["inputs"]["fetch_manifest"]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    mp = sk.need(Path(a.manifest) if a.manifest else sk.resolve(spec), "SAR fetch manifest", spec)
    man = pd.read_csv(mp)
    miss = [c for c in spec["schema"] if c not in man.columns]
    if miss:
        raise ValueError(f"{mp} lacks {miss}")
    sk.ek.assert_unique(man.assign(k=man.sensor + "/" + man.filename), "k")
    dest = Path(a.dest) if a.dest else sk.resolve(cfg["outputs"]["source"])
    log = []
    for r in man.itertuples():
        f = dest / str(r.sensor) / str(r.filename)
        ok, info = verify(f, r.sha256, r.bytes)
        if ok:
            status = "present, verified"
        elif a.dry_run:
            status = f"would fetch ({info})"
        else:
            f.parent.mkdir(parents=True, exist_ok=True)
            try:
                download(str(r.url), f)
                ok, info = verify(f, r.sha256, r.bytes)
                status = "fetched, verified" if ok else f"fetched, FAILED check ({info})"
            except Exception as e:  # noqa: BLE001  logged, the run continues with the next file
                status = f"error {type(e).__name__}: {e}"[:200]
        log.append({"time": dt.datetime.now().isoformat(timespec="seconds"), "sensor": r.sensor, "file": str(f),
                    "status": status, "bytes": f.stat().st_size if f.exists() else 0, "sha256": info if ok else ""})
        print(f"{status:30s} {f}")
    lg = pd.DataFrame(log)
    if not a.dry_run:
        dest.mkdir(parents=True, exist_ok=True)
        lf = dest / "sar_fetch_log.csv"
        lg.to_csv(lf, mode="a", header=not lf.exists(), index=False)
        sk.prov(dest, "sar_fetch_new_9t", inputs=[mp], outputs=[Path(p) for p in lg.file], params={"n": len(man)})
    return 0 if all(s.startswith(("present", "fetched, verified", "would")) for s in lg.status) else 1


if __name__ == "__main__":
    raise SystemExit(main())

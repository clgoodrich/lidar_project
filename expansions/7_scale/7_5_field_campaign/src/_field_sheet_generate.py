"""Blind field sheets, the entry template and the codebook (7.5 S3).

Purpose
    One markdown sheet per sampled site plus one CSV entry template for the whole campaign.
    Sheets come from the blind sample only. They carry the site id, coordinates and the protocol.
    They never carry a model score, a record status, a stratum or an arm name. Searchers stay blind.
    Safety comes first on every sheet. Screen for methane before approaching any suspected open well.
    The codebook lists every allowed code for outcome, identity status, access and evidence.
    Identity status is recorded separately from outcome (protocol section 6). Steel alone is not
    identity. A negative search of unknown sensitivity is not a definite non-well.

Inputs
    results/tables/field_sample_blind_v1.csv (from _field_sample_draw_frames.py), config_7_5.json
Outputs (expansions/7_scale/7_5_field_campaign/results/field_sheets_v1/)
    sheet_<site_id>.md, field_entry_template_v1.csv, field_codebook_v1.json, field_waypoints_v1.gpx

Run
    python expansions/7_scale/7_5_field_campaign/src/_field_sheet_generate.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _field_sample_draw_frames import CFG, ek, load_cfg, need  # noqa: E402

ENTRY_COLUMNS = ["site_id", "visit_id", "search_round", "searcher_id", "date", "access", "gnss_x", "gnss_y",
                 "gnss_datum", "gnss_accuracy_m", "search_radius_m", "search_minutes", "methane_screen_ppm",
                 "magnetometer_done", "magnetic_anomaly", "evidence_codes", "outcome", "identity",
                 "identity_basis", "photos", "blind_confirmed", "notes"]
FORBIDDEN_ON_SHEET = ("score", "stratum", "arm", "record", "permit", "dep_id", "era", "controls")

SHEET = """# Field sheet {site_id}

Evidence produced here can be level (c) steel anomaly or level (d) confirmed well. Nothing else on this sheet is a claim.

## Safety first
- Screen for methane before approaching any suspected open well. Stop and back off above the action level in the safety plan.
- Do not enter cellars or open excavations. Do not touch valves or casing.

## Site
- Site id {site_id}
- Target position {x:.2f} E, {y:.2f} N ({datum}). Longitude {lon:.7f}, latitude {lat:.7f}
- Search mode. {mode}

## Protocol
1. Record access status first. If you cannot reach the site, record why and stop. The site still counts.
2. Navigate to the target. Record your GNSS position, datum and accuracy (target {acc} m or better).
3. Search as the search mode says. Do not stop early when you find something.
4. Methane screen at the target before approach{mag}.
5. Tick every evidence code seen. Photograph each one with a scale.
6. Record the outcome and, separately, the identity status with its basis.

## Evidence codes (tick all seen)
{evidence}

## Outcome (one)
{outcome}

## Identity status (one, separate from outcome)
- confirmed_well. Visible wellhead, casing, wellbore access, or an agency record tied by on-site evidence
- definite_non_well. Another feature positively identified (write which in identity_basis)
- ambiguous. Anything else, including steel only, nothing found, unresolved and inaccessible

## Searcher
- Searcher id ______  Date ______  Visit id ______  Search round (1 first, 2 independent repeat) ______
- Notes
"""


def codebook(cfg: dict) -> dict:
    c = cfg["codes"]
    return {"version": "field_codebook_v1", "columns": ENTRY_COLUMNS, "outcome": c["outcome"], "identity": c["identity"],
            "access": c["access"], "evidence": c["evidence"],
            "rules": ["identity is recorded separately from outcome",
                      "steel_anomaly_only never gives identity confirmed_well",
                      "nothing_found with unknown search sensitivity is ambiguous, not definite_non_well",
                      "an inaccessible sampled site stays in the frame as ambiguous",
                      "search_round 2 is an independent repeat by a second searcher blind to round 1"]}


def write_sheets(blind: pd.DataFrame, cfg: dict, out: Path) -> list[Path]:
    bad = [c for c in blind.columns if any(f in c.lower() for f in FORBIDDEN_ON_SHEET)]
    if bad:
        raise AssertionError(f"blind sample carries unblinding columns {bad}")
    out.mkdir(parents=True, exist_ok=True)
    p = cfg["protocol"]
    cb = codebook(cfg)
    paths = []
    order = blind.sample(frac=1.0, random_state=cfg["master_seed"] % (2**32))    # visit order hides arm
    for _, r in order.iterrows():
        cell = float(r.get("area_m2", 0) or 0) >= 0.5 * cfg["arm_C"]["cell_m"] ** 2
        mode = (f"Area search. Walk the whole {cfg['arm_C']['cell_m']:.0f} m cell centred on the target in transects"
                if cell else f"Point search. Search a {p['search_radius_m']:.0f} m radius for {p['search_minutes']} minutes")
        txt = SHEET.format(site_id=r["site_id"], x=r["x"], y=r["y"], lon=r["lon"], lat=r["lat"], mode=mode,
                           datum=p["datum"], acc=p["gnss_accuracy_m"], radius=p["search_radius_m"], minutes=p["search_minutes"],
                           mag=". Run one magnetometer pass over the search area" if p["magnetometer_pass"] else "",
                           evidence="\n".join(f"- [ ] {e}" for e in cb["evidence"]),
                           outcome="\n".join(f"- [ ] {o}" for o in cb["outcome"]))
        fp = out / f"sheet_{r['site_id']}.md"
        fp.write_text(txt, encoding="utf-8")
        paths.append(fp)
    tmpl = pd.DataFrame({c: [] for c in ENTRY_COLUMNS})
    tmpl = pd.concat([tmpl, pd.DataFrame({"site_id": order["site_id"]})], ignore_index=True)
    tmpl.to_csv(out / "field_entry_template_v1.csv", index=False)
    (out / "field_codebook_v1.json").write_text(json.dumps(cb, indent=2), encoding="utf-8")
    wpt = "".join(f'<wpt lat="{r.lat:.7f}" lon="{r.lon:.7f}"><name>{escape(r.site_id)}</name></wpt>' for r in order.itertuples())
    (out / "field_waypoints_v1.gpx").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="field sheets" '
                                                'xmlns="http://www.topografix.com/GPX/1/1">' + wpt + "</gpx>\n", encoding="utf-8")
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="7.5 S3 blind field sheets.")
    ap.add_argument("--config", default=str(CFG))
    ap.add_argument("--blind", default=str(ek.sub("7.5", "results/tables") / "field_sample_blind_v1.csv"))
    ap.add_argument("--out", default=str(ek.sub("7.5", "results/field_sheets_v1")))
    a = ap.parse_args(argv)
    try:
        blind = pd.read_csv(need(Path(a.blind), "blind sample (run _field_sample_draw_frames.py)"))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    # arm, pi and weight would reveal the arm or the stratum. The sheet keeps only the search mode.
    blind = blind.drop(columns=[c for c in ("arm", "pi", "weight") if c in blind.columns])
    paths = write_sheets(blind, load_cfg(Path(a.config)), Path(a.out))
    print(f"{len(paths)} sheets in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

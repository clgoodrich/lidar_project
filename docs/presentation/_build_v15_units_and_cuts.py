"""v14 -> v15: hectares out, one slide out, one title made to mean something.

1. HECTARES REPLACED
--------------------
A hectare is 10,000 m2, and almost nobody carries that conversion. Pads are big
enough for km2; pits are small enough that m2 is the natural unit and a hectare
would round them into mush.

    995 well pads, 144.4 ha   ->   1.44 km2
    723 pit outlines, 14.84 ha ->  148,400 m2
    712 pit floors, 2.29 ha    ->   22,900 m2

Straight conversions, not recalculations: 1 ha = 10,000 m2 exactly, so the
figures mean precisely what they meant before. That matters because the "pit
outlines" layer does not reconcile cleanly with any single layer in the
annotation geopackage -- 723 outlines at 14.84 ha is neither `pit_full` (841,
17.72 ha) nor `pit_inside` (714, 2.30 ha) -- so recomputing from the source
risks changing the meaning of the line rather than just its units.

2. SLIDE "are the discarded returns any good?" REMOVED
------------------------------------------------------
Requested. Its point is carried anyway: slide 12 already shows what the cut
cost, and the accuracy claim survives in the speaker notes of the cut slide.

3. "where the ground stops" RETITLED
-------------------------------------
The old title reads like a fact about terrain. The slide is about a threshold
in the vendor's PROCESSING: past 18 degrees of scan angle, nothing was
classified as ground at all. The new title says that.

Run:
    python docs/presentation/_build_v15_units_and_cuts.py
Reads:  docs/presentation/WellSight_Presentation v14.pptx
Writes: docs/presentation/WellSight_Presentation v15.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/presentation/WellSight_Presentation v14.pptx"
DST = ROOT / "docs/presentation/WellSight_Presentation v15.pptx"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

DROP_TITLE = "Data QA — are the discarded returns any good?"
OLD_TITLE = "Data QA — where the ground stops"
NEW_TITLE = "Data QA — nothing past 18° was called ground"

REWORD = {
    "995 well pads, 144.4 ha in total":
        "995 well pads, 1.44 km² in total",
    "•  9t 115.2 ha   |   613590 0.0 ha   |   elsewhere 29.3 ha":
        "•  9t 1.15 km²   |   613590 none drawn   |   elsewhere "
        "0.29 km²",
    "723 pit outlines, 14.84 ha":
        "723 pit outlines, 148,400 m²",
    "•  9t 9.7 ha   |   613590 1.0 ha   |   elsewhere 4.2 ha":
        "•  9t 97,000 m²   |   613590 10,000 m²   |   elsewhere "
        "42,000 m²",
    "•  586 pair with a floor, giving 9.91 ha of measurable wall":
        "•  586 pair with a floor, giving 99,100 m² of measurable wall",
    "712 pit floors, 2.29 ha":
        "712 pit floors, 22,900 m²",
    "•  9t 1.5 ha   |   613590 0.6 ha   |   elsewhere 0.3 ha":
        "•  9t 15,000 m²   |   613590 6,000 m²   |   elsewhere "
        "3,000 m²",
    "Ground classification falls off a cliff at one exact angle.":
        "The survey classified no ground at all past 18° of scan angle.",
}

NOTE_FOR_RETITLED = (
    "Scan angle is how far off straight-down the laser was pointing when it "
    "fired. The laser sweeps side to side under the aircraft, so pulses at the "
    "edge of the swath have the highest angles.\n\n"
    "The chart plots how often a return that reached the ground was actually "
    "labelled ground, against that angle.\n\n"
    "From 0 to about 13 degrees it is 97 to 98 percent. It tapers to 88 by "
    "17.5. At 18.5 and beyond it is zero.\n\n"
    "Not a decline, a wall. A clean vertical edge at a round number is a "
    "setting in someone's processing software, never a property of the "
    "physics.\n\n"
    "The accuracy question comes up here, so have the answer ready: the "
    "discarded returns were checked against ground from neighbouring flight "
    "lines and came back at 6.5 to 6.7 cm RMSE, against 7.0 to 9.9 cm for the "
    "wide-angle returns the survey kept. Both sit inside the 10 cm the "
    "specification allows. The deleted data is as good as the data that "
    "stayed.")


def title_of(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def replace_line(slide, old, new) -> bool:
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        for p in sh.text_frame.paragraphs:
            if p.text.strip() != old.strip():
                continue
            runs = list(p.runs)
            if not runs:
                continue
            runs[0].text = new
            for r in runs[1:]:
                r._r.getparent().remove(r._r)
            return True
    return False


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"missing: {SRC}")
    prs = Presentation(SRC)
    before = len(prs.slides)

    # ---- 1. units and wording ------------------------------------------
    hits = {k: 0 for k in REWORD}
    for s in prs.slides:
        for old, new in REWORD.items():
            if replace_line(s, old, new):
                hits[old] += 1
    missed = [k for k, v in hits.items() if v == 0]
    if missed:
        raise SystemExit("not found, so the deck has moved:\n  "
                         + "\n  ".join(missed))
    print(f"  rewrote {sum(hits.values())} line(s)")

    # ---- 2. retitle ------------------------------------------------------
    tgt = next((s for s in prs.slides if title_of(s).strip() == OLD_TITLE),
               None)
    if tgt is None:
        raise SystemExit(f"could not find {OLD_TITLE!r}")
    if not replace_line(tgt, OLD_TITLE, NEW_TITLE):
        raise SystemExit("title paragraph not replaced")
    tgt.notes_slide.notes_text_frame.text = NOTE_FOR_RETITLED
    print(f"  retitled -> {NEW_TITLE!r}")

    # ---- 3. drop the slide ----------------------------------------------
    doomed = [s for s in prs.slides if title_of(s).strip() == DROP_TITLE]
    if len(doomed) != 1:
        raise SystemExit(f"expected one {DROP_TITLE!r}, found {len(doomed)}")
    lst = prs.slides._sldIdLst
    for sid in list(lst):
        if prs.part.rels[sid.get(RID)].target_part is doomed[0].part:
            lst.remove(sid)
            prs.part.drop_rel(sid.get(RID))
            break
    print(f"  dropped {DROP_TITLE!r}")

    prs.save(DST)

    out = Presentation(DST)
    import re
    left = []
    for i, s in enumerate(out.slides, 1):
        for sh in s.shapes:
            if sh.has_text_frame and re.search(r"\bha\b|hectare",
                                               sh.text_frame.text):
                left.append(i)
    print(f"\n  {before} -> {len(out.slides)} slides")
    print(f"  slides still mentioning hectares: {sorted(set(left))}")
    print(f"  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

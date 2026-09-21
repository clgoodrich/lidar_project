"""v13 (the user's edited copy) -> v14: drop the QC slide, correct two claims.

v13 ON DISK IS THE USER'S FILE, NOT MINE
----------------------------------------
It was edited by hand after I built it -- 82 slides now, with a new opener at
slide 9, "Data QA - something is wrong here". So this reads v13 and writes v14
rather than editing in place. Nothing of theirs is overwritten.

WHAT CHANGES, AND WHY EACH ONE
------------------------------

1. SLIDE 50, "Annotation Quality Control", is removed. Requested, and the
   evidence supports it. The work was real -- `_pit_morphology_audit_1m.py`
   with a 856-row output -- but it ran in April against a different annotation
   set ("updated 861 pits"), lives in `archive/` on the pre-reorganisation
   path layout, covered tiles 9t/mk5/mk/mkf rather than this deck's, and has
   no iteration write-up. The annotations were rebuilt ann527 -> ann712 on
   2026-09-04 with the split reassigned, so the QC predates everything the
   deck's models were trained on. The slide's closing line, "before any model
   is trained on them", was therefore not true of this pipeline.

2. THE VENDOR-ONLY DISCLOSURE. `_build_derivatives.py` filters
   `Classification[2:2]`, so the derivative stack every model reads is built
   from the vendor's ground alone. Confirmed against the data, not just the
   code: over a window where the recovered returns fill many voids, the
   training DEM is identical to the vendor-only DEM in 100.0% of cells and
   differs from the vendor-plus-recovered DEM in 40.8%.

   Four slides currently read as though the restoration is in the pipeline:

       19  "the discarded returns added back"
       20  "We add ground where it had none."
       21  "the same ground with the deleted returns restored"
       22  "The restored data does not rewrite the survey. It finishes it."

   Every one is true of the experiment and false of the pipeline. Each is
   reworded to past-experiment, and slide 22 gains an explicit closing line
   saying the detection results are built on vendor ground alone.

3. THE OUTCOME COUNTS. Slides 62 and 63 pair an all-areas annotation count
   with a rate measured on 9t only:

       drawn everywhere      714 pit floors, 995 pads
       inside 9t             503 pits, 650 pads
       n_gt in the CV file   470 pits, 650 pads
       single test split      91 pits,  95 pads

   The slide shows the largest of these. Rather than substitute a number whose
   provenance is still unsettled -- the deck's 0.928 matches none of the CV5
   fold means -- the count is replaced with the scope it was measured on. That
   is true regardless of which evaluation produced the rate.

WHAT IS DELIBERATELY NOT CHANGED
--------------------------------
The slope figure offered for the "does the surface move" slide, and anything
about the cross-validation story, because the source of the headline 0.928 is
still unresolved and guessing at it would replace one wrong number with
another.

Run:
    python docs/presentation/_build_v14_from_user_v13.py
Reads:  docs/presentation/WellSight_Presentation v13.pptx
Writes: docs/presentation/WellSight_Presentation v14.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/presentation/WellSight_Presentation v13.pptx"
DST = ROOT / "docs/presentation/WellSight_Presentation v14.pptx"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

INK2 = RGBColor(0x54, 0x5C, 0x63)

DROP_TITLE = "Annotation Quality Control"

#: exact paragraph text -> replacement. Matched on the stripped line so a
#: bullet marker or trailing space cannot cause a silent miss.
REWORD = {
    "•  Bottom: the discarded returns added back. 2%.":
        "•  Bottom: the same line with the discarded returns added back. 2%.",
    "Where the vendor had ground we agree with it. We add ground where it had none.":
        "Where the vendor had ground we agreed with it. Adding ground where it "
        "had none was tested, not adopted.",
    "•  Right: the same ground with the deleted returns restored":
        "•  Right: the same ground rebuilt with the deleted returns put back",
    "•  The restored data does not rewrite the survey. It finishes it.":
        "•  Putting them back does not rewrite the survey — it only fills "
        "what was never measured",
    "995 pads  ·  recall 0.912  ·  precision 0.587  ·  flags 11.6%":
        "held-out blocks on 9t  ·  recall 0.912  ·  precision 0.587  ·  "
        "flags 11.6%",
    "712 pits  ·  recall 0.928  ·  precision 0.633  ·  flags 0.21%":
        "held-out blocks on 9t  ·  recall 0.928  ·  precision 0.633  ·  "
        "flags 0.21%",
}

#: appended to the data-QA closing slide
DISCLOSURE = ("•  None of this is in the detection pipeline yet — "
              "every result in this talk is built on the vendor's ground alone")
DISCLOSURE_ON = "Data QA — does the surface actually move?"

NOTE_ADD = (
    "\n\nOne thing to say plainly if anyone asks whether this reprocessing is "
    "in use. It is not. Every detection number in this talk -- pits, pads, "
    "roads, the second tile, the architecture comparison -- is built from the "
    "vendor's ground classification alone. The derivative builder keeps class "
    "2 only, and the training DEM is identical to the vendor-only DEM cell for "
    "cell.\n\n"
    "So this section is a finding about the delivery and a measured "
    "opportunity, not a change to the method. That is a stronger position than "
    "implying otherwise and being caught.")


def title_of(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"missing: {SRC}")
    prs = Presentation(SRC)
    before = len(prs.slides)

    # ---- 1. reword, before anything is deleted -------------------------
    hits = {k: 0 for k in REWORD}
    for s in prs.slides:
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                key = p.text.strip()
                if key not in REWORD:
                    continue
                runs = list(p.runs)
                if not runs:
                    continue
                runs[0].text = REWORD[key]
                for r in runs[1:]:
                    r._r.getparent().remove(r._r)
                hits[key] += 1

    missed = [k for k, v in hits.items() if v == 0]
    if missed:
        raise SystemExit("these lines were not found, so the deck has moved "
                         "under this script:\n  " + "\n  ".join(missed))
    print(f"  reworded {sum(hits.values())} line(s) across "
          f"{len([k for k in hits if hits[k]])} distinct claims")

    # ---- 2. the disclosure line ----------------------------------------
    tgt = next(s for s in prs.slides
               if title_of(s).strip() == DISCLOSURE_ON)
    texts = [sh for sh in tgt.shapes
             if sh.has_text_frame and sh.text_frame.text.strip()]
    title_sh = min(texts, key=lambda s: s.top if s.top is not None else 0)
    body = max((sh for sh in texts if sh is not title_sh),
               key=lambda sh: sh.height)
    tf = body.text_frame
    last = tf.paragraphs[-1]
    p = tf.add_paragraph()
    p.alignment = PP_ALIGN.LEFT
    p.space_after = last.space_after
    r = p.add_run()
    r.text = DISCLOSURE
    src_run = last.runs[0] if last.runs else None
    r.font.size = src_run.font.size if src_run else Pt(13)
    r.font.bold = True
    r.font.color.rgb = INK2
    r.font.name = "Calibri"
    if tgt.has_notes_slide:
        ntf = tgt.notes_slide.notes_text_frame
        ntf.text = ntf.text.rstrip() + NOTE_ADD
    print(f"  added the vendor-only disclosure to {DISCLOSURE_ON!r}")

    # ---- 3. drop the QC slide ------------------------------------------
    doomed = [s for s in prs.slides if title_of(s).strip() == DROP_TITLE]
    if len(doomed) != 1:
        raise SystemExit(f"expected one {DROP_TITLE!r} slide, found "
                         f"{len(doomed)}")
    lst = prs.slides._sldIdLst
    for sid in list(lst):
        if prs.part.rels[sid.get(RID)].target_part is doomed[0].part:
            lst.remove(sid)
            prs.part.drop_rel(sid.get(RID))
            break
    print(f"  dropped {DROP_TITLE!r}")

    prs.save(DST)
    out = Presentation(DST)
    still = [i for i, s in enumerate(out.slides, 1)
             if title_of(s).strip() == DROP_TITLE]
    print(f"\n  {before} -> {len(out.slides)} slides")
    print(f"  {DROP_TITLE!r} remaining: {still}")
    print(f"  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

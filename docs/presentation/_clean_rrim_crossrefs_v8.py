"""Remove the last canopy-height references from the RRIM slides.

Deleting "Two different stripes, one nickname" left two dangling references
behind it:

  slide 31 kicker  "The second kind: stripes in ground we actually measured"
                   -- there is no longer a first kind on screen, so "second"
                   points at nothing.

  slide 33 notes   "It does not delete these stripes the way it deletes the
                   canopy holes" -- argues the RRIM case using the canopy
                   case, which is exactly what the split was for.

Both are rewritten to stand on their own evidence. The RRIM slides now say
what they need to say without borrowing a canopy-height fact, and the canopy
slides never mention the RRIM.

Run:
    python docs/presentation/_clean_rrim_crossrefs_v8.py
Writes (in place):
    docs/presentation/WellSight_Presentation v8.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "docs/presentation/WellSight_Presentation v8.pptx"

OLD_KICKER = "The second kind: stripes in ground we actually measured"
NEW_KICKER = "Stripes in ground the survey did measure"

OLD_NOTE = ("It does not delete these stripes the way it deletes the canopy "
            "holes, because here there is nothing empty to fill.")
NEW_NOTE = ("It does not delete them, because there is nothing empty here to "
            "fill.")


def title_of(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def main() -> int:
    prs = Presentation(DECK)
    fixed = []

    for s in prs.slides:
        t = title_of(s)
        for sh in s.shapes:
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if OLD_KICKER in r.text:
                        r.text = r.text.replace(OLD_KICKER, NEW_KICKER)
                        fixed.append(f"{t!r}: kicker no longer says 'second kind'")
        if s.has_notes_slide:
            tf = s.notes_slide.notes_text_frame
            if OLD_NOTE in tf.text:
                tf.text = tf.text.replace(OLD_NOTE, NEW_NOTE)
                fixed.append(f"{t!r}: notes no longer cite the canopy holes")

    if not fixed:
        raise SystemExit("nothing matched -- has the deck already been cleaned?")

    prs.save(DECK)
    for f in fixed:
        print(f"  {f}")

    # prove it: no canopy word may survive on an RRIM slide, and no RRIM word
    # on a canopy slide
    out = Presentation(DECK)
    bad = []
    for i, s in enumerate(out.slides, 1):
        t = title_of(s).lower()
        body = " ".join(sh.text_frame.text for sh in s.shapes
                        if sh.has_text_frame).lower()
        note = (s.notes_slide.notes_text_frame.text.lower()
                if s.has_notes_slide else "")
        both = body + " " + note
        if "rrim" in t and ("canopy" in both):
            bad.append(f"slide {i} ({t[:40]}) mentions canopy")
        if "canopy" in t and ("rrim" in both):
            bad.append(f"slide {i} ({t[:40]}) mentions RRIM")
    print("\n  cross-references remaining:", len(bad))
    for b in bad:
        print("   ", b)
    print(f"  {DECK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

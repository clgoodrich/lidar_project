# -*- coding: utf-8 -*-
"""Move the deck off British spellings.

The deck drifted into -re, -our and -ise endings. This normalises them, on the
slides and in the speaker notes, leaving everything else alone.

ORDER MATTERS
-------------
"centred" is rewritten before "centre", because centre -> center applied to
"centred" gives "centerd". Every other pair here is safe in any order, and the
longer forms are handled by the shorter rule: centimetre, millimetre and
kilometre all contain "metre", so one rule covers them.

WHAT IS DELIBERATELY NOT TOUCHED
--------------------------------
Quoted material and published titles keep the spelling of their source. The
OpenTopography quotation on slide 38 and every reference title were checked and
contain no British spelling, so nothing here reaches them -- but if a quotation
is added later that does, it must be excluded rather than normalised, because
changing the spelling inside quotation marks misquotes the source.

Run standalone on any deck:
    python docs/presentation/_american_spellings.py "<deck.pptx>"
Or import `normalise_deck(prs)` and call it as the last step of a build.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: British -> American, applied in this order. Substring rules, so each one
#: also covers its own plurals and inflections.
PAIRS = [
    ("centred", "centered"),      # must precede "centre"
    ("centring", "centering"),    # same reason
    ("metre", "meter"),           # + centimetre, millimetre, kilometre
    ("centre", "center"),
    ("neighbour", "neighbor"),
    ("labelled", "labeled"),
    ("labelling", "labeling"),
    ("modelled", "modeled"),
    ("modelling", "modeling"),
    ("generalis", "generaliz"),
    ("vectoris", "vectoriz"),
    ("programme", "program"),
    ("colour", "color"),
    ("judgement", "judgment"),
    ("artefact", "artifact"),
    ("behaviour", "behavior"),
    ("analyse", "analyze"),
    ("recognis", "recogniz"),
    ("normalis", "normaliz"),
    ("whilst", "while"),
    ("grey", "gray"),
]


def _cap(word: str) -> str:
    return word[0].upper() + word[1:]


def fix(text: str) -> str:
    """Rewrite one string, preserving a leading capital."""
    for brit, amer in PAIRS:
        if brit in text:
            text = text.replace(brit, amer)
        cb = _cap(brit)
        if cb in text:
            text = text.replace(cb, _cap(amer))
    return text


def _frames(slide):
    for sh in slide.shapes:
        if sh.has_text_frame:
            yield sh.text_frame
    if slide.has_notes_slide:
        yield slide.notes_slide.notes_text_frame


def normalise_deck(prs) -> int:
    """Rewrite every run in place. Returns the number of runs changed.

    Runs rather than paragraphs, so the font, size and colour of each span
    survive. A word split across two runs by an editing accident would be
    missed, which is why the caller re-scans afterwards.
    """
    n = 0
    for slide in prs.slides:
        for tf in _frames(slide):
            for para in tf.paragraphs:
                for run in para.runs:
                    new = fix(run.text)
                    if new != run.text:
                        run.text = new
                        n += 1
    return n


def audit(prs):
    """Every British form still present after the pass, with its slide."""
    left = []
    for i, slide in enumerate(prs.slides, 1):
        for tf in _frames(slide):
            t = tf.text
            for brit, _ in PAIRS:
                if brit in t or _cap(brit) in t:
                    left.append((i, brit))
    return left


def main() -> int:
    from pptx import Presentation
    deck = Path(sys.argv[1])
    prs = Presentation(deck)
    n = normalise_deck(prs)
    left = audit(prs)
    prs.save(deck)
    print(f"  {n} runs rewritten in {deck.name}")
    if left:
        print("  STILL PRESENT (probably split across runs):")
        for i, b in sorted(set(left)):
            print(f"    slide {i}: {b}")
        return 1
    print("  no British spellings left")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

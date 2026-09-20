"""Give each presentation figure builder a BARE mode, and point it at v6/.

WHY
---
Every one of these builders draws a headline, a subtitle and a footnote INSIDE
the PNG. The deck already has a title, so on a slide that is a double title, and
the footnote lands at 11 pt where nobody reads it. The instruction was to get
that text off the graphics and into the slide's side column and speaker notes.

Rather than delete the chrome -- these figures are also used standalone in
docs/iterations, where the headline is the only thing naming them -- each call
is routed through a `_chrome()` shim that is a no-op when WELLSIGHT_BARE=1, and
in that mode the output goes to a `v6/` subdirectory. Default behaviour, and
every existing file on disk, is unchanged.

WHAT IS AND IS NOT SUPPRESSED
-----------------------------
Suppressed: the figure's own headline, its subtitle paragraph, and its footnote.
Kept: panel labels that tell two panels apart ("RRIM -- the terrain" against
"road probability"), axis labels, legends, scale bars. Removing those would not
be de-cluttering, it would be deleting the key.

This script is idempotent -- running it twice changes nothing the second time.

Run:
    python tools/add_bare_mode_to_figure_builders.py
    python tools/add_bare_mode_to_figure_builders.py --check
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs/presentation/figures_30to45min"
S7 = ROOT / "notebooks/wellsight_v2/s7_analysis"

HEADER = '''
# --- v6 bare mode -----------------------------------------------------------
# WELLSIGHT_BARE=1 suppresses this figure's own headline, subtitle and footnote
# and writes to a v6/ subdirectory. The deck supplies those words instead, in
# the slide's side column and its speaker notes. Added by
# tools/add_bare_mode_to_figure_builders.py.
import os as _os

BARE = _os.environ.get("WELLSIGHT_BARE") == "1"


def _chrome(_fn, *a, **k):
    """Draw slide chrome only when the figure has to stand on its own."""
    if not BARE:
        return _fn(*a, **k)
    return None


def _out(p):
    """Redirect an output directory into v6/ when building bare figures."""
    from pathlib import Path as _P
    p = _P(p)
    if BARE:
        p = p / "v6"
        p.mkdir(parents=True, exist_ok=True)
    return p
# ----------------------------------------------------------------------------
'''

#: file -> (anchor line to insert the header after,
#:          [(exact prefix to wrap, ...)],
#:          [(out-dir assignment, ...)])
PLAN = {
    FIG / "_build_preprocessing_figures.py": dict(
        wrap=['    fig.suptitle("Which rim belongs to which floor"',
              '    fig.suptitle("One split, shared by every task"'],
        wrap_text=[(188, '    fig.text(0.03, 0.885,'),
                   (277, '    fig.text(0.03, 0.885,'),
                   (350, '    fig.text(0.03, 0.022,')],
        outs=['OUT_A = ROOT / "docs/presentation/figures_30to45min/3_annotations"']),
    FIG / "_build_method_diagrams.py": dict(
        wrap=['    fig.suptitle("Two layers overlap on purpose.'],
        wrap_text=[(303, '    fig.text(0.018, 0.925,'),
                   (355, '    fig.text(0.018, 0.028,')],
        outs=['OUT_M = ROOT / "docs/presentation/figures_30to45min/4_model_building"',
              'OUT_A = ROOT / "docs/presentation/figures_30to45min/3_annotations"']),
    FIG / "_build_report_figures.py": dict(
        wrap=['        ax.set_title(title, fontsize=19',
              '    ax.set_title("The holes line up in stripes"'],
        wrap_text=[],
        outs=['OUT = Path(__file__).resolve().parent / "1_data_qa"']),
    FIG / "_build_rrim_vs_prob_compare.py": dict(
        wrap=[],
        wrap_text=[(239, '    fig.text(0.012, 0.014,')],
        outs=['OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "5_probability_surfaces"']),
    FIG / "_build_derivative_overview.py": dict(
        wrap=[],
        wrap_text=[(89, '    fig.text(0.012, 0.975,'),
                   (91, '    fig.text(0.012, 0.895,'),
                   (148, '    fig.text(0.012, 0.035,')],
        outs=[]),
    S7 / "_recovered_ground_maps_9t.py": dict(
        wrap=['    ax.set_title(title, fontsize=20',
              '    fig.suptitle("The same slice of ground, before and after"'],
        wrap_text=[(391, '    ax.text(0, 1.012, subtitle, transform=ax.transAxes'),
                   (438, '    ax.text(0.5, -0.022,'),
                   (458, '    ax.text(0.5, -0.022,'),
                   (477, '    ax.text(0.5, -0.022,')],
        outs=['OUT = ROOT / "data" / "9t" / "results" / "recovered_ground_9t"']),
    S7 / "_scan_angle_cliff_across_acquisitions.py": dict(
        wrap=['    ax[0].set_title("Of the returns that reached the ground'],
        wrap_text=[(466, '        fig.text(0.055, 0.018,')],
        outs=['OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "1_data_qa"']),
}


def wrap_call(text: str, prefix: str) -> tuple[str, int]:
    """Turn `<indent>obj.method(` into `<indent>_chrome(obj.method, `."""
    n = 0
    out = []
    for line in text.split("\n"):
        if line.startswith(prefix) and "_chrome(" not in line:
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]
            call, _, rest = stripped.partition("(")
            out.append(f"{indent}_chrome({call}, {rest}")
            n += 1
        else:
            out.append(line)
    return "\n".join(out), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    total = 0
    for path, plan in PLAN.items():
        if not path.exists():
            print(f"MISSING {path}")
            continue
        src = path.read_text(encoding="utf-8")
        orig = src
        n = 0

        if "def _chrome(" not in src:
            # insert after the last top-level import block
            # Skip the first line of a multi-line `from x import (` -- an
            # earlier version inserted the header inside the paren list and
            # broke the file.
            m = [x for x in re.finditer(r"^(?:from|import) .+$", src, re.M)
                 if x.group(0).count("(") == x.group(0).count(")")]
            at = m[-1].end() if m else 0
            src = src[:at] + "\n" + HEADER + src[at:]

        for pref in plan["wrap"]:
            src, k = wrap_call(src, pref)
            n += k
        for _ln, pref in plan["wrap_text"]:
            src, k = wrap_call(src, pref)
            n += k
        for assign in plan["outs"]:
            if assign in src and "_out(" not in assign:
                name, _, rhs = assign.partition(" = ")
                new = f"{name} = _out({rhs})"
                if new not in src:
                    src = src.replace(assign, new, 1)
                    n += 1

        if src != orig:
            total += n
            if not a.check:
                path.write_text(src, encoding="utf-8")
            print(f"{'would patch' if a.check else 'patched'} "
                  f"{path.relative_to(ROOT)}  ({n} sites)")
        else:
            print(f"unchanged   {path.relative_to(ROOT)}")
    print(f"\n{total} sites total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

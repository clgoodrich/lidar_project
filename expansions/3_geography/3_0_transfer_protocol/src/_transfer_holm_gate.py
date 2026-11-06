"""3.0 multiplicity. Holm correction over the declared PRIMARY gates of one expansion.

Purpose
    User default 2026-11-06 ("take defaults"). Each expansion declares its primary gates in its config
    (`multiplicity.family`). Only those are corrected and gated. Secondaries and sensitivities are reported and
    never gated. Undefined bootstrap draws are tolerated at share max_undefined 0 (any undefined draw gives an
    undefined p, which is inconclusive).
    One-sided bootstrap share. For a non-inferiority gate against minus the margin the share is the fraction of
    difference draws at or below minus the margin. For a superiority gate against a gain it is the fraction at
    or below the gain. A 95% two-sided percentile interval clears the bound exactly when this share is under
    0.025, so a family of one reproduces ek.decide.
    Holm. Sort the m shares, adjusted p_(i) = max over j <= i of min(1, (m - j + 1) p_(j)). An undefined share
    enters the family as 1 and stays undefined in the output.
    Verdict per gate. success if the Holm-adjusted share is below alpha / 2. failure if the unadjusted interval
    lies wholly beyond the bound (ek.decide gives failure). inconclusive otherwise. Failure is not corrected,
    because it never supports a transfer claim.
    Partial family. When only some members are scored, `holm_partial` gives success only if the share clears
    alpha / (2 m). That implies Holm success whatever the others show. Otherwise the gate waits for the family
    step (`family_gate` or this file's CLI).

Inputs
    library. CLI --inputs <score JSON> ... each holding a `holm_input` dict
    {gate, p_one_sided, lo, hi, bound_kind, margin, family, family_size}

Outputs
    CLI --out <json>  per gate p, Holm p, verdict, family, method

Run
    python expansions/3_geography/3_0_transfer_protocol/src/_transfer_holm_gate.py --inputs a.json b.json --out family.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "_shared" / "src"))
import expkit as ek  # noqa: E402

ALPHA = 0.05            # two-sided level of the fw_00 95% interval, one-sided share threshold alpha / 2
MAX_UNDEFINED = 0.0     # user default 2026-11-06. No tolerated undefined bootstrap draws
METHOD = "holm over declared primary gates (user default 2026-11-06)"


def one_sided_p(draws, margin: float, kind: str = "noninferiority", max_undefined: float = MAX_UNDEFINED) -> float:
    """Share of draws on the wrong side of the bound. NaN when the undefined share exceeds max_undefined."""
    if kind not in ("noninferiority", "superiority"):
        raise ValueError(kind)
    d = np.asarray(draws, float)
    und = ek.undefined_share(d)
    if d.size == 0 or und > max_undefined or und == 1.0:
        return float("nan")
    d = d[np.isfinite(d)]
    bound = -float(margin) if kind == "noninferiority" else float(margin)
    return float(np.mean(d <= bound))


def holm(pvals: dict) -> dict:
    """{gate: p} -> {gate: Holm-adjusted p}. NaN counts as 1 in the family and stays NaN."""
    names = list(pvals)
    m = len(names)
    if m == 0:
        return {}
    p = np.array([pvals[n] if np.isfinite(pvals[n]) else 1.0 for n in names], float)
    order = np.argsort(p, kind="mergesort")
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[i]))
        adj[i] = run
    return {n: (float(adj[i]) if np.isfinite(pvals[n]) else float("nan")) for i, n in enumerate(names)}


def _verdict(p_adj: float, lo: float, hi: float, margin: float, kind: str, alpha: float) -> str:
    if np.isfinite(p_adj) and p_adj < alpha / 2:
        return "success"
    if np.isfinite(lo) and np.isfinite(hi) and ek.decide(lo, hi, margin, kind) == "failure":
        return "failure"
    return "inconclusive"


def family_gate(gates: dict, alpha: float = ALPHA) -> dict:
    """gates {name: {p_one_sided, lo, hi, margin, bound_kind}} -> {name: {..., p_holm, decision}}.
    A gate may carry forced_inconclusive (a reason). It stays in the family with p treated as 1."""
    ps = {n: (float("nan") if g.get("forced_inconclusive") else float(g["p_one_sided"])) for n, g in gates.items()}
    adj = holm(ps)
    out = {}
    for n, g in gates.items():
        dec = ("inconclusive" if g.get("forced_inconclusive")
               else _verdict(adj[n], g["lo"], g["hi"], float(g["margin"]), g.get("bound_kind", "noninferiority"), alpha))
        out[n] = {**g, "p_holm": adj[n], "decision": dec, "family": list(gates), "family_size": len(gates),
                  "alpha": alpha, "method": METHOD}
    return out


def holm_partial(p: float, lo: float, hi: float, margin: float, kind: str, family_size: int,
                 alpha: float = ALPHA) -> tuple[str, str]:
    """Verdict of one primary when the rest of its family is not scored yet. Success needs p < alpha / (2 m)."""
    m = max(int(family_size), 1)
    if np.isfinite(p) and p < alpha / (2 * m):
        return "success", f"one-sided share {p:.4f} < alpha/(2m) = {alpha / (2 * m):.4f}. Holm success whatever the rest"
    if np.isfinite(lo) and np.isfinite(hi) and ek.decide(lo, hi, margin, kind) == "failure":
        return "failure", "interval wholly beyond the bound (failure is not corrected)"
    if m > 1:
        return "inconclusive", (f"Holm family of {m} primaries. Not decidable alone. "
                                "Run _transfer_holm_gate.py over the family score JSONs")
    return "inconclusive", "interval spans the bound"


def holm_input(gate: str, draws, lo: float, hi: float, margin: float, kind: str, family: list) -> dict:
    """The dict every primary score JSON stores for the family step."""
    p = one_sided_p(draws, margin, kind)
    dec, why = holm_partial(p, lo, hi, margin, kind, len(family))
    return {"gate": gate, "p_one_sided": p, "lo": lo, "hi": hi, "margin": margin, "bound_kind": kind,
            "family": list(family), "family_size": len(family), "max_undefined": MAX_UNDEFINED,
            "undefined_share": ek.undefined_share(draws), "decision_partial": dec, "decision_partial_basis": why,
            "method": METHOD}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Holm gate over one expansion's primary score JSONs")
    ap.add_argument("--inputs", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    gates, fams = {}, set()
    for p in a.inputs:
        h = json.loads(p.read_text(encoding="utf-8")).get("holm_input")
        if h is None:
            raise SystemExit(f"{p} holds no holm_input. Only primary score JSONs enter the family")
        gates[h["gate"]] = {**h, "source": str(p)}
        fams.add(tuple(h["family"]))
    if len(fams) != 1:
        raise SystemExit(f"inputs declare different families {sorted(fams)}")
    fam = list(next(iter(fams)))
    missing = [g for g in fam if g not in gates]
    if missing:
        raise SystemExit(f"family members not scored yet {missing}. Holm needs every declared primary")
    extra = [g for g in gates if g not in fam]
    if extra:
        raise SystemExit(f"gates {extra} are not in the declared family {fam}")
    res = family_gate(gates)
    a.out.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    for n, r in res.items():
        print(f"{n}: p {r['p_one_sided']:.4f} Holm {r['p_holm']:.4f} -> {r['decision']}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

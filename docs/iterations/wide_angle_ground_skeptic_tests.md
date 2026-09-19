# Was the vendor right to throw the wide-angle returns away?

**Date:** 2026-09-19
**Status:** three tests run, one claim retracted, one strengthened
**Tests:** `notebooks/wellsight_v2/s7_analysis/_test_overage_hypothesis.py`,
`_test_wideangle_accuracy_and_seams.py`
**Tile:** `621594` (9t). `616591` is not in `OTHER_DATA/` and was not re-run.

## Why

We had been presenting the 18° ground cut as good measurement thrown away by an
arbitrary rule. That is an accusation against the data producer and it had not
been stress-tested. Three things could have made the vendor right, and all three
were cheap to check.

## Test 1 — is this just swath-overlap handling?

3DEP vendors routinely flag points in the overlap between flight lines as
overage and build the DTM from the core of each swath. The symptom is identical
to ours: ground stopping at a fixed angle, gaps in stripes along swath edges. If
that is what this is, the ground in those stripes **is** measured — by the
neighbouring line — and our void count is measuring the wrong thing.

| | `621594` |
|---|---|
| LAS point format | 6 |
| points | 8,956,340 |
| flight lines | **2** |
| scan angle range | −19.9° to +5.2° |
| classes present | 1, 2, 7, 18 |
| ASPRS class 12 (overlap) | **0** |
| Overlap flag bit set | **0** |
| **Withheld flag bit set, on the discarded points** | **1,394,626 of 1,412,392 — 98.74%** |
| Withheld across the whole tile | 15.61% |

**The overage hypothesis is rejected**, on two counts. There is no overlap
marking of any kind, and at 1 m resolution **93.8% of void cells are covered by
one flight line only** — there is no neighbouring swath that could supply the
missing ground.

**But the test found something worse for our framing.** 98.74% of the discarded
points carry the **Withheld** bit. The vendor did not merely decline to classify
them as ground; it marked them do-not-use, explicitly and to specification. Any
use of those points is overriding a producer's stated exclusion, and the talk has
to say so rather than imply an oversight.

One more number worth keeping: of the 1 m void cells, only **26.8%** hold nothing
but wide-angle returns. **68.1% contain near-nadir returns and still have no
ground**, which is canopy occlusion that no reclassification can fix. The angle
rule explains about a quarter of the holes, not all of them.

## Test 2 — is the accuracy claim as strong as we said?

The 0.065 m RMSE came from fitting a plane through ground from *other* flight
lines. Two weaknesses: it can only be computed where two lines overlap, and it
was never stratified by slope, even though off-nadir horizontal error maps into
vertical error as `dz = dx·tan(slope)` and pits sit on slopes.

Re-run on `621594`, at-ground defined as `|z − vendor DEM| < 0.15 m`, plane fit
from the other line within 3 m, slope taken from the fitted plane:

| slope | excluded, >18° | accepted, 10–18° |
|---|---|---|
| 0–5° | **0.065 m** (n 8,361) | 0.060 m (n 2,898) |
| 5–10° | **0.082 m** (n 9,439) | 0.072 m (n 3,183) |
| 10–15° | **0.096 m** (n 4,575) | 0.091 m (n 1,696) |
| 15–20° | **0.116 m** (n 2,145) | 0.124 m (n 789) |
| 20–25° | **0.199 m** (n 329) | 0.180 m (n 146) |
| 25–30° | **0.285 m** (n 115) | 0.272 m (n 33) |
| 30°+ | **0.457 m** (n 36) | — |
| **overall** | **0.089 m** | **0.087 m** |

**This is the strongest result of the three.** The returns the vendor withheld
are statistically indistinguishable from the ground it kept, at every slope
class. Whatever the reason for the cut, it is not that these points are worse.

Three caveats that belong with the number:

1. **Both degrade hard with slope.** 0.06 m on flat ground, ~0.28 m at 25–30°.
   That is a property of the survey, not of the wide-angle points — but it means
   any pit-depth claim on steep ground sits close to the noise, and our typical
   pit is 0.7 m deep.
2. **The narrow-angle control is structurally impossible here.** Ground under 10°
   is **0% validatable**: the two lines meet only at their edges, so there is
   never a second line over the swath centres. The headline number has no
   best-case baseline in this geometry.
3. **52.8% of the "at ground" excluded points sit over a cell where the vendor
   had no ground at all**, so their height-above-ground was decided against a DEM
   interpolated across the hole. The selection is half-circular.

## Test 3 — does putting them back leave a seam?

The earlier check measured `|dz|` only where the vendor already had ground, which
is where the recovery changes nothing, so it could not have detected a seam. This
one measures `dz` against distance to the recovered patches — a step would show as
`p95 |dz|` climbing toward the near band.

| distance to recovered ground | cells | median dz | p95 \|dz\| |
|---|---|---|---|
| 0–1 m | 633,837 | 0.0000 | 0.0487 |
| 1–2 m | 1,151,197 | 0.0000 | 0.0094 |
| 2–5 m | 2,032,831 | 0.0000 | 0.0000 |
| 5–10 m | 751,766 | 0.0000 | 0.0000 |
| 10–25 m | 274,443 | 0.0000 | 0.0000 |
| 25 m+ | 3,942 | 0.0000 | 0.0000 |

**No seam.** Median disagreement is exactly zero everywhere, and the 4.9 cm at
the immediate boundary is TIN edge behaviour, not a step.

## What changes in the talk

Retracted: "good measurement dropped by a rule." The exclusion is deliberate,
flagged, and spec-conformant.

Kept, and now better supported: the delivered surface has systematic
stripe-shaped gaps, and the returns that would fill them measure as well as the
ones already in it — 0.089 m against 0.087 m, matched at every slope.

## Still open

Nobody has retrained on SMRF ground and re-scored. Until that exists this section
demonstrates a problem in the input and never demonstrates it matters to the
output. It stays the top item in `BACKLOG.md`.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_test_overage_hypothesis.py --tiles 621594
python notebooks/wellsight_v2/s7_analysis/_test_wideangle_accuracy_and_seams.py \
    --tiles 621594 --sample 25000
```

## Outputs

`data/9t/results/nonground_classification/`

- `overage_hypothesis_test.json`
- `wideangle_accuracy_and_seam_tests.json`

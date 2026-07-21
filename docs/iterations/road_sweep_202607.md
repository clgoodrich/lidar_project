# road_sweep_202607 — five road U-Net optimizations, ranked

**Date:** 2026-07-20/21 · **Driver:** `notebooks/wellsight_v2/roads/_road_sweep_202607.py` · **Outputs:** `data/derivatives/tiles/9t/road_sweep_202607/<variant>/` · **Spec:** [[ROAD_SWEEP_HANDOFF]]

## Goal

Test the five highest-value tweaks to the road U-Net (chosen from a menu of ten)
as one-change-each variants, ranked honestly against the current champion
`road_unet_1m_corrected`. The target is *reliable, connected* roads; the known
failure mode is gaps in real roads, so connectivity metrics matter more than raw
pixel overlap.

## Method (identical across variants — that's the point)

All five share the data (9t + 613590 corrections, except res05 = 9t-only), the
U-Net body, and one shared seeded train loop. **Fully seeded**
(torch/np/random + deterministic algos), and **val patches are frozen per epoch**
(the val sampler RNG is reset each epoch) — fixing the methodology-audit
re-jitter noise so the five are comparable, not lucky. Model selection on 9t val
road IoU. Each variant changes exactly one thing (see the registry in the driver
or [[road_unet_sweep_explained]]).

## Results

| model | res | 9t val IoU | 9t pixIoU | AP vs drain | P(road) | P(drain) | 613590 added P | added≥0.5 | reject P | add-v-rej AP |
|---|---|---|---|---|---|---|---|---|---|---|
| recall (baseline) | 1m | — | 0.581 | 0.999 | 0.778 | 0.004 | — | — | — | — |
| corrected (baseline) | 1m | 0.636 | 0.573 | 0.999 | 0.784 | 0.005 | 0.780 | 0.957 | 0.162 | 0.541 |
| **cldice** | 1m | 0.593 | 0.558 | 0.998 | **0.885** | 0.006 | **0.889** | 0.957 | 0.155 | 0.470 |
| alpha078 | 1m | 0.639 | 0.580 | 0.999 | 0.790 | 0.005 | 0.779 | 0.935 | 0.158 | 0.553 |
| **boundary** | 1m | **0.668** | **0.601** | 0.999 | 0.742 | **0.004** | 0.732 | 0.913 | 0.147 | 0.530 |
| orient | 1m | 0.636 | 0.577 | 0.996 | 0.739 | 0.030 | 0.681 | 0.826 | 0.116 | **0.660** |
| res05 | 0.5m | 0.502 | 0.486 | 0.997 | 0.707 | 0.027 | — | — | — | — |

`fig_sweep.png` shows the two-axis split. Held-out corrections are 613590
val+test cells the model never trained on.

## Interpretation — no single runaway winner; two poles

- **boundary = precision/accuracy pole.** Best 9t val IoU (0.668) and pixel IoU
  (0.601), cleanest drainage (0.004). By committing to a crisp road *width* it
  scores best on pixel-overlap metrics. But it fills *less*: P(road) on real
  roads drops to 0.742 and held-out missed-road recovery is the lowest of the
  fine-tunes (added≥0.5 0.913). Crisper, but more conservative.
- **cldice = connectivity/recall pole.** Highest P(road) on real roads (0.885,
  +0.10 over corrected) and best recovery of the roads the human marked as
  missed (added P 0.889). This is the gap-filling behavior we wanted. Its low
  pixel IoU (0.558) is a **metric artifact**: clDice optimizes the centerline
  skeleton, not pixel overlap, so a pixel metric structurally undersells it.
  Cost: add-vs-reject separation drops to 0.470 (it raises P(road) on all
  linear features, slightly muddying precision).
- **alpha078 ≈ no-op.** 0.72→0.78 barely moved anything (val IoU +0.003) —
  confirms the earlier finding that the big α jump (0.60→0.72) already captured
  the recall headroom.
- **orient — mixed, with a real regression.** Best add-vs-reject separation
  (0.660) but lowest recall AND **drainage bled to 0.030 (6× the 1 m loss
  variants)**. Trained from scratch (extra head), so it's a different regime;
  the drainage regression is disqualifying for deployment as-is.
- **res05 — inconclusive, not weak.** 0.5 m numbers are not grid-comparable to
  1 m (thinner relative features → naturally lower pixel IoU), it trained
  9t-only from scratch (likely undertrained at 30 ep), and drainage bled
  (0.027). Needs the road-physics channels + more epochs before a fair verdict.

## Recommendation

The honest arbiter for "reliable roads" is **vector extraction / APLS**, not
pixel IoU — and that's exactly the axis where clDice's topology objective and
boundary's precision objective diverge. So:

1. **Run cldice and boundary through `_road_optimize.py`** and compare
   completeness/correctness/APLS on the extracted network (vs the recall model's
   0.754 test F1). That decides it on the metric that matches the goal.
2. **cldice is the front-runner** for the connectivity goal pending that check —
   it directly fixes the gap failure mode and recovers missed roads best.
3. **Try cldice + boundary combined** (both loss terms) — they attack different
   things (connectivity vs crisp width) and may stack. Natural first entry if we
   extend to the full-10 sweep.
4. **Defer orient** (drainage regression) and **re-run res05 properly**
   (road-physics channels, more epochs) before judging 0.5 m.

Not yet deployed — the winner gets promoted after the extraction/APLS check.

## Reproduce

```bash
python -u notebooks/wellsight_v2/roads/_build_orient_labels.py     # orient prereq
for v in cldice alpha078 boundary res05 orient; do
  python -u notebooks/wellsight_v2/roads/_road_sweep_202607.py --variant $v
done
python notebooks/wellsight_v2/roads/_road_sweep_aggregate.py
```

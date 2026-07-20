# The Road U-Net, in plain terms

A quick, non-jargon explainer of what our road model does, what we feed it, and
how the five sweep variants differ. Written 2026-07-20 alongside the
`road_sweep_202607` run.

## What the U-Net is actually doing

Think of it as an automatic map-colorer. We hand it a stack of terrain images of
an area. It looks at every pixel and decides which of three things that pixel is:

- **road** (an old access road or haul road)
- **drainage** (a stream channel or ditch)
- **background** (everything else)

It does this because roads and drainage channels look almost the same from above
once the trees are stripped away — both are narrow lines carved into the
hillside. So the model has to learn the subtle difference. It outputs a
*probability* for each pixel: "I'm 85% sure this is road."

The name "U-Net" just describes its shape. It first zooms **out** step by step
(to understand the big picture — where the ridges and valleys are), then zooms
back **in** step by step (to place the road precisely, pixel by pixel), with
shortcuts connecting the matching zoom levels so it keeps both the context and
the fine detail. Drawn out, that path looks like the letter U.

## What we feed in (the inputs)

For each patch of ground we give the model **7 terrain layers**, all derived from
the LiDAR bare-earth surface (no trees, no buildings — just the ground shape):

| Layer | What it captures (plain) |
|---|---|
| **lrm_25 / lrm_5** | "Local relief" — bumps and dips compared to the smoothed-out land nearby, at two zoom levels. Roads show up as a subtle shelf. |
| **slope** | How steep each spot is. Roads hold a gentle, steady grade; drainage plunges downhill. |
| **tpi_05** | Whether a spot sits in a groove or on a nub relative to its immediate surroundings. |
| **openness_pos / openness_neg** | How "open to the sky" vs "tucked into a hollow" a spot is — good at outlining incised cuts. |
| **roughness** | How bumpy the surface is over a small window. Compacted roadbeds read smoother than raw forest floor. |

Before the model sees them, each layer is **normalized** — rescaled to a common
range so no single layer dominates just because its numbers are bigger. Those
rescaling constants are measured only on the training ground (never the test
ground), so we don't accidentally peek at the answer.

Alongside the images, during training only, we also give it the **answer key**: a
hand-drawn map marking which pixels are road, which are drainage, and which are
background. That's how it learns. A special value (255 = "ignore") marks places
nobody checked, so the model is never taught from a guess.

## What the model contains (the ~7.8 million dials)

Everything the model "knows" lives in about 7.8 million internal numbers (its
"weights") — the dials that training slowly turns until the coloring comes out
right. We don't set those by hand; the training process does. When we
"fine-tune," we start from a model whose dials are already good and nudge them,
instead of starting from random.

Two settings **we** choose by hand (not learned) matter most:

- **Class weights** — how much we punish mistakes on each class. We weight road
  mistakes heavily (0.72) so the model tries hard not to miss roads, drainage
  moderately (0.25), background lightly (0.10). This is the main "care about
  roads" knob.
- **Resolution** — whether each pixel is 1 meter or 0.5 meter of ground. Finer
  pixels mean a 4-meter-wide road is 8 pixels across instead of 4, so the model
  can see its shape better.

## The five variants we're testing

All five start from the same data and the same U-Net. Each changes **one thing**
so we can see what actually helps. The goal is *reliable, connected* roads — the
old models tended to leave gaps in real roads.

1. **cldice** — Adds a second scoring rule during training that grades the road's
   **centerline as a connected line**, not just pixel-by-pixel. A normal score
   barely notices a small gap; this one punishes broken roads directly. Aimed
   straight at the gap problem. *(Early result: fills gaps aggressively — road
   confidence jumped a lot.)*

2. **alpha078** — Turns the "care about roads" dial up a notch (0.72 → 0.78).
   A simple probe: does pushing harder on recall find more road, or just more
   false alarms?

3. **boundary** — Tells the model to pay 3× extra attention to the **edges** of
   roads, so it commits to a crisp road width instead of a fuzzy smear.

4. **orient** — Gives the model a second job: besides "is this road?", also
   predict **which direction** the road runs at each pixel. Learning direction
   is a well-known trick for keeping roads connected (a road shouldn't suddenly
   change direction, so the model learns to continue lines). This one is trained
   from scratch because it has an extra output.

5. **res05** — Same recipe, but at **0.5-meter resolution** instead of 1 meter —
   4× more pixels, so roads are physically bigger in the image. Trained on the
   9t area only (the other block has no half-meter data yet).

## How we judge them (fairly)

Every variant is scored on ground it never trained on:

- **9t test area** — pixel accuracy and how confidently it lights up real roads
  vs drainage.
- **The 613590 correction area** — the roads you personally marked as "missed"
  and "false." A good variant should light up the missed ones and stay dark on
  the false ones.

Everything is seeded (fixed randomness) so the five are compared on identical
footing, not luck. The winner earns a deeper look — and possibly the full-detail
0.5-meter rebuild.

## Reproduce / where things live

- Driver: `notebooks/wellsight_v2/roads/_road_sweep_202607.py`
- Outputs: `data/derivatives/tiles/9t/road_sweep_202607/<variant>/road_prob.tif`
- Leaderboard (built when all finish): same folder, `leaderboard.md`
- Full technical spec: `docs/handoff/ROAD_SWEEP_HANDOFF.md`

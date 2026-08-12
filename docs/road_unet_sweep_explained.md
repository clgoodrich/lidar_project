# The Road U-Net, in plain terms

A quick, non-jargon explainer of what our road model does, what we feed it, and
how the five sweep variants differ — followed by a technical section on exactly
which code each variant changes. Written 2026-07-20 alongside the
`road_sweep_202607` run; code-level section + Model Lab hook added 2026-07-21.

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

## In the code: exactly what each variant changes

Everything below is in `notebooks/wellsight_v2/s3_train/_road_sweep_202607.py`
unless noted. The point of the sweep is that **only one thing moves per
variant** — so here is the single dispatch point and then the one delta each
variant makes.

### The one dispatch point — the `VARIANTS` registry

Every variant is a row in the `VARIANTS` dict. `run_variant(name)` reads that
row and wires up the run from it. The fields:

| Field | What it controls in code |
|---|---|
| `res` | `"1m"` or `"05"`. Selects the input raster set: `build_datasets` picks `(F1,L1)` vs `(F05,L05)`, and `run_variant` picks the matching normalization stats + channel list `(S1,CH1)`/`(S05,CH05)`. |
| `init` | `"corrected"` → load the champion checkpoint (`CORRECTED`) with `load_state_dict(..., strict=False)` and fine-tune. `"scratch"` → random init. |
| `loss` | Which loss object gets built — `focal` / `cldice` / `boundary` / `orient` (see below). |
| `model` | `"unet"` → `UNet`; `"orient"` → `UNetOrient` (adds a second output head). |
| `ep`, `lr` | Epoch count and AdamW learning rate for the cosine schedule. |
| `corr` | Whether to append the 613590 correction dataset to the training set (`build_datasets` concatenates it). |
| `alpha` | The 3-tuple of focal class weights `(bg, road, drainage)`. |

### Shared scaffolding (identical across all five — this is what makes it fair)

- **`seed_all()`** seeds `random` / `numpy` / `torch` / CUDA and turns on
  deterministic algorithms, so two runs with the same config are bit-comparable.
- **`build_datasets(cfg, mu, sd)`** builds the training sampler(s) from
  *centered-patch policies* (`nine_t_policies` for 9t, `corr_policies` for the
  613590 corrections). Each policy says "sample patches centered on these
  labeled points (road / drainage / added / reject / kept) with ±jitter." The
  val sampler is always single-head, `augment=False`, fixed seed.
- **`train_variant(...)`** is the one training loop: AdamW + `CosineAnnealingLR`,
  mixed-precision (`GradScaler`/`autocast`), batch 16. After each epoch it calls
  **`road_iou_val`** and keeps the checkpoint with the best **road-class IoU**.
  Crucially `road_iou_val` resets the val sampler's RNG (`val_ds._rng = None`)
  every call, so the model is always judged on the *same frozen* val patches —
  that removes the re-jitter noise the methodology audit caught.

### The per-variant deltas

**`alpha078` — one number.** The only change from the champion recipe is
`alpha=(0.10, 0.78, 0.25)` instead of `0.72`. Loss is still plain `FocalCE`.
`FocalCE` is focal cross-entropy: `-alpha_c * (1-p)^gamma * log(p)` per pixel,
`ignore_index=255`. Raising the road weight tells the optimizer a missed-road
pixel costs more, i.e. trade precision for recall. Nothing else differs.

**`cldice` — swap the loss object to `ClDiceFocal`.** `run_variant` builds
`ClDiceFocal(alpha, w, iters)` instead of `FocalCE`. It returns
`focal_loss + w * (1 - soft_clDice)`. The clDice term grades **connectivity**,
computed differentiably:
- `_soft_skel(x, iters)` approximates a morphological skeleton (centerline)
  using `_soft_erode` (a 3×3 **min**-pool) and `_soft_dilate` (a 3×3 **max**-pool)
  — the standard soft-skeleton of Shit et al. 2021. `iters` = how many
  erode/dilate rounds (thinner skeleton with more).
- `tprec = |skel(pred) ∩ true| / |skel(pred)|` (topology precision) and
  `tsens = |skel(true) ∩ pred| / |skel(true)|` (topology sensitivity); soft
  clDice is their harmonic mean. A broken road drops the intersection sharply,
  so gaps are penalized directly — which a per-pixel loss barely notices.
  It is ignore-safe (masks out 255 before skeletonizing). Knobs: `w` (how much
  the connectivity term counts) and `iters`.

**`boundary` — swap the loss object to `BoundaryFocal`.** Same focal per-pixel
loss, but multiplied by a spatial weight map: `edge = _soft_dilate(road) - road`
is the 1-pixel ring just outside each road-class region, and pixels on that ring
get weight `edge_w` (default 3×) while everything else gets 1×. This forces the
model to get the road **width/edge** right instead of producing a fat fuzzy
blob. Knob: `edge_w`.

**`orient` — change the model *and* the sampler *and* add a loss term.**
- Model: `UNetOrient` subclasses `UNet` and adds `self.ori = Conv2d(base, N_ORI)`
  hanging off the last decoder feature `u1`. In `training` mode `forward`
  returns `(seg_logits, orient_logits)`; in eval it returns `seg` only, so the
  downstream `predict_full_tile` is unchanged.
- Labels: `OrientSampler` reads a **third** raster — per-pixel road-direction
  bins (`N_ORI=8` bins over 0–180°) built offline by
  `notebooks/wellsight_v2/s2_labels/_build_orient_labels.py`.
- Loss: the train loop adds `ori_w * CrossEntropyLoss(orient_logits, ori_target)`
  to the segmentation loss. Predicting direction is a known trick for keeping
  roads continuous. Because of the extra head it trains from `scratch`. Knob:
  `ori_w`.

**`res05` — pure data/resolution swap, no loss or architecture change.**
`res="05"` flips `build_datasets` and `run_variant` to the 0.5 m feature/label/
stats/channel set; `corr=False` (no half-meter corrections exist yet) so it's
9t-only; `scratch` init. Same `UNet`, same `FocalCE`. It isolates the effect of
resolution alone.

### Where the Model Lab plugs in

The `--config PATH` CLI path (used by Roads Studio's Model Lab) calls
`register_config(cfg)`, which merges a custom dict **over a named base preset**
and injects it into `VARIANTS` under a new name — so a Lab run is just a
programmatically-created row. The loss **sub-knobs** are threaded from that row:
`run_variant` now reads `cfg.get("cldice_w"/"cldice_iters"/"edge_w"/"gamma")`
into the loss constructors and passes `ori_w=cfg.get("ori_w")` into
`train_variant`. That is why the Lab can vary clDice weight, boundary edge
weight, focal γ, etc. — those were hard-coded defaults before this change.

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

- Driver: `notebooks/wellsight_v2/s3_train/_road_sweep_202607.py`
  - Built-in preset: `... --variant cldice [--epochs N]`
  - Custom (Model Lab): `... --config runs/<name>.config.json`
- Outputs: `data/derivatives/tiles/9t/road_sweep_202607/<variant>/`
  (`best.pt`, `road_prob.tif`, `road_prob_613590_1m.tif`,
  `drainage_prob_613590_1m.tif`, `train_log.csv`, `test_metrics.json`)
- Orientation-label prereq: `notebooks/wellsight_v2/s2_labels/_build_orient_labels.py`
- Leaderboard: `docs/iterations/road_sweep_202607.md` (aggregated by
  `_road_sweep_aggregate.py`)
- Interactive front-end: Roads Studio → **Model Lab** tab
  (`roads_studio/train.py` builds the config and launches the driver)
- Full technical spec: `docs/handoff/ROAD_SWEEP_HANDOFF.md`

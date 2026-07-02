# FINESST Talking Points — Personal Reference

*Private crib sheet. Everything here is phrased the way you'd actually say it out loud.
Numbers in **bold** are the ones worth memorizing. Companion docs: `finesst_proposal.md`
(formal), `finesst_proposal_plain.md` (approachable), `barlow_dissertation_readalong.md`
(the source science, decoded).*

---

## 1. The pitch, three lengths

**Ten seconds.** "Antarctica's dry valleys — the place everyone called the most stable
landscape on Earth — are measurably changing. A recent dissertation built the tool that
detects the change. I'm proposing to figure out *what's driving it* and make the tool
work anywhere."

**Thirty seconds.** "Mary Barlow's 2026 dissertation taught a neural network to outline
Antarctic stream channels using only the shape of the ground — no water visible, because
these streams are dry 11 months a year. Then she subtracted elevation maps from 2001,
2014, and 2021–23 and showed sediment is moving, and in places accelerating. But the
dissertation stops at *where* change happens. My project answers *why*: I pair each
stream's measured change with its climate history — heat, sunlight, meltwater, thaw
depth — and build a model that predicts where the change goes next. I've already rebuilt
her whole pipeline and my numbers land inside her published error ranges."

**Two minutes — add these beats:**
1. Why it matters: the Dry Valleys are a *climate canary*. The system is energy-limited —
   plenty of ice, barely enough heat to melt it — so a tiny warming shift produces an
   outsized, measurable response. If the most stable place on Earth is speeding up,
   that's a continental early-warning signal.
2. The three objectives: **attribution** (what drives the change), **generalization**
   (make the detector sensor-agnostic so free satellite DEMs extend the record forever),
   **calibrated uncertainty** (every change map ships with an honest error bar).
3. The teaser result: across the six gauged streams, sediment movement scales with
   meltwater almost perfectly — **r = +0.95, p = 0.004** — in the period with good gauge
   data. Where gauges get sparse the relationship vanishes, which is exactly why we need
   modeled melt *energy* instead of patchy gauges. That's Objective 1 in one sentence.
4. My credential: I independently built and run this same toolchain — U-Net on lidar
   terrain, ICP alignment, DEM differencing — on Appalachian oil-and-gas landscapes.
   Different biome, same physics of the method. That de-risks the generalization aim.

---

## 2. The Barlow foundation — what you're building on

Say it as a three-step story:

1. **Detect (her Ch. 4 + 6).** A U-Net segments stream channels from terrain derivatives
   alone — elevation, slope, aspect were the most informative; no color or water signal
   needed. Proof of concept in Taylor Valley (published 2022, *Remote Sensing*), then
   scaled to all the valleys and all three survey years. Trained on **217 hand-labeled
   300 × 300 m tiles** — about 1% of the study area.
2. **Trust the ruler (her Ch. 5).** Free REMA satellite DEMs (2 m, from WorldView stereo
   pairs) are accurate enough for change detection *after* you align them to lidar with
   point-to-plane ICP. Key detail people respect: the elevation errors are **Laplacian**
   (sharp peak, heavy tails), not Gaussian — so she uses **NMAD**, an outlier-proof
   standard deviation, for all error bars.
3. **Measure change (her Ch. 7).** Subtract old DEM from new DEM inside the stream
   outlines; only count pixels whose change beats the **level of detection**
   (LOD95 = 1.96 × NMAD — the smallest change you can distinguish from noise at 95%
   confidence). Result: **Denton Hills is the erosion hotspot**, coastal Taylor Valley is
   depositional, and some Taylor streams are **accelerating** across the three epochs.

The three elevation snapshots, worth having cold: **2001 airborne lidar** (NASA ATM, 2 m),
**2014 airborne lidar** (NCALM, 1 m — the accuracy benchmark), **2021–23 REMA** (satellite,
2 m).

---

## 3. Your own results — the "I've already done the homework" numbers

These are yours, not Barlow's. You reproduced her pipeline independently, from public data.

| What | Your number | Why it's credible |
|---|---|---|
| Noise level, 2001→2014 (lidar–lidar) | **NMAD 0.21 m** (LOD95 0.41 m) | Inside Barlow's published range (0.07–0.46) |
| Noise level, 2014→REMA (lidar–satellite) | **NMAD 0.23 m** (LOD95 0.44 m) | Inside her range (0.19–0.53) |
| Melt–sediment link, lidar epoch | **r = +0.95 (p = 0.004), ρ = +0.94 (p = 0.005)** | Survives dropping any single stream (leave-one-out) |
| Melt–sediment link, REMA epoch | no coherent relation | Honest: gauges ran only 48–362 days/stream after 2015 — the water axis is unreliable, so no fit is drawn |
| Lake Fryxell screen | lake rose **~1.5 m**; auto-detected and excluded | Standing-water screen keeps lake level out of stream rates |

Speakable version of the last row: "The biggest 'change' signal in the map wasn't
sediment at all — Lake Fryxell rose a meter and a half. My pipeline catches flat water
surfaces automatically and drops them, so the stream numbers stay clean. Before the
screen, that lake was inflating one stream's deposition volume by a factor of four."

Also pocketable: your ICP behaved exactly like hers — it helps on steep terrain and
correctly does nothing on the flat valley floor, because alignment needs relief to grip.

---

## 4. The three objectives, at conversation depth

**O1 — Attribution (the headline).**
"For every gauged stream I compute how much sediment moved per year. Then I rebuild that
stream's *energy history* — positive degree-days, which is just a running total of
melting weather; incoming sunlight; meltwater discharge; and summer thaw depth. Then I
ask the statistical question: which of these actually predicts the sediment number?
The hypothesis is that *cumulative melt energy* beats raw water volume. I always test on
streams the model never saw during fitting, so I can't fool myself."
- If asked what models: hierarchical regression and random forests — one interpretable,
  one flexible; agreement between them is the sanity check.
- If asked why not just discharge: "Because the gauges are the weak link — coverage
  collapses after 2015. Weather-model energy (ERA5, AMPS) is continuous everywhere.
  If energy predicts as well as water, I can attribute change on *ungauged* streams too.
  That's the unlock."

**O2 — Generalization.**
"The detector was trained on lidar. Satellite DEMs look subtly different — a *domain
shift*. Step one is boring but crucial: measure exactly how REMA disagrees with lidar
over ground that didn't change, as a function of slope and aspect. Step two: correct
that bias and retrain with both sensors in the training data. Success looks like
near-lidar accuracy on satellite data in all four valleys. That matters because there
will be no more lidar flights any time soon — REMA updates are how this record continues."

**O3 — Calibrated uncertainty.**
"Right now there's one noise number per map. But error isn't uniform — steep slopes are
noisier than flat floors. I replace the single number with a per-pixel threshold that
knows about slope, aspect, and sensor. And I verify it honestly: on stable ground, a 95%
threshold should be crossed by only 5% of pixels. If it is, you can trust every pixel of
the change map, not just the average."

The thread that ties them: **a model that predicts where acceleration migrates next.**
Detection → attribution → prediction. That's the arc.

---

## 5. Questions you'll get, and answers that land

**"What's actually new here? Isn't this just her dissertation again?"**
"Her dissertation ends at description — where change happened. She explicitly lists both
of my main aims — driver attribution and sensor generalization — as future work she
didn't do. I'm starting where she stopped, with her measurement engine already rebuilt
and verified."

**"How do you know the changes are real and not noise?"**
"Everything is thresholded at the level of detection — a change has to beat 1.96 times
the robust noise level before it counts. And the noise level itself is measured on
terrain that shouldn't change. My reproduction of both epochs' noise landed inside her
published ranges."

**"Six streams and an r of 0.95? Small sample."**
Own it: "Absolutely — n = 6, it's a pilot signal, not a conclusion. Three things keep it
interesting: the p-value is 0.004 even at n = 6, the rank correlation is just as strong
so it's not one outlier stretching a line, and it survives leaving out any single
stream. The proposal is precisely about growing that n — modeled energy covers every
stream, gauged or not."

**"What if you can't get her training labels?"**
"That's my one access-gated dependency, and it has two exits. The public LTER stream
centerlines already work as a stand-in — my current figures are built on them. And
worst case I re-digitize a comparable label set myself; hand-labeling terrain features
is literally what I do in my other project."

**"Why REMA? Why not fly lidar again?"**
"Cost and cadence. Lidar campaigns over Antarctica are rare, expensive, one-off events —
2001 and 2014 are what exist. REMA is free, continent-wide, and keeps updating. Chapter 5
of the dissertation — and my reproduction — show that after careful alignment it's
accurate to about 20-odd centimeters, which is enough for these channels."

**"Why does NASA care?"**
"Three reasons. It's Antarctic climate response measured directly, not modeled. It
converts free NASA-adjacent data products — lidar archives, REMA, reanalysis — into a
long-term monitoring capability with calibrated uncertainty, which is the 'trustworthy
Earth observation' direction. And it's a transferable method: terrain-only detection
works wherever features shape the ground — including Mars-analog and planetary terrain,
which is exactly why people study the Dry Valleys in the first place."

**"What's your role versus your advisor's?"**
"FINESST is a Future Investigator award — I'm the intellectual lead and primary author;
the advisor is PI of record and provides domain mentorship. The proposal, the pipeline,
and the preliminary results are my work."

**"Timeline?"**
"Three years. Year 1: driver data harmonized, attribution model on Taylor Valley,
manuscript drafted. Year 2: sensor generalization across all four valleys, second paper.
Year 3: the predictive model — where does acceleration go next — plus the public
calibrated-uncertainty data products."

**"What can go wrong?"**
"Three known risks, all mitigated: the gated labels (stand-in exists, re-digitizing is
plan C); REMA's uneven coverage after 2014 (Taylor Valley has full three-epoch coverage,
so acceleration analysis anchors there); and gauge gaps (that's not a bug — replacing
gauges with modeled energy is the whole point of O1)."

---

## 6. Sixty-second glossary — say these definitions, don't recite acronyms

- **DEM** — an elevation map; every pixel stores ground height.
- **Lidar** — laser scanning from a plane; centimeter-accurate ground heights.
- **REMA** — free elevation model of Antarctica built from stereo satellite photos.
- **ICP** — sliding one 3-D surface over another until they line up.
- **DoD (DEM of Difference)** — new map minus old map; positive = dirt arrived, negative = dirt left.
- **NMAD** — a standard deviation that ignores outliers; the honest noise estimate here.
- **LOD95** — the smallest elevation change you can call real with 95% confidence (1.96 × NMAD).
- **Laplacian errors** — sharply peaked with heavy tails; a few big blunders, so you need NMAD not RMSE.
- **PDD (positive degree-days)** — melting weather, totaled: sum of every degree above freezing, every day.
- **Active layer** — the top of the permafrost that thaws each summer; deeper thaw = looser ground.
- **Ephemeral stream** — flows a few weeks a year during melt season; dry the rest.
- **Energy-limited** — plenty of frozen water, barely enough heat; heat is the control knob.
- **Specific rate** — sediment change per square meter of channel (mm/yr), so bigger survey footprints can't inflate the number.
- **U-Net** — an image-segmentation neural network; input terrain layers, output "stream / not stream" per pixel.
- **F1** — balance of "found everything" and "didn't cry wolf"; her Taylor Valley model hits ~0.94.

---

## 7. Program facts (don't fumble these)

- **Program:** NASA ROSES-2025 F.5 FINESST — Future Investigators in NASA Earth and Space
  Science and Technology. Earth Science Division.
- **Deadline: 14 July 2026**, 11:59 PM EDT.
- **Money:** up to ~**$50,000/year**, up to **3 years** (stipend + tuition + research allowance).
- **Structure:** graduate student = **Future Investigator (FI)** and intellectual lead;
  faculty advisor = **PI of record** who formally submits.
- **Every dataset needed is free/public and already in hand** — the one exception is
  Barlow's 217 label tiles (author-gated; mitigations above).

---

## 8. Honesty guardrails — things NOT to oversell

- The r = 0.95 is **six streams, one epoch, correlation** — call it a pilot signal that
  motivates O1, never "proof" of the driver.
- The REMA-epoch attribution is currently **unresolved** (sparse gauging) — that's the
  motivation for modeled energy, not a result.
- "Attribution" in this proposal means statistical driver modeling with honest
  cross-validation — not formal causal inference; don't let the word write checks.
- Barlow's dissertation, not you, established the detection method and error framework —
  your contribution so far is an independent reproduction that matches, plus the
  attribution signal. Credit her generously; it costs nothing and reviewers notice.
- InSAR/NISAR, if it comes up: interesting future covariate, but the PA experiment was
  one image pair — say "worth exploring," nothing stronger.

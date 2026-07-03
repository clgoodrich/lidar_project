# FINESST Personal Reference — MDV Stream-Change Project

*Lookup document, not a script. Find the section you need, read the entry, done.
Companions: `finesst_proposal.md` (formal), `finesst_proposal_plain.md` (plain-language),
`barlow_dissertation_readalong.md` (the source science, decoded).*

---

## 1. Project at a glance

| Item | Fact |
|---|---|
| One-line summary | Measure how Antarctic Dry Valley stream channels are changing, identify the climate drivers, and make the method work on free satellite elevation data |
| Study area | McMurdo Dry Valleys, Antarctica (Taylor, Wright, Victoria, Garwood valleys) |
| Foundation | Mary C. Barlow, PhD dissertation, Univ. Houston, 2026 (advisor: Craig Glennie) |
| What Barlow did | Detected stream channels from terrain shape alone (U-Net) and measured elevation change 2001 → 2014 → 2021–23 |
| What Barlow did NOT do | Explain *why* change happens (drivers), or make the detector work on satellite DEMs — both listed by her as future work |
| My proposal, in three words | Attribution, generalization, uncertainty |
| Program | NASA ROSES-2025 F.5 FINESST (Future Investigators in NASA Earth and Space Science and Technology), Earth Science Division |
| Deadline | **14 July 2026**, 11:59 PM EDT |
| Funding | Up to ~$50,000/year, up to 3 years (stipend + tuition + research allowance) |
| Roles | Grad student = Future Investigator, intellectual lead and primary author. Advisor = PI of record, submits formally. |

---

## 2. Key numbers (memorize the bold column)

| Number | What it is | Source |
|---|---|---|
| **2001, 2014, 2021–23** | The three elevation snapshots (epochs) | NASA ATM lidar / NCALM lidar / REMA satellite |
| **2 m / 1 m / 2 m** | Pixel size of each epoch, in the same order | Barlow Ch. 3 |
| **217** | Hand-labeled 300 × 300 m tiles in the original Taylor Valley proof of concept (~1% of the valley) | Barlow Ch. 4 / 2022 paper |
| **1,274** | Training tiles in the scaled-up multi-valley model: 601 from 2014 lidar + 528 from 2001 lidar + 145 from REMA, drawn at 616 unique locations | Barlow Ch. 6 |
| **~0.94** | F1 score of her Taylor Valley channel detector | Barlow 2022, *Remote Sensing* |
| **0.21 m** | My NMAD (noise level) for 2001→2014 lidar–lidar differencing | My reproduction; her range 0.07–0.46 |
| **0.23 m** | My NMAD for 2014→REMA lidar–satellite differencing | My reproduction; her range 0.19–0.53 |
| **r = +0.95, p = 0.004** | Correlation: per-stream sediment rate vs mean gauged discharge, lidar epoch, n = 6 streams | My pilot result |
| **ρ = +0.94, p = 0.005** | Same relationship by rank (Spearman) — not driven by one outlier | My pilot result |
| **~1.5 m** | Lake Fryxell rise caught and excluded by my standing-water screen | My pipeline |
| **6** | Gauged streams in the attribution pilot — small n, call it a pilot signal | LTER gauge network |
| **48–362 days/stream** | Gauge coverage after 2015 — why the REMA epoch shows no discharge relation | LTER records |

---

## 3. The Barlow dissertation — chapter map

| Chapter | What it establishes | The takeaway sentence |
|---|---|---|
| Ch. 4 (+ 2022 paper) | U-Net segments stream channels from terrain derivatives only — elevation, slope, aspect most informative; no water or color needed | "She proved you can find dry streambeds from ground shape alone." |
| Ch. 5 | REMA satellite DEMs are usable for change detection after point-to-plane ICP alignment to lidar; elevation errors are Laplacian (heavy-tailed), so NMAD replaces RMSE | "She proved the free satellite ruler is trustworthy once aligned." |
| Ch. 6 | Detection scaled from Taylor Valley to all valleys and all three survey years | "The detector generalizes across the region." |
| Ch. 7 | DEM differencing inside the channel outlines, thresholded at LOD95: Denton Hills = erosion hotspot, coastal Taylor Valley = depositional, some Taylor streams accelerating | "The 'most stable landscape on Earth' is measurably changing, and in places speeding up." |

---

## 4. Method reference — the pipeline in five steps

1. **Detect** — U-Net takes terrain layers (elevation, slope, aspect, curvature, flow
   accumulation, intensity) and outputs a per-pixel stream/not-stream map.
2. **Align** — point-to-plane ICP slides the newer surface over the older one until they
   fit. Needs relief to grip: helps on slopes, correctly does nothing on flat valley floor.
3. **Difference** — DEM of Difference (DoD) = new elevation minus old. Positive =
   deposition (dirt arrived), negative = erosion (dirt left).
4. **Threshold** — measure noise on terrain that shouldn't change, summarize it with
   NMAD (an outlier-proof standard deviation), keep only changes bigger than
   LOD95 = 1.96 × NMAD. Anything smaller is indistinguishable from noise.
5. **Rate** — sum surviving change inside each stream's outline, divide by channel area
   and by years elapsed → specific rate in mm/yr. Area-normalized so a bigger survey
   footprint can't inflate the number. A standing-water screen drops flat lake surfaces
   first (Lake Fryxell's rise was inflating one stream's deposition volume ~4×).

---

## 5. My reproduction — status and credibility

| Claim | Evidence |
|---|---|
| I rebuilt the full pipeline independently from public data | Fetch → derivative stack → ICP → DoD → per-stream rates, all scripted in `barlow/build/` |
| My noise levels match hers | Both epochs' NMAD land inside her published ranges (see §2) |
| My ICP behaves like hers | Improves steep terrain, no effect on flat floor — same pattern she reports |
| The attribution signal is real but preliminary | r = +0.95 survives leave-one-out (drop any stream, correlation holds); still only n = 6, one epoch |
| The REMA-epoch gap is understood, not hidden | Post-2015 gauge coverage collapses to 48–362 days/stream, so no fit is drawn — this *motivates* O1 |
| The signal doesn't depend on my channel choice | Re-ran rates inside **Cami's own detected channel outlines** (author-provided, May 2026): r = +0.95 either way; leave-one-out worst case *improves* (+0.82 → +0.87) |

---

## 6. The three objectives

**O1 — Attribution (the headline).**
Compute each gauged stream's sediment rate, rebuild its energy history — positive
degree-days (running total of melting weather), incoming sunlight, meltwater discharge,
summer thaw depth — and test which predicts the sediment number. Hypothesis: cumulative
melt *energy* beats raw water volume. Models: hierarchical regression + random forest
(one interpretable, one flexible; agreement = sanity check). Always validated on
held-out streams. Why not just discharge: gauges are the weak link after 2015;
weather-model energy (ERA5, AMPS) is continuous everywhere, so it extends attribution
to ungauged streams.

**O2 — Generalization.**
The detector was trained on lidar; satellite DEMs look subtly different (a *domain
shift*). Step 1: measure exactly how REMA disagrees with lidar over unchanged ground,
by slope and aspect. Step 2: correct the bias and retrain with both sensors in the
training data. Success = near-lidar accuracy on satellite data in all four valleys.
Stakes: no more lidar flights are coming — REMA updates are how the record continues.

**O3 — Calibrated uncertainty.**
Replace the single per-map noise number with a per-pixel threshold that knows about
slope, aspect, and sensor. Verification: on stable ground, a 95% threshold should be
crossed by exactly 5% of pixels. Then every pixel of the change map is trustworthy,
not just the average.

**The arc:** detection → attribution → prediction. End state is a model that predicts
where acceleration migrates next.

---

## 7. Stock answers to likely questions

**What's new vs the dissertation?**
She ends at description — *where* change happened. Driver attribution and sensor
generalization are both on her future-work list. I start where she stopped, with her
measurement engine already rebuilt and verified.

**How do you know changes are real, not noise?**
Everything is thresholded at LOD95, and the noise level is measured on terrain that
shouldn't change. My reproduction of both epochs' noise landed inside her published
ranges.

**n = 6 and r = 0.95 — small sample?**
Yes — pilot signal, not conclusion. Three reasons it's still interesting: p = 0.004 even
at n = 6; the rank correlation is equally strong (not one outlier); it survives
leave-one-out. The proposal grows the n — modeled energy covers every stream, gauged or
not.

**What if you can't get her training labels?** (217 tiles in the 2022 paper; the full
Ch. 6 set is 1,274 tiles at 616 locations — that's the real ask.)
Two exits: the public LTER stream centerlines already work as a stand-in (current
figures use them), and worst case I re-digitize a comparable set — hand-labeling terrain
features is what I do in my other project. Update: she has already shared her final
*detected* channel outlines (May 2026) — I've verified my rates inside her exact masks;
only the training tiles remain author-gated.

**Why REMA instead of flying lidar again?**
Cost and cadence. Antarctic lidar campaigns are rare one-offs (2001 and 2014 are what
exist). REMA is free, continent-wide, keeps updating, and after alignment is accurate to
~20-odd cm — enough for these channels.

**Why does NASA care?**
(1) Antarctic climate response measured directly, not modeled. (2) Converts free
NASA-adjacent data (lidar archives, REMA, reanalysis) into long-term monitoring with
calibrated uncertainty. (3) Transferable: terrain-only detection works wherever features
shape the ground, including planetary-analog terrain — the reason people study the Dry
Valleys at all.

**Your role vs your advisor's?**
FINESST makes the student the Future Investigator: intellectual lead, primary author.
Advisor is PI of record and mentor. Proposal, pipeline, and preliminary results are mine.

**Timeline?**
Y1: drivers harmonized, attribution model on Taylor Valley, first manuscript.
Y2: sensor generalization across all four valleys, second paper.
Y3: predictive model + public calibrated-uncertainty data products.

**What can go wrong?**
Three known risks, all mitigated — see §9.

---

## 8. Glossary (plain definitions)

| Term | Plain meaning |
|---|---|
| DEM | Elevation map; every pixel stores ground height |
| Lidar | Laser scanning from a plane; cm-accurate ground heights |
| REMA | Free elevation model of Antarctica from stereo satellite photos |
| ICP | Sliding one 3-D surface over another until they line up |
| DoD | DEM of Difference: new map minus old; + = deposition, − = erosion |
| NMAD | Outlier-proof standard deviation; the honest noise estimate |
| LOD95 | Smallest change callable as real at 95% confidence (1.96 × NMAD) |
| Laplacian errors | Sharp peak, heavy tails — a few big blunders; why NMAD, not RMSE |
| PDD | Positive degree-days: sum of every degree above freezing, every day |
| Active layer | Top of permafrost that thaws each summer; deeper thaw = looser ground |
| Ephemeral stream | Flows a few weeks a year during melt; dry otherwise |
| Energy-limited | Plenty of ice, barely enough heat — heat is the control knob |
| Specific rate | Sediment change per m² of channel (mm/yr); footprint-proof |
| U-Net | Image-segmentation neural network: terrain in, stream/not-stream out |
| F1 | Balance of found-everything vs didn't-cry-wolf; her model ~0.94 |
| Domain shift | Model trained on one sensor's data degrades on another's |
| ERA5 / AMPS | Global / Antarctic-specific weather reanalysis models |

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Barlow's label tiles are author-gated (217 in Ch. 4; 1,274 in Ch. 6) | LTER centerlines already work as stand-in; plan C = re-digitize myself |
| REMA coverage uneven after 2014 | Taylor Valley has full three-epoch coverage — acceleration analysis anchors there |
| Gauge record gaps | Not a bug: replacing gauges with modeled energy is the point of O1 |

---

## 10. Do not oversell

- r = 0.95 is six streams, one epoch, correlation — a pilot signal motivating O1, never "proof."
- REMA-epoch attribution is currently unresolved — that's motivation, not a result.
- "Attribution" = statistical driver modeling with honest cross-validation, not formal causal inference.
- Barlow established the detection method and error framework; my contribution is an independent matching reproduction plus the attribution signal. Credit her generously.
- InSAR/NISAR: one PA image pair exists — say "worth exploring," nothing stronger.

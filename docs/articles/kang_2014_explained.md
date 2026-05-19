# Kang et al. 2014 — Explained Like You're 16

A walkthrough of the first study to ever directly measure methane leaking out of abandoned oil and gas wells, written so a curious teenager can follow it cover-to-cover.

**Citation:** Kang, M., Kanno, C. M., Reid, M. C., Zhang, X., Mauzerall, D. L., Celia, M. A., Chen, Y., & Onstott, T. C. (2014). *Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania.* PNAS, 111(51), 18173–18177. doi:10.1073/pnas.1408315111. Princeton University.

---

## The one-sentence version

They put plastic boxes over 19 old oil and gas wells in rural Pennsylvania, measured how fast methane built up inside, and discovered that a handful of "super-leakers" pump out so much methane that abandoned wells — never before counted in any emissions inventory — likely account for **4–7% of all the human-caused methane emissions in Pennsylvania**.

---

## Part 1 — Why anyone should care

### What's methane and why does it matter?

Methane (CH₄) is the main ingredient in natural gas. It's also a **greenhouse gas** — meaning when it floats up into the atmosphere it traps heat, contributing to climate change. **Pound-for-pound, methane is about 80× more potent than CO₂ over the short term.** It also breaks down in the atmosphere into ozone, which is bad for human lungs, crops, and ecosystems.

So if methane is leaking somewhere, climate scientists really want to know.

### The "missing methane" mystery

There are two ways to count how much methane is being released:

- **Bottom-up:** Add up every known source — cows, landfills, gas-production sites, etc. — and sum it. This is what official US EPA inventories do.
- **Top-down:** Measure how much methane is actually in the atmosphere (from planes, satellites, towers) and back-calculate where it must be coming from.

For years, the top-down numbers have been bigger than the bottom-up numbers. That means there are **methane sources nobody is counting.** A 2014 study estimated that emissions from abandoned wells might be the second-largest missing source — but before this paper, **no one had ever actually measured any of them directly.** Everyone was just guessing.

### The abandoned-well problem

When an oil or gas well runs dry (or stops being profitable), the company is supposed to "plug" it — fill the hole with cement so nothing can leak up. But:

- Wells drilled before plugging regulations existed (decades, sometimes a century ago) often weren't plugged at all.
- Cement degrades. Plugs from the 1950s might not hold today.
- Records are bad. Many old wells are "lost" — nobody knows where they are.
- There are an estimated **3 million abandoned oil and gas wells in the US.** Pennsylvania alone has somewhere between **300,000 and 500,000.**

And until this study, **zero of them had been monitored for methane emissions.**

---

## Part 2 — The Setting

### Where they worked

**McKean and Potter counties, in northwestern Pennsylvania** — old oil and gas country that's been producing since the late 1800s. McKean County alone has 4,273 wells on Pennsylvania's official Department of Environmental Protection (DEP) abandoned/orphaned/plugged-well list. (Heads-up: this is the *same region* where the WellSight LiDAR project is hunting for lost wells.)

### What they measured

**19 abandoned wells**, picked mostly based on whether the team could legally and physically get to them. Of those 19:

- **5 were "plugged"** based on visible cement or markers at the surface (26%).
- **14 were "unplugged"** — just an open hole in the ground or a rusty pipe sticking up.
- **Only 1 of the 19 was on Pennsylvania DEP's official abandoned-well list.** The other 18 were essentially undocumented in any state records.

They also measured **52 "control" locations** near the wells (0.1 to 62 meters away) to see what normal background methane looked like in that landscape (forest soil, wetland, grassland, riverbank).

### When they measured

Five sampling trips spread across all four seasons to catch any seasonal effects:
- July 2013
- August 2013
- October 2013
- January 2014 (twice)

Total: **42 measurements at wells** + **52 measurements at controls.**

---

## Part 3 — The Method: Static Flux Chambers

### The basic idea

To measure how fast methane is leaking out of a well, you put a sealed container over it, wait, and check how much methane has built up inside. **More buildup per minute = bigger leak.**

It's the same principle as putting a glass over a candle and timing how long until the flame goes out — except instead of measuring oxygen disappearing, you're measuring methane appearing.

### The chamber

They built custom chambers designed to fit over an abandoned wellhead and seal against the ground around it, so the only methane that gets in is methane coming **out of the well**. The chamber is connected to a syringe port that lets them pull air samples at known time intervals (typically a few minutes apart, for ~30 minutes total).

### The math

They use a simple formula:

```
F = (dc/dt) × V_e
```

Where:
- `F` = flow rate of methane out of the well (mass per time)
- `dc/dt` = the slope of methane concentration over time inside the chamber (how fast it's building up)
- `V_e` = effective chamber volume

So if you plot methane concentration vs. time inside the chamber, you should get a straight line going up. The **slope** of that line tells you the leak rate. (For 88% of the well measurements, the line was a clean fit — `R² > 0.8`.) For control measurements, they scale the flow rate by area, since the chamber covers more ground than just a wellhead.

### What they measured beyond methane

They didn't just measure CH₄. They also captured:

- **Ethane (C₂H₆), propane (C₃H₈), and n-butane (n-C₄H₁₀)** — heavier hydrocarbons. Their relative concentrations are like a fingerprint that tells you *where* the methane came from.
- **Carbon isotopes of methane (¹³C/¹²C, written as δ¹³C-CH₄)** — another fingerprint method. Methane formed by ancient geological processes deep underground has a different isotopic signature than methane made by bacteria near the surface.

The lab gear: a **Shimadzu GC-2014 flame ionization gas chromatograph** for the hydrocarbons, and a **near-IR continuous-wave cavity ring-down spectrometer (CW-CRDS)** for the isotopes.

---

## Part 4 — The Results: Numbers That Slap

### Wells leak way more than the ground around them

| Statistic | Wells | Controls |
|---|---|---|
| Mean flow rate | **0.27 kg CH₄/day** (11,000 mg/hr) | 4.5 × 10⁻⁶ kg/day (0.19 mg/hr) |
| Median flow rate | 1.3 × 10⁻³ kg/day (56 mg/hr) | 0 mg/hr (most controls had no leak at all) |
| Range | 6.3 × 10⁻¹ to 8.6 × 10⁴ mg/hr | −0.12 to 4.2 mg/hr |

Read that table carefully:

- The **mean well leak (0.27 kg/day) is about 60,000× higher than the mean control leak.**
- Every single one of the 19 wells was leaking *some* methane (every well had a positive flow rate).
- The leak rates span **seven orders of magnitude** — meaning the biggest leakers are 10,000,000× bigger than the smallest. That's a massive spread.

### The "high emitters" — a few wells dominate the total

Three of the 19 wells (about 16%) were **high emitters** with flow rates roughly **1,000× higher than the median well.** These few wells produce *most* of the total emissions.

This is shown clearly in the cumulative-fraction plot (their Fig. 5): even though the median well leaks only ~56 mg/hr, the **mean is 11,000 mg/hr** because a handful of monsters drag the average way up. Practically, this means: if you want to reduce methane emissions cheaply, you don't need to plug all 500,000 wells — **you need to find the worst few percent.**

### Land cover matters for the background, but not for the wells

The methane coming out of the wells doesn't care whether the well is sitting in a forest, a wetland, a grassland, or by a river. The flow rates were similar across all four environments.

But the **background (control) emissions** depended strongly on land cover:
- **Forest and grassland soil:** often *negative* methane fluxes — these soils actually *absorb* methane (microbes in dry, oxygenated soil eat it).
- **Wetlands:** consistently positive emissions — anaerobic bacteria in waterlogged soil *produce* methane (the same way they do in cow stomachs and rice paddies).

This is important context: in wetland background, ground-level methane can already be measurable, so you can't just assume any methane signal near an old well is from the well. You have to compare against local controls.

### Plugging doesn't necessarily help

You'd hope that a plugged well leaks less than an unplugged one. But:

> "In the grassland area, both the largest and the second-lowest methane fluxes originated from plugged wells."

In other words, **plugging status isn't a reliable predictor of how much a well leaks.** This is bad news — it means cement plugs from decades ago aren't doing the job we'd hope they were, and you can't tell which plugged wells are still sealed just by looking.

(The authors note that visual inspection alone can't tell you about wellbore integrity downhole. A well might *look* plugged on the surface and still have gas migrating up around the cement, or through cracks in the cement, or via "horizontal" subsurface migration through nearby fractures.)

---

## Part 5 — Where Is The Methane Coming From?

This is the detective-story part of the paper. Methane on Earth comes from two main sources:

- **Thermogenic methane** — formed deep underground over millions of years by heat and pressure cooking ancient organic material. This is the same methane that's in natural gas reservoirs. It's typically *enriched in ¹³C* (more of the heavier carbon isotope) and comes with a tail of heavier hydrocarbons (ethane, propane, butane).
- **Microbial methane** — made by bacteria today, in places like swamps, cow guts, and shallow soil. It's typically *depleted in ¹³C* (less of the heavy isotope) and contains almost no heavier hydrocarbons.

So if methane near an old well has a thermogenic fingerprint, it's coming up from deep underground — *through the well* — meaning the well really is acting as a chimney from oil/gas reservoirs to the atmosphere.

### Fingerprint #1: Heavier hydrocarbons

If you see **ethane/methane ratios > 0.01**, it's basically guaranteed to be thermogenic (because microbes don't make ethane). The team found these high ratios **much more often at wells than at controls** — strong evidence wells are leaking gas of geological origin.

But they also found *some* heavier hydrocarbons at *some* control locations, suggesting subsurface gas can travel sideways underground away from a well and seep up through the soil nearby. That's important because it means a leak's "footprint" is bigger than just the wellhead itself.

### Fingerprint #2: Carbon isotopes (δ¹³C-CH₄)

The δ¹³C numbers tell the same story. Northern Appalachian thermogenic methane has known δ¹³C values between −47.9‰ and −30.7‰ (less negative = more ¹³C-enriched = thermogenic).

- **Well samples:** δ¹³C ranged from −71‰ to −21‰ — mostly in the thermogenic range, with some mixed thermogenic/microbial.
- **Control samples:** δ¹³C ranged from −85‰ to −56‰ — overwhelmingly microbial.
- **Only 3 of 26 well measurements** had purely microbial-looking signatures.

Even better — there's a clear correlation: **the biggest-leaking wells emit the most thermogenic-looking methane.** Wells leaking > 1,000 mg/hr are basically guaranteed to be venting deep gas; lower-emitting wells are a mix.

> The bottom line: when you integrate all the emissions weighted by leak size, **the methane from abandoned wells is primarily thermogenic** — it really is fossil-source gas coming up the wellbore, not just biology.

### One weird wrinkle

Normally, more thermogenic methane = more heavier hydrocarbons relative to methane. But Kang et al. saw some samples that were *isotopically depleted* (looked microbial) *and* had high heavier-hydrocarbon ratios. That shouldn't happen with a simple two-source mixing model. The most likely explanation: **microbes living in and around the well are eating some of the methane after it comes up**, which changes its isotopic signature (microbes preferentially eat ¹²C, leaving the remaining methane more ¹³C-enriched — or in some cases the microbes produce extra methane that mixes in). So there's a complex little biological zone right at the wellhead.

---

## Part 6 — Scaling Up: How Much Total Methane?

This is the part that got the paper a lot of attention.

### The simple math

If the average abandoned PA well leaks 0.27 kg CH₄/day, and there are an estimated 300,000–500,000 abandoned wells in Pennsylvania, then total emissions are:

```
0.27 kg/day × 365 days × 300,000 wells ≈ 0.03 Mt/year
0.27 kg/day × 365 days × 500,000 wells ≈ 0.05 Mt/year
```

So **0.03 to 0.05 megatonnes of methane per year** from PA's abandoned wells alone.

### How big is that compared to other PA emissions?

- **4 to 7%** of Pennsylvania's total estimated anthropogenic (human-caused) methane emissions for 2010.
- **0.3 to 0.5%** of PA's gross natural gas withdrawal in 2010.
- That last number is in the same ballpark as official estimates of leakage from *active* US gas production (~0.53–0.59% in 2011).

In other words: **the abandoned, decades-old wells that nobody is paying attention to are leaking about as much, relative to gas produced, as the active production infrastructure that's heavily regulated.**

### The cumulative concern

The active oil/gas infrastructure typically operates for 10–30 years before being decommissioned. **The abandoned wells in this study were 50+ years old, and they're still leaking.** A leak that small but persistent over a century adds up to a *lot* of methane. The cumulative emissions from abandoned wells over time might be much larger than active-production leakage, because abandoned wells just keep leaking forever.

### The big honest caveats

The authors are pretty upfront about uncertainties:

1. **Sample size is tiny.** 19 wells out of hundreds of thousands. The mean is dominated by 3 super-emitters; with such a skewed distribution, you can't be sure the "true mean" across all PA wells is similar.
2. **Site selection wasn't random.** They picked wells they could legally access — these might or might not be representative.
3. **The total number of abandoned wells in PA is itself a guess** (300k–500k is a wide range).
4. **Measurement error is up to a factor of 2** — but they note most of the error sources would make their numbers *under*-estimates, not over-estimates.
5. **The chamber method might miss subsurface horizontal migration** — methane that leaks out of the side of a wellbore and seeps up through the ground a few meters away. They tried to capture this by measuring controls near the well, but it's hard to fully account for.

But even with all these caveats, **the headline finding stands**: the average abandoned well leaks ~60,000× more methane than nearby background, and a small fraction of wells are responsible for most of the total leakage.

---

## Part 7 — Why This Paper Matters

### What was new

- **The first direct measurements ever.** Before Kang 2014, every estimate of abandoned-well methane emissions was a guess. This study turned the guess into data.
- **The "super-emitter" finding.** The discovery that emissions are heavy-tailed — a few wells dominate — has huge implications for cleanup strategy.
- **The thermogenic fingerprint.** Combining hydrocarbon ratios + carbon isotopes proved the methane really is coming up from deep reservoirs through the wellbore, not just from local soil biology. That had been a major source of skepticism.
- **The 4–7% number.** A concrete, defensible, quantitative reason for state and federal regulators to start including abandoned wells in greenhouse-gas inventories.

### What it sparked

This paper became one of the most-cited papers in methane-leakage research. It directly motivated:

- Larger follow-up studies measuring thousands of wells across multiple states.
- Inclusion of abandoned-well emissions in EPA inventory revisions.
- Federal funding (Inflation Reduction Act, infrastructure bills) for finding and plugging the highest-emitting orphaned wells.
- A whole subfield of "find the lost wells" research — which is **exactly the gap** that LiDAR projects like WellSight try to fill. Kang's work proved the wells *matter*; we just need to find them.

### The connection to LiDAR work

A key bottleneck Kang et al. point out: **many abandoned wells are "lost"** — no surface evidence, no public records. You can't measure or plug a well you can't find. This is the gap LiDAR fills:

- Old well sites leave **terrain scars** (excavated pits, access road cuts, pad clearings) that survive long after the rusty pipe falls over and the brush grows back.
- LiDAR punches through forest canopy and lets you see those scars from above.
- So: Kang quantifies *why* lost wells matter (they leak, sometimes a lot). LiDAR is the tool to *find* them at scale so they can be measured and plugged.

It's a perfect one-two: Kang says "abandoned wells are an underestimated climate problem and the worst leakers are hidden in the population." LiDAR + ML says "here's how we find them."

---

## In one breath, again

> Mary Kang and her Princeton team strapped sealed chambers over 19 forgotten old oil and gas wells in Pennsylvania, measured the methane bleeding out, and found that nearly every well leaks — but a few are absolute monsters that dominate the total. By analyzing the heavier hydrocarbons and carbon isotopes coming up the chamber, they proved the gas is real fossil methane from deep underground, not just local soil biology. Scaling their findings to the 300,000–500,000 estimated abandoned wells in Pennsylvania alone, they calculated that these uncounted, un-regulated wells leak as much as 4–7% of all human-caused methane in the state — turning a long-suspected hole in the greenhouse-gas inventory into a measurable, quantitative climate problem and lighting a fuse under the much bigger national question: where are the rest of America's 3 million lost wells, and which ones are the super-emitters?

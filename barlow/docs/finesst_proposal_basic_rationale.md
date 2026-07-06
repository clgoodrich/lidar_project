# Basic Proposal — Line-by-Line Rationale

*Companion to `finesst_proposal_basic.md`. For every block of the proposal, this doc
answers two questions: **why** the line is there (what it is doing to the reviewer or
guarding against) and **how** it works (the mechanism or evidence behind it). Internal
document — never submitted.*

---

## Title

> *"Measuring and Explaining Geomorphic Change in the McMurdo Dry Valleys, Antarctica"*

**Why:** the title is a promise, and this one promises exactly two verbs — measure and
explain. No "novel," no "framework," no method name. Reviewers read dozens of titles;
plain verbs stand out and are impossible to overclaim.
**How:** "Geomorphic Change" (not "Stream-Channel Change") matches the O2 rescope — the
project measures the whole valley floor. "McMurdo Dry Valleys" names the place
specifically enough that a panelist who knows the region is instantly oriented.

## Summary block

> *"The McMurdo Dry Valleys hold the only streams in Antarctica that flow over open ground."*

**Why:** the first sentence must establish stakes in one breath for a reviewer who may
know nothing about the region. "Only streams in Antarctica" is a superlative that is
*true*, cheap to verify, and does the entire why-should-anyone-care job.
**How:** it also quietly scopes the project — streams are the anchor even though O2
widens the view.

> *"A 2026 dissertation (Barlow) mapped two decades of that change but stopped short of
> explaining it — and measured it only inside the stream channels."*

**Why:** names the prior work immediately and honestly. Reviewers distrust proposals
that bury their intellectual parentage; leading with it converts a vulnerability
("isn't this just her work?") into the setup for the gap.
**How:** the two clauses are the two objectives in embryo: "stopped short of explaining"
→ O1; "only inside the stream channels" → O2. Every later section unpacks this sentence.

> *"This document is a plan. No results are claimed here..."*

**Why:** the plan-only rule, stated in the proposal's own voice. It preempts the
reviewer question "where are the preliminary results?" by making their absence a
deliberate posture rather than an omission.
**How:** it reframes what the reviewer should score: the plan's design quality, not a
portfolio of prior outputs.

## §1 Background

> *"...largest ice-free region of Antarctica. For most of a century they were treated as
> the most stable landscape on Earth. That view is now in question."*

**Why:** three sentences that set up the entire scientific tension: stability was the
consensus (cosmogenic dating gives erosion rates of tens of cm per *million* years;
Miocene ash deposits still sit undisturbed), and change against that baseline is
therefore loud. A reviewer needs this contrast to feel why small changes matter here.
**How:** "treated as" (not "is") keeps the claim historical and safe; "in question"
states the current situation without overclaiming that stability is dead.

> *"The valleys are **energy-limited**: frozen water is everywhere, but there is barely
> enough summer heat to melt any of it."*

**Why:** this single definition carries the whole causal argument of O1. If heat is the
scarce input, then heat — not water supply — should control the response. H1 is this
sentence turned into a testable statement.
**How:** defining "energy-limited" at first use follows the rule that a proposal must
parse on first read by a non-specialist panelist.

> *"**What already exists**" (three bullets: terrain-only U-Net, REMA validation,
> three-epoch change maps)*

**Why:** the fair-credit ledger. Each bullet is something the proposal does NOT need to
invent, which shrinks the perceived risk of the plan. Reviewers score feasibility;
showing that the hard foundational pieces are published work makes the plan look
buildable without claiming any of it as ours.
**How:** the three bullets deliberately mirror Barlow's three methodological pillars, in
the order the pipeline runs: detect → validate the ruler → difference.

> *"**What does not exist**... it does not test why... and its analysis is masked to the
> stream channels, so everything the elevation differencing measures outside them...
> was discarded unexamined."*

**Why:** the gap statement is the proposal's reason to exist, so it names both gaps in
parallel structure. "Discarded unexamined" is the strongest honest phrasing: the
measurement of the whole surface already happens inside a DoD; Barlow's channel mask
throws most of it away. That framing makes O2 sound like picking up dropped data, not
inventing a new instrument — which is exactly what it is.
**How:** "named in the dissertation as future work" (for drivers) shows the gap is
real by the prior author's own account, not manufactured by us.

> *"**Relevance to NASA**..."*

**Why:** Relevance to SMD is a *scored criterion* in FINESST review; a proposal without
an explicit relevance statement forfeits points a paragraph can win.
**How:** four arguments in rising order of reach: (1) the 2001 baseline literally *is*
NASA data (ATM lidar) being revived; (2) the methods transfer to NASA missions
(ICESat-2, NISAR elevation records); (3) the MDVs are NASA's canonical planetary-analog
terrain; (4) the FI development itself matches the Division's open-science goals. If a
reviewer rejects one leg, three remain.

## §2 Objectives

> *"**O1 — Attribution.** Determine which climate drivers control each stream's rate of
> geomorphic change."*

**Why:** O1 is first because it is the headline science and the reason the project is a
*science* proposal rather than a mapping exercise. Everything else in the proposal
either feeds it (O2 gives it more change types to explain, O3 makes its inputs
trustworthy) or supports it.
**How:** the driver list (PDD, sunlight, discharge, glacier mass balance, thaw depth)
is exactly the list of datasets in §4 — every named driver is backed by a named, free
data source. No driver is promised that can't be built.

> *"Hypothesis: cumulative melt energy predicts sediment movement better than water
> volume alone. This is testable and falsifiable — if discharge alone predicts just as
> well, the hypothesis fails and that is a publishable answer too."*

**Why:** review panels reward hypotheses that can lose. Stating the failure condition
in the objective itself signals scientific maturity and removes the "what if you're
wrong?" attack — being wrong is a listed outcome.
**How:** the energy-vs-water contrast is not arbitrary: in an energy-limited system
(§1), energy *should* win. The hypothesis is the background section cashed out.

> *"**O2 — Landscape-wide geomorphic change.**... classify each patch of significant
> change by the process responsible: channel shift, thaw-driven subsidence
> (thermokarst), slope movement, fan growth, lake-margin change."*

**Why:** this is the project's scope claim — geomorphology broadly, not channels only.
The five named process types make "landscape-wide" concrete instead of hand-wavy, and
each type is a real MDV phenomenon (thermokarst and lake-level rise are documented in
the region; lake margins move meters because closed-basin levels integrate melt).
**How:** classification is the bridge to O1: each process type gets its own driver
test. That is what H2 means by "distinct driver fingerprints" — channels should follow
melt energy and water, thermokarst should follow thaw depth. If the types *share* one
driver, the sentence "that is also an answer" makes the null explicit and publishable.
Note also what the classes quietly handle: lake-margin change is mostly a *water-level*
signal, not sediment transport — giving it its own class keeps it from contaminating
the geomorphic classes.

> *"One practical note on satellite data... Measuring and correcting that disagreement
> is part of the method (§3), not an objective."*

**Why:** this paragraph is the tombstone of the old O2 (cross-sensor generalization).
The sensor problem is real and a reviewer will think of it, so the proposal must show
it is handled — but handled as plumbing, not headline. Demoting it explicitly prevents
a reviewer from mistaking the project for a remote-sensing methods exercise.
**How:** one sentence of stakes (the record only continues on REMA), one sentence of
placement (it's in §3). Nothing more — proportionality is the message.

> *"**O3 — Calibrated uncertainty.**... on ground that did not change, a 95%-confidence
> threshold should be exceeded by roughly 5% of pixels — no more, no less."*

**Why:** O3 is what makes O2 credible. Outside the channels there is no prior on where
change should appear, so the only defense against a map full of noise is a threshold
that provably behaves. It also produces the most reusable deliverable (an
uncertainty-layer recipe any DEM-differencing study can copy).
**How:** the "no more, no less" calibration test is strict on purpose: exceeding 5%
means the threshold lies (false confidence); far under 5% means it wastes real signal
(too conservative). Verifiable calibration is a claim very few change-detection studies
make — it's the proposal's quality signature.

> *"Together the three objectives turn a one-time survey into a continuing,
> self-checking monitoring capability with an explanatory model behind it."*

**Why:** the closing line answers "so what do we have at the end?" in one sentence —
the difference between three projects stapled together and one program.

## §3 Planned approach

> *O1 step 1: "...keep only changes larger than the detection floor, sum inside the
> stream's channel outline, normalize by channel area and by years elapsed."*

**Why:** each clause kills a specific artifact. Thresholding kills noise counted as
change; area-normalizing kills "bigger footprint = bigger number" (survey footprints
differ between epochs); per-year rates make epochs of different lengths comparable.
**How:** stating the normalizations here — rather than discovering them in Year 1 —
shows the FI already knows where this analysis usually goes wrong.

> *O1 step 3: "Fit two model families — hierarchical regression (interpretable) and
> random forest (flexible)... Validate only on streams held out of fitting. Agreement
> between the two families is the sanity check."*

**Why:** two families because each covers the other's weakness: regression gives
interpretable coefficients but assumes a functional form; a random forest fits anything
but explains little. Agreement means the signal is in the data, not the model choice.
**How:** held-out-stream validation is the honest version of "our model fits well" —
with few streams, in-sample fit is nearly meaningless, and a reviewer who knows small-n
statistics will look for exactly this sentence.

> *O2 steps 1–3 (threshold the whole floor → classify by shape and setting → per-type
> driver tests)*

**Why:** the three steps show O2 is a pipeline, not a wish: detection is inherited from
the existing DoD machinery (nothing new to invent), classification uses observable
evidence (slope position, distance to channels and lakes, ice-cored terrain), and the
output feeds directly into O1's already-built driver models.
**How:** ordering matters — thresholds come from O3, so O2 is explicitly *gated* by O3.
The dependencies among objectives are stated, which is what makes the Year-2 placement
in §6 credible.

> *"**Sensor continuity (method, Years 1–2)**..."*

**Why/How:** same demotion logic as §2's note — present so the reviewer sees it is
scheduled and scoped, small so it can't be mistaken for the point.

> *"**Methods note.** All elevation differencing uses robust statistics (NMAD...)
> because elevation errors in this terrain are known to be heavy-tailed..."*

**Why:** one technical commitment stated up front. Elevation error in this terrain has
a few large blunders (heavy tails); a standard deviation would let those blunders
inflate the noise estimate and hide real change.
**How:** "known to be heavy-tailed" leans on the published error analysis (Höhle &
Höhle; Barlow's own error model) without claiming any measurement of ours — consistent
with plan-only.

## §4 What the project needs

> *The data table, with an "Availability" column reading "public, free" — and one row
> reading "author-gated — must be requested."*

**Why:** the table exists to let a reviewer verify in ten seconds that the project
cannot be data-blocked. The column says "availability," not "status" or "in hand" —
the plan-only rule extends to not implying anything has been fetched.
**How:** putting the single gated item *in the same table* rather than hiding it in
prose is deliberate: the honesty is visible at the same glance as the mitigation
pointer.

> *"**Labels.**... If that request fails, a comparable set will be re-digitized by hand.
> This costs weeks, not months, and is budgeted in Year 1."*

**Why:** the label dependency is the proposal's only real external risk, so it gets its
own paragraph with a fallback that depends on nobody. "Weeks, not months" sizes the
fallback so the reviewer doesn't have to guess whether it wrecks the timeline.
**How:** the claim is credible because hand-labeling terrain features is the FI's
documented prior experience (Research Readiness Statement carries the detail).

> *"**Computing.** A single workstation GPU is sufficient... No supercomputer allocation
> is required."*

**Why:** removes an entire category of reviewer doubt (infrastructure risk) in three
sentences. Modest needs also signal that the budget will be spent on the student, not
on hardware.

> *"**Skills and mentoring.** The FI... is new to Antarctic hydrology and to
> hierarchical statistical modeling — a genuine gap, stated as one."*

**Why:** FINESST's third scored criterion is Research Readiness, and its purpose is
training. A proposal with no gaps reads as either dishonest or as not needing the
fellowship. Naming the two real gaps — and pointing to where the closing plan lives
(RRS, Mentoring Plan) — turns a weakness into program fit.
**How:** the gaps chosen are real but bounded: both are closable by coursework and
advisor mentorship, neither blocks Year-1 work (which is pipeline construction, the
FI's demonstrated strength).

> *"**Community contact.** The dissertation author has been contacted and is responsive.
> Continued cooperation is helpful but not load-bearing..."*

**Why:** answers two opposite reviewer worries at once — "do they have access to the
prior group?" (yes, contact exists) and "does the plan collapse without that
goodwill?" (no, everything runs from public data).
**How:** "not load-bearing" is the operative phrase; it is verifiable against §4's
table, where every required dataset is public.

## §5 Honest assessment

> *The section exists at all.*

**Why:** most proposals bury risk in two mitigative sentences. A section titled
"Honest assessment" that leads with "What could go wrong, and what happens then" is a
credibility play: it does the adversarial review *for* the panel, which leaves them
less to write and signals the FI can be trusted with three unsupervised years.
**How:** every risk follows the same grammar — failure mode, consequence, what gets
delivered anyway. No risk is listed without a landing zone.

> *Risk 1: weak attribution signal → "a rigorous null result with calibrated
> uncertainty... The risk is to impact, not to feasibility."*

**Why/How:** separates the two things reviewers conflate: whether the project can fail
to *finish* (it can't — the measurement gets made regardless) versus fail to *excite*
(possible, admitted). Feasibility risk is the killer in review; impact risk is
survivable and honest.

> *Risk 2: gauges patchy after 2015 → "...the discharge side of the hypothesis test is
> weakest in the most recent period, and the proposal accepts that."*

**Why/How:** this risk is also an argument *for* the design — modeled melt energy
(continuous everywhere) is O1's independent variable precisely because gauges decay.
The last clause ("accepts that") is there because pretending reanalysis fully replaces
gauges would be overclaiming.

> *Risk 3: REMA coverage uneven → anchor on Taylor Valley; scope conclusions.*

**Why/How:** pre-commits the fallback geography so a reviewer can't discover it as a
gotcha. Taylor Valley genuinely has the best three-epoch coverage; claims degrade
gracefully from "acceleration" (3 epochs) to "change" (2 epochs) elsewhere.

> *Risk 4: label request declined → re-digitize.*

**Why/How:** closes the loop opened in §4. Redundant on purpose — risk sections get
read in isolation.

> *Risk 5: outside-channel change may be too small to detect → "O2 narrows back to
> in-channel change and the landscape-wide result is reported as a calibrated null —
> which is itself a quantitative statement about how spatially confined active change
> currently is."*

**Why:** the newest risk, created by the O2 rescope, and the most important to state:
the whole-landscape ambition could genuinely find mostly noise-floor. The mitigation
shows the failure mode converts into a *finding* — "active change is confined to X% of
the surface at our detection limits" is a real, citable number.
**How:** this only works because of O3 — a calibrated null means something; an
uncalibrated null is just a shrug. The risks section quietly demonstrates the
objectives' interdependence.

> *"**What this proposal does not claim.**"*

**Why:** the plan-only posture restated as a boundary. It also protects the FI in any
later interview — no sentence in the document asserts work performed.

> *"**Why it is worth doing anyway.**"*

**Why:** an honest-assessment section that ends on risk would leave the reviewer in a
down-beat. This paragraph is the recovery: the data exist, are free, and the missing
ingredients (drivers, whole-landscape picture, error bars) are "exactly the size of a
three-year graduate project" — which reframes the fellowship as the natural container
for the work.

## §6 Timeline

**Why the shape:** Year 1 = build + first science (attribution on Taylor Valley);
Year 2 = the new-scope science (landscape-wide classification), *after* O3 exists to
gate it; Year 3 = synthesis, prediction, and product release. Each year ends in a
named deliverable because reviewers check whether a timeline produces papers or just
activity.
**How:** the dependencies run downhill — nothing in Year 2 needs anything that isn't a
Year-1 deliverable. "Secure or rebuild training labels" sits in Year 1 because it's
the longest-lead external dependency.

## §7 Data management and open science

**Why:** a compressed echo of the separate 2-page OSDMP (which is the binding
document). It exists in the S/T/M so the open-science posture is visible even to a
reviewer who reads nothing but the six pages.
**How:** the sentence structure mirrors NASA's expectations: what is produced, where it
is released, what is deliberately not archived (heavy regenerable rasters), and what
metadata every product carries.

## References

**Why these seven:** [1] the dissertation (the foundation — citing it generously is
both honest and strategic); [2] the peer-reviewed proof of concept (shows the
foundation survived review, not just a committee); [3] Höhle & Höhle (the NMAD
methodology the error handling rests on); [4] REMA (the dataset the future of the
record depends on); [5] U-Net (the architecture's origin); [6] the LTER data catalog
(the driver data's provenance); [7] ERA5 (the reanalysis gap-filler). Every reference
is load-bearing — each one backs a specific claim in §1–§3, and nothing is cited for
decoration.

---

*Maintained alongside `finesst_proposal_basic.md` — when a proposal line changes, its
entry here changes in the same pass.*

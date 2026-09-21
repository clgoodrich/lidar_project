# Hard questions, and plain answers

Written from the outside: a sceptic who knows lidar, knows Pennsylvania oil and
gas, and is not inclined to be generous. Every answer uses the project's own
numbers.

Where the honest answer is "we don't know" or "we haven't tested that", it says
so. Those are the ones worth rehearsing.

---

## The premise

**Q. Pennsylvania has hundreds of thousands of undocumented wells. You surveyed
20 square kilometres. Why should anyone care?**

Because the bottleneck is not money, it is addresses. The 2021 Infrastructure
Act put $4.7 billion toward plugging orphaned wells. You cannot plug a well you
cannot find, and for most of these there is no record to look up.

This is a method, tested on two tiles. The point is whether the method works,
not whether 20 km² is a lot of ground.

**Q. Why not just use the state's well records and go look?**

That was the first thing tried, and it fails on the data. The DEP list has
20,108 well records for Venango County. **8,054 of them carry a placeholder
spud date of 1 January 1800** — the database's way of saying it does not know.
Another 1,553 have no date at all. So roughly 48% have no usable date.

Worse, where records exist the coordinates are unreliable. Anything logged
before 1990 was read off paper plat maps, carrying 50 to 200 metres of error.
On the ground that means the dot and the pit are not in the same place, and
sometimes the dot has no pit anywhere near it.

**Q. If a well was plugged properly, why does it matter that you found it?**

It may not. But "plugged" for a pre-1985 well often meant a wooden plug, or a
tree stump, or nothing. Casing was frequently pulled out for scrap, which
leaves an open conduit rather than a sealed one. Finding it is step one;
whether it needs work is a field decision.

---

## Pennsylvania history

**Q. Drake's well was 1859. Why would a 160-year-old hole still leave a mark?**

Because what you are seeing is not the hole. It is the disturbed ground around
it — the earthen pit dug beside the well for oil and brine, the cleared and
levelled pad where the rig stood, and the access track cut in to reach it.

Those are earthworks. In forest, on the Appalachian Plateau, earthworks
persist. They fill with leaf litter and silt and become shallower, which is
exactly why the measured shape is a dish 0.7 m deep rather than a hole.

**Q. Why 1985? That date looks arbitrary.**

It comes from Pennsylvania's Oil and Gas Act. A well counts as orphaned if it
was abandoned before the Act took effect, has not been operated by the current
owner, and the current owner never took any economic benefit from it.

Before that, walking away was legal. That is the whole reason this category
exists.

**Q. Your slide says Pennsylvania had 77% of the world's oil. Can you source
that?**

Have the citation ready before you say it out loud. The defensible version is
that Pennsylvania dominated world production for roughly the first two decades
after 1859 and remained the leading source into the 1880s. If you cannot cite
the exact 77% figure, use the softer claim.

**Q. Venango County is Oil Creek and Pithole. Those are 1860s boomtown wells,
drilled fast and cheap. Are they even the same kind of feature as a 1920s
well?**

Probably not, and nothing here has tested that. The annotations were drawn on
shape, not on age. A dense 1860s field and a scattered 1920s lease would look
different on the ground, and the model was never asked to tell them apart.

It is a fair criticism that the training set mixes eras without saying so.

---

## The lidar itself

**Q. Four points per square metre. How do you expect to resolve a 70-centimetre
depression with that?**

Density is not the limit here — vertical accuracy is, and there is room.

At ~4 points per square metre, a pit 13 m across has roughly five hundred
ground measurements inside it. The survey's vertical accuracy requirement is
10 cm RMSE. The feature is 70 cm deep.

So the signal is about seven times the noise floor, measured with hundreds of
points. That is a comfortable margin — the difficulty is separating it from
other 70 cm dishes, not detecting it.

**Q. The laser can't see through leaves. How much of the ground are you
actually measuring?**

Not all of it, and the deck says so. Even after recovering the discarded
returns, 8.2% of the training area has no ground measurement at all. Those are
under canopy thick enough that no pulse reached dirt.

Surveys are flown leaf-off for this reason. It helps; it does not solve it.

**Q. You threw out the survey contractor's classification and substituted your
own. Why should anyone trust yours over a professional vendor's?**

We did not replace it. Where the vendor classified ground, we agree with it and
keep it. What we add is ground where the vendor had none.

And the returns we added are not junk. Their measured accuracy was compared
against the returns the vendor kept, and both clear the published
specification. The vendor discarded good data.

**Q. Discarded why?**

Every return past 18 degrees of scan angle was deleted before delivery. Not
degraded gradually — deleted, at exactly 18 degrees.

A clean vertical cliff at a round number is a processing decision, never
physics. And it is not universal: that cut appears in six of seven Venango
tiles from the March 2020 block and zero of seven McKean tiles from a different
block.

**Q. What did that actually cost you?**

13.8% of the training area had no ground measurement under it. Putting the
discarded returns back brings that to 8.2% — 2.9 million cells filled, about a
quarter of the holes.

On a single cross-section it is starker: 32% of one line across the ground had
nothing beneath it, down to 2% with the returns restored.

---

## The artefacts

**Q. You found stripes in your own data that are the same size as the thing you
are looking for. How do you know your detections are not stripes?**

That is the right question, and it is why the artefact is in the deck rather
than hidden.

Two different stripe problems were found. On canopy height they are empty
cells — no return came back, nothing to draw — and coarsening the grid from
0.5 m to 1 m removes them completely, 3.22% of a test window down to 0.00%.

On the shape layers they are real measurements that disagree with each other.
The ground surface has **no empty cells at either resolution**, so those cannot
be missing data. They run at 78°, the bearing of the scanner's own lines.

Their amplitude is tens of centimetres against a 70 cm target, so they are a
genuine risk. The mitigation is that a pit is a closed, roughly circular dish
and a stripe is a long straight line. The model sees shape over a patch, not
one cell at a time.

**Q. "Mitigation" is doing a lot of work there. Have you measured that the
detections are not artefact-driven?**

Not directly. That test has not been run. The honest position is that the
detections behave like pits — closed, circular, in the right size range, in
plausible places — and that the artefact has a different geometry. That is an
argument, not a measurement.

**Q. You tried three explanations for the stripes and all three failed. Doesn't
that mean you don't understand your own data?**

It means we do not understand that artefact. A washboard from line-to-line
height offsets, a scan-angle or attitude effect, and interswath disagreement
were each tested and each refuted by the measurement meant to confirm it.

The data provider's own position is that it is in the raw data and cannot be
fixed by the end user. Their suggested fix — averaging points in a radius
instead of triangulating — made the shape layers visibly worse, because
averaging smooths heights and roughens the slopes between cells.

So: managed, not solved. Saying otherwise would be untrue.

---

## The ground truth

**Q. One person drew every label. Then that person's model was scored against
that person's drawings. What is precision actually measuring?**

Agreement with one annotator. Not correctness.

Precision runs 0.59 to 0.69 across the three tasks. That is the rate at which
the model agrees with one person's judgement about what counts as a pit, on
ground that person had already looked at.

A second annotator on a subset is the only thing that measures this, and it has
not been done. It is on the next-steps slide for that reason.

**Q. Recall 0.928 sounds excellent. Recall of what?**

Of pits that were drawn. If there are pits on that tile nobody noticed, they
are not in the denominator, and the model is not penalised for missing them.

So 0.928 means: of the 712 features a person identified, the model found 92.8%.
It does not mean 92.8% of the wells that are there.

**Q. So you have never confirmed a single well in the field.**

Correct, and the deck states it. No field visit, no records check. Everything
produced here is a candidate.

That is the single largest gap in the work, and it is the first item on the
next-steps slide — because field-checking a sample is what converts recall from
a rate against drawings into a rate against reality.

**Q. Why did you draw roads and streams at all? You are looking for wells.**

Roads because a well that nobody recorded still had to be reached, so an
overgrown access track is evidence. 535.9 km of it was drawn by hand.

Streams because the model kept calling them roads. Drainage is not a target —
it is a class the model is taught in order to reject it, which worked.

---

## The model

**Q. Why a neural network? A pit is a circular depression. Why not just look
for circular depressions?**

That was the earlier approach — match a template of a mean pit across the
terrain layers — and it is not in this deck any more.

The reason is on the slide about layers: no single terrain measure separates a
well pit from a natural hollow. Local relief and topographic position light up
both. What separates them is a combination, and a network is a practical way to
learn a combination.

**Q. You tested four architectures and the biggest one gained 0.002 on pits.
Doesn't that mean the network is not doing much?**

It means architecture is not the constraint. Three times the parameters and
ImageNet pretraining bought a gain smaller than the spread between folds.

The useful reading is that the limit is upstream — the channels the model gets,
and the labels it is trained on. That is why the next-steps slide is about
channels and labels rather than about bigger models.

**Q. Your model sees seven terrain layers and nothing else. You built a canopy
height model and an intensity layer and feed it neither. Why?**

No good reason. Both are built and neither reaches any detector, so the network
only ever sees shape — never material, never vegetation.

That is listed as one of the next changes precisely because it is cheap: a
channel, not a new architecture.

**Q. How do you know the model didn't just memorise the tile?**

Because of how the split was made. The tile is cut into a 12 by 12 grid and
whole blocks go to training or testing. Individual pits are never split.

If you split pit by pit, a training pit ends up 30 metres from a test pit, on
the same hillside, in the same light. The model would recognise the hillside
and score beautifully while learning nothing.

And the second tile is the harder check: 1.5 km away, never seen, thresholds
frozen. Recall drops 0.017.

---

## The numbers

**Q. "Flags 0.21% of the tile" sounds tiny. What is it in the field?**

The tile is 4.5 km square, so 20.25 km². 0.21% of that is about 42,500 m².

Combining recall and precision: to recover roughly 660 real pits the model
points at about 1,040 places, of which around 380 are wrong. So a field crew
checks a thousand spots to find six hundred and sixty wells.

That is a workable ratio. It is not "the computer found the wells".

**Q. And the pad model?**

Much worse on burden. Recall 0.912 and precision 0.587, flagging 11.6% of the
tile — about 2.3 km² to review.

Its finding rate is fine. The amount of ground it asks someone to walk is the
problem, and the deck says so rather than reporting only the recall.

**Q. Precision 0.63 means a third of your detections are false. On 350,000
wells that is an enormous amount of wasted field time.**

Two things. First, that third is measured against one person's drawings, so
some of those "false" detections may be real pits the annotator missed. Nobody
knows which, because nothing has been field-checked.

Second, the threshold is adjustable. Raising it trades recall for precision. The
right setting depends on whether the cost is a wasted site visit or a missed
well, and that is a programme decision, not a modelling one.

---

## Generalisation

**Q. Two tiles, 1.5 km apart, same county, same survey, same flight block. What
exactly has been generalised?**

Nothing, and the conclusion slide says so in those words.

What the second tile shows is that the model did not memorise the first one —
recall fell from 0.928 to 0.911 on ground it had never seen, with thresholds
frozen. That is a real result and a narrow one.

A tile from a different acquisition is the actual generalisation test, and it
has not been run.

**Q. If the artefacts are specific to one flight block, does your method only
work on that block?**

The opposite is more likely. McKean County is QL1 — roughly twice the point
density — and shows none of the 18-degree cut in seven tested tiles. Cleaner
data should make this easier, not harder.

But that is an expectation, not a result. The model has not been run there.

---

## The questions with no good answer yet

**Q. Pennsylvania forests are full of relict charcoal hearths — flat circular
platforms 10 to 15 metres across, cut for the charcoal iron industry, and
mapped in their tens of thousands elsewhere in the state with exactly this kind
of lidar. Your pit rims average 16 metres across. How do you tell them apart?**

This is the sharpest question in the set, and the honest answer is that it has
not been addressed. Charcoal hearths appear nowhere in the annotations, the
negative classes, or the analysis.

The argument that they should separate is geometric: a hearth is a **flat or
slightly raised platform**, often cut into a slope, while a well pit is a
**closed concave dish**. Negative openness — the layer that matters most for
pits — measures enclosure, and a platform is not enclosed. On a slope, though,
a hearth's back-cut can read as a partial depression, and that is where
confusion would live.

Venango borders Clarion County, which was a genuine charcoal-iron district, so
hearths are plausibly present. Nobody has checked.

**If this comes up: concede it, say the geometry argues for separation, and say
it needs labelling and testing.** Do not claim it is handled.

**Q. What else looks like a well pit?**

Several things, and only some are covered:

- **Vernal pools and seasonal ponds** — natural, closed, and the right size.
  Ponds are listed as a proposed negative class and are not yet trained in.
- **Cellar holes** from abandoned farmsteads. These turned up in the annotation
  quality-control review as unusual-but-correct features, so they are already a
  known source of confusion.
- **Tree-throw pits** from windthrown trees. Smaller, typically 1 to 3 metres,
  and paired with an adjacent mound — usually separable on size.
- **Strip-mine scrapes and quarry workings.** Listed as a proposed negative
  class.
- **Sinkholes** are the one thing you can dismiss cleanly: this is Appalachian
  Plateau sandstone and shale, not carbonate karst.

**Q. Your annotation quality control found that half the flagged pits were
genuine errors. Doesn't that mean the training data is roughly 5% wrong?**

Something like that, yes. 90 of 856 measured pits were flagged as unusual, the
top 30 were reviewed, and about half of those were real mistakes — mis-clicks
and wrong spots.

That is why the check was run and reported rather than left out. It does not
make the labels clean; it makes the error rate known.

---

## Practical

**Q. What would it take to run this on a whole county?**

The processing is not the hard part — it is reproducible and the derivative
build is scripted. Two things scale badly.

The first is annotation. Every label in this project was drawn by one person by
hand.

The second is verification. Without field checks, running it wider produces
more candidates of unknown reliability, which is not obviously useful to
anyone.

**Q. What is the single biggest weakness?**

No field validation. Every number in the deck is measured against hand-drawn
annotation by one person. Until somebody walks to a sample of candidates and
reports back, "recall 0.928" means agreement with a drawing, not with the
ground.

**Q. If you had to defend one number, which is it?**

Pits: recall 0.928 while flagging 0.21% of the tile, and 0.911 on a tile the
model had never seen with nothing retuned.

The second number is the one that matters. Detection rates are easy to inflate
by flagging everything. Finding nearly all of the features while pointing at a
fifth of one percent of the map is the result.

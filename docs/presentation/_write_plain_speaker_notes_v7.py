"""Plain-language speaker notes for every slide in v6.

WHY
---
Before this, 2 of 70 slides had no notes at all and 13 carried the placeholder
"(no speaker notes written yet -- the figure still carries its own caption)".
The rest were written at varying levels, several assuming the reader already
knows what recall, openness or a U-Net is.

These are written to be read out or glanced at under pressure, by someone who
should not have to decode their own slide. House style, applied throughout:

  * short declarative sentences, one idea each
  * every term defined the first time it appears -- recall, precision, LRM,
    openness, threshold, coherence, QL2
  * no jargon left standing on its own
  * the number on the slide is restated in words, because a number nobody can
    paraphrase is a number the room will not remember
  * where a claim has a limit, the limit is in the note, so it gets said out
    loud rather than discovered in questions

Notes are keyed by slide NUMBER as the deck currently stands (70 slides). If
slides move, this script's keys move with them -- it re-checks each slide's
title against EXPECT before writing, and refuses rather than putting the wrong
note on the wrong slide.

Run:
    python docs/presentation/_write_plain_speaker_notes_v6.py
Reads:
    docs/presentation/WellSight_Presentation v6.pptx
Writes:
    docs/presentation/WellSight_Presentation v7.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/presentation/WellSight_Presentation v6.pptx"
DECK = ROOT / "docs/presentation/WellSight_Presentation v7.pptx"

#: slide number -> (first words of its title, the note)
#: The title check is a guard: a note is only written if the slide is the one
#: it was written for.
NOTES: dict[int, tuple[str, str]] = {

1: ("Morphological Characterization", """
This is about finding old oil wells that nobody has a record of.

"Morphological" just means "by shape". I am not looking for the well itself. I
am looking for the dent it left in the ground.

Western Pennsylvania, because that is where the American oil industry started,
and where it was least regulated.
"""),

2: ("The Problem", """
Oil drilling here started in the 1850s. At one point this state produced most
of the world's oil.

There were no rules about cleaning up. When a well stopped paying, people
walked away and that was legal.

Over 350,000 wells are on the books. The real number drilled is far higher,
because for most of that period nobody was required to write it down.
"""),

3: ("The Problem", """
Two words that sound the same and are not.

Abandoned means no production for twelve months and no equipment left on site.

Orphaned means abandoned before 1985, with nobody responsible for it any more.

Orphaned is the harder problem. There is no company left to send the bill to,
so the cleanup falls to the public.
"""),

4: ("What Does an Orphaned Well Pit", """
That photo is a real wellhead. A pipe sticking out of the brush.

Left alone, these leak. Methane comes up, which is a strong greenhouse gas.
Brine and oil can reach groundwater. And someone can fall in one.

There are at least 35,000 of them in Pennsylvania. The 2021 Infrastructure Act
put 4.7 billion dollars toward plugging them.

So the money exists. The bottleneck is finding them. They are decades old and
sitting under thick forest.
"""),

5: ("Why LiDAR", """
LiDAR is a laser on an aeroplane. It fires pulses at the ground and times how
long the bounce takes. That gives a distance, and a distance gives a height.

The useful trick: some pulses slip through gaps in the leaves and hit actual
dirt. Throw away everything that hit a leaf, and you are left with a map of the
bare ground underneath the forest.

The two pictures are the same place. The satellite image shows trees. The LiDAR
shows the ground, with roads and pits in it.
"""),

6: ("Study Area", """
Two counties in western Pennsylvania. Steep slopes, deep stream valleys, heavy
deciduous forest. 150 years of coal, oil and gas on top of that.

The data is free, from the US Geological Survey's 3DEP programme, flown between
2018 and 2020.

"QL2" is a quality grade. It means roughly four laser points per square metre.
Think of it as the resolution of the measurement.

Each study tile is 4.5 kilometres square.
"""),

7: ("Where the two study tiles", """
Two squares on a map.

Everything was trained on the one called 9t. That is the homework.

The other one, 613590, sits 1.5 kilometres west. No model has ever seen it.
That is the exam.

Keeping those two separate is the whole basis for believing any number later in
this talk.
"""),

8: ("The DEP Records Problem", """
DEP is the state environmental agency. Their well list is the obvious thing to
train a model on.

It does not work. The dots do not sit on the pits.

Before 1990 those coordinates were read off paper plat maps, so they can be 50
to 200 metres out. Some records have nothing on the ground at all.

That is why everything in this project is hand-drawn instead. It was not a
preference. It was the only option.
"""),

9: ("Pipeline Overview", """
The whole method on one page.

Laser points go in. They get turned into pictures of the ground's shape. I draw
examples by hand. A network learns from those. Then it runs on ground it has
never seen.

Every slide after this is one of these boxes, in detail.
"""),

10: ("Data QA", """
Before trusting any of this, I checked what we were actually given.

The survey company deleted a large number of their own measurements before
handing the data over. That is normal practice. But it has a cost.

This slide is what that cost us. The next few slides show how I measured it.
"""),

11: ("Data QA", """
The laser sweeps side to side under the aircraft. "Scan angle" is how far off
straight-down a given pulse was pointing.

Whoever processed this data threw away every return past 18 degrees.

And not gradually. At exactly 18 degrees the ground classification falls off a
cliff. A clean vertical edge like that is always a human decision, never a
property of the physics.
"""),

12: ("Data QA", """
The obvious worry is that I am criticising airborne LiDAR in general. I am not.

Only the March 2020 batch of flights has this cut in it. Other flights in the
same programme, over the same kind of terrain, do not.

So this is one contractor's choice on one batch of work. Not a standard, and
not something wrong with the technology.
"""),

13: ("Data QA", """
The fair question: maybe they deleted those returns because they were bad.

They were not. I measured the accuracy of the discarded returns against the
ones that were kept.

Both clear the published specification. The thrown-away data is good data.

That is what justifies putting it back.
"""),

14: ("Data QA", """
Red is where there is no ground measurement at all.

Not "the ground is flat here". Nothing was measured. Zero points.

Look at the pattern: the red runs in stripes, along the edges of each flight
line. That is the 18-degree cut, drawn on a map.

13.8% of the training area. Wherever it is red, the surface is a guess drawn
between the two nearest real measurements.
"""),

15: ("Data QA", """
Same piece of ground. This time showing only what was thrown away.

13.7 million ground measurements.

They fall in exactly the same stripes as the holes on the last slide. That is
not a coincidence. These are the measurements that would have filled them.
"""),

16: ("Data QA", """
Put the discarded returns back and most of the holes close.

13.8% empty drops to 8.2%. That is 2.9 million cells filled in.

About a quarter of the holes close. Be honest about the rest: those are under
canopy so thick that no pulse ever reached the dirt. No amount of reprocessing
recovers those.
"""),

17: ("Data QA", """
This is the same story as a cross-section, which is easier to see.

One line drawn across the ground, twice.

Top is only what the survey called ground. 32% of that line has nothing
underneath it.

Bottom is the same line with the discarded returns added back. 2%.

Same place, same laser, same flight. The only difference is a processing
choice.
"""),

18: ("Data QA", """
This is the fair-check slide, and it is worth saying out loud.

Where the vendor said "this is ground", we agree with them. I am not
overwriting their work or claiming they got it wrong.

We are adding ground where they had none. That is the whole change.
"""),

19: ("Step 1: terrain derivatives", """
Now the ground surface gets turned into pictures.

A "derivative" sounds technical. It just means one question asked about the
shape, at every single point on the map, and the answer drawn as an image.

Eleven questions, eleven pictures, all of the same hillside.

The model looks at several at once, because no single one of them is enough on
its own.
"""),

20: ("Step 1: Terrain Derivatives", """
Slope. How steep is it.

Flat ground is dark. Steep ground is bright.

A pit has steep walls around a flat floor, so on a slope map it shows up as a
bright ring with a dark middle.
"""),

21: ("Step 1: terrain derivatives", """
Canopy height. How tall are the trees.

You get it by taking the top surface, subtracting the ground surface, and
keeping whatever is left over.

One thing to be clear about, because people ask: those stripes are not trees.
They are missing data. 3.2% of this window had no first return come back at
all, so there is nothing to measure the height of.
"""),

22: ("Step 1: Terrain Derivatives", """
Roughness. Is it bumpy.

It measures how much the surface wobbles over a short distance.

Rubble and ploughed ground are rough. A pit floor is smooth, because it filled
in with silt and settled flat.
"""),

23: ("Step 1: Terrain Derivatives", """
TPI stands for Topographic Position Index, which is a mouthful for a simple
idea.

Is this spot higher or lower than the ground immediately around it.

Ridge tops come out positive. Hollows come out negative. A pit is a small but
strong negative.
"""),

24: ("Step 1: Terrain Derivatives", """
LRM stands for Local Relief Model.

Take the landscape, smooth it heavily, then subtract the smoothed version from
the real one.

The big hills cancel out, because they are in both. What survives is the small
stuff sitting on top of them.

That is useful here, because everything man-made is small.
"""),

25: ("Step 1: Terrain Derivatives", """
Openness, positive.

Imagine standing at a point and looking out in every direction. Positive
openness asks how much open sky you can see.

On a hilltop, a lot. In a ditch, very little.

It finds things that stick up.
"""),

26: ("Step 1: Terrain Derivatives", """
Openness, negative. Same idea, upside down.

How enclosed are you. How much of your view is blocked by ground that is higher
than you.

Standing in a pit, almost all of it.

This ends up being the single most useful picture for finding pits.
"""),

27: ("Step 1: Terrain Derivatives", """
Hillshade. Pretend the sun is shining from one direction and draw the shadows.

It is not real light and it is not real data. It is a drawing that makes shape
readable to a human eye.

Worth saying: this is the picture I did all the hand-annotation on.
"""),

28: ("Step 1: Terrain Derivatives", """
RRIM stands for Red Relief Image Map.

Hillshade has a real flaw. It invents a sun direction, so anything lined up
with that fake sun disappears into the glare.

RRIM does not use a sun at all, so nothing hides.
"""),

29: ("Step 1: Terrain Derivatives", """
The same picture, explained.

Red is the strength of the relief. Light and dark is openness, which is the
enclosed-or-exposed measure from two slides ago.

Put together, the shape reads equally well from every direction. No fake sun,
so no direction gets favoured.

And yes, it is red. That is just the convention.
"""),

30: ("Why we drew our own labels", """
This is the evidence for the claim I made earlier.

The state's well records and the visible ground do not line up. There are dots
with no pit under them. There are obvious pits with no dot.

So the records cannot be the answer key. If you train on them, you teach the
model to find bad coordinates.

The last line matters too: one terrain picture on its own is not enough either.
LRM and TPI light up natural hollows just as happily as man-made ones.
"""),

31: ("Manual Annotation", """
Every road here was drawn by hand. 535.9 kilometres of it.

3,690 separate lines, which join up into 1,747 connected networks.

The network count is the more honest number. One road drawn in four pieces is
still one road.

I also drew 112 lines marked "not road". Those teach the model what to reject,
which turns out to matter as much as what to accept.
"""),

32: ("Manual Annotation", """
Streams and ditches. 45 kilometres, on the training tile only.

I did not draw these because I want to find streams. I drew them because from
above they look like roads, and the model kept calling them roads.

So they get taught as their own thing. This is teaching by counter-example.

Cut into 1,791 short segments for training, because a model learns better from
many short examples than a few long ones.
"""),

33: ("Manual Annotation", """
A pad is the flat clearing where the drilling equipment sat.

995 of them, 144 hectares in total. The average is about 1,450 square metres,
so roughly 40 metres on a side.

Note the tile breakdown: 613590 has zero. Nobody ever drew pads there.

Remember that. It comes back later when I say pads cannot be scored on that
tile.
"""),

34: ("Measured pit morphology", """
This is what a pit actually is, measured rather than guessed.

A shallow bowl. About 0.7 metres deep and 13 metres across.

Sit with how small that is. Seventy centimetres of depth spread over thirteen
metres of width. It is a dish, not a hole.

That is exactly why resolution matters so much here, and why this is hard.
"""),

35: ("Manual Annotation", """
The rim. The outer edge of the disturbed ground around a pit.

723 outlines, averaging 205 square metres, so about 16 metres across.

586 of them pair up with a floor. Having both means you can measure the wall
between them, which is where the shape information lives.
"""),

36: ("Manual Annotation", """
The floor. The flat bottom of the pit.

712 of them, averaging 32 square metres. That is about six metres across.

Here is the useful ratio: the floor is only 16% of the outline by area. The
other 84% is wall.

Floor and rim were drawn separately because they look completely different to
the laser. One is flat, one is sloped.
"""),

37: ("Preprocessing", """
Bookkeeping, and it matters for honesty.

Seven layers were drawn by a human hand. Everything else in this project was
computed from those seven by code.

Nobody hand-drew the pit walls. Nobody hand-matched rims to floors. Those were
derived, and derived things can be re-derived and checked.
"""),

38: ("Preprocessing", """
A problem I made for myself.

Every pit got drawn twice. Once as a floor, once as a rim. Nothing in the file
recorded that those two shapes were the same pit.

712 floors, 723 rims.

I matched them by taking, for each floor, whichever rim it overlaps most. That
found 586 pairs.

126 floors have no rim, and 138 rims have no floor. Those are simply the ones
where only one of the two got drawn.
"""),

39: ("Preprocessing", """
The agreed numbers, in one place.

Every downstream script reads its constants from here rather than defining its
own.

It is dull, and it is the reason two scripts never quietly disagree about what
a pit is.
"""),

40: ("Annotation Quality Control", """
This is me checking my own drawings, which nobody enjoys.

I ran four anomaly-detection methods over 856 measured pits. Anomaly detection
just means "which of these look unlike all the others".

90 got flagged, about one in ten. I reviewed the worst 30 by hand.

Half were genuine mistakes. Mis-clicks, wrong spots, sloppy outlines.

The other half were correct but unusual. Deep cellars. Badly degraded pits on
steep ground.

The point is not that the labels are perfect. The point is that the answer key
got audited before anything trained on it.
"""),

41: ("Preprocessing", """
Sometimes two labels land on the same pixel. A pit sits inside a pad, say.

Something has to decide which one wins, and it has to decide the same way every
single time.

That is all this is: a fixed order, applied everywhere.
"""),

42: ("Preprocessing", """
Pits are clumped together, not spread evenly.

So if you cut the tile into two equal halves by area, you do not get two equal
amounts of evidence. One half can have most of the pits in it.

Balance on the number of pits instead. Area is the wrong thing to make equal.
"""),

43: ("Preprocessing", """
This is the most important slide about whether the results are real.

The tile gets cut into a 12 by 12 grid. Whole blocks go to training or to
testing. Never individual pits.

Here is why. If you split pit by pit, a training pit ends up thirty metres from
a test pit, on the same hillside, in the same light.

The model would then recognise the hillside, not the pit. The score would look
great and mean nothing.

Splitting by block makes that impossible.
"""),

44: ("Preprocessing", """
The held-out blocks, and every pit inside them.

These are the exam questions. The model never saw a single one of them while
learning.

Every recall number later in this talk is measured on these.
"""),

45: ("Preprocessing", """
Pits, pads and roads all use the same block assignment.

If they each had their own split, a block could be test ground for pits and
training ground for roads at the same time.

The tasks would leak into each other and the numbers would quietly inflate.
One split for everything closes that door.
"""),

46: ("Model building", """
A U-Net. It is a standard, well-known image model, not something exotic.

Seven pictures go in. For every half-metre cell it gives back a number per
class.

It is called U-shaped because it zooms out to understand context, then zooms
back in to place the edges precisely. The zoom-out sees "this is a hollow on a
hillside". The zoom-in says "and the edge is exactly here".
"""),

47: ("Model building", """
The model does not answer yes or no.

It gives a probability for every cell. 0.9 means very confident. 0.1 means
barely.

That is more useful than a yes, because it lets you choose afterwards how
cautious you want to be.
"""),

48: ("Model building", """
Eventually you have to commit to an answer.

Pick a cutoff. Above it, the cell becomes a candidate. Below it, nothing.

Moving that cutoff is a trade, and it is worth naming the trade out loud. Lower
catches more real pits and also more junk. Higher is cleaner and misses more.

There is no correct setting. There is only the one that suits what you plan to
do with the output.
"""),

49: ("Outcome - Roads", """
43 kilometres of road were withheld from training entirely.

Recall 0.982 means it found 98.2% of them. Recall is simply: of the real things
out there, what fraction did we find.

It flags 5% of the tile to do that. So you would be walking one twentieth of
the ground.
"""),

50: ("Outcome - Drainage", """
Drainage is not something we want to find. It is something we want the model to
stop being fooled by.

Teaching it as its own separate class is what stopped the road model calling
every stream a road.

It worked. That is the whole result on this slide.
"""),

51: ("Outcome - Pads", """
Recall 0.912, so it found 91% of the pads.

Precision 0.587 is the other half of the story. Of everything it flagged, 59%
were real. So about four in ten are false alarms.

And it flags 11.6% of the tile. That is a lot of ground for somebody to walk.

The finding rate is fine. The burden is the problem.
"""),

52: ("Outcome", """
This is the good one.

Recall 0.928, so it found 93% of the pits.

And it only flags 0.21% of the tile to do it. That is a fifth of one percent of
the ground.

That second number is the one that matters if you are actually sending someone
out. It found nearly all of them while pointing at almost nothing.
"""),

53: ("Held-Out Tile 613590", """
Now the exam tile. Different ground, 1.5 kilometres away, never seen in
training.

153 pits there. Recall 0.911.

At home it was 0.928. So moving to completely new ground cost 0.017.

That is a small drop, and a small drop is the point. A model that collapses on
new ground has learned the tile, not the feature.
"""),

54: ("Held-Out Tile 613590", """
Nothing to report here, and I would rather say that than pad it out.

No pads were ever drawn on this tile, so there is no answer key to score
against.

That is not a failure of the model. It is a gap in the annotation. The
candidates it produced may well be right. There is simply no way to check.
"""),

55: ("Held-Out Tile 613590", """
Three road numbers, and they are easier than they sound.

Completeness 0.811: it found 81% of the real road.

Correctness 0.816: 82% of what it drew is real road.

Quality 0.686: a single number combining the two, so you cannot win by cheating
on one of them.
"""),

56: ("Held-out tile 613590", """
146 of 153 found, by a model that had never seen this tile.

Two ways of setting the cutoff, and I am showing both rather than the flattering
one.

The recall-weighted rule gives 0.911, down 0.017 from home. The balanced rule
gives 0.792, down 0.069.

Thresholds were frozen from the training tile. Nothing was retuned here. Tuning
on the exam tile would be cheating.

No precision figure, because the tile is not fully annotated. You cannot count
false alarms when the answer key is incomplete.
"""),

57: ("Held-Out Tile 613590", """
Same situation as the pads.

No drainage was drawn on this tile, so the class trains on the other tile
alone.

Nothing to score.
"""),

58: ("Held-out tile 613590", """
42 pit candidates and 161 pad candidates, with no retraining of any kind.

Pits can be scored here, because 153 were drawn. Recall 0.911.

Pads cannot, because none were drawn.

And the last line is the one to actually say: every one of these is a
candidate. Not a confirmed well. Nothing on this slide has been visited.
"""),

59: ("Held-Out Tile 613590", """
The full road network the model drew on a tile it had never seen.

Nothing was hand-corrected. This is raw output.
"""),

60: ("Held-Out Tile 613590", """
TIGER is the Census Bureau's public road map.

Compared against it, we find far more road. Roughly six times as much.

That is not an error, and it is worth heading off the question. TIGER records
roads people drive on today. We are finding overgrown access tracks cut a
century ago, which is exactly what should lead to a forgotten well.
"""),

61: ("Held-Out Tile 613590", """
Where it got the roads right, and where it missed.

Only scored on the part of the tile that was actually annotated. Scoring
against blank ground would invent errors that are not there.
"""),

62: ("What the numbers say", """
The summary. Three models, all scored on ground they never trained on.

Pits: found 93%, while flagging a fifth of one percent of the tile.

Roads: found 98% of 43 withheld kilometres, flagging 5%.

Pads: found 91%, but flagging 11.6% to get there. That one is expensive.

On a second tile never trained on, pit recall only dropped 0.017.

And precision, between 0.59 and 0.69, means roughly a third of what gets
flagged is a false alarm. Measured against what one person drew.
"""),

63: ("What it does not say", """
This slide exists so nobody has to catch me out in questions.

Nothing here is a confirmed well. No field visit, no records check. Every one
is a candidate.

One person drew all the training data, so the ground truth carries one person's
bias, and the precision numbers are measured against that one person's opinion.

613590 has no pads and no drainage drawn, so neither gets scored there.

And two tiles in one county is not proof it works regionally. It is a start.
"""),

64: ("What would move it next", """
In rough order of what would pay off most.

Field-check a sample. That is the one that turns recall into a real rate
instead of a rate against my own drawings.

Finish annotating the second tile. 63% of it is unswept, and that is precisely
why there is no precision number for it.

Get a second annotator on a subset. That measures the single-annotator bias,
and nothing else can.

A tile from a completely different survey. That is the real generalisation
test.

And cut the pad model's flagged area. Its finding rate is fine; the amount of
ground it asks you to walk is not.
"""),

65: ("Further research", """
Three ways to widen this, and none of them needs new data collection.

McKean County first, because we already have it, and it is better data. QL1
rather than QL2, so about twice the point density.

It is also cleaner. That 18-degree cut shows up in six of seven Venango tiles
and zero of seven McKean tiles. Worth saying out loud: the striping problem
belongs to one flight block, not to LiDAR.

Older fields is the interesting one, and needs careful wording. Of 20,108 DEP
records for Venango, 8,054 carry a spud date of January 1800. That is a
placeholder the database uses when it does not know. Another 1,553 have nothing
at all.

So do not say "8,054 wells predate 1900". Say the records are missing. Missing
records is exactly the population we are trying to find on the ground.

Then the Permian basin in Texas. Denser LiDAR, sparse vegetation, and the Texas
Railroad Commission publishes a confirmed orphan list. For once there would be
ground truth I did not draw myself. One cell there holds 136 confirmed orphans
in five kilometres.
"""),

66: ("Further research", """
This is the part of the old future-work list that survived, with the stale
numbers taken off it.

Start with what the model does not see. Seven channels, all derived from the
bare-earth surface.

We built a canopy height model and a ground-intensity map, and neither one is
wired into any detector. So the network only ever sees shape. It never sees
material or vegetation.

The negative class is the one I would do first. Ponds, cellars and quarry
scrapes look like pits. The right fix is to label them and train them in as
negatives, not to filter them out afterwards.

On geomorphons: the old slide claimed a 31% gain. That was measured on a
gradient-boosted model that is no longer in this deck, so treat it as untested
here.

The last line is the cost argument. None of this is a new architecture. It is
extra channels and better labels, on the split we already have.
"""),

67: ("Further research", """
NISAR is a radar satellite, launched 2025, free data, over the same ground
every twelve days.

Lead with the limitation, because someone will do the arithmetic otherwise. Its
backscatter pixel is 10 metres and its interferometry pixel is 80 metres. Our
pits average 32 square metres, about six metres across. A pit is a third of one
pixel. It will not find them.

The useful question runs the other way. LiDAR finds the candidates. NISAR then
asks whether the ground over them is sinking, every twelve days, for free. That
is a wellbore-integrity question, and a single 2019 flight cannot answer it at
all.

Feasibility is already measured, not hoped for. "Coherence" is how stable the
radar signal is between two passes; you need it above about 0.3 to measure
anything. A snow-free autumn pair over our tile held 0.50, with 94% of pixels
usable. A mid-winter pair came back at 0.14, wrecked by snow and freeze-thaw.

So the constraint is which season you order the images from, not the satellite.

If asked about maturity, be straight: this is beta pre-calibration data and one
pair. Validated products start around July 2026, and nothing quantitative
should be claimed before then.
"""),

68: ("References", """
References, for the written version.

The ones that actually shaped the method: Yokoyama on openness, Hesse on local
relief models, Chiba on the red relief image map, and Weiss on topographic
position.

The parameter values taken from each are in the appendix.
"""),

69: ("Appendix", """
Backup slide. The collection parameters for the survey, and what the QL2 grade
formally requires.

Pull this up if someone asks about point density, sensor, flying height, or
whether the data meets specification.
"""),

70: ("Appendix", """
Backup slide. Every tuneable number in the pipeline, with the paper it came
from.

The point of it is that these were not picked by taste. Each one has a
citation.

Two honest caveats if pressed. It lists the DEM resolution as 1 metre, while
the stack we actually work on is half-metre. And the blob-sigma row belongs to
an earlier detection stage that is no longer in the method.
"""),
}


def title_of(slide) -> str:
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def main() -> int:
    prs = Presentation(SRC)          # v6 in, v7 out
    n = len(prs.slides)
    if sorted(NOTES) != list(range(1, n + 1)):
        missing = [i for i in range(1, n + 1) if i not in NOTES]
        extra = [i for i in NOTES if i > n]
        raise SystemExit(f"note coverage does not match the deck: "
                         f"{n} slides, missing {missing}, extra {extra}")

    # verify every note is going onto the slide it was written for BEFORE
    # writing any of them -- a half-applied renumber is worse than none
    bad = []
    for i, (expect, _) in NOTES.items():
        got = title_of(prs.slides[i - 1])
        norm = lambda s: s.replace("–", "-").replace("—", "-").lower()
        if not norm(got).startswith(norm(expect)):
            bad.append(f"  slide {i}: expected {expect!r}, found {got!r}")
    if bad:
        raise SystemExit("slides have moved since these notes were written:\n"
                         + "\n".join(bad))

    for i, (_, text) in sorted(NOTES.items()):
        prs.slides[i - 1].notes_slide.notes_text_frame.text = text.strip()

    prs.save(DECK)
    out = Presentation(DECK)
    lens = [len(s.notes_slide.notes_text_frame.text.strip())
            for s in out.slides]
    print(f"  wrote notes on all {len(lens)} slides")
    print(f"  shortest {min(lens)} chars, longest {max(lens)}, "
          f"median {sorted(lens)[len(lens)//2]}")
    print(f"  {DECK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

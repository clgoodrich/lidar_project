"""Speaker notes that describe what is ON the slide.

WHAT CHANGED FROM THE PREVIOUS SET
----------------------------------
The previous notes drifted into commentary about the deck itself -- why a slide
was added, which earlier version a number came from, how to phrase something,
when to pause. None of that helps someone looking down at a slide mid-talk.

These describe the slide: what the picture shows, what each number on it means
in plain words, and what the point is. No references to earlier versions of the
deck, no "this slide exists because", no stage directions.

Where a figure has panels, the note says which panel is which. Where a number
appears on the slide, the note says what it means. Where a claim has a limit,
the limit is stated as a fact about the content.

Run:
    python docs/presentation/_write_content_notes_v12.py
Reads:  docs/presentation/WellSight_Presentation v11.pptx
Writes: docs/presentation/WellSight_Presentation v12.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/presentation/WellSight_Presentation v11.pptx"
DST = ROOT / "docs/presentation/WellSight_Presentation v12.pptx"

#: slide number -> (expected title prefix, note)
NOTES: dict[int, tuple[str, str]] = {

1: ("Morphological", """
Title slide.

The work: finding old oil wells that have no usable record, by the shape of the
ground they left behind.

"Morphological" means "by shape". Not by paperwork, and not by anything visible
from the air. By the dent in the dirt.

Location is western Pennsylvania, where the American oil industry began.
"""),

2: ("The Problem", """
The scale of the problem, with a historic oil-field photograph.

Drilling here started in the mid-1800s. At its peak Pennsylvania produced about
77% of the world's oil.

There was no regulation. When a well stopped paying, the operator walked away,
and that was legal.

Over 350,000 wells are documented statewide. The number actually drilled is
higher, because for most of that period nobody had to write it down.
"""),

3: ("The Problem", """
Two definitions that sound alike and are not.

Abandoned: no production, extraction or injection for twelve months, and no
equipment left on site. Treated as a dry well, not equipped to produce again.

Orphaned: abandoned before 1985, not operated by the current owner, and the
current owner never got any economic benefit from it.

Orphaned is the harder category, because there is no responsible operator left.
The cost falls to the public.
"""),

4: ("What Does an Orphaned Well Pit", """
A photograph of a real exposed wellhead in overgrown brush, credited to Scott
Detrow, StateImpact PA, 2012.

The hazards listed beside it: escaping gases, a trip hazard, and groundwater
pollution.

Scale and money: over 35,000 such wells, and the 2021 Infrastructure Act put
$4.7 billion toward remediation.

The last line is the one that matters for this talk. The biggest obstacle is
finding them. They are decades old and sit under dense forest canopy.
"""),

5: ("Why LiDAR", """
Two images of the same location, side by side. Satellite on one side showing
canopy, LiDAR hillshade on the other showing the ground beneath it.

LiDAR is a laser flown on an aircraft. It fires pulses and times the return,
which gives a distance and so a height.

Some pulses find gaps in the leaves and reach bare dirt. Keep only those and
you have a map of the ground under the forest.

The bullets: roads, pads and collapse pits become visible, and 1 m resolution
resolves features larger than about 2 m across.

The comparison is the argument. The satellite image shows trees. The LiDAR
shows roads and pits.
"""),

6: ("Study Area", """
Study-area maps, with the survey specification beside them.

Venango and McKean Counties, western Pennsylvania. Appalachian Plateau terrain:
moderate to steep slopes, deeply incised stream valleys, heavy deciduous and
mixed forest.

150-plus years of coal, oil and gas extraction on top of that.

The data is USGS 3DEP LiDAR flown 2018 to 2020, quality level QL2, Leica ALS80
sensor, flown 1,400 to 2,400 m above ground, about 4 points per square metre.

QL2 is a USGS grade. Roughly, it sets the minimum point density.

The DEM is gridded at 1 m from ground-classified points, and each study tile
covers 4.5 by 4.5 km.
"""),

7: ("The DEP Records Problem", """
DEP well locations plotted as dots over a hillshade, with visible pit features
beneath them.

DEP is the Pennsylvania Department of Environmental Protection.

The picture is the point: the dots do not sit on the pits.

Why: coordinates recorded before 1990 came off paper plat maps, carrying 50 to
200 m of error. Some orphan records have no terrain signature at all.

So the records are not just incomplete. Where they exist they are unreliable,
which rules them out as training labels and leaves hand annotation on hillshade
as the only option.
"""),

8: ("Pipeline Overview", """
The whole method as one diagram.

Point cloud in. Turned into raster layers describing the shape of the ground.
Features drawn by hand as examples. A network trained on those. The network run
on ground it has never seen.

Every slide from here to the results is one box on this diagram, in detail.
"""),

9: ("Data QA", """
Opens the data-quality section: what the survey's own processing cost us.

The survey contractor discarded a large share of its own measurements before
delivery. That is normal practice, and it has a price.

This figure shows that price. The next several slides measure it.
"""),

10: ("Data QA", """
A chart of ground classification against scan angle.

Scan angle is how far off straight-down a pulse was pointing when it left the
aircraft. The laser sweeps side to side, so edge-of-swath pulses have high
angles.

The line falls off a cliff at exactly 18 degrees.

A clean vertical edge at a round number is a processing decision, never
physics. Everything past 18 degrees was thrown away.
"""),

11: ("Data QA", """
The same cliff, tested across flight blocks.

Only the March 2020 block shows it. Other flights in the same USGS programme,
over the same kind of terrain, taper off smoothly instead.

So this is one contractor's choice on one batch of work. Not a standard, not a
property of the county, and not a limitation of airborne LiDAR.
"""),

12: ("Data QA", """
Accuracy of the discarded returns measured against the accuracy of the kept
ones, both against the published specification.

The obvious objection is that they were discarded because they were bad.

They were not. Both groups clear the specification.

That is what justifies putting them back in.
"""),

13: ("Data QA", """
The delivered ground surface, with red marking every cell that has no ground
measurement at all.

Red does not mean flat. It means nothing was measured there.

The red runs in stripes along the swath edges, which is the 18-degree cut drawn
on a map.

13.8% of the training area. Wherever it is red, the surface shown is an
interpolation between the nearest real measurements on either side.
"""),

14: ("Data QA", """
The same ground again, this time showing only what the survey discarded.

13.7 million ground measurements.

They fall in the same stripes as the holes on the previous slide. That is the
whole point of showing them together: these are the measurements that would
have filled those holes.
"""),

15: ("Data QA", """
Both put together: the delivered ground plus the discarded returns.

The void drops from 13.8% of the area to 8.2%. That is 2.9 million cells
filled.

About a quarter of the holes close.

The rest do not, and the slide says so. Those sit under canopy thick enough
that no pulse reached the ground at any scan angle.
"""),

16: ("Data QA", """
The same story as a cross-section, which is easier to read than a map.

One line drawn across the ground, plotted twice.

Top: only the returns the survey classified as ground. 32% of that line has
nothing beneath it.

Bottom: the same line with the discarded returns added back. 2%.

Same place, same flight, same laser. The only difference is which returns were
kept.
"""),

17: ("Data QA", """
Our ground classification compared against the vendor's, on the same ground.

Where the vendor found ground, we agree with it. We are not overwriting or
contradicting their work.

What we add is ground where they had none.
"""),

18: ("Step 1: terrain derivatives", """
An overview panel: the same hillside rendered eleven different ways.

A "derivative" here means one question asked about the shape of the ground at
every point on the map, with the answer drawn as an image.

Eleven questions, eleven pictures, one hillside.

The model looks at several at once, because no single one separates a pit from
everything else.
"""),

19: ("Step 1: Terrain Derivatives", """
Slope. How steep the ground is at each point.

Flat is dark, steep is bright.

A pit is a flat floor ringed by steep walls, so on a slope map it reads as a
bright ring with a dark centre.
"""),

20: ("Step 1: terrain derivatives", """
Canopy height over a 300 m window at 0.5 m cells. Bright is tall vegetation,
dark is low.

Canopy height is the top surface minus the ground surface. Whatever is left
over is what is growing.

There are diagonal stripes running across the image.

They are not rows of planted trees, and they are not a rendering fault. The
next slide shows what they are.
"""),

21: ("Step 1: terrain derivatives", """
The same window twice. Left at 0.5 m cells with the empty cells painted orange.
Right at 1 m cells.

The orange lands exactly on the stripes. That is the answer: the stripes are
cells holding no value.

No pulse came back there, so there is no height to draw.

3.22% of this window is empty at 0.5 m. At 1 m it is 0.00%.

The cause is cell size, not the laser. The scanner draws lines across the
ground, and a half-metre cell can fall between two lines and catch nothing. A
one-metre cell always catches a return.

Nothing was filled in or invented. The grid simply stopped asking for detail
the survey never delivered.
"""),

22: ("Step 1: Terrain Derivatives", """
Roughness. How much the surface wobbles over a short distance.

Rubble, ploughed ground and steep broken slopes are rough.

A pit floor is smooth, because it silted up and settled flat.
"""),

23: ("Step 1: Terrain Derivatives", """
TPI, the Topographic Position Index.

The question is simple: is this point higher or lower than the ground
immediately around it?

Ridge tops come out positive. Hollows come out negative.

A pit is a small patch of strong negative.
"""),

24: ("Step 1: Terrain Derivatives", """
LRM, the Local Relief Model.

Take the landscape, smooth it heavily, then subtract the smoothed version from
the real one.

The hills and valleys are in both, so they cancel. What survives is the small
stuff sitting on top of them.

That suits this work, because everything man-made here is small.
"""),

25: ("Step 1: Terrain Derivatives", """
Positive openness.

Stand at a point and look out in every direction. Positive openness measures
how much open sky you can see.

High on a hilltop or a ridge. Low in a ditch.

It finds things that stick up.
"""),

26: ("Step 1: Terrain Derivatives", """
Negative openness. The same idea inverted.

It measures how enclosed a point is: how much of the view is blocked by ground
higher than you.

Standing in a pit, almost all of it.

Of the eleven layers, this is the single most useful one for finding pits.
"""),

27: ("Step 1: Terrain Derivatives", """
Hillshade. A fake sun is placed in one direction and the shadows are drawn.

It is not measured light and it is not data. It is a rendering that makes shape
legible to the human eye.

This is the layer all the hand annotation was drawn on.
"""),

28: ("Step 1: Terrain Derivatives", """
RRIM, the Red Relief Image Map.

Hillshade has a flaw: it invents a sun direction, so any feature lined up with
that direction washes out.

RRIM uses no sun at all, so no direction is favoured and nothing hides.
"""),

29: ("Step 1: Terrain Derivatives", """
The same RRIM, with the recipe.

Red carries intensity of relief. Brightness and darkness carry openness, the
enclosed-or-exposed measure from the previous two slides.

Combined, shape reads equally well from every direction, without a fake light
source.

And yes, it is red. That is the published convention for this product.
"""),

30: ("The corn rows in the RRIM", """
Two RRIM panels of the same 240 m window. Left at 0.5 m cells, right at 1 m.

Fine diagonal stripes run through both, weaker on the right.

They run at 78 degrees, which is the bearing of the lines the scanner draws
across the ground.

They show up in every layer built from shape: local relief, openness,
hillshade, RRIM.

Their size is tens of centimetres. A collapse pit is a dish about 0.7 m deep.
So the artefact and the target are the same size, which is why it matters here
rather than being merely untidy.

The last bullet separates this from the canopy stripes: the ground surface has
no empty cells at either resolution, so these are real measurements, not
missing ones.
"""),

31: ("What the data provider says", """
A direct quotation from OpenTopography's FAQ on linear "corduroy" striping in
DEMs, set out in full on the slide.

OpenTopography distributes this data. Their position: the striping is in the
raw data they receive, and neither the user nor they can fix it.

That places the problem in the survey rather than in any processing done here.

They offer two remedies. Use a coarser grid. Or use their other gridding
algorithm, "local gridding", which averages points inside a radius instead of
triangulating between them.

Both were tested. The next slide is the result.
"""),

32: ("What the two remedies actually did", """
Two RRIM panels of the same ground at the same 0.5 m cell size. Left built by
triangulating between the points, which is the current method. Right built by
averaging points inside a 1.5 m disc, which is local gridding.

Coarser grid: helps partly. At 1 m the stripes fade but do not disappear.

Local gridding: made it worse. Averaging takes whatever points fall inside a
circle around each cell, and as that circle slides the set of points inside it
changes abruptly, so the surface jumps slightly from cell to cell. Heights get
smoother; the slopes between them get rougher.

RRIM draws shape, which is built from those slopes, so it amplifies exactly
that. Every tree in the right panel has grown a starburst.

Conclusion on the slide: build at 1 m and keep the triangulated surface.

Two limits stated: coarsening cannot delete these the way it deletes the canopy
holes, because nothing here is empty to fill; and no cause has been proven --
three explanations were tested and all three failed.
"""),

33: ("Why we drew our own labels", """
DEP-listed orphan wells plotted where there is no visible terrain signature at
all.

The records and the ground do not line up in either direction. There are dots
with no pit under them, and there are clear pits with no record.

So the state's well list cannot serve as an answer key. Training on it would
teach the model to reproduce bad coordinates.

The last bullet covers the other half: one terrain layer is not enough either.
LRM and TPI on their own also light up natural hollows.
"""),

34: ("Manual Annotation", """
Every road on the tile, drawn by hand, shown as a map.

535.9 km of road in total.

3,690 separate drawn lines, which join into 1,747 connected networks. The
network count is the more honest figure, because one road drawn in four pieces
is still one road.

Median line 104 m, mean 145 m.

By area: 206.1 km on 9t, 187.6 km on 613590, 142.2 km elsewhere.

Plus 112 lines totalling 18.0 km drawn as "not road" -- features that look like
roads and are not, which teach the model what to reject.
"""),

35: ("Manual Annotation", """
Streams and ditches, drawn by hand on the training tile only. 45.0 km.

594 drawn lines, cut into 1,791 shorter segments for training. Short segments
train better than a few long ones.

Median segment 21 m, mean 25 m. 344 connected networks.

Broken down: 1.9 km short channels, 27.5 km stream, 15.6 km unlabelled.

These are not drawn because drainage is a target. They are drawn because from
above drainage looks like road, and the model kept confusing the two.
"""),

36: ("Manual Annotation", """
Well pads, drawn by hand. A pad is the flat cleared area where the drilling
equipment stood.

995 pads, 144.4 hectares in total.

Average 1,451 m2, median 1,343 m2 -- roughly 38 m on a side. The middle 80%
fall between 667 and 2,357 m2.

By area: 115.2 ha on 9t, 29.3 ha elsewhere, and 0.0 ha on 613590.

That last figure matters later. No pads were ever drawn on the second tile, so
there is nothing there to score a pad model against.
"""),

37: ("Measured pit morphology", """
The measured shape of a pit, from the annotations rather than from assumption.

A shallow bowl. About 0.7 m deep and 13 m across.

Worth pausing on the proportions: seventy centimetres of depth spread over
thirteen metres of width. It is a dish, not a hole.

That is why cell size and vertical accuracy matter so much in this work.
"""),

38: ("Manual Annotation", """
Pit rims -- the outer edge of the disturbed ground around each pit -- drawn by
hand.

723 outlines, 14.84 hectares total.

Average 205 m2, median 197 m2, so about 16 m across. Middle 80% between 127 and
292 m2.

By area: 9.7 ha on 9t, 1.0 ha on 613590, 4.2 ha elsewhere.

586 of them pair with a drawn floor. Having both gives 9.91 ha of measurable
wall, which is where the shape information lives.
"""),

39: ("Manual Annotation", """
Pit floors -- the flat bottom inside the rim -- drawn by hand.

712 floors, 2.29 hectares total.

Average 32 m2, median 29 m2, so about 6 m across. Middle 80% between 15 and
51 m2.

By area: 1.5 ha on 9t, 0.6 ha on 613590, 0.3 ha elsewhere.

The ratio at the bottom is the useful one: a floor is only 16% of its outline
by area. The other 84% is wall.

Floor and rim were drawn as separate layers because they look completely
different to the laser -- one flat, one sloped.
"""),

40: ("Preprocessing", """
A diagram separating what a person drew from what code worked out.

Seven layers were drawn by hand. Everything else in the project was computed
from those seven.

Nobody hand-drew the pit walls. Nobody hand-matched rims to floors. Those were
derived, which means they can be re-derived and checked.
"""),

41: ("Preprocessing", """
Matching pit rims to pit floors, shown as a map of the pairings.

Each pit was drawn twice, once as a floor and once as a rim, with nothing in
the file recording that the two shapes belong to the same pit.

712 floors drawn. 723 rims drawn.

Matched by taking, for each floor, whichever rim it overlaps most. That found
586 pairs.

126 floors have no rim and 138 rims have no floor. Those are the ones where
only one of the two was ever drawn.
"""),

42: ("Preprocessing", """
The agreed constants, in one place.

Every script downstream reads its thresholds and class values from here rather
than defining its own.

The purpose is that two scripts can never quietly disagree about what a pit is.
"""),

43: ("Annotation Quality Control", """
A check on the annotations themselves, with the results table beside it.

Four anomaly-detection algorithms were run over 856 measured pits. Anomaly
detection here means finding the ones that look unlike all the others.

90 pits, 10.5%, were flagged with a Mahalanobis distance above 5. Mahalanobis
distance measures how far a pit sits from the average across all its measured
properties at once.

The top 30 were reviewed by hand. Half were genuine errors: mis-clicks and
wrong spots. Half were unusual but correct: deep cellars, and degraded pits on
steep terrain.

PCA on the measurements shows 3 components explain 86.4% of the variance, so
the pits vary along only a few dimensions.

The point is that the answer key was audited before anything was trained on it.
"""),

44: ("Preprocessing", """
How overlapping labels are resolved.

Sometimes two labels cover the same pixel -- a pit inside a pad, for instance.

A fixed burn order decides which one wins, applied identically everywhere.
"""),

45: ("Preprocessing", """
Why the train/test split balances on the number of pits rather than on area.

Pits are clustered, not spread evenly.

So cutting the tile into two halves of equal area does not produce two halves
with equal evidence. One half can hold most of the pits.

Balancing on pit count fixes that. Area is the wrong thing to equalise.
"""),

46: ("Preprocessing", """
The spatial block split, drawn on the tile.

The tile is cut into a 12 by 12 grid. Whole blocks are assigned to training or
testing. Individual pits are never split.

The reason is on the slide: splitting pit by pit would put a training pit 30 m
from a test pit, on the same hillside in the same light.

The model would then be recognising the hillside, not the pit, and the score
would look excellent and mean nothing.

Assigning whole blocks makes that impossible.
"""),

47: ("Preprocessing", """
The held-out blocks, with every pit inside them marked.

These blocks were withheld from training entirely. The model never saw a single
one of these pits while learning.

Every recall figure later in the deck is measured on these.
"""),

48: ("Preprocessing", """
One split shared by every task.

Pits, pads and roads all use the same block assignment.

If each task had its own split, a block could be test ground for pits and
training ground for roads at the same time. The tasks would leak into each
other and every score would quietly inflate.
"""),

49: ("Model building", """
The network, as a diagram. A U-Net.

Seven raster layers go in. For every half-metre cell it returns one probability
per class.

It is U-shaped because it zooms out to take in context and then back in to
place edges precisely. The zoom-out sees "a hollow on a hillside". The zoom-in
says "and the edge is here".

It is a standard, widely used architecture, not a custom design.
"""),

50: ("Model building", """
What the model actually returns.

Not a yes or a no. A probability for every half-metre cell.

0.9 means very confident. 0.1 means barely.

That is more useful than a verdict, because it leaves the decision about how
cautious to be until afterwards.
"""),

51: ("Model building", """
Turning probabilities into an answer.

A threshold is chosen. Above it, a cell becomes part of a candidate. Below it,
nothing.

Moving that threshold is a trade. Lower catches more real pits and more junk.
Higher is cleaner and misses more.

There is no correct setting, only the one that suits what happens next with the
output.
"""),

52: ("Model building", """
Whether a larger network would do better.

Four architectures: a plain U-Net, a ResNet-34 backbone from scratch, the same
pretrained on ImageNet, and a U-Net++ with that pretrained backbone. Five folds
each, with folds, channels, loss and schedule held identical.

Pits: plain U-Net 0.559, full stack 0.561. A gain of 0.002 against a spread
between folds of 0.020. The gain is smaller than the noise.

Pads: plain U-Net 0.555, full stack 0.608. That one is a real difference and
worth pursuing.

So for pits, architecture is not the constraint. Three times the parameters and
ImageNet pretraining bought nothing, which points at the data and the labels
instead.

The last line is a warning about units: these are segmentation overlap scores
at 1 m, measuring how well the shape is traced. They are not the detection
recall on the outcome slides, which counts whole features found at 0.5 m.
"""),

53: ("Outcome - Roads", """
Road results on the held-out blocks.

43.07 km of road was withheld from training entirely.

Recall 0.982 means it found 98.2% of that road. Recall is: of the real things
out there, what fraction did we find.

It flags 5.02% of the tile to achieve that -- the share of ground a person
would have to walk or review.
"""),

54: ("Outcome - Drainage", """
Drainage results.

Drainage is not a detection target. It is there to be rejected.

Teaching it as its own class is what stopped the road model calling every
stream a road.

The caption states it plainly: not a detector, a negative class, and it worked.
"""),

55: ("Outcome - Pads", """
Pad results on the held-out blocks. 995 pads.

Recall 0.912: it found 91.2% of the real pads.

Precision 0.587: of everything it flagged, 58.7% were real. So roughly four in
ten flags are false alarms.

Flags 11.6% of the tile.

The finding rate is good. The flagged area is the problem -- that is a ninth of
the whole tile to review.
"""),

56: ("Outcome", """
Pit results on the held-out blocks. 712 pits. This is the strongest result in
the deck.

Recall 0.928: it found 92.8% of the pits.

Precision 0.633: 63.3% of what it flagged was real.

Flags 0.21% of the tile. That is a fifth of one percent of the ground.

That last number is the operational one. It found nearly all the pits while
pointing at almost none of the map.
"""),

57: ("Where the two study tiles are", """
A locator map showing both study tiles, with the distance between them.

Everything up to this point was trained on 9t and scored on blocks inside 9t
that the model never saw.

613590 is a different tile, 1.5 km west. No model has ever seen any part of it.

The tiles do not overlap, so nothing leaks between them.

Two things this is not. It is not a "held-out" tile, because it was never part
of the dataset to be withheld from. And it is not a generalisation test: same
county, same 2019 survey, same flight block, same terrain.
"""),

58: ("Second tile, 613590", """
Pit results on the second tile. 153 pits, none of them ever trained on.

Recall 0.911 here, against 0.928 on the training tile.

The drop is 0.017 -- under two percentage points for moving to entirely new
ground.

A model that had memorised the training tile would collapse here. This one
barely moves.
"""),

59: ("Second tile, 613590", """
Pads on the second tile, and there is no score.

No pads were ever drawn on this tile, so there is no answer key to measure
against.

The model did produce pad candidates here. They may well be correct. There is
simply no way to check without someone drawing the pads first.

This is a gap in the annotation, not a failure of the model.
"""),

60: ("Second tile, 613590", """
Road results on the second tile. Three numbers, all on the caption.

Completeness 0.811: it found 81.1% of the real road.

Correctness 0.816: 81.6% of the road it drew is real road.

Quality 0.686: a single score combining both, so you cannot win by sacrificing
one for the other.
"""),

61: ("Second tile, 613590", """
The pit result on the second tile in detail. 146 of 153 found.

Two different threshold rules are shown rather than only the favourable one.

The recall-weighted rule gives 0.911, against 0.928 on the training tile -- a
drop of 0.017.

The balanced rule gives 0.792, against 0.861 -- a drop of 0.069.

Containment 0.906 measures how much of each drawn pit the detection actually
covers.

Thresholds were frozen from the training tile. Nothing was retuned here, which
would amount to fitting to the test.

No precision figure, because the tile is not fully annotated. False alarms
cannot be counted when the answer key is incomplete.
"""),

62: ("Second tile, 613590", """
Drainage on the second tile, and again there is no score.

None was drawn here, so the drainage class trains and scores on the first tile
alone.
"""),

63: ("Second tile, 613590", """
The candidates the model produced on the second tile, mapped.

42 pit candidates and 161 pad candidates, with no retraining of any kind.

Pits can be scored here: 153 were drawn, and recall is 0.911.

Pads cannot, because none were drawn.

The last line is the important one. Every one of these is a candidate. Not a
confirmed well. Nothing on this map has been visited or checked against
records.
"""),

64: ("Second tile, 613590", """
The full road network the model drew on the second tile.

Raw output. Nothing hand-corrected, nothing cleaned up afterwards.
"""),

65: ("Second tile, 613590", """
The generated road network compared against TIGER.

TIGER is the US Census Bureau's public road dataset.

We find substantially more road than TIGER lists -- roughly six times as much.

That is not an error. TIGER records roads people drive on today. These are
overgrown access tracks cut a century ago, which is exactly what should lead to
a forgotten well.
"""),

66: ("Second tile, 613590", """
Where the road model got it right and where it missed, mapped.

Scored only on the part of the tile that was actually annotated. Scoring
against unannotated ground would invent errors that are not there.
"""),

67: ("What the numbers say", """
The results summary. Three models, all scored on ground never used in training.

Pits: recall 0.928, flagging 0.21% of the tile.

Roads: recall 0.982 on 43 km withheld, flagging 5.0%.

Pads: recall 0.912, but flagging 11.6% to get there.

On the second tile, never trained on, pit recall 0.911 -- down 0.017.

Precision across the three runs 0.59 to 0.69, which means roughly a third of
what gets flagged is a false alarm. Measured against what one person drew.
"""),

68: ("What it does not say", """
The limits, stated on the slide rather than left for questions.

Nothing here is a confirmed well. No field visit, no records check. Everything
is a candidate.

One annotator drew all the training data, so the ground truth carries one
person's bias -- and every precision figure is measured against that one
person's judgement.

613590 has no pads and no drainage drawn, so neither is scored there.

Two tiles in one county is not evidence that this generalises regionally.
"""),

69: ("What would move it next", """
Near-term next steps, in rough order of payoff.

Field-check a sample of candidates. That converts recall from a rate against
hand-drawn annotation into a real rate.

Finish annotating 613590. 63% of it is unswept, which is exactly why there is
no precision figure for it.

Put a second annotator on a subset. That measures the single-annotator bias,
which nothing else can.

Get a tile from a different acquisition. That is the real generalisation test.

Cut the pad model's flagged area. Its recall is fine; the 11.6% of ground it
asks someone to review is not.
"""),

70: ("Further research", """
Three directions for widening the work, all using data already downloaded.

McKean County: QL1 rather than QL2, so roughly twice the point density, and
already held.

It is also a cleaner delivery. The 18-degree vendor cut appears in six of seven
Venango tiles and zero of seven McKean tiles, which confirms the striping
belongs to one flight block rather than to LiDAR.

Older fields: of 20,108 DEP records for Venango, 8,054 carry a placeholder spud
date rather than a real one, and another 1,553 have none at all. That is the
records being missing, not the wells being old -- and missing records is
exactly the population this method targets.

The Permian basin in Texas: QL1 at 12 to 15 points per square metre, sparse
vegetation, and the Texas Railroad Commission publishes a confirmed orphan
list. That would be ground truth nobody here drew. One cell there holds 136
confirmed orphans within 5 km.
"""),

71: ("Further research", """
Four changes to the model, none of which requires a new architecture.

What the detectors currently see: seven channels, all derived from the
bare-earth surface -- LRM, slope, TPI, both openness layers, roughness.

Canopy height and return intensity are both already built and neither reaches
any model. So the network only ever sees shape, never material or vegetation.

A negative class for the confusers -- ponds, cellars, quarry scrapes. These
look like pits, and the fix is to label them and train them in as negatives
rather than filter them out afterwards.

Geomorphon enclosure as an extra channel. The 31% gain quoted for it was
measured on a different model and has not been tested against these.

The closing line is about cost: all of this is extra channels and better
labels, on the split that already exists.
"""),

72: ("Further research", """
NISAR: a radar satellite launched in 2025, free data, revisiting the same
ground every 12 days.

The first bullet is the limitation, because the arithmetic invites the
question. Its backscatter pixel is 10 m and its interferometry pixel is 80 m.
Our pits average 32 m2, about 6 m across. A pit is roughly a third of one
pixel. It will not detect them.

What it can do is measure whether the ground above them is moving, to the
millimetre.

Feasibility was tested on this tile. Coherence measures how stable the radar
signal stays between two passes; above about 0.3 is usable. A snow-free autumn
pair reached 0.50, with 94% of pixels usable. A mid-winter pair managed 0.14,
wrecked by snow and freeze-thaw.

So the constraint is which season the imagery comes from, not the satellite.

That converts a one-time 2019 snapshot into a monitored surface, which is the
wellbore-integrity question.

Maturity caveat on the slide: this is beta pre-calibration data and one pair.
Validated products start around July 2026.
"""),

73: ("References", """
References for the written version.

The ones that shaped the method directly: Yokoyama on openness, Hesse on local
relief models, Chiba on the red relief image map, Weiss on topographic
position, and the ASPRS LAS specification for the point classification
standard.

The specific parameter values taken from each are in the appendix.
"""),

74: ("Appendix", """
Backup slide. Two tables: the survey's collection parameters, and what the QL2
quality level formally requires.

Use it for questions about point density, sensor, flying height, or whether the
delivery meets its own specification.
"""),

75: ("Appendix", """
Backup slide. Every tuneable parameter in the pipeline with the paper it came
from: TPI radii, LRM window sizes, roughness kernel, openness radius, slope
threshold, minimum pad area.

The point is that these were not chosen by taste. Each one has a citation.

Two entries need care if questioned. The DEM resolution row says 1 m while the
working stack is 0.5 m, and the blob-sigma row belongs to a detection stage no
longer in the method.
"""),
}


def title_of(slide) -> str:
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def norm(s: str) -> str:
    return s.replace("–", "-").replace("—", "-").lower()


def main() -> int:
    prs = Presentation(SRC)
    n = len(prs.slides)
    if sorted(NOTES) != list(range(1, n + 1)):
        missing = [i for i in range(1, n + 1) if i not in NOTES]
        raise SystemExit(f"{n} slides, notes missing for {missing}")

    bad = []
    for i, (expect, _) in NOTES.items():
        got = title_of(prs.slides[i - 1])
        if not norm(got).startswith(norm(expect)):
            bad.append(f"  slide {i}: expected {expect!r}, found {got!r}")
    if bad:
        raise SystemExit("slides have moved:\n" + "\n".join(bad))

    for i, (_, text) in sorted(NOTES.items()):
        prs.slides[i - 1].notes_slide.notes_text_frame.text = text.strip()
    prs.save(DST)

    out = Presentation(DST)
    lens = [len(s.notes_slide.notes_text_frame.text.strip()) for s in out.slides]
    banned = ("this slide exists", "earlier version", "retired pipeline",
              "be careful how you say", "do not explain", "carried over from",
              "v6", "v7", "v8")
    hits = []
    for i, s in enumerate(out.slides, 1):
        t = s.notes_slide.notes_text_frame.text.lower()
        for b in banned:
            if b in t:
                hits.append((i, b))
    print(f"  notes rewritten on all {len(lens)} slides")
    print(f"  shortest {min(lens)}, longest {max(lens)}, "
          f"median {sorted(lens)[len(lens)//2]} chars")
    print(f"  meta-commentary phrases remaining: {len(hits)} {hits[:6]}")
    print(f"  {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

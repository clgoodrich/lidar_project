"""Plain-language speaker notes, kept apart from the deck's layout code.

WHY A SEPARATE FILE
-------------------
These get rewritten often and by hand. Burying them inside the layout spec in
_build_deck_v6.py means editing a 400-line dict every time a sentence changes,
and that dict already caused one bad merge. Here they are just text.

HOW THEY ARE WRITTEN
--------------------
Assume the reader knows nothing. No jargon without a definition in the same
sentence. Short sentences, one idea each. A number is always given something to
compare against -- "34 cm" means nothing, "34 cm against a pit that is 70 cm
deep" means something.

KEYED BY V5 SLIDE NUMBER, like everything else in the deck builder, because
that is the numbering the review comments used. The builder maps it to the v6
position. v5 -> v6 is: 1-9 unchanged, 10 dropped (merged into 9), 11-40 shift
down by one, then one inserted slide takes v6 40, and 41 onwards are unchanged.
"""
from __future__ import annotations

#: v5 slide number -> speaker notes. Anything here wins over the layout spec.
PLAIN_NOTES = {

 17: """WHAT THE VERTICAL STRIPES MEAN

Imagine walking a 300 metre line across the hillside and measuring the ground
height every half metre.

The striped bands are the stretches where nobody ever got a measurement. The
laser fired, but nothing came back from the ground there.

The black line still runs through those stripes. That is not measured ground.
It is a guess, stretched straight between the last real measurement on one side
and the first real measurement on the other.

Top panel: only the ground the survey gave us. 32% of the line is guesswork.
Bottom panel: the discarded returns put back. 2%.


AND THE OBVIOUS FOLLOW-UP: DO THE TWO SURFACES ACTUALLY DIFFER?

Measured over all 81 million cells, split by what happened to each one.

Where the survey already had ground (44.4 million cells):
  the two surfaces are the same to a centimetre. Median change 0.000 m. Only
  0.2% of cells move more than 10 cm. That is the control, and it passing is
  what says we did not quietly rewrite good ground.

Where the holes got filled (2.9 million cells):
  median change is also about zero -- so the old guess was not systematically
  too high or too low. But one filled cell in five moves more than 10 cm, and
  the 95th percentile is 34 cm.

Say that last number out loud: a typical pit is 70 cm deep. So in the holes,
the old surface could be off by half a pit, in either direction.

This is also why re-training on the recovered ground changed nothing. The
errors were unbiased, so they were not systematically hiding pits, and only
27% of the holes were the wide-angle kind anyway. The rest are canopy, which
recovering discarded returns does not fix.""",

 36: """WHAT THE LEFT AND RIGHT COLUMNS ARE

Left: the seven things a person drew by hand in QGIS. That is it. Seven layers,
drawn with a mouse.

Right: everything the code works out by itself from those seven, every time it
runs. Nobody types these.

The point of showing them side by side is that a reviewer can see exactly where
human judgement stops and arithmetic starts.


ABOUT "n_pits, n_roads, n_not_roads" IN THE BOTTOM RIGHT BOX

Each pad record stores how many pits sit on it, how many roads touch it, and
how many rejected road-lines touch it.

The box's real point is bookkeeping: those counts are thrown away and
recalculated from scratch on every run, instead of being stored. That is
because once, a re-run merged the data twice and silently doubled them.

Honestly, this box is an internal note and does not earn its place in front of
an audience. Recommend cutting it.""",

 37: """WHAT YOU ARE LOOKING AT, AND WHAT IS MISSING

A pit was drawn twice by hand. Once as a big outline around the outer rim, and
once as a smaller blob for the flat floor inside it. They were drawn as two
separate layers, with separate numbering, and nothing connected them.

So the computer had to work out which rim goes with which floor. The rule is
the simplest one that works: pair each floor with whichever rim it overlaps
most.

712 floors drawn. 723 rims drawn. 586 pairs found.
126 floors have no rim. 138 rims have no floor.

Only a paired pit gets a measurable wall, which is why 712 floors produce 586
walls. The leftovers are not mistakes to be tidied up -- they are real places
where only one of the two was visible from the air.


A FAIR CRITICISM OF THIS GRAPHIC

Right now it is outlines floating on blank paper. There is no terrain
underneath, so there is no way to see that these are real dents in the ground.
It needs a shaded-relief background behind the outlines.""",

 39: """WHY ANY OF THIS IS NEEDED

A pit is drawn twice: a big circle round the rim, a small blob for the floor
inside it. The two overlap.

But the computer works on a grid of squares, and each square can only carry one
label. So something has to decide what an overlapping square is.

The rule: paint the wall first, then paint the floor on top. Any square inside
both ends up labelled "floor".

That is the entire idea. It looks trivial, and it is, but it has to be decided
in exactly one place in the code. If two different parts of the pipeline made
that choice separately, you would get two different label maps and spend a day
wondering why your score moved.""",

 40: """WHAT THE CHECKERBOARD IS

The 4.5 km square of land is chopped into a 12 by 12 grid. 144 blocks, each
about 375 m across.

The COLOUR of a block says which of three piles it went into.
The NUMBER inside it is how many pit floors are in that block.
Grey blocks hold no pits at all, so they are not used.


WHAT THE THREE PILES ARE, PLAINLY

TRAIN. The model studies these and adjusts itself to get them right.

VAL, short for validation. The model never studies these. We look at them to
choose settings -- when to stop training, how confident a prediction has to be
before we count it. Using them this way means they can no longer be a fair
test.

TEST. Nobody looks at these until the very end. Scored once. This is the only
honest number.


WHY BLOCKS AND NOT INDIVIDUAL PITS

If you shuffled individual pits into the three piles, a training pit could sit
30 metres from a test pit. The model would have studied the ground right next
to the test pit, and the test would flatter it.

Handing over whole blocks of land makes that impossible.""",

 41: """WHAT THIS MAP SHOWS

The blocks the model was never allowed to study, and every pit inside them.

Every one of those pits is scored by a model that never saw that block during
training. That is what makes the recall number mean something.


ON THE COLOURS

Noted that these are hard to tell apart. Test should be black, and the three
categories need more separation than they currently have.""",

 42: """WHY THIS SLIDE EXISTS

We are not building one model, we are building four: pits, pads, roads and
drainage. Each one needs its land split into train, validation and test.

The trap: if each of the four drew its own split, a block used for TRAINING the
road model could be the same block used for TESTING the pit model. The road
model would then have studied ground that the pit model is being examined on.
Nothing would error. The score would just be quietly too good.

The fix is dull and complete: all four tasks share one block assignment.


WHAT THE 110 AND THE 0 ARE

110 blocks contain more than one kind of feature -- a pad and a road, say.
Those are the only blocks where the trap could spring.

0 of them disagree about which pile they are in.

Zero is the whole point. It is a check that was run, not a claim that was
made.""",
}

#: Notes for slides that v6 inserts, keyed by the v5 slide they follow.
INSERT_NOTES = {
 40: """WHAT THESE BARS ARE COMPARING

Two things, for each of the three piles.

GREY is how much of the MAP that pile got.
BLUE is how many of the PITS that pile got.

If pits were sprinkled evenly across the land, the two bars in each pair would
be the same length. They are not.

Train has 53% of the map but 70% of the pits. Val has 10% of the map and 15%
of the pits.

That is because pits cluster. They sit together around old well fields, not
scattered at random.


SO WHAT

It means "give training 70% of the land" would NOT give training 70% of the
evidence. The split has to be balanced on the number of pits, not on area,
or the test set ends up with too few pits to say anything reliable.

The grey bar at the bottom is the 20% of the map holding no annotated pits at
all. Leaving it out costs nothing.""",
}

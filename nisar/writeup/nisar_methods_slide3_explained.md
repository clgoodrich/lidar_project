# Slide 3, explained like you're 12

This explains slide 3 of `nisar/writeup/nisar_checkpoint_slides_methods_9t.pptx`. It covers the plan only. Nothing here says how the test came out.

## The big picture first

Old oil wells hide in the woods. Each one usually left three marks on the ground: a pit, a flat pad and a road.

We already have one tool for finding them. It's **lidar**: a plane shoots laser pulses at the ground and maps its shape, even under trees. A computer program (the **detector**) looks at that map and says "this spot might be a pad."

Now we have a second tool. It's **NISAR**, a radar satellite. The question is simple:

> If we add the radar to the lidar, do we find more real pads?

That's the whole slide. Everything else is how we make sure the answer is honest.

## The headline

> "Verified pads found at a fixed inspection budget, lidar alone against lidar plus radar, answer the question. The bar is +0.05 recall."

Think of it as a treasure hunt.

- The detector hands a field crew a list of spots to go check.
- The crew can only visit so many spots. That limit is the **inspection budget**. Say it's 10 spots for every square kilometre.
- **Recall** means "out of all the real pads out there, what share did we find?" Find 90 out of 100 and recall is 0.90.
- We run the hunt twice with the same budget:
  - Once with a list made from lidar only.
  - Once with a list made from lidar plus radar.
- **+0.05 recall** is the pass mark. The radar list has to find at least 5 more real pads out of every 100, for the same number of visits. If it can't, the radar isn't worth the trouble.

Why fix the budget? Because it's easy to "find more" by sending the crew everywhere. That's cheating. A fair test makes both lists spend the same effort.

We pick the pass mark **before** we look at any scores. If you set the bar after seeing the result, you can always move it to where you want it.

## The five steps (left side)

### 1. Build one input manifest for every date and layer

A **manifest** is a packing list. It names every radar picture we use, the date it was taken, and any picture we threw out and why.

Every later step reads the same list. If a step finds a file that isn't on the list, or a file is missing, the run stops.

Why: without a list, one step might use 35 pictures and another 36, and nobody notices. The list makes every step use exactly the same stuff.

### 2. Geocode again on lidar heights

**Geocoding** means putting each radar pixel on the right spot on the map.

The radar looks at the ground sideways, at a slant. So to know where a pixel lands, you need to know how high the ground is there. NASA uses a height map called the **Copernicus DEM**. Under a forest, that map often measures the treetops, not the ground. Get the height wrong, and the pixel lands in the wrong place. It's like guessing where a ball lands but being wrong about how tall the hill is.

Our lidar knows the real ground height, so we redo the placement with lidar heights.

"Offsets fit on reference targets" means we line things up using a few known, solid objects, like bridges or metal reflectors. Then we check the result on *other* objects we didn't use for lining up. That's like checking your homework with a different problem from the one you practised on.

### 3. Stack dates into a small fixed radar feature set

The radar passes over every 12 days, so we have many pictures of the same place. Stacking them means combining them.

A **feature** is one number the computer gets to look at. We allow only a few kinds:
- **HH and HV level.** How bright the radar echo is. HH and HV are two ways the radar sends and receives its wave. HV mostly reacts to messy, tangled things like tree crowns.
- **Local contrast.** Is the spot brighter or darker than the ground right around it?
- **Texture.** Is the area smooth or speckly?

"Small" and "fixed" mean we choose this short list once and don't keep adding to it. If you try 500 features, one will look good just by luck, the way one of 500 coin-flippers will get 9 heads in a row.

### 4. Score the lidar detector's candidates with and without radar

A **candidate** is a spot the lidar detector suggests. We take that exact list of spots and score it two ways: lidar only, and lidar plus radar.

"Same candidates" means both versions judge the same spots. Otherwise it's like two students taking different tests.

**Spatial folds** keep the computer from cheating by memorising. We cut the map into blocks. The computer learns on some blocks and gets tested on blocks it has never seen. "Fixed once" means the blocks are assigned one time and never reshuffled. Reshuffling lets you keep trying until you get a lucky split.

### 5. Recall at a fixed budget on a reserved area

A **reserved area** is a piece of land kept locked away. We don't use it for any choice: not the features, not the settings, nothing. We open it once, at the end, for the final test. It's like a test the teacher hides until exam day.

The **cluster bootstrap** tells us how sure we can be. We re-run the count many times, each time on a random mix of the areas, and see how much the answer wobbles. "Cluster" means pads that sit together (sharing a road, say) get picked together, because they aren't really separate examples.

"Budget, bar and labels fixed before scoring" means three things get locked in before we peek: how many spots the crew can visit, the +0.05 pass mark, and which spots are real pads.

## What could go wrong (the table on the right)

Each row is a way the test could fool us, a sign to watch for, and the fix.

### Row 1. The picture is in the wrong place

- **Risk.** NASA's height map sits on the treetops, so the radar picture can be shifted off the real ground.
- **How you'd notice.** We can fake what the radar *should* see using lidar, then compare. If the fake and the real picture only match after we slide one over, the picture is off. Metal reflectors with known positions would show it too.
- **Fix.** Place the picture with lidar heights. Then check it on reflectors we didn't use to line it up.

### Row 2. The score learns the place, not the pad

- **Risk.** Say pads happen to cluster in the north part of the map. A computer can score well just by learning "north means pad", without looking at any pads at all.
- **How you'd notice.** Give a computer only the map coordinates (the x and y position) and nothing else. If that scores as well as the radar, the radar isn't telling us anything new.
- **Fix.** Use fixed blocks for training and testing. Also run two checks:
  - **Coordinate-only:** the computer gets only the location.
  - **Placebo:** we make fake pads in made-up spots. A fair method should score no better than a coin flip on those.

### Row 3. The answer key only has what lidar can see

- **Risk.** Our list of real pads was drawn by people looking at lidar maps. So it only holds pads lidar can see. If radar could find pads that lidar misses, our answer key wouldn't count them. Radar could never get credit.
- **How you'd notice.** Radar only ever "finds" pads that lidar already drew.
- **Fix.** On the reserved area, label the real pads in other ways: aerial photos, old records and site visits, without looking at the radar scores. Also check a random sample of ground *outside* the detector's list, so we learn what the whole hunt missed.

## Words to know

| Word | Plain meaning |
|---|---|
| Lidar | A laser from a plane that maps the ground's shape, even under trees. |
| Radar (NISAR) | A satellite that sends radio waves and listens for the echo. |
| Detector | The computer program that suggests where pads might be. |
| Candidate | A spot the detector suggests. Not checked yet. |
| Recall | Out of all the real pads, the share we found. |
| Inspection budget | How many spots the crew can visit per square kilometre. |
| Manifest | The packing list of every input file. |
| Geocode | Put each radar pixel on the right spot on the map. |
| DEM | A height map of the ground. |
| Feature | One number the computer looks at. |
| Spatial folds | Map blocks for training and testing, kept apart. |
| Reserved area | Land kept locked away until the final test. |
| Cluster bootstrap | Re-counting many times to see how much the answer wobbles. |
| Placebo | A fake test that should come out as a coin flip. |
| Labels | The answer key: which spots really are pads. |

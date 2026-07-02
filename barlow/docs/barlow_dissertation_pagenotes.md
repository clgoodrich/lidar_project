# Barlow Dissertation — Read-Along Companion

**The book this goes with:** Barlow, M. C. (2026). *A Comprehensive Spatial Analysis of
Stream Boundary and Geomorphological Change Detection: McMurdo Dry Valleys, Antarctica.*
PhD dissertation, University of Houston. 240 pages.

## How to use this

Keep this open next to the dissertation PDF. Every heading here tells you which **PDF
pages** it covers (the number your PDF viewer shows — the number printed at the bottom of
the manuscript page is different, so trust your viewer). For each section of the
dissertation you get: **What's going on here** (the plain-English version), **New words**
(every technical term, defined the first time it shows up), **Where people get lost**
(the dense paragraphs and scary equations, decoded, with page numbers), and **The one
thing to remember** before you move on. Nothing is assumed — every acronym gets spelled
out.

## The whole dissertation in one paragraph

Antarctica has a weird ice-free desert called the McMurdo Dry Valleys — bare rock and
gravel that looks like Mars. Every summer, glacier ice melts a little and temporary
streams run for a few weeks, quietly rearranging the ground. For a century people called
this the most unchanging landscape on Earth. Barlow built a way to check: she taught a
neural network to outline every stream channel using only the *shape* of the ground
(chapters 4 and 6), proved that free satellite elevation maps are accurate enough to
trust once you line them up carefully (chapter 5), and then subtracted elevation maps
from three different years to see where dirt left and where it piled up over 20 years
(chapter 7). Verdict: the "most stable place on Earth" is measurably changing — and in
some places the change is speeding up.

## Map of the book

| Chapter | PDF pages | What it is |
|---|---|---|
| 1 Introduction | 17–30 | Why this place, why now, and the three goals |
| 2 Technical Background | 31–47 | The toolbox: lasers, satellites, neural networks, map-subtraction |
| 3 Study Area & Datasets | 48–62 | Meet the valleys and the three elevation surveys |
| **4 Teaching a network to find streams** | 63–85 | Her published paper — the proof it works (one valley) |
| **5 Lining up satellite maps with laser maps** | 86–107 | Proving the free satellite data is trustworthy |
| **6 Going big** | 108–129 | Running the stream-finder over every valley, every year |
| **7 The payoff** | 130–165 | Twenty years of erosion and deposition — the actual science |
| 8 Conclusions | 166–171 | What it all means and what comes next |
| Appendices | 199–240 | Big lookup tables backing chapters 5–7 |

**In a hurry?** Read the Abstract (pp. 7–8), then her goals (pp. 28–29), then jump to
chapter 4 and ride chapters 4 → 5 → 6 → 7 in order. Chapters 2–3 are there for whenever
something doesn't make sense.

---

### Pages 1–6
**Gist:** Front matter only — title page through acknowledgments — with nothing to study.

Page 1 is the title page: the dissertation is about finding stream edges and measuring landscape change in the McMurdo Dry Valleys, Antarctica, submitted by Mary Camille Barlow at the University of Houston, May 2026, with Craig Glennie as her advisor.

Page 2 is the copyright line. Page 3 dedicates the work to her mom.

Pages 4–6 are thank-yous — advisor, committee, funders (the National Science Foundation and an Army cold-regions lab), labmates, friends, an online PhD co-working group, and family, including her husband Dr. Alex Craik.

Notice how many people and organizations it takes to get one person across this finish line. Read the dedication, smile, and move on.

### Pages 7–8
**Gist:** The abstract shrinks the whole thesis to two pages: a three-part plan — trace stream boundaries with a U-Net, validate satellite elevation maps, then subtract maps across years to measure erosion and deposition.

Decode it slowly. The Dry Valleys (MDVs) barely changed for decades. Now glaciers melt more and permafrost is thawing, feeding ephemeral streams, which move sediment around.

- *polar desert* — freezing cold and bone-dry
- *permafrost* — ground frozen year-round
- *ephemeral streams* — streams that flow only a few summer weeks

Her plan has three parts. First, she trained a U-Net to trace stream boundaries from DEMs for 2001, 2014, and 2021–23.

- *U-Net* — a pattern-spotting computer program that outlines shapes in images pixel by pixel
- *DEMs* — digital elevation models: maps where each pixel stores ground height

Second, she tested satellite-made elevation maps (REMA), sliding them into alignment with laser maps and measuring errors honestly. Errors follow a heavy-tailed pattern, so she uses a robust yardstick called NMAD.

- *ICP* — the method for sliding one elevation map into alignment with another

Third, subtracting old maps from new ones inside the stream outlines reveals where dirt eroded or piled up. Denton Hills is losing the most, and in Taylor Valley some change is speeding up.

Everything after this is those three sentences, expanded.

### Pages 9–16
**Gist:** The table of contents (pp. 9–11), list of tables (pp. 12–13), and list of figures (pp. 14–16) — worth 60 seconds, not more.

The chapter list is the map. Chapters 2–3 are background and the study area; Chapter 4 is the proof-of-concept stream-finding program in one valley; Chapter 5 checks whether satellite elevation maps can be trusted.

Chapter 6 maps streams across all the valleys and years; Chapter 7 measures how the ground changed; Chapter 8 wraps up.

The figure list gives away some treats coming later — a 1630s map of Antarctica, a 1956 aerial photo of glaciers, and lots of erosion/deposition charts. Skim and keep moving.

## Chapter 1 — Introduction (PDF pp. 17–30)
**The chapter in one breath:** The most frozen-in-place landscape on Earth is starting to wake up, its little meltwater streams are where you can see it first, and since no tool exists to map those streams at scale, she will teach a computer to trace them and then measure twenty years of change inside them.

### Page 17
**Gist:** The MDVs, one of the most geomorphically stable landscapes on Earth, are starting to change — and because they stayed still so long, their motion could signal change across all of Antarctica.

The opening argument: glaciated regions worldwide are changing fast because of climate change — even places long considered rock-solid stable. The McMurdo Dry Valleys are Antarctica's largest ice-free patch.

- *geomorphology* — the study of land shapes and how they change

But recently researchers describe the MDVs as "a landscape on the threshold of change": more surface warming, more glacier melt.

The kicker in the last sentences: because this place stayed still for so long, it works as a climate baseline — a reference point. If even the stillest landscape starts moving, that shift may signal something happening across all of Antarctica.

Notice the density of citations — she's stacking evidence that this claim isn't hers alone.

### Page 18
**Gist:** Because glacier melt is essentially the only water source here, stream change directly tracks climate — and nobody has a tool to trace stream boundaries valley-wide, which is the gap this dissertation fills.

Three linked ideas. First: in the MDVs, stream and channel changes track climate closely, because glacier melt is basically the *only* water source — almost no rain or snow falls. So if streams change, melt changed.

Channel adjustments also betray thawing permafrost, since extra meltwater can loosen sediment that used to be frozen in place.

Second, the gap: nobody has a way to semi-automate tracing stream boundaries across the whole valley system for decade-scale monitoring — the hole this dissertation fills.

Third: even small climate nudges could destabilize this landscape, so monitoring stream change works as an early-warning system — showing both *whether* the region is tipping from stability into rapid change and *where* it is happening first.

### Page 19
**Gist:** The MDVs are energy-limited, so a tiny bump in absorbed sunlight can trigger a burst of meltwater — making the valleys a diagnostic landscape, but one where change is easy to miss without sharp, sustained measurement.

The "why here" argument sharpens. The MDVs are *energy-limited*, not precipitation-limited: how much melt happens depends on incoming energy (sunlight, warmth), not on rainfall.

That extreme sensitivity makes the valleys a diagnostic landscape — an early smoke alarm for a continent-wide shift toward melt-driven, Arctic-style behavior.

Then the practical problem: changes here are small and happen in short summer melt windows, so they're easy to miss. Standard change detection first outlines the channel, then compares elevations between epochs to estimate sediment movement.

- *epochs* — snapshots in time

Outlining channels across huge, messy terrain is the hard part. The last paragraph introduces the fix: deep learning, specifically the U-Net.

### Page 20
**Gist:** The pitch closes — a U-Net can trace stream extents at scale, turning the MDVs into a working early indicator — and the historical background begins with the first reported sighting of Antarctica.

The top finishes the pitch: applying a U-Net to trace stream extents makes it possible to estimate stream-driven landscape change at much larger scales. This research aims to automate boundary detection to fill that gap. ("Barlow et al., 2022" is her own earlier paper; it becomes Chapter 4.)

Then Section 1.1, Historical Background, opens with a fun fact: the first reported sighting of Antarctica was in 1603, when Spanish sailor Gabriel de Castilla claimed to see a "white land mass."

In the late 1630s, Dutch mapmaker Henricus Hondius drew the first map of Antarctica, stitched together from earlier explorers' sketches — that map is the figure on the next page.

### Page 21
**Gist:** From Hondius's guessy 1630s map to Scott's 1903 Discovery Expedition and the 1910–1913 Terra Nova surveys, this page traces the first 300 years of seeing the Dry Valleys.

The text marches forward: in 1841 James Clark Ross mapped the coastline, spotting "Victorialand," the Transantarctic Mountains, and the volcanoes Erebus and Terror.

In 1903 Captain Scott's Discovery Expedition became the first to scientifically explore the Dry Valleys — just Taylor Valley, which looked dry and lifeless.

The 1910–1913 Terra Nova Expedition then surveyed Taylor Valley in detail — glaciers, water, rocks, climate — creating records scientists still compare against today, back when the valleys were in equilibrium.

- *equilibrium* — in balance, not changing

**On the page:** Figure 1.1 is Hondius's 1630s map of Antarctica — the first ever, built from early explorers' drawings. Look how vague and guessy the coastline is; that's the starting point of a 400-year effort to see this continent clearly, which this dissertation continues with lasers and satellites.

### Page 22
**Gist:** Decades of measured glacier equilibrium ended when an extreme warming event in 2001 broke the pattern — the hinge of the whole dissertation, and why her before-and-after comparisons pivot on 2001.

In the 1950s, U.S. Navy aerial photographs revealed more inland valleys; comparing glacier snouts against 1910–1911 photos showed the glaciers hadn't budged.

Glacier science began in Wright Valley in 1961, and from 1969 New Zealand's Antarctic Program ran the first long-term glacier monitoring, photographing glacier ends until 1983: balances near zero, glaciers in equilibrium.

Even 1993–2001, while glaciers worldwide were visibly melting, Taylor Valley's glaciers stayed balanced — genuinely weird.

Then the hinge: an extreme warming event in 2001 — only the third on record since instruments arrived in the 1970s — triggered a decade of landscape change. Slow down on this last sentence.

### Page 23
**Gist:** The stream-measurement story runs from New Zealand's 1969 Onyx River gauging through the LTER's 16-stream monitoring to the big one — the 2001 NASA/NSF/USGS airborne lidar flight over the valleys.

Half picture, half data history. New Zealand researchers began monitoring flow on the Onyx River in 1969 and other streams through the '70s and '80s.

In 1992 the Long-Term Ecological Research (LTER) project started watching 16 streams — using flow gauges, surveying instruments, and tripod-mounted laser scanners every 2–3 years — to study the microbial mats living in them.

Then the big one: in 2001, NASA, NSF, and USGS flew airborne lidar over the valleys.

- *airborne lidar* — a plane-mounted laser that times light pulses to build a precise 3D ground map

**On the page:** Figure 1.2 is the first aerial photograph of glaciers in the southwest Dry Valleys, taken in 1956 — labeled with McMurdo Sound, Garwood Glacier, Denton Hills, and Miers Glacier. This is what "remote sensing" looked like before lasers.

### Page 24
**Gist:** The 2001 and 2014 lidar surveys are the backbone of everything ahead, and prior studies using them were either tiny-and-detailed or huge-and-blurry — never every stream in detail.

In 2014 a second airborne lidar mission (NCALM, Portland State, NSF) re-scanned the valleys specifically to measure change since 2001.

Recent studies used them: Crisp (2015) tracked stream channels shifting sideways near microbial habitats, but only on small pieces of famous streams; Levy and Fountain measured change across the whole region but only in broad strokes. Her complaint: never every stream in detail.

Section 1.2 then asks why existing stream-finding tools won't work.

- *flow accumulation* — models that trace where water should run downhill on an elevation map

Flow accumulation assumes rain falls everywhere, but here water enters only at glacier edges — so it draws channels in the wrong places.

### Page 25
**Gist:** Centerline methods don't scale to big, messy landscapes, so she needs continuous full outlines that no off-the-shelf tool provides — and the five channel-change words that Chapter 7 speaks are introduced.

Centerline methods — drawing a line down a stream's middle, then guessing bank positions from cross-section slices — don't scale. MDV channels are narrow, shallow, and subtle, so connect-the-dots between spaced slices misses gentle bends and faint bank edges, and humans must hand-fix messy spots.

Bottom line: she needs continuous full outlines (boundaries), not lines, and no off-the-shelf tool provides them.

Section 1.3 then opens the measurement side: tiny warming triggers melt, thaw, and moving sediment, which reshape channels through incision, aggradation, widening, narrowing, lateral migration, and avulsion.

- *incision* — bed cutting down
- *aggradation* — bed building up
- *lateral migration* — sweeping sideways
- *avulsion* — jumping to a whole new path

Learn these five words — Chapter 7's results speak this language.

### Page 26
**Gist:** Change is measured by subtracting elevation maps from different dates, but MDV changes are so tiny that success hinges on map resolution, quality, and uncertainty — the seed of all of Chapter 5.

Top half: how change is actually measured. Remote sensing covers big, hard-to-reach areas, and the standard move is comparing elevation maps from different dates — subtract, and each pixel says whether ground rose (deposition) or sank (erosion).

The catch: MDV changes are tiny, so success is limited by map resolution, quality, and the uncertainty in comparing maps made years apart. She notes again that no method exists to capture stream-scale change across multiple valleys — what future monitoring needs.

Bottom half: Section 1.4, the Summary, begins — a compressed replay: warming drives melt, thaw, and sediment movement worldwide; the MDVs stayed stable thanks to cold, dry conditions; but rising activity hints acceleration is coming.

Skim, but don't skip the next two pages.

### Page 27
**Gist:** Two fresh nuggets hide in the recap — floods are getting more frequent and bigger, and repeat WorldView satellite DEMs now make broad-scale repeat studies (and acceleration detection) possible.

The evidence of destabilization: floods are getting more frequent and bigger, enlarging channels, eroding banks, and changing stream shapes.

Then the limitations tour: remote sensing transformed geomorphology, but MDV stream research lacked data sharp enough to catch small changes; existing detection methods fail on dry stream beds; and repeat measurements — tripod laser scans, surveying instruments — cover only short pieces of major streams. So MDV streams have never been fully mapped.

Nugget two, last paragraph: repeat DEMs built from WorldView satellite photos now enable broad-scale repeat studies — the key to detecting *acceleration*, and the data of Chapters 5 and 7.

- *WorldView DEMs* — elevation maps made by comparing two photos taken from different angles, like your two eyes judging depth

### Page 28
**Gist:** The clearest page in the chapter states the gap plainly — stream science exists here, system-wide assessment doesn't — and launches the numbered objectives.

First paragraph: her main contribution is a computer-traced stream boundary dataset covering everywhere the 2001 and 2014 lidar flights mapped, enabling detection of channel change and long-term monitoring, focused on pinpointing where change is happening and speeding up. Read it slowly.

Then Section 1.5 lists numbered objectives. Objective 1: build the U-Net stream detector using 2001/2014 lidar DEMs plus 2021–23 WorldView DEMs, delivering a reusable pre-trained model and the first complete database of stream locations across the MDVs (Chapter 6).

Objective 2: compute region-wide rates of change by DEM differencing.

- *DEM differencing* — subtracting one elevation map from another to find vertical change

### Page 29
**Gist:** Objective 3 checks for accelerating change — possible only along selected Taylor Valley streams, where a third snapshot exists — and the chapter-by-chapter roadmap begins.

Objective 3: check for *accelerating* change using the two lidar snapshots plus the 2021–23 WorldView DEMs — but only along selected streams in Taylor Valley, because that's where the third snapshot exists. (Detecting acceleration needs three points in time, like needing three speedometer readings to know you're speeding up.)

Then Section 1.6, the roadmap: Chapter 2 explains the technical concepts; Chapter 3 describes the study area, its melt and sediment drivers, and the datasets; Chapter 4 is the proof-of-concept U-Net in Taylor Valley using 2014 lidar features.

Chapter 5 builds the workflow for aligning satellite REMA DEMs with lidar and grading their accuracy; Chapter 6 scales the U-Net to multiple valleys and years.

One sneaky detail: Chapter 4's bullet says "topographic and reflectance features" — laser-echo brightness — an input that quietly disappears by Chapter 6, since satellites don't provide it.

### Page 30
**Gist:** The roadmap wraps with Chapter 7, the science payoff — quantifying two decades of volumetric erosion, deposition, and geomorphic acceleration — and three things to carry forward from the introduction.

The Chapter 7 bullet finishes: using the 2001 and 2014 lidar plus the 2021–23 REMA DEMs, it quantifies volumetric erosion, deposition, and geomorphic acceleration over two decades across the MDVs and Denton Hills. That's where the tools built in Chapters 4–6 finally answer "how much did the land change, and where?"

Chapter 8 then pulls the outcomes together and points at future directions for long-term monitoring and predictive modeling.

That's the whole introduction. Carry three things forward: the 2001 warming event is the hinge; the 2001 and 2014 laser flights plus 2021–23 satellite maps are the three snapshots; and the plan is trace the streams, then measure change inside them.

## Chapter 2 — Technical Background (PDF pp. 31–47)
**The chapter in one breath:** This is the toolbox chapter — every measuring trick, mapping method, and math idea the rest of the dissertation depends on, explained one at a time.

### Page 31
**Gist:** This page is a table of contents in paragraph form — a parts list of every tool the rest of the dissertation depends on.

Barlow lists every tool she is about to explain: how streams shape land in polar deserts, two ways of measuring terrain from above (lasers and paired photos), a method for lining up two terrain maps so they can be fairly compared, a way to describe the errors in those maps, a machine-learning program that outlines streams, and finally simple subtraction to measure change.

Nothing here is a result. Read it as a parts list; each part gets its own section in the pages ahead.

- *MDVs* — the McMurdo Dry Valleys, the nearly snow-free desert valleys in Antarctica where all this happens. One term to bank now.

### Page 32
**Gist:** One idea, stated formally: streams are shape-shifters, and climate holds the controls.

In the Dry Valleys, water only flows for a few summer weeks when glaciers melt, and permafrost sits just below the surface. Whether dirt washes away depends on grain size, how sticky it is, and how deeply the active layer has softened.

Freeze–thaw cycles and thawing permafrost loosen material, so even a small warm-up frees more sediment to move. That's why these channels are so sensitive, and why they're worth measuring carefully. Skip the citations.

- *Fluvial geomorphology* — the science of how flowing water sculpts the landscape.
- *Permafrost* — ground that stays frozen all year.
- *Active layer* — the thin top layer that thaws each summer.
- *Sediment* — loose sand, gravel, and mud.

### Page 33
**Gist:** Meet lidar — a laser rangefinder flown on an aircraft that times its own light pulses to build a detailed 3-D terrain model.

It fires short laser pulses at the ground, times how long each takes to bounce back, and converts that time into a distance. Millions of these hits build a point cloud.

The page ends introducing the supporting gadgets, continued next page.

- *Lidar* — "light detection and ranging."
- *Active* sensor — brings its own light instead of relying on the sun.
- *Point cloud* — a huge swarm of 3-D dots, each marking a spot the laser touched, together forming a detailed terrain model.

**On the page:** The equation's job: distance equals the speed of light times half the round-trip time (half, because the pulse travels out AND back), adjusted for the air it travels through.

### Page 34
**Gist:** The supporting cast — GNSS and an IMU pin each laser dot to a real spot on Earth — plus the fine print on spot width, multiple bounces, and laser color.

Combine the plane's position (GNSS) and pointing direction (IMU) with the laser's distance and you can pin each dot to a real spot on Earth.

Fine print: the laser spot on the ground has a width, and a wider spot means fuzzier location. One pulse can bounce off several things — a bush, then the ground — so points get filtered to build a DTM.

The laser's color matters too: near-infrared light gets swallowed by water, while green light can see through shallow water.

- *GNSS* — satellite positioning, like GPS; tells the plane where it is.
- *IMU* — a motion sensor tracking tilt and rotation; tells the plane which way it's pointing.
- *DTM* — a bare-ground elevation map with the clutter removed.

### Page 35
**Gist:** Lidar's errors vary from place to place — and since Antarctic lidar flights are rare and costly, repeat measurements come from satellite stereo photos instead.

First, lidar's error list: GPS wobble, tilt-sensor drift, steep or repetitive terrain, multipath, and striping where flight lines overlap. Key takeaway: errors vary from place to place, so you must account for that before trusting any change map.

Second, the hand-off: lidar flights over Antarctica are rare and costly, so repeat measurements come from satellites instead. Enter stereophotogrammetry — exactly how your two eyes give depth.

Blink one eye, then the other, watching your thumb: that's the whole idea.

- *Multipath* — the laser bouncing off two surfaces before returning, faking a wrong distance.
- *Stereophotogrammetry* — getting 3-D shape from two overlapping photos taken from different angles.
- *Parallax* — the apparent jump of an object between two viewpoints; closer things jump more.

### Page 36
**Gist:** Modern satellites aren't one-click cameras — they scan line by line, so stereo elevation depends on RPC formulas, and the matching breaks in predictable ways.

The classroom version of stereo photos assumes one camera click from one spot — but modern satellites use a pushbroom sensor while racing along in orbit. No single click, no fixed geometry.

The fix is RPCs. Match the same point in two images, trace both viewing rays with the RPCs, and where they cross is the elevation.

Then the failure list: bland texture, shadows, repetitive terrain, and hidden spots all break the matching, and a small convergence angle amplifies errors.

- *Pushbroom sensor* — a camera that scans one line at a time, like a document scanner sweeping the ground.
- *RPCs* — pre-computed math formulas shipped with each image that translate between photo pixels and ground positions.
- *Convergence angle* — the angle between the two viewing directions.

### Page 37
**Gist:** SETSM automates the stereo matching (it built REMA), but even the best stereo DEM carries leftover errors — so two DEMs must be precisely aligned with ICP before comparing.

First, SETSM does the stereo matching for you, starting with a rough coarse match and sharpening step by step. It built REMA from sub-meter satellite photos.

Second: before comparing two DEMs, they must be precisely aligned. In the Dry Valleys, real changes are tiny, so even small misalignments could fake erosion that never happened.

- *SETSM* — an automated program that does the stereo matching for you.
- *REMA* — the elevation map covering all of Antarctica, made from sub-meter satellite photos.
- *DEM* — digital elevation model, an image where each pixel stores the ground height.
- *ICP (iterative closest point)* — an algorithm that nudges and rotates one 3-D surface to best fit another, repeating until they line up.

### Page 38
**Gist:** How ICP works — and why leftover sideways misalignment sneakily fakes elevation change that follows a telltale wavy, slope-facing pattern.

The algorithm finds the best rigid move — a rotation plus a slide, no stretching — and repeats until the fit stops improving. The "point-to-plane" flavor compares each point to the local flat patch of the other model instead of to a single nearest point; that works better on smooth ground and converges faster.

Now the warning: if two elevation maps stay slightly shifted sideways, subtracting them creates fake ups and downs that depend on which way each slope faces — its aspect — following a telltale wavy pattern.

Steeper terrain amplifies the fakery. Sometimes alignment must even be done piece by piece across the map.

- *Tangent plane* — the small flat surface that approximates terrain right at one point.
- *Aspect* — the compass direction a slope faces.

### Page 39
**Gist:** Figure 2.1 shows the fingerprint of horizontal misalignment; then the chapter pivots to mapping where streams ARE.

The wavy pattern in the figure is a fingerprint — see it in your data and you know your "change" is really a shift, not real erosion.

Then a new section begins: to measure stream change, you first need to map where streams ARE, because channel boundaries define where erosion gets counted. Traditional methods start by extracting a drainage network from a DEM and tracing centerlines.

- *Centerlines* — the line down the middle of a stream, without its edges.

**On the page:** Figure 2.1 — the top panel shows that fake elevation errors grow with slope steepness; the bottom panel shows those errors tracing a smooth wave as you go around the compass directions the slopes face.

### Page 40
**Gist:** A tour of stream-mapping methods that don't work here — each assumes something the Dry Valleys don't provide.

Tracing channels by hand from photos? Fine for small areas, but too slow and too subjective for whole valleys.

Detecting water by its color signature — indexes like NDWI? Fails, because Dry Valley channels are dry most of the year, and water color finds water surfaces, not the channel's topographic edges.

Flow accumulation predicts stream centerlines, but requires pre-cleaning steps like filling pits and smoothing terrain, which can erase exactly the faint bumps that shallow channels are made of.

- *NDWI* — a formula combining satellite image colors that lights up open water.
- *Flow accumulation* — a simulation of where water would collect if it flowed downhill across an elevation map.

### Page 41
**Gist:** Flow-simulation methods (D8, D-Infinity) are touchy to DEM noise and assume evenly spread rain — but the Dry Valleys are melt-dominated, so predicted centerlines miss.

Both rules are touchy: tiny elevation errors in the DEM can swing the predicted streams far off course, especially in flat or noisy terrain.

Worse, these methods assume rain falls roughly evenly everywhere. The Dry Valleys are melt-dominated — water comes almost entirely from glacier edges, in patchy pulses — so predicted centerlines get missed or mislocated, especially near the glaciers.

Even expert-tuned thresholds over- or under-draw the network.

- *D8* — a rule sending each pixel's simulated water to exactly one downhill neighbor; suits small, simple basins.
- *D-Infinity* — a rule that can split flow between two neighbors; more flexible but can scatter flow into too many branches.

### Page 42
**Gist:** One more traditional method — cross-section slicing — and why it fails on shallow, braided Dry Valley channels.

Cross-section approaches slice across the channel at set intervals and find the banks by looking for where the slope kinks, then connect the dots between slices.

Problems: shallow, braided Dry Valley channels often have no clear kink to find; slices must be closely spaced to catch detail, which gets expensive over big areas; the whole thing leans on the centerline being right in the first place.

Also, slice length must be guessed correctly — too long and you grab nearby hills, too short and you miss the banks. Confluences and tight bends usually need manual fixing.

- *Cross-section* — a cut across the stream, like slicing a loaf of bread.

### Page 43
**Gist:** The verdict — traditional methods extract centerlines, not full outlines, and don't scale — so machine learning takes over.

Traditional methods don't scale to many valleys while keeping the fine detail that subtle polar changes demand. That failure list is the motivation for machine learning.

A CNN will do the job — specifically, semantic segmentation will mark each pixel "stream" or "not stream."

The chosen design is *U-Net*, an *encoder-decoder* model (shrink-to-understand, enlarge-to-answer; explained on page 45).

- *CNN (convolutional neural network)* — a computer program that learns to recognize visual patterns from examples, the same family of tech that finds faces in phone photos.
- *Semantic segmentation* — labeling every single pixel of an image with a category, like a paint-by-numbers map where the computer figures out the lines.

### Page 44
**Gist:** Why U-Net specifically: it learns well from small training sets while capturing fine detail AND the big picture — the load-bearing sentence of the page.

Most powerful segmentation networks are data-hungry — they need thousands of labeled examples, and training data is brutally expensive to make when every stream outline must be drawn by a person.

U-Net's claim to fame is learning well from small training sets, thanks to its architecture and tricks like augmentation (stretching your examples further) and skip connections (coming on page 45).

It has already worked for roads, building footprints, land cover, and medical scans — skim that list. The page ends by setting up the architecture walkthrough: the network is U-shaped, an encoder on the left, decoder on the right.

- *Training data* — the hand-labeled examples a network learns from.

### Page 45
**Gist:** The guts of U-Net — encoder shrinks to understand, decoder enlarges to answer, skip connections keep edges sharp — and the closing point: it has never been tried on dry, waterless streams using terrain shape instead of photo colors. That's this dissertation's new move.

The encoder stacks two kinds of steps: convolutional layers and max pooling. Shrinking helps the network grasp context ("this region looks channel-ish") but blurs exact locations.

The decoder blows the image back up to draw the pixel-by-pixel answer, and skip connections keep the edges sharp. After training, inference means running the network on brand-new images.

- *Encoder* — the shrinking half of the network.
- *Convolutional layer* — sliding a small pattern-detecting window across the image.
- *Max pooling* — shrinking the image by keeping only the strongest signal in each small block.
- *Decoder* — the enlarging half.
- *Skip connections* — shortcut wires carrying crisp detail from each shrinking step to its matching enlarging step.
- *Inference* — running the trained network on brand-new images.

### Page 46
**Gist:** Two things share this page: the classic U-Net diagram (Figure 2.2), and the start of the payoff method — the DoD, elevation subtraction that maps erosion and deposition.

The DoD is the map you get by subtracting one elevation model from another taken years apart. Positive means ground rose (deposition); negative means it fell (erosion).

Multiply by pixel area to turn height change into volume.

- *DoD (DEM of Difference)* — the map made by subtracting one elevation model from another taken years apart.
- *Feature maps* — the image's in-progress representations inside the network.
- *Deposition* — dirt piled up.
- *Erosion* — dirt carved away.

**On the page:** Figure 2.2, the classic U-Net diagram — read it left to right: blue boxes are feature maps, arrows are operations; the image steps down the left side of the U (shrinking, understanding), crosses the bottom, and climbs the right side (enlarging, answering), with horizontal arrows across the U being the skip connections. Equation 2.1's job is exactly the DoD subtraction: new heights minus old heights, pixel by pixel.

### Page 47
**Gist:** The chapter's last small step turns "how much" into "how fast" — divide total elevation change by elapsed time to get a rate she names DGC.

Sum the erosion and deposition volumes across a watershed and you get a sediment budget. That's it — the math is subtraction and division.

The honesty of the answer depends entirely on everything earlier in the chapter: good elevation maps, careful alignment, and knowing where the streams are. Toolbox complete; the next chapters put it to work.

- *Watershed* — all the land whose water drains to the same stream.
- *Sediment budget* — the net total of dirt gained and lost, like a bank statement for soil.
- *DGC (differential geomorphic change)* — a speed of landscape change.

**On the page:** Equation 2.2's job: divide total elevation change by the time elapsed between the two surveys to get a rate.

## Chapter 3 — Study Area & Datasets (PDF pp. 48–62)
**The chapter in one breath:** The McMurdo Dry Valleys are a huge frozen desert in Antarctica where every stream is fed by melting glaciers, and this chapter introduces both the place and the three elevation "snapshots" (2001, 2014, 2021–23) the dissertation uses to watch that landscape change.

### Page 48
**Gist:** The McMurdo Dry Valleys (MDVs) — Antarctica's biggest ice-free patch — are an ultra-stable frozen desert now nicknamed a "landscape on the threshold of change."

Chapter 3 introduces the star of the show: the MDVs, about 5,000 square kilometers of bare rock and soil in East Antarctica — the biggest ice-free patch on the whole continent.

Why ice-free? The Transantarctic Mountains act like a wall: they block the giant ice sheet from flowing in and create a rain shadow.

- *rain shadow* — the dry zone behind a mountain range where almost no moisture arrives.

The result is a super-cold desert with widespread permanently frozen ground, so stable it has barely changed in about 10 million years. But the page ends on the hook: since 2002, warming spells have earned the MDVs the nickname "landscape on the threshold of change."

Remember "MDVs" — you'll see it on every page from here on.

### Page 49
**Gist:** Warming is already reshaping the MDVs, and the four valley systems named here (Victoria, Wright, Taylor, Denton Hills) are the geography every later result is reported by.

The warming is already reshaping things: thermokarst, plus thinning glaciers, rising lakes, and more meltwater runoff.

- *thermokarst* — ground that sinks or collapses when the ice frozen inside it melts.

Since most MDV water is locked in glaciers and ground ice, more melting means faster landscape change — which is why the dissertation needs tools that watch streams in fine detail across many valleys at once.

Then comes a page to memorize: the four valley systems, north to south — the Victoria Valley system, the Wright Valley system, Taylor Valley (the most studied), and the Denton Hills. Later chapters report every result by these names.

The last paragraph is the chapter's roadmap: describe the climate, ice, water, and geology, then the datasets used later.

### Page 50
**Gist:** Figure 3.1 is the master lookup map of the whole study region, and the Climate section reveals that with under 10 cm of snow a year (mostly sublimating away), temperature is the master control on streamflow.

The Climate section starts with a startling fact: the MDVs get less than 10 cm of snow a year, and most of that sublimates.

- *sublimates* — turns straight from ice into vapor without ever melting.

So liquid water is scarce, and temperature becomes the master control knob deciding how much glacier melt (and thus streamflow) happens.

**On the page:** The top is Figure 3.1 — the only overview map of the whole study region. The main map shows the four valley systems (Victoria, Wright, Taylor, Denton Hills) stretching between the Polar Plateau and the Ross Sea; the small inset shows where this patch sits on the continent of Antarctica. Bookmark it — it's your lookup map for every place name later.

### Page 51
**Gist:** Summer temperatures flicker right around freezing — which makes the system touchy — and the landscape splits into three microclimate zones (CTZ / IMZ / USZ) reused throughout the dissertation.

Some numbers to feel the cold: average yearly air temperature is −18 to −22°C. But in summer — November to February, because seasons are flipped in the Southern Hemisphere — valley floors hover right around freezing, and warm spells can spike to +10°C.

That flickering around the melting point is what makes the system so touchy. Conditions also vary across the landscape: wetter near the coast, drier inland and uphill.

Then the page introduces the chapter's most reused idea:

- *microclimate zones* — small areas with their own distinct local climate.
- *Coastal Thaw Zone (CTZ)* — warm and moist, along coasts and low valley floors.
- *Inland Mixing Zone (IMZ)* — cooler mid-elevation slopes.
- *Upland Stable Zone (USZ)* — introduced next page.

Memorize CTZ / IMZ / USZ.

### Page 52
**Gist:** Glaciers are essentially the MDVs' only water source, so melt is limited by energy rather than precipitation — and even tiny warming triggers melt that can move sediment.

First, the third zone: the USZ covers high inland areas and glacier surfaces — the coldest, driest conditions in the MDVs. Keep the ladder in mind: CTZ (most active) > IMZ > USZ (least).

Then the cryosphere section begins, glaciers first.

- *cryosphere* — the frozen parts of the world.
- *glacier* — a huge, slowly flowing mass of ice.

Here glaciers are essentially the only water source, since snow sublimates away. That means water production is limited by energy (heat, sunlight), not precipitation — so even tiny warming triggers melt that can move sediment.

Recent decades show accelerating ice loss from named glaciers (Canada, Commonwealth, Taylor, Garwood, Wright Lower). Coastal CTZ glaciers like Miers, Canada, Commonwealth, and Garwood are thinning fast, feeding erosion downstream.

### Page 53
**Gist:** Melting follows the zone ladder — strongest at the coast, weakest inland — and permafrost 70–100 m deep, topped by a thin summer-thawing active layer, controls how easily slopes and stream banks collapse.

The glacier story finishes with a neat contrast: Wright Lower Glacier is thinning fast, but Taylor Glacier is roughly in balance — it loses ice mainly by sublimation, not melting. Cold inland glaciers (like those in the Victoria Valley system) mostly sublimate too and produce little meltwater.

Pattern: melting follows the zone ladder — strongest at the coast, weakest inland.

Then a new key idea, running 70–100 meters deep here:

- *permafrost* — ground that stays frozen all year. Two types here: ice-cemented soil (soil glued together by ice, ~55%) and dry-frozen soil (frozen but nearly ice-free, ~43%).
- *active layer* — the thin top 30–75 cm that thaws each summer; deeper near the coast, barely 10 cm inland.

Daily freeze–thaw cycles weaken icy soils, making slopes and stream banks collapse.

### Page 54
**Gist:** Permafrost controls how easily stream channels erode — ice-cemented banks are rock-hard while frozen but can cave in during warm spells, and coastal valleys even hide massive buried ice.

The text explains why permafrost matters for streams: it controls how easily channels erode. Ice-cemented banks are rock-hard while frozen but can fail — cave in — during warm spells, while coarse, well-drained stretches change more slowly.

Geography matters: coastal CTZ valleys (Denton Hills, Garwood, Miers, lower Taylor and Wright) are dominated by ice-cemented permafrost and even hide massive buried ice — big slabs of old ice under the dirt, left by an ancient ice advance called the Ross Sea Drift.

**On the page:** Most of the page is Figure 3.2, a map of estimated active-layer depths (borrowed from Bockheim et al., 2007). It shows how deep the summer thaw reaches across the valleys — deeper generally near the coast, shallower inland — which tells you where the ground gets soft enough to erode.

### Page 55
**Gist:** The valleys sort onto a fragility spectrum — Denton Hills (ice-cemented, most fragile) to Victoria (dry-frozen, most stable) — that explains most later "why did the land change *here*?" results.

The Denton Hills are the extreme case: about 98% ice-cemented — soil glued by ice that collapses when thawed — with the deepest active layers, making them the most prone to thermokarst sinking, bank failure, and rapid channel change.

Moving inland, dry-frozen ground (frozen but with little ice, so thawing barely matters) takes over: roughly 67% of Taylor Valley's floor, ~87% of Wright Valley's loose sediments, and ~89% in the Victoria Valley system — the most stable of all.

Don't memorize the percentages; keep the ranking: Denton Hills most fragile, Victoria most stable. This single spectrum — ice-cemented coast versus dry-frozen inland — will explain most of the "why did the land change *here*?" results in later chapters.

### Page 56
**Gist:** The Hydrosphere section opens with the dissertation's broad working definition of "stream" — any meltwater-driven channel that leaves a visible shape in the ground — which matters because the whole project detects those shapes in elevation data.

Below the figure, the Hydrosphere section begins — the water part of the system. It opens with a definition worth underlining:

- *stream* (as used in this dissertation) — any meltwater-driven channel that leaves a visible shape in the ground, from named rivers down to short glacier-fed trickles.

That definition matters because the whole project is about detecting those channel shapes in elevation data.

**On the page:** The top is Figure 3.3, a map of permafrost types across the MDVs (from Bockheim et al., 2007). Each color marks a different kind of frozen ground — dry-frozen permafrost, ice-cemented permafrost, and buried ground ice. Bookmark this one; permafrost type is the best single predictor of which streams change later in the dissertation.

### Page 57
**Gist:** MDV streams are ephemeral, narrow channels cut into ice-cemented soil, so even small extra meltwater visibly reshapes them — and each valley drains in its own distinctive way.

MDV streams live in valley bottoms where glacier meltwater collects.

- *ephemeral* — flowing only during the short summer.

Even with 24-hour summer sunlight, shadows from the terrain and shifting weather make melt patchy in time and space.

The channels are narrow and cut into ice-cemented soil, so even small extra meltwater can visibly reshape them — deepening, bank collapse, or sideways migration.

Each valley drains its own way: Taylor's streams feed closed salty lakes with no outlet (so lakes rise); Wright Valley has the Onyx River, Antarctica's longest at ~32 km, which flows *inland* to Lake Vanda; southern rivers like Garwood and Miers run straight to the sea; and Victoria's channels flow only in rare big-melt years. Flow is also "flashy" — surging and crashing.

### Page 58
**Gist:** Streamflow arrives in short, intense bursts — from garden-hose-sized creeks to rare floods over 10 m³/s — so erosion is concentrated too, speeding landscape change.

A short page putting numbers on "flashy." Small glacier-fed streams in Taylor Valley, like Canada Stream and Harnish Creek, typically flow at 10–25 liters per second — think a few garden hoses.

Big systems like the Onyx and Garwood Rivers average near 1 cubic meter per second (a thousand liters every second), with historic floods topping 10 cubic meters per second.

Flow swings with the sun in a daily rhythm, varies wildly year to year, and rare flood years can multiply annual flow by 3 to over 1,000 times — while in some summers certain channels never flow at all.

- *diel* cycle — a 24-hour cycle.

Because all the water arrives in short, intense bursts, the erosion is concentrated too — which speeds up landscape change.

### Page 59
**Gist:** Figure 3.4 is the stream-name lookup map, and hyporheic exchange — some channels acting like sponges — helps explain why some stream reaches erode dramatically and others barely change.

The text adds one more wrinkle:

- *hyporheic exchange* — water seeping back and forth between a stream and the soggy sediment under and beside it.

Long channels with big hyporheic zones act like sponges, losing much of their flow into the ground (and to evaporation) in low-flow years, while short, steep streams deliver their meltwater straight to the lakes.

That difference helps explain why some stream reaches erode dramatically and others barely change.

**On the page:** Most of the page is Figure 3.4, the stream map of the MDVs. All mapped streams are drawn across the valleys, the ones scientists actively monitor are highlighted in red, and the green dots are gage stations — fixed instruments that measure streamflow. Bookmark it as your stream-name lookup for later chapters.

### Page 60
**Gist:** Faint stream shapes defeat traditional flow-tracing methods — hence deep learning — and the Datasets section names the three elevation snapshots: 2001 ALS, 2014 ALS, and 2021–23 REMA.

Two big moments on this page. First, the punchline of the whole hydrology section: many MDV streams leave only faint, subtle shapes in the terrain, so traditional computer methods — which trace where water *should* flow downhill (called flow accumulation) — often miss them. That's exactly why the dissertation turns to deep learning, a type of AI that learns patterns from examples.

Second, the Datasets section opens and names the three elevation sources: an ALS survey from 2001, another from 2014, and 2021–23 elevation maps from WorldView satellite photos, part of REMA (the Reference Elevation Model of Antarctica).

- *ALS* — Airborne Laser Scanning; lidar flown from a plane.

Together they let the study map stream boundaries, measure decades of elevation change, and ask whether change is accelerating. Fix the dates: 2001, 2014, 2021–23.

### Page 61
**Gist:** Figure 3.5 maps where each dataset has coverage — results can only exist where the footprints overlap — and the airborne surveys are the sparse 2001 NASA ATM flight and the much sharper 2014 NCALM flight.

Details on the airborne lidar: the 2001 NASA survey used the Airborne Topographic Mapper (ATM), a laser scanner firing two wavelengths of light. It was sparse — about one height measurement per 2.7 square meters, roughly one reading per parking space — over ~4,500 km².

In 2014, NCALM (the National Center for Airborne Laser Mapping) teamed with Portland State University to fly a much sharper survey with a three-wavelength Optech Titan sensor.

**On the page:** The top is Figure 3.5, the dataset coverage map — bookmark it. Each color outlines where one dataset has data: the 2001 NASA lidar in red, the 2014 NCALM lidar in dark blue, 2014 REMA elevation maps (used for accuracy checking) in light blue, and the 2021–23 REMA maps in green. Results can only exist where these footprints overlap.

### Page 62
**Gist:** The 2014 lidar is about ten times sharper than 2001 (~7 cm accuracy), and the REMA satellite strips split roles — 2014 for uncertainty estimation, 2021–23 for change detection — but aren't pre-aligned, so hand-alignment covers only bits of Taylor Valley.

The 2014 survey's stats: three laser colors, though the green one got overwhelmed — saturated — by sunlight glinting off snow and ice, so it wasn't used everywhere. Heights are accurate to ~7 cm, over ~3,600 km².

- *point density* — laser measurements per square meter, like pixels in a photo; here 2–10, averaging 4.7 — about ten times sharper than 2001.

Then the satellite data: the Polar Geospatial Center built REMA elevation maps from stereo pairs of WorldView satellite photos — two photos from different angles, combined for depth like your two eyes.

The 2014 REMA strips are for developing an uncertainty (error) estimate; the 2021–23 strips are the actual change-detection snapshot.

Catch: strips aren't pre-aligned to true ground positions, and hand-aligning them is so slow that this part covers only bits of Taylor Valley. Automation comes later.

## Chapter 4 — Teaching a Neural Network to Find Streams (PDF pp. 63–85)
**The chapter in one breath:** Barlow teaches a computer program to look at laser-scanned maps of a frozen Antarctic desert and color in every dry streambed — and one simple map (just elevation) beats every fancy combination, getting about 94% right.

### Page 63
**Gist:** The dissertation's engine room begins: this chapter is her published paper (Barlow et al., 2022, *Remote Sensing*) on finding stream edges in Taylor Valley, one of the McMurdo Dry Valleys.

Why care about edges? A stream's width and cross-sectional area — the shape of the channel if you sliced it like a loaf of bread — tell scientists how much water and sediment it can move.

The note at the top matters: Taylor Valley is just the test kitchen. If the recipe works here, Chapter 6 cooks it for the entire Dry Valleys region.

**On the page:** The citation pile-up at the bottom is normal science-paper throat-clearing — skim it.

### Page 64
**Gist:** These streams are ephemeral, so the tell-tale bank edges are faint or missing — her fix is to stop splitting hairs and use one single "stream" category.

The streams only flow sometimes, during a few weeks of summer melt. In rainy climates, streams fill to the brim every year or two, carving obvious banks; here that almost never happens, so the edge between "channel" and "bank" is faint or missing.

She also explains why remote sensing is required at all — walking Antarctica measuring streambanks by hand is brutal — and lists what others have used, setting up her own twist on these tools.

- *ephemeral* — streams that only flow sometimes, during brief melt periods
- *bankfull* — the state where a stream fills to the brim, carving obvious banks
- *DEMs* — digital elevation models: maps where every pixel stores ground height
- *flow accumulation models* — predictions of where water would drain

### Page 65
**Gist:** The punchline of the setup: she'll feed lidar-derived maps into a U-Net to trace stream edges across 770 square kilometers of ice-free Taylor Valley.

She claims nobody has used deep learning on small (10–150 m wide) desert streams at this multi-valley scale before.

- *U-Net* — a type of neural network, a program that learns patterns from examples instead of hand-written rules

**On the page:** Figure 4.1 is a side-view slice of a stream. The red dotted arrows show two possible widths — bankfull width (water at the brim) and active channel width (where water actually flows). In these trickle-streams the difference is too blurry to see, which is exactly why she merged them into one class on the previous page.

### Page 66
**Gist:** The takedown of existing methods: older cross-section approaches need extra data, guess between measuring lines, and fail on small desert streams — hers will need no cross-sections, no precipitation data, no imagery.

Older approaches slice the stream with imaginary measuring lines laid perpendicular to the stream's centerline, then hunt for the banks along each line. Problems: they need extra data (rain records, photos), and between measuring lines they have to extrapolate — which breeds errors if lines are spaced too far apart.

Even satellite-photo methods only work on rivers wider than 30 m, and in the Dry Valleys a photo may show nothing at all, since water, wet soil, and ice come and go. Covering a huge multi-watershed region with enough cross-sections gets computationally expensive fast.

- *cross-sections* — imaginary measuring lines laid perpendicular to a stream's centerline for hunting banks

### Page 67
**Gist:** Cross-section methods break on curvy and braided streams — every mistake needs hand-fixing, which is hopeless across a whole valley network, so her goal is an algorithm that colors in stream pixels directly.

Cross-section methods handle straight streams fine. But a braided stream gives a measuring line multiple bumps and dips, and the algorithm can grab the wrong pair as "the banks." On a tight meander, a line drawn perpendicular to the centerline can accidentally stab upstream and downstream instead of crossing the banks.

- *braided* — a stream split into rejoining threads, like a loose hair braid
- *meandering* — tightly curving
- *inflection points* — spots where the ground's curve changes direction

**On the page:** Figure 4.2 shows four stream shapes: (a) straight, (b) braided, (c) meandering, (d) intersecting.

### Page 68
**Gist:** Why U-Net: it needs fewer training examples and produces smooth, connected shapes — perfect for streams, which should be continuous ribbons, not confetti.

She's refreshingly honest: streams here flow so rarely, and field data is so scarce, that even humans can't label every boundary with certainty. So the study only targets streams whose edges are *visually distinguishable*.

Keep that in your pocket — the impressive scores later are earned on streams a careful human could also see. The payoff she promises: track stream change through time across Taylor Valley's climate zones.

- *CNNs* — convolutional neural networks: pattern-learning programs especially good at images, able to spot objects at different sizes and positions

### Page 69
**Gist:** Methods begin: the raw ingredient is an airborne lidar survey from 2014 covering roughly 560 km² of ice-free terrain, collected by NCALM, a national laser-mapping center.

A plane fires laser pulses at the ground and times the echoes, producing millions of precise 3D points (about 2.7 points per square meter here). No trees in Antarctica means the lasers see bare ground perfectly.

Aerial photos (5–20 cm detail) were captured at the same time to help humans trace the answer key.

- *lidar* — laser scanning: a plane fires laser pulses at the ground and times the echoes to produce precise 3D points

**On the page:** Figure 4.3 is the whole recipe as a flowchart: prepare data, hand-label examples, train the U-Net, predict across the valley. Glance at it now and again after page 76 — it'll make more sense the second time.

### Page 70
**Gist:** The point cloud becomes four flat map layers — DEM, intensity, slope, and flow accumulation — the candidate inputs to the U-Net; the labeled dataset is only about 1% of the study area.

Natural neighbor interpolation (a smart averaging method) turns the laser dots into two rasters with 1×1 m pixels: a DEM (height everywhere) and an intensity map (how brightly the ground reflects the laser; wet ground and ice reflect differently than dry dirt).

From the DEM she computes slope (steepness) and flow accumulation (for each pixel, how much upstream land drains into it — a "where water would go" map).

Bottom of the page: the labeled dataset is 217 tiles, each 300×300 m — only about 1% of the study area. Tiny homework set, big exam.

- *rasters* — grid-of-pixels maps

**On the page:** Figure 4.4 is just the "you are here" map of Taylor Valley.

### Page 71
**Gist:** The 217 practice tiles deliberately include every stream shape — straight, sinuous, meandering, braided/intersecting — plus tiles with no stream at all, so the network learns what "nothing" looks like.

To confirm a stream really existed, she cross-checked LTER (Long-Term Ecological Research) stream maps, flow-accumulation paths, and photos showing linear streaks of water, ice, or wet ground.

Then normalization, followed by labeling: every pixel gets one of two labels, "stream area" or "non-stream area."

- *normalization* — within each tile, subtract the minimum value and divide by the range, stretching every tile to use the full 0–255 brightness scale — like auto-adjusting each photo's contrast so faint bank edges pop
- *labels* — human-drawn correct answers

### Page 72
**Gist:** The crucial confession: a neural network is only as good as its answer key, so ambiguous tiles were excluded — the model learns only from clear-cut cases. Remember this when the scores arrive.

What does a stream edge look like to a human tracer? Inflection points (bends in the ground's profile), changes in sediment texture, staining on the floodplain, and linear stripes of snow, ice, water, or wet ground.

She traced boundaries using terrain profiles, elevation, and slope; photos, intensity, and flow accumulation were backup clues — they reveal where a stream *is* (if something wet or icy sits in it) but not where its *edges* are.

Rock layers poking through the surface make bends in the ground that mimic stream banks, which is why ambiguous tiles were cut.

- *strata* — rock layers

### Page 73
**Gist:** Mostly a figure page, plus the start of the U-Net section: U-Net does segmentation, classifying every single pixel (stream or not) rather than captioning the whole image, while preserving fine detail.

- *segmentation* — classifying every single pixel rather than naming the picture — coloring inside the lines instead of captioning the image

**On the page:** Figure 4.5 shows the same patch of ground through six lenses — what the network "sees." Panels a and d: hillshade (a fake-sunlight 3D rendering) with the human-traced truth overlaid. Panels b and c: elevation and slope, where the stream shows up as a linear depression with sharp bank inflections — the shape clues. Panels e and f: intensity and flow accumulation, where the stream appears as a bright or accumulating line — the "something's in the channel" clues.

### Page 74
**Gist:** The U-Net's two halves get explained, then the training setup: free open-source code, a pre-trained encoder, a 50/20/30 data split, rotation augmentation, and free Google Colab GPUs — shoestring budget, real science.

The training stack: DroneDeploy's landcover tool, built on PyTorch, with a pre-trained ResNet-18 encoder — a network that already learned basic vision from other images, so it isn't starting from zero.

The 217 tiles split 50/20/30: training (studied), validation (progress checks), test (final exam, never seen during learning). Each training tile is also rotated three times by 90° — same stream, four viewpoints — to stretch the small dataset. Free Google Colab GPUs (fast graphics chips) run it all in 4–6 hours.

- *encoder* — shrinks the image step by step, trading sharpness for understanding ("there's a channel here somewhere")
- *decoder* — zooms back out, restoring full resolution to draw exact edges

### Page 75
**Gist:** The knob settings and the grading system: hyperparameters chosen for a smoothly falling loss curve, and three grades — precision, recall, F1.

Hyperparameters — the dials you set before training: 200 epochs, batch size 16, a tiny learning rate of 0.00001 (baby-step corrections after each mistake).

Prediction then covers the valley with 852 overlapping 1500×1500 m tiles.

- *epochs* — full passes through the training set, like rereading the textbook 200 times
- *precision* — of all pixels painted "stream," what fraction truly were?
- *recall* — of all true stream pixels, what fraction got found?
- *F1* — a 0-to-1 blend of both; you only score high by scribbling neither outside nor short of the lines

(Her sentence tying recall to non-stream regions is oddly worded — use these definitions.)

### Page 76
**Gist:** The sneakiest trade-off in the chapter: prediction tiles are 1500 m though training used 300 m — bigger tiles show the whole channel, but per-tile contrast stretching can flatten a faint stream toward the background.

Why bigger? Small tiles often held only a fragment of a channel — no banks in view — and the confused network painted tile edges as "stream" and stream bottoms as "not stream." Bigger tiles show the whole channel: full sentence instead of one word.

But each tile's contrast is stretched by its own min and max — a 5×-bigger tile spans a wider range of values, so a faint stream gets flattened and can vanish. She names the cost openly. Whole-valley prediction takes ~15 minutes.

Then Results begin with the surprise: single-feature models beat every multi-feature combo, and elevation and slope tie for the crown.

### Page 77
**Gist:** The numbers: elevation scores precision 0.94 / recall 0.95 / F1 0.94; slope 0.96 / 0.93 / 0.94; intensity and flow accumulation trail (F1 0.94 and 0.93, but shakier precision: 0.88, 0.89).

Translation: of everything the elevation model painted "stream," ~94% really was, and it found ~95% of true stream pixels. The ± values are standard deviations — the wobble across test tiles.

The fine print matters most: true positives average only 0.71 versus 0.93 for true negatives. Most of the desert isn't stream, so easy "not stream" pixels inflate the grade; the model's real habit is *missing* stream — underprediction — especially where bank slopes break gently.

Coastal tiles score F1 0.81–0.99; scores sag inland.

**On the page:** Table 4.1, one column per single input.

### Page 78
**Gist:** Table 4.2 is the graveyard of combinations: every pairing and stacking of elevation (E), slope (S), intensity (I), and flow accumulation (A) loses to single features — F1 0.83–0.92 versus 0.93–0.94 alone.

Notice the pattern in *how* they fail: combos like E/S post sky-high recall (0.96–0.99) but weak precision (0.74–0.79) — they find nearly all the stream but smear paint everywhere else too.

Counterintuitive but real: with a small training set, giving the network more input layers gives it more ways to get confused, not more wisdom. The discussion on page 83 explains the why.

**On the page:** Skim Table 4.2 to confirm the pattern; don't memorize the grid.

### Page 79
**Gist:** Figure 4.6 is the report card drawn on a map: high-F1 test tiles cluster near the coast and fade inland, and the dominant error is skipped tributaries.

Tributaries — the small side-branches feeding the main channel — get missed because their banks slope too gently to leave a sharp signature.

Below the figure, a new angle: comparing scores against the valley's three microclimate zones, the coastal thaw zone wins — but she notices the scores may track *geology* even better: loose glacial till near the coast scores high, bedrock areas score low.

**On the page:** Each dot is a test tile, colored white (low F1) to blue (high F1), scattered across Taylor Valley. Panels a–f zoom into representative spots: predicted stream outlines against human-traced truth. Look at what's missing rather than what's wrong.

### Page 80
**Gist:** Figure 4.7 doubles down on the geography story: the weak (white) F1 dots tend to sit on bedrock, while streams cutting loose glacial till carve crisp, learnable banks.

That makes physical sense — streams on hard rock leave subtle edges, and rock outcrops make bank-like bends that fool both human and machine.

Below, the stream-shape analysis begins: elevation and slope stay steadiest across all four stream geometries.

**On the page:** Two maps of the same F1 dots (white = low, blue = high). Panel (a) lays them over the three microclimate zones — coastal thaw, intermediate, upland stable. Panel (b) lays them over geology: tan-yellow shades for loose sediment grain sizes, green/gray/black for bedrock types. Read it by asking: do the white (weak) dots sit on any one background?

### Page 81
**Gist:** A beautiful reversal: straight streams do *worst* and curvy meandering streams do *best* — the exact opposite of the old cross-section methods, which loved straight channels and choked on curves.

Below, a sanity check on Commonwealth Stream: predictions closely match the human tracing, elevation's version is a bit cleaner than slope's, and — the recurring theme — small tributaries stay the hardest to catch.

**On the page:** Figure 4.8 is a boxplot grid — each box shows the spread of F1 scores (the line in the middle is the typical score, the box the middle half, whiskers the range) for each stream shape and each input: elevation red, slope green, intensity blue, flow accumulation gray. Shapes: straight (ST), sinuous (SN), meandering (M), multi-threaded (I).

### Page 82
**Gist:** Figure 4.9 is the eyeball test on Commonwealth Stream — and the tiebreaker between the two co-champion inputs: when in doubt, elevation is the calmer, cleaner artist.

Both predictions trace the main channel faithfully — that's the win. The red arrows point at tributary junctions where the slope-based model overpredicts, bleeding "stream" paint beyond the real banks, while the elevation-based model stays tidier.

It also previews the tool she'll trust going forward.

**On the page:** A single figure fills the page: the human-traced ground truth, the elevation-based prediction, the slope-based prediction, and a location map of Commonwealth Stream (which runs from Commonwealth Glacier down to the Ross Sea). Read it by comparing the two predictions against the truth panel.

### Page 83
**Gist:** The Discussion answers the chapter's riddle: adding inputs hurt because intensity and flow accumulation don't contain the defining clue — the inflection point where bank meets ground — and extra input dimensions make a small-data network's job harder.

Intensity and flow accumulation flag where water or ice sits, not where edges are. With a small training set, more knobs plus the same little textbook means more confusion, not more wisdom.

She notes intensity might shine in wetter regions, where water gleams brightly to the laser; this hyper-arid soil is too uniformly dull.

Practical payoff: you only need elevation *or* slope — skip computing the rest, saving time and compute. Coastal streams score best because more frequent flow has carved crisper channels. And the tributary theme returns: gentle bank slopes mean underprediction, with slope-models overpredicting where elevation stays clean.

### Page 84
**Gist:** Why straight streams flop while meanders shine: straight channels here are shallow with mushy, barely-there breaks in slope, while meandering streams have had time to dig distinct banks.

Braided and intersecting streams concentrate extra flow at junctions, deepening their edges.

Then the honest limitations list: the whole method leans on correct human labels; training used only streams with well-established boundaries; rock-layer inflections were never disentangled (no field data); shallow or newly-formed channels may be invisible even to people. But unlike cross-section methods, hers handles tight curves and braids without hand-editing.

Future work: detect *active* streams (water, snow, ice) to track deglaciation, test other regions and algorithms, and use these outlines to fence in change detection — the exact bridge to Chapters 6 and 7.

### Page 85
**Gist:** One page of conclusions, pure recap — nothing new, so use it as a self-quiz.

The method automatically outlines small (10–150 m wide) ephemeral streams across 770 km² after training on just ~1% of the area. Final grades: elevation scores precision 0.94, recall 0.95, F1 0.94; slope scores 0.96 / 0.93 / 0.94.

Meandering streams range F1 0.67–0.98 — the best geometry. Coast beats inland; glacial till beats bedrock. The selling points: cheap, fast, little training data, no cross-sections.

The forward pointer that matters for the rest of your read: this Taylor Valley stream map becomes the seed for charting the entire Dry Valleys river network in Chapter 6, which in turn powers the change-detection work later. Proof of concept: delivered.

## Chapter 5 — Lining Up Satellite Maps with Laser Maps (PDF pp. 86–107)
**The chapter in one breath:** Barlow snaps free satellite elevation maps of Antarctica's Dry Valleys into alignment with a super-accurate laser-scanned map, then measures exactly how wrong the satellite maps still are — and where.

### Page 86
**Gist:** Antarctica must be measured from space, but the Dry Valleys change so slowly that satellite elevation maps have to be unusually precise.

Chapter 5 opens with the core problem: Antarctica is brutally hard to visit, so scientists measure it from space. Satellite DEMs cover huge areas and get updated often — perfect for watching remote places over many years.

- *DEM* — a digital elevation model: a map made of pixels where each pixel stores a ground height instead of a color.

The catch, at the bottom of the page: the McMurdo Dry Valleys change over decades to centuries, so any real change is tiny. The maps must be unusually precise — especially in deep, carved-out stream channels, where satellite maps tend to glitch.

### Page 87
**Gist:** Satellite DEMs fail worst exactly where streams live, and in a barely-changing landscape those errors can masquerade as change that never happened.

To spot sediment moving in a stream, the elevation map's errors must be smaller than the change itself — otherwise noise buries the signal.

Steep slopes and deep channels cause shadows, bad viewing angles, and photo-matching failures that make heights come out wrong. A channel facing the wrong direction can be half-hidden from the satellite.

The killer sentence is the last one: in a landscape that barely changes, errors on *stable* ground can masquerade as change that never happened.

- *co-registration* — carefully aligning the satellite map to a trusted reference before believing anything; the fix previewed here.

### Page 88
**Gist:** The mission: test whether REMA, checked against airborne lidar, is good enough for change detection in Dry Valleys streams — and build the error rulebook Chapter 7 will use.

Even at pixels as small as 2 meters, REMA still carries distortion and bias.

- *lidar* — laser radar: a plane fires laser pulses at the ground and times the bounce-back to measure height very precisely; this is the trusted reference.
- *REMA* — the Reference Elevation Model of Antarctica: a continent-wide DEM built by comparing pairs of satellite photos taken from different angles (the same depth trick your two eyes use); this is the tested map.

The Methods section starts at the bottom: align, find bad terrain, measure leftover error.

### Page 89
**Gist:** The two contestants: dense 2014 NCALM lidar as truth versus 2014 REMA DEMs — and only two satellite datasets (Y14A, Y14B) survived the audition.

Trusted map: the 2014 NCALM lidar survey, with 5–10 laser hits per square meter — very dense. Tested map: 2014 REMA DEMs at 2-meter pixels, built by an algorithm called SETSM from WorldView satellite photo pairs.

Good summer satellite photos of Antarctica are rare, and most candidates got cut — one set had stripes running across it, others had uncorrectable photo-matching glitches. Selection worked like tryouts: eyeball it, align it, check its errors, keep or reject.

Only two survived, nicknamed Y14A and Y14B, from photos taken January 18 and February 14, 2015. (Yes, "2014 season" data dated 2015 — Antarctic summers straddle New Year.)

### Page 90
**Gist:** A dictionary page: six report-card scores used to pre-screen each satellite dataset — grade what each measures, don't memorize the acronyms.

- *MMD and VAMD* — how often the computer successfully matched the same spot in both photos; more matches mean more trustworthy heights, fewer means the software had to guess.
- *VA* — the percentage of the map that actually has data; completeness, not accuracy.
- *AC* — the angle between the two camera views; wider angles usually sharpen height precision, except on very steep terrain where they cause blind spots.
- *AEHA* — the predicted typical height error, in meters.
- *ASE* — how high the sun was; a higher sun means fewer long shadows, and shadows wreck photo matching.

### Page 91
**Gist:** Both surviving datasets scored well on the report cards — yet even after cleanup, the satellite maps still floated several meters off from the laser map.

About 88–91% of each map has valid data, and expected height errors are roughly 0.75 and 1.0 meters. Note the low sun angles — around 19–27 degrees, a permanently low Antarctic sun — which is why shadows matter so much here.

Then the cleanup: unreliable pixels were stenciled out, the maps were converted to a common coordinate system, and heights were shifted to a common "sea level" reference.

The punchline is the last sentence — even after all that, the satellite maps still floated *several meters* off from the laser map. Hence the next section.

**On the page:** Table 5.1 holds the report-card grades; Figure 5.1 maps the coverage — blue is lidar, green is REMA.

### Page 92
**Gist:** The alignment recipe: cut the valley into drainage basins and align each independently in CloudCompare, with strict quality control on the leftover errors.

Because terrain and data quality vary, the valley was cut into separate drainage basins and each piece aligned independently. A rough manual placement came first, then automatic fine-tuning.

- *co-registration* — sliding and tilting one map until it sits perfectly on the other, like lining up two transparency sheets.
- *ICP* — Iterative Closest Point: an algorithm that repeatedly nudges one 3D surface toward the other until they match; the "point-to-plane" flavor matches points to little flat patches of surface, which works even on smooth ground.

Quality control: if a piece's errors weren't centered on zero, spread wider than half a meter, or leaned to one side, it got cut smaller and re-aligned.

### Page 93
**Gist:** Alignment wraps up (pieces subdivided to 0.5–6 km², error defined as laser minus satellite) and a new question begins: WHERE does the satellite go wrong?

Pieces got subdivided down to 0.5–6 square kilometers; steep, shadowy areas were the stubborn ones. The lidar was averaged down to 2-meter pixels to match REMA.

Equation 5.1 defines the error: simply "laser height minus satellite height at the same spot" — positive means the satellite map sits too low.

Then every pixel gets terrain attributes, computed from its 3×3 neighborhood, and Equation 5.2 begins.

- *slope* — steepness in degrees.
- *aspect* — the compass direction the slope faces.
- *exceedance probability* — Equation 5.2's quantity, explained on the next page.

### Page 94
**Gist:** Equation 5.2 is just a failure rate — the fraction of pixels in a terrain bin with errors bigger than a chosen limit — used to decide which terrain gets masked.

Errors get sorted into 5-degree slope bins and 10-degree aspect bins, with half a meter as the "this would matter geomorphically" line. Bins that fail too often will be masked — stenciled out of later analysis.

Extra masks: a 25-meter buffer around glaciers and lakes, plus every pixel that was in shadow when the photo was taken (computed from the sun's actual position at that moment).

Section 5.2.4 then lists the grading stats and asks what *shape* the errors have.

- *NMAD* — a typo-proof average error that ignores wild outlier pixels.

### Page 95
**Gist:** The load-bearing assumption: ground away from streams never changes, so any "difference" there is pure error — a clean yardstick to extend into streams.

Top of the page: error shape. Two "which curve fits better?" scores, K–S and AIC, will judge; DEM errors usually turn out Laplacian.

- *Gaussian* — the classic bell curve.
- *Laplacian* — a spikier shape with a sharper peak and fatter tails, meaning more extreme outliers.

That stable-ground assumption gives a clean error yardstick to extend into streams, where real change and error tangle.

Results begin: slopes steeper than 50°, plus south-to-west-facing slopes (160–290°) even at moderate 15–40° steepness, blow past half-meter errors too often.

### Page 96
**Gist:** The mask function M(A,S) keeps a pixel only if it's NOT very steep (roughly 48°+) and NOT in the moderately steep, south-to-west-facing wedge — everything else gets ignored.

The equation renders as a horrifying wall of curly-brace conditions — do not attempt the algebra. Its entire job is that one sentence; masked pixels get a 0, meaning "ignore this pixel later."

Why that wedge? The low Antarctic sun casts long shadows on south- and west-facing slopes, and shadows break the photo-matching that builds REMA.

**On the page:** Figure 5.2 is the picture that justified the mask — the exceedance plot showing which slope-and-aspect combinations fail the half-meter test most often; the satellite's danger zones, mapped.

### Page 97
**Gist:** The headline numbers: errors are Laplacian, a typical pixel is off by ~25 cm, and streams are the satellite's weak spot — slightly worse and far more lopsided.

After alignment, errors form a sharp spike with fat tails — Laplacian, not a bell curve; the Laplace fit scores about ten times better (K–S values 0.01–0.04 versus 0.10–0.12). That justifies NMAD, the outlier-proof metric, as the yardstick.

The results: average error 0.01 m — essentially zero, no overall tilt — NMAD 0.25 m (a typical pixel off by about a ruler's length), and RMSE 0.46 m.

The kurtosis of 29.5 is the fat-tail smoking gun: a bell curve scores 3, so extreme errors are far more common than "normal."

Streams versus stable ground: 28 cm versus 24 cm NMAD, with streams far more lopsided (skewness −2.04) — deep channels are the satellite's weak spot.

### Page 98
**Gist:** Figure 5.3 is the visual proof for page 97's claims — errors are spiky with fat tails, worst in streams.

Three rows: everything, stream regions only, non-stream regions only. In the histograms the data spike sharply at zero and spill into long tails; the pointy Laplace curve hugs the data, the bell curve doesn't.

The Q–Q plots compare the data's extremes against what a bell curve predicts; when points peel away from the straight line at the ends, the tails are too fat for a bell curve. Here they peel dramatically, worst in the stream row.

**On the page:** A full-page figure. Left column: error histograms with Normal and Laplace fits overlaid. Right column: Q–Q plots. Glance, confirm "spiky with fat tails, streams worst," move on.

### Page 99
**Gist:** Streams err only 4 cm worse than stable ground on typical error, but produce lopsided, extreme mistakes far more often — and Equation 5.3 predicts stream error from stable-ground error.

Stable ground has NMAD 24 cm, streams 28 cm. But the shape columns tell the real story: stream skewness is −2.04 versus −0.40, and kurtosis 40 versus 11.

Equation 5.3 says stream NMAD ≈ 0.97 × stable NMAD + 3 cm — essentially "same error plus a 3 cm stream penalty." Its fit quality, R² = 0.43, means it explains a bit under half the variation from place to place — decent, not great.

Useful trick: measure error where nothing changed, estimate it where things might have.

**On the page:** Table 5.2 is THE table — the stable-ground versus stream error comparison.

### Page 100
**Gist:** Figure 5.4 plots the page-99 regression, and the formula turns out to capture the geography of error — not just an average.

Each dot is one region: stable-ground error across, stream error up. The red line is the formula, with a red band (confidence interval — where the *line itself* probably lives) and a wider blue band (prediction interval — where an individual *new dot* would probably land).

The paragraph below previews Figure 5.5: side-by-side maps of *observed* stream errors versus what the formula *predicts* from stable ground alone. The patterns match reasonably well.

Where it misses most: deeply entrenched channels, the usual troublemakers. The leftover misses (residuals) are small and tucked into supplementary materials.

**On the page:** Figure 5.4 — the regression scatter plot with confidence and prediction bands.

### Page 101
**Gist:** The observed and formula-predicted stream-error maps look alike — and the spatial analysis finds the biggest errors hugging stream boundaries where channel walls are steep.

The point of Figure 5.5 is that the two maps match: the cheap trick (predicting stream error from stable ground) genuinely tracks where errors are big.

Below the figure, the spatial error analysis begins with a clear pattern: the biggest errors hug stream *boundaries*, especially where channel walls are steep and sharply defined. Those edges show much larger errors than the flat ground beside them — even though nothing real should have changed there.

The last line sets up the key idea: errors spike at sharp *breaks* in slope, where flat channel bed meets steep bank.

**On the page:** Figure 5.5 fills the top — two maps of stream-region error, observed above and formula-predicted below, warmer colors meaning more uncertainty.

### Page 102
**Gist:** Three spatial findings: errors are worst at abrupt slope transitions, stream-channel errors are lopsided and extreme-prone, and some error clusters simply cannot be aligned away.

First, errors are worst at abrupt slope transitions — where a flat channel bed meets a steep bank or valley wall — while smooth, low-relief ground shows small, evenly spread errors.

Second, inside stream channels the errors aren't just bigger; they're more lopsided and extreme-prone, matching the fat-tailed statistics from earlier.

Third — and most sobering — some error clusters refused to die: no matter how finely the maps were subdivided and re-aligned, certain patches of complex terrain kept their errors. Translation: there's a floor to how good alignment can get, and Chapter 7's change detection must budget for these stubborn leftovers rather than pretend they're gone.

### Page 103
**Gist:** Figure 5.6 is the error map itself — a where-not-to-trust map showing that disagreement traces stream boundaries and slope breaks rather than scattering randomly.

Errors are not sprinkled randomly. They trace lines — following stream boundaries, channel walls, and sharp slope breaks — while broad flat ground stays quiet.

Remember that both datasets are from the same season, so essentially none of this is real ground change; every colored blotch is measurement disagreement. The tight clustering along channels is exactly why streams got their own error budget in Table 5.2.

**On the page:** A single full-page figure, Figure 5.6 — the spatial distribution of disagreement between the 2014 REMA satellite DEM and the 2014 airborne lidar, laid over the landscape. Read it as the picture version of the last two pages.

### Page 104
**Gist:** The Discussion cashes in the results — masking bad terrain is legitimate, NMAD was the right yardstick, and the satellite's channel-bottom bias fakes deposition.

First: errors are controlled by slope and aspect — steep ground and south-to-west-facing slopes fail most, thanks to bad viewing angles and shadows — so masking those zones before change detection is legitimate, not cherry-picking.

Second: the fat-tailed Laplace shape confirms NMAD was the right yardstick.

Third, the trap to remember: in deep, narrow channels the satellite tends to *overestimate* the channel-bottom height. In a map subtraction that error looks exactly like sediment piling up — fake "deposition" — and in a landscape where real change is millimeters-per-year slow, that fake signal could easily outshout the truth.

The regression discussion starts at the bottom: stream and stable-ground errors scale almost one-to-one.

### Page 105
**Gist:** Three honest caveats: use the formula's cautious upper band, same-year differencing is what makes this an error budget, and lasers versus stereo photos guarantee some error is irremovable.

The stream-error formula only has R² = 0.43 — a moderate fit — so Barlow recommends using its upper 95% band: the cautious, worst-reasonable-case error estimate rather than the best guess.

Why this whole exercise counts as an error budget: both maps come from the same year, so real change should be near zero — any measured "difference" is by definition error (misalignment, lighting, terrain artifacts).

Why perfection is impossible: photos infer height from matching two images — fragile in shadow and on textureless snow — while lidar measures directly. In narrow, steep-banked channels, a tiny sideways mismatch between maps becomes a large fake vertical jump.

### Page 106
**Gist:** Endless subdivision can't fix things — rasterization artifacts and overfitting set a limit — but the chapter's real job is done: REMA is usable, with known, mapped limits.

Why not just keep subdividing until everything aligns? Rasterization — turning scattered measurements into a grid of pixels — smooths sharp edges differently in each dataset, so channel banks get phantom up/down offsets that no amount of aligning removes.

- *overfitting* — bending each tiny piece to match its own noise instead of the true ground; a risk of ever-smaller pieces, which are also brutally slow to align by hand.

Future work: software that automatically slices the terrain along smart boundaries and aligns each piece. That's beyond this chapter, whose real job is done: quantify the leftover uncertainty so Chapter 7 can subtract maps from different decades and know which differences are believable.

### Page 107
**Gist:** The chapter's closing word lands here — pause and lock in the takeaways before Chapter 7 differences maps across decades.

This page holds just the final word of the chapter's closing sentence — "MDVs," the McMurdo Dry Valleys — the tail end of the thought begun on page 106. Take it as the chapter's period.

The takeaways: the satellite maps are trustworthy to about 25 cm on stable ground and about 28 cm inside streams; errors are predictable from steepness and sun direction, so bad terrain can be stenciled out in advance; and deep channels carry a known bias that fakes sediment build-up.

Chapter 7 will difference maps across decades — and thanks to this chapter, it knows the rule: only believe changes clearly bigger than the error budget written here.

## Chapter 6 — Going Big: Mapping Streams in Every Valley (PDF pp. 108–129)
**The chapter in one breath:** Barlow takes the stream-finding computer program she tested in one valley and unleashes it on the entire McMurdo Dry Valleys, producing the first-ever detailed stream outline maps for the whole region at three points in time — 2001, 2014, and 2021–23.

### Page 108
**Gist:** Nobody has stream boundary outlines for all the Dry Valleys at once, and Barlow's fix — previewed here — is deep learning applied to terrain maps, across multiple years.

The Dry Valleys are an Antarctic desert where glaciers melt for a few summer weeks and feed real streams. Existing maps mostly show centerlines, cover limited areas, and are outdated in several valleys.

Barlow needs actual channel outlines because a sediment budget only works if you know exactly where the channels are.

- *stream centerlines* — single lines down the middle of each channel, like drawing a road as one pencil stroke with no width
- *stream boundary polygons* — closed outlines tracing each channel's actual edges
- *sediment budget* — an accounting of how much dirt and gravel moves around over time

### Page 109
**Gist:** Ephemeral desert streams defeat the usual river-finding tricks, so the stated aim is to fine-tune a U-Net to trace stream edges from terrain clues computed from elevation maps.

The usual methods fail here: rainfall-based approaches are useless (the water comes from glaciers, not rain), and measuring channel cross-sections by hand is slow and error-prone over big areas.

The best existing data — centerlines from the LTER research program and Land Information New Zealand — gives location but not width or shape. A handful of hand-drawn outlines exist, but only around one lake basin in Taylor Valley.

The chapter-4 pilot proved the idea; this is the scale-up.

- *ephemeral streams* — channels that only flow occasionally and sit dry most of the year
- *U-Net* — a pattern-learning program that labels every spot on a map

### Page 110
**Gist:** The raw material is four DEMs — two lidar (NASA 2001, NCALM 2014) and two satellite-derived REMA (2014 and 2021–23) — all forced into one map projection and one shared height reference.

REMA is an Antarctica-wide elevation map built by comparing overlapping satellite photos. Everything is put into one projection, and heights are converted to a common reference so the datasets agree on what "sea level" means.

Key detail: the 2014 satellite DEMs were nudged into alignment with the 2014 lidar using chapter 5's co-registration method — so later comparisons are fair.

- *DEMs* — digital elevation models, grids where every square of ground gets a height number, like a 3D map stored as numbers
- *lidar* — an aircraft firing laser pulses at the ground and timing the echoes to measure heights precisely

### Page 111
**Gist:** The three data sources differ in sharpness and coverage, and from each DEM Barlow computes the terrain clues the model will learn from.

The 2014 lidar is the sharpest (heights good to about 7 centimeters); the 2001 lidar is coarser (about 20 centimeters vertically, one point per 2.7 square meters); the satellite DEMs sit at 2-meter resolution. Coverage: 3,296 square kilometers in 2001, 2,420 in 2014.

Each clue reveals something: elevation finds dips, slope finds banks, aspect catches direction flips at channel edges. The lidar is turned into 1-meter DEMs by interpolation.

- *slope* — steepness
- *aspect* — which compass direction a hillside faces
- *curvature* (two kinds) — whether the ground bends like a bowl or a dome; one measured along the flow direction, one across it

**On the page:** Table 6.1 is a spec sheet comparing the three data sources — read it row by row for resolution and coverage.

### Page 112
**Gist:** Two upgrades over the chapter-4 pilot: normalization is now done once per whole landmass (killing seams at tile edges), and the training set roughly triples.

The last terrain clue is flow accumulation, computed with an algorithm that lets flow spread out realistically.

Normalization used to be done separately on each small map tile, which made predictions jump at tile edges — like adjusting brightness on every puzzle piece independently. Now it is done once across each whole landmass, so tiles match at the seams.

Training data: 616 hand-labeled stream spots, many reused across years, giving 1,274 tiles of 300×300 meters — 145 satellite, 601 from 2014 lidar, 528 from 2001 lidar. Chapter 4 had just 217.

- *flow accumulation* — a computed map of where water would pile up if it flowed downhill
- *normalization* — rescaling numbers to a common range so the computer treats all clues fairly

### Page 113
**Gist:** The sampling strategy in one glance — hand-labeled tiles deliberately spread across many valleys and terrain types, so no valley is a total stranger at prediction time.

The scattered markers are the 300×300-meter tiles Barlow hand-labeled — training tiles teach the model, test tiles grade it later. The spread beyond Taylor Valley (the chapter-4 pilot area) is what lets the model generalize.

**On the page:** Figure 6.1 is a region-wide map of every training and testing sample across the Dry Valleys; the black boxes outline the regions whose full finished stream maps appear later in Figure 6.4, and the background is satellite imagery for context.

### Page 114
**Gist:** Lakes and glaciers are labeled on purpose — so the model learns which stream look-alikes to ignore — and all inputs are resampled to a shared 1-meter grid fine enough that narrow channels don't vanish.

Barlow traced stream outlines by eye, using shaded terrain views, slope, and curvature as guides, marking every pixel "stream" or "non-stream." She is honest that hand-labeling has errors, especially where channel edges are faint or rocky ledges mimic banks.

- *resampled* — converted to a shared 1-meter pixel size

**On the page:** Table 6.2 breaks down the samples by valley group and landform (streams, waterbodies, glaciers); counts may not sum to totals because one tile can hold several landform types.

### Page 115
**Gist:** Two things meet here: the 45 held-out test locations, and the model itself — a ResNet18-backed U-Net now run inside ArcGIS Pro's Deep Learning Toolbox instead of the chapter-4 homemade workflow.

The exams: 45 co-registered test locations the model never saw during training. Fifteen sit in Taylor Valley where all three data sources overlap — asking "does the data source matter?" — and thirty are scattered across many valleys in both lidar years, asking "does the model work in places it barely saw?"

The toolbox switch (PyTorch under the hood, GPU-accelerated) meshed better with her preprocessing tools and — importantly — produced smoother, less broken-up stream predictions. Training used labels from both lidar and satellite DEMs, so the model handles both.

- *backbone* — a pre-built pattern-recognizing core the U-Net is wrapped around

### Page 116
**Gist:** The training recipe, spelled out for reproducibility — and held identical across model versions so the upcoming clue-comparison bake-off is fair.

Hardware: one NVIDIA RTX 3090 graphics card. Settings: 300×300-meter tiles, batch size 32, one-fifth of the training data held out to check progress, and a fixed 50 epochs for every version.

The scoring during training is weighted so stream pixels — rare compared to bare ground — still count heavily; otherwise the model could score well by predicting "no stream" everywhere.

The page ends with the grading formulas: precision (Eq. 6.1) and recall (Eq. 6.2), defined in plain words on page 118's note.

- *epochs* — full passes through all training examples
- *data augmentation* — randomly cropping, shifting, and rotating training tiles so the model can't just memorize them

### Page 117
**Gist:** The model runs across the entire region tile by tile, then two cleanup rules discard noise: keep skinny, delete compact.

The F1 formula finishes, then prediction runs everywhere — every valley for both lidar years, selected areas for the satellite data — one 300×300-pixel tile at a time, with 75 pixels of overlap so tile edges get double-checked.

Cleanup rule one: a morphological fill closes small holes (under 50 square meters) inside predicted streams. Rule two: keep a predicted blob only if it covers at least 1,000 square meters *and* its aspect ratio is at least 5. The little equations just estimate length and width by pretending each blob is a rectangle.

Logic: streams are long and skinny; noise is compact.

- *morphological fill* — an automatic paint-bucket step
- *aspect ratio* — length divided by width

### Page 118
**Gist:** In the solo-clue bake-off, aspect (83.6%), elevation (83.0%), and slope (81.2%) win on stream pixels — a channel's two banks face opposite compass directions, a giveaway even in flat terrain.

Every single clue scores above 89% on non-stream pixels (easy — most of the map is bare ground), but stream scores spread widely, 64.9% to 83.6%.

Some clues under-draw streams, others over-draw; the differences set up the combination tests next.

- *precision* — when the model says "stream," how often it's right (how rarely it cries wolf)
- *recall* — how much of the real stream it actually finds
- *F1* — one score balancing both, high only if both are high

### Page 119
**Gist:** Weak solo clues aren't discarded — tested as sidekicks, they help, and combinations beat any solo act, topping out at 85.7% stream F1.

Elevation, slope, and aspect cluster in the low 80s on stream F1, while profile curvature, planform curvature, and flow accumulation sag to about 65%. Their recall values (57–59%) show why: they miss over 40% of real stream pixels.

Composites of elevation + slope + aspect ("ESA") plus one weak clue reach the top stream F1 of 85.7% and non-stream F1 of 95.1%; plain ESA lands right behind at 85.6%. Teamwork wins.

**On the page:** Table 6.3 is the solo-clue report card — six rows, one per terrain clue, with stream and non-stream scores side by side; read the stream F1 column, then check recall to see why the weak clues sag.

### Page 120
**Gist:** Three combos tie at 85.7% stream F1, and Barlow picks ESA plus profile curvature (ESA-Pr) because it has the highest recall and drew the most connected, least fragmented channels.

For faint desert streams, missing a real channel is worse than an occasional false alarm — chapter 7's change measurements depend on continuous outlines.

The bottom rows teach a lesson: piling on *all* the clues (ESA-PrPl-Acc, 84.2%) actually scores lower than simpler mixes. More information isn't automatically better; past a point, extra inputs add redundancy, not skill.

**On the page:** Table 6.4 is the combination report card — the tied combos are ESA plus profile curvature, plus planform curvature, or plus flow accumulation; the bottom rows show the everything-mix scoring lower.

### Page 121
**Gist:** In Taylor Valley, where all three data sources overlap, lasers beat satellite photos — but not by a landslide: stream F1 of 81.7% (2001 lidar), 81.5% (2014 lidar), 78.6% (2014 REMA satellite).

Non-stream scores run 88–90%. The scores dropped a few points from the bake-off's 85.7%; that's normal and honest, because these test tiles were never seen during training.

Where everyone struggles: wide, shallow channels with faint edges and small streams without built-up banks produce broken predictions — with the satellite data stumbling worst there and showing slightly fuzzier edges overall.

**On the page:** Table 6.5 holds the Taylor Valley exam scores, graded against hand-drawn truth at held-out spots.

### Page 122
**Gist:** A satisfying twist — in some regions the model traced streams *better than the human labels did*, catching narrow channels and continuity the annotator missed, so the true scores are probably a touch better than measured.

That means the "ground truth" itself is imperfect. The bottom of the page tees up exam two: the multi-valley test.

**On the page:** Figure 6.2 shows side-by-side map panels comparing predicted stream outlines (2001 lidar, 2014 lidar, 2014 satellite) against hand-drawn boundaries at selected test spots — look for where the colored prediction hugs the manual outline (success) versus fragments or spills over (the faint-edged, shallow channels from the previous page).

### Page 123
**Gist:** The headline of exam two: the model holds roughly 80% stream F1 even in valleys and years it barely trained on — the generalization that justifies trusting the full-region maps.

Across 30 test spots shared by both lidar years, the 2001 NASA data wins on stream precision — 87.1% versus 82.3% — meaning fewer false alarms. The 2014 NCALM data edges ahead on recall — 77.4% versus 76.5%.

Overall stream F1: 81.5% for 2001, 79.8% for 2014. Non-stream scores are excellent for both: 94.9% and 94.2%.

The odd detail — older, blurrier data slightly outscoring newer, sharper data — gets explained in the Discussion.

- *generalization* — the ability to perform on unfamiliar ground

**On the page:** Table 6.6 holds the multi-valley exam scores.

### Page 124
**Gist:** The finished product takes shape — both lidar years cover the northern Dry Valleys, together holding roughly 100 square kilometers of mapped stream area and on the order of 3,700 kilometers of stream length.

The northern valleys covered: Victoria, Barwick, McKelvey, Balham, Bull Pass, Wright Valley, and the maze-like Labyrinth.

**On the page:** Figure 6.3 is the multi-valley version of the earlier comparison figure — paired map panels of predicted outlines from the 2001 NASA and 2014 NCALM lidar over hand-drawn truth, at test regions far from Taylor Valley; check hugging versus fragmenting in unfamiliar valleys, the harder test.

### Page 125
**Gist:** The valley-by-valley tour of coverage, a roll call of famous streams now fully outlined, and two honest caveats about what a mapped outline means.

Coverage: the central valleys — Taylor, Pearce, Beacon — get near-complete coverage in both years (2001 misses only the highest valley walls). In the coastal Denton Hills, 2014 covers Salmon, Garwood, Marshall, Miers, Hidden, and Ward Valleys; 2001 covers south of Garwood and reaches slightly farther inland.

The roll call: the Onyx River (Antarctica's longest), Packard, Victoria, and Bull Streams up north; Canada, Delta, Von Guerard, Lost Seal, and dozens more in Taylor Valley; Hobbs, Adams, and Alph in Denton Hills.

Caveats: the maps include many channels *nobody had documented before* — mostly in the north and Denton Hills — which still need verification, and a mapped outline means a channel groove existed, not that water was flowing.

### Page 126
**Gist:** The money shot — the complete stream boundary map of the McMurdo Dry Valleys, the first wall-to-wall, edge-to-edge stream atlas of the region, in two lidar epochs.

Compare this mentally to what existed before — sparse centerlines in a few valleys — and the leap is obvious. Everything chapter 7 does — measuring erosion and channel change — happens inside these outlines.

**On the page:** Figure 6.4 shows three region panels (Northern Valleys, Taylor Valley, Denton Hills) — the areas marked by black boxes back in Figure 6.1 — with every detected stream outline drawn; zoom your eyes to the valley floors, where the branching, vein-like networks hug valley walls and thread between lakes and glaciers.

### Page 127
**Gist:** The Discussion explains the results: aspect won solo because opposite-facing banks are a built-in giveaway; ESA-Pr earned selection on recall and continuity; and overly complex input mixes hit diminishing returns.

Aspect's advantage works even where the land is nearly flat and other clues fade. Elevation and slope carried similar weight, and merged into ESA they gave the most balanced predictions.

The weak solo clues — curvatures and flow accumulation — turned genuinely useful as sidekicks, supplying complementary information the strong trio lacked. ESA-Pr's highest stream recall is vital for subtle, ephemeral channels, and its better spatial continuity means fewer broken stream segments.

A lesson worth remembering beyond this thesis: extra inputs past a point add redundancy and computing cost, not accuracy. Knowing when to stop adding features is part of the craft.

### Page 128
**Gist:** The best puzzle resolved — blurrier 2001 lidar slightly outscored sharper 2014 lidar because sharpness cuts both ways: the newer data reveals tiny, barely-carved streams that are too thin for the network to hold onto.

The network's early layers shrink the image, and a meter-wide channel simply vanishes when you shrink. Sharper input exposed harder targets, so the score dipped.

The satellite data's fragmented predictions in steep, shadowy terrain are also expected: photo-based elevation maps glitch where shadows and distortion corrupt the images.

The grand totals: roughly 110, 138, and 20 square kilometers of stream area — about 4,550, 5,400, and 1,000 kilometers of length — in the 2001, 2014, and 2022 datasets respectively.

### Page 129
**Gist:** Bottom line — ephemeral stream boundaries can now be mapped at high resolution across whole regions, opening the door to chapter 7's change detection.

The biggest additions beyond re-mapping famous streams in Wright and Taylor Valleys are undocumented channels along valley walls — small tributaries feeding the main channels — which older centerline inventories never captured. These new segments sharpen sediment budgets and flag candidate sites for future field studies.

Honest accounting: agreement with hand-drawn truth is best on well-incised channels and floodplains with clear levees.

Because the method reads only terrain shape from DEMs, it should transfer to other polar, arid, or ephemeral-stream regions — though trees, buildings, or rugged terrain would demand fresh local training data.

- *levees* — raised banks built up along a stream's edges

## Chapter 7 — The Payoff: Watching the Landscape Change (PDF pp. 130–165)
**The chapter in one breath:** Barlow subtracts three elevation maps of the Dry Valleys — 2001, 2014, and 2021–23 — inside 116 computer-mapped stream outlines and finds the streams are moving more dirt than ever, with change actually speeding up.

### Page 130
**Gist:** The payoff chapter combines the neural-network stream outlines (Chapters 4 and 6) and the carefully aligned elevation maps (Chapter 5) to answer how this landscape actually changed over 20 years.

The problem she names up front: scientists have only watched a handful of famous streams, so nobody knows the valley-wide picture.

Her plan: compare laser-scanned elevation maps from 2001 and 2014 with satellite-made ones from 2021–23, measuring change only inside her mapped stream boundaries.

- *fluvial* — anything to do with streams and rivers.
- *geomorphic change* — the shape of the ground changing; dirt washing away here and piling up there.

### Page 131
**Gist:** The specific method is DEM differencing inside her deep-learning stream outlines, computing a dirt budget for each of 116 streams across two time windows.

For each stream she'll compute erosion (dirt lost), deposition (dirt gained), the net balance, and total dirt shuffled, for two windows: 2001–2014 and 2014–2021/23. Then she checks whether change is *accelerating* between the windows.

The coverage is huge: Taylor, Wright, and Victoria Valleys, the Denton Hills (Garwood, Miers, Marshall, Ward), plus Barwick, Hidden Valley, Bull Pass, the Scott Coast, and Pearse. In all: 116 streams, many never monitored by anyone before.

That's the whole point — system-wide answers, not just the famous channels.

- *DEM differencing* — subtracting one elevation map from another; a DEM (digital elevation model) is a grid where every cell stores ground height.

### Page 132
**Gist:** Figure 7.1 is the "you are here" map for the entire chapter — an overview of the McMurdo Dry Valleys with black boxes marking each study region.

Every one of those boxes reappears later as a zoomed-in results map (Figures 7.2, 7.7, 7.9, 7.10, 7.12, 7.13, and 7.16), so it's worth ten seconds now to fix the geography in your head.

Roughly: Victoria and Wright Valleys sit inland to the north, Taylor Valley runs toward the coast in the middle, and the Denton Hills cluster sits to the south. When later pages say "Denton Hills is the hotspot," this is the map that tells you where that is.

**On the page:** A full-page overview map — no numbers, just orientation.

### Page 133
**Gist:** Figure 7.2 plots all 116 mapped streams across the Dry Valleys and Denton Hills, each with a name and an ID number — the cast list before the play.

The master list lives in appendix Table D.1. The text constantly says things like "Ward Stream (ID 84)" or just refers to an ID, and many streams had no official names at all — she invented provisional ones. When a number appears without a name, don't panic; it's just her catalog system.

The sheer density of dots is itself a result: this many streams have never been measured at once before.

**On the page:** A full-page map of every stream; use it (and Table D.1) to decode IDs throughout the chapter.

### Page 134
**Gist:** Methods begin with the data prep: three elevation snapshots — sparse 2001 lidar, dense 2014 lidar, and satellite-built REMA — all gridded at 2 meters.

The 2001 lidar survey was sparse (0.14–0.32 laser points per square meter); 2014 was much denser (2.7 points/m²). The third snapshot is REMA: elevation maps built by computers comparing pairs of satellite photos, the way your two eyes judge depth.

Every map is gridded at 2 meters — one height number per 2 m square.

- *lidar* — a laser scanner flown on an airplane that bounces light off the ground millions of times to measure its shape.

**On the page:** Figure 7.3 is the whole chapter drawn as a flowchart — stream outlines from Chapter 6 + aligned elevation maps → subtract → dirt budget per stream. Spend 30 seconds on it; the next sections just explain its boxes.

### Page 135
**Gist:** Two honest housekeeping notes: the third snapshot had to widen from 2021 alone to 2021–2023, and all three maps are forced to speak the same spatial language.

The confession: she wanted the third snapshot to be just the 2021 melt season, but those satellite maps alone had holes and errors, so she widened the window. That's why "2021-23" appears everywhere.

All three maps get the same map coordinates (a system called EPSG:3294) and the same definition of "zero elevation" (the EGM2008 *geoid* — a scientific stand-in for sea level). The satellite maps were already snapped into alignment with the 2014 lidar back in Chapter 5, so that hard work carries over.

Recap: the stream outlines come from her U-Net, already accuracy-checked in Chapter 6.

- *geoid* — a scientific stand-in for sea level (here, EGM2008).
- *U-Net* — a neural network that colors in stream pixels using elevation, slope, aspect, and curvature.

### Page 136
**Gist:** Before believing any change, she asks how wobbly her ruler is — and gives each stream its own custom noise threshold.

Two elevation maps disagree a little even where nothing moved — that's noise, and it's not the same everywhere.

Method: look at "stable" ground 10–300 m outside the stream outline (staying 75 m clear of lakes and glaciers, hand-removing spots with obvious real change), measure how much the maps disagree there, and set a detection threshold.

Then change detection starts: outlines from both epochs merged; 116 streams for 2001–2014 (50 named, 66 unnamed).

- *NMAD* — a sturdy statistic for typical wobble that ignores freak outliers.
- *Level of Detection (LOD95)* — any change smaller than about twice the wobble is thrown out as probably noise.

### Page 137
**Gist:** Only 38 Taylor Valley streams make the 2014–2021/23 comparison (satellite coverage was limited to there), and the first key formula — the gross rate — is defined.

Unnamed channels get provisional names tagged "(u)" plus ID numbers (Table D.1). She admits openly that splitting branching drainage networks into separate "streams" took human judgment — she eyeballed geomorphic continuity and flow connections.

The math: after masking out anything below the noise threshold (LOD95 = 1.96 × NMAD), she computes the gross rate. The equation looks scary; the sentence below is all it says.

- *gross rate* — add up the absolute elevation change in every grid cell, multiply by cell area, divide by the years elapsed: total dirt shuffled per year, ignoring direction. A stream can move mountains of sediment and still break even.

### Page 138
**Gist:** The second key formula is the net rate — same sum but keeping the signs — plus a per-area decade scaling and the acceleration metric.

She also divides by each stream's active channel area and scales to a 10-year period, because yearly per-square-meter changes here are tiny; a decade makes the numbers readable.

Roadmap for the results: noise stats, then the 2001–2014 budgets, then 2014–2021/23, then acceleration where all three maps overlap.

- *net rate* — the gross sum with signs kept, so ups and downs cancel; positive means the stream gained dirt overall, negative means it lost.
- *aggradation* — sediment piling up.
- *incision* — a stream cutting down, losing dirt.
- *acceleration* — take a stream's rate in window one and window two, subtract, divide by the years between window midpoints (units m³/yr²): is the dirt-moving itself speeding up?

### Page 139
**Gist:** The headline: Ward Stream (ID 84) in the Denton Hills moved a gross 78,713 m³ of dirt per year — about thirty Olympic pools annually — and almost all of it was loss.

First, the ruler's report card. Laser-vs-laser (2001–2014): typical wobble of 0.07–0.46 m per stream, so changes had to beat 0.15–0.92 m to count. Satellite-vs-laser: wobble 0.19–0.53 m, thresholds 0.37–1.04 m — roughly twice as blind, so the recent era's numbers are automatically more cautious.

Ward's split: 77,598 m³/yr eroded versus just 1,116 deposited, net −76,482 m³/yr. Garwood, Marshall, and other Denton Hills streams follow as the busiest.

Meanwhile Onyx, Murray, Kite, Thomas, Wales, Lizotte, and Brownworth were dirt gainers.

**On the page:** One number list here is slightly garbled — trust appendix Table D.2.

### Page 140
**Gist:** The 2001–2014 headline wrap-up: Onyx tops the dirt gainers at +13,418 m³/yr, while some big movers ended up near balance.

Murray, Kite, Thomas, Wales, Lizotte, and Brownworth each gained a few thousand m³/yr. Garwood and Commonwealth shuffled lots of dirt but ended up near balance — huge gross, small net.

Every stream's full numbers live in appendix Table D.2.

**On the page:** Figure 7.4 shows actual change maps for the wildest Denton Hills streams, colored by elevation change per year. Read them like a bruise map — one color means the ground dropped (erosion), the other means it rose (deposition). Notice how the change hugs the channel: it's the stream doing this, not the whole hillside.

### Page 141
**Gist:** Figure 7.5 charts every stream's erosion, deposition, and net sediment flux for 2001–2014, ranked by total activity — and Ward's giant erosion bar dwarfs everything.

How to read it: each stream gets bars for dirt lost, dirt gained, and the balance; positive net means gaining, negative means losing. The top 10 streams sit in the upper panel, ranks 11–50 in the lower.

Notice the shape of each stream's story: Ward is all one-way loss, while others have tall bars in both directions that nearly cancel. The scale drop between panels shows how top-heavy activity is.

**On the page:** The upper panel is the money panel (Ward, then Garwood and Marshall). Don't try to memorize the lower panel; it exists so you can look up any particular stream later.

### Page 142
**Gist:** Figure 7.6 covers the quieter half of the inventory (ranks 51–90 and 91–118), and its tiny axis numbers prove activity is extremely top-heavy.

Most of these streams move hundreds of cubic meters a year, not tens of thousands — a handful of streams (mostly Denton Hills) do most of the landscape's work while the long tail barely budges.

**On the page:** These are reference charts, not reading material. If a specific small stream ever comes up, this is where you find its bars; otherwise, turn the page.

### Page 143
**Gist:** Where is the action? Gross activity concentrates in valley bottoms and near the coast — warm, wet, coastal, low ground is busy; cold, dry, inland is calm.

Denton Hills wins overall — Ward, Garwood, Marshall, and Lower Miers rework the most sediment.

Coastal Taylor Valley streams mostly shuffle a modest 1,000–3,000 m³/yr, except Commonwealth (9,843) and Wales (5,444) — and their nets differ tellingly: Commonwealth loses (−2,577) while Wales gains (+3,043).

Upper and central Taylor Valley are quiet (0–2,000 m³/yr) apart from Lawson Creek (6,296) and Mason (5,174).

In Victoria and Wright Valleys, streams on the valley walls stay under 4,000 m³/yr, but Onyx — Antarctica's longest river — hits 26,625 and Kite 13,369, with Murray and Deshler elevated too.

### Page 144
**Gist:** Figure 7.7 is the "where is it busy?" map of 2001–2014 gross activity, while the prose starts sorting net balance by geography.

Taylor Valley streams near the coast mostly gain dirt; streams draining toward Lake Fryxell (mid-valley) run about even; and the Lake Bonney region (further inland) is a patchwork — stronger erosion along the southern cliffs, more variable behavior toward the north.

Hold that southern-cliff thread: it comes back in the Discussion with a neat explanation involving sunshine.

Remember the sign convention everywhere: positive = deposition (ground rose), negative = erosion (ground fell).

**On the page:** Figure 7.7 colors each stream by total dirt reworked per year — Denton Hills should glow.

### Page 145
**Gist:** The regional net-balance scorecard: Denton Hills streams are predominantly erosional — they're bleeding sediment.

Victoria and Barwick Valleys mostly gain, with Packard Stream the lone slight loser.

In Wright Valley and Bull Pass, dirt piles up along the valley floor toward the coast while streams on the southern valley walls tend to erode — that south-wall pattern again.

**On the page:** Figure 7.8 shows every stream colored by net change — positive (deposition) one way, negative (erosion) the other. Compare it mentally with Figure 7.7 on the previous page: a stream can be bright on the "busy" map but neutral here — busy but balanced — while Ward is extreme on both.

### Page 146
**Gist:** A fairness correction — dividing each stream's change by its channel area and scaling to a decade — still leaves Denton Hills dominant, and a tiny newcomer pops out.

Big streams move more dirt just by being big; the corrected units are "meters of thickness change per decade," so small streams get a fair shot.

Result: Ward is still the champion per square meter; Garwood and Marshall stay elevated; Lower Miers is moderate. The newcomer: a tiny stream draining Joyce Glacier's eastern flank into Colleen Lake — "Joyce (u)," ID 50 — is fiercely active for its size.

Elsewhere: Wright Valley is moderate, led by Meserve Central and Bartley East; Victoria Valley is low-to-moderate with Packard busiest; central Taylor runs moderate-to-high along Mason, Lawson East, and the Lacroix Glacier flank; coastal Taylor stays mild except Commonwealth and the Bowles–Maria–Green complex.

### Page 147
**Gist:** Ward takes a double crown — it moves the most dirt in absolute terms and loses the most per square meter.

Below the figure, the prose pivots to normalized *net* change: per square meter, the strongest sediment-loss signals are again in Denton Hills, with Ward and Marshall Streams recording the highest normalized erosion rates of all.

Whatever is driving change here, Denton Hills is where it bites hardest.

**On the page:** Figure 7.9 is the normalized gross map — every stream colored by decadal thickness change per unit area, the "pound-for-pound" activity rankings. It's the fair-fight version of Figure 7.7: tiny hyperactive streams like Joyce (u) finally show up next to the giants, and Denton Hills should still read hottest.

### Page 148
**Gist:** The normalized-net tour continues: strong per-area erosion in Denton Hills, a zoned patchwork in Taylor Valley, and a short list of exceptions in Wright and Victoria.

In Denton Hills, the Joyce Glacier–Lake Colleen stream, Garwood, and Colleen all show strong erosion; Hidden Valley Stream erodes too but more moderately.

Taylor Valley's zones: streams around Lake Fryxell sit near equilibrium (except Canada Stream, mildly gaining); coastal segments mostly gain, though Commonwealth and Weatherwax show moderate net erosion; and the central-to-upper valley trends erosional, especially along the southern valley walls — that recurring south-wall signal.

Wright and Victoria Valleys are mostly balanced or gently gaining, but a specific short list bucks the trend with marked per-area erosion: Bartley East and West, Meserve West and Central, and Packard. Keep those names loosely in mind; the Discussion will explain them with climate zones and buried ice.

### Page 149
**Gist:** Figure 7.10 — normalized net change in meters per decade — is arguably the chapter's best single picture: per square meter of streambed, is this place gaining or losing ground, and how fast?

Positive values (one color) mean deposition wins; negative (the other) mean erosion wins.

Because it's area-normalized, a small stream in an alarming color genuinely is changing fast; size can't hide anything here.

**On the page:** Find the deep-erosion colors clustered in Denton Hills (Ward and Marshall darkest), then trace Taylor Valley's zones — gaining near the coast, near-even around Lake Fryxell, losing along the southern walls inland — and note how quiet Wright and Victoria look apart from a few marked exceptions.

### Page 150
**Gist:** The recent era (2014–2021/23, 38 Taylor Valley streams only) echoes the earlier window: deposition keeps dominating this valley, with new characters stepping forward.

The restriction exists because only Taylor Valley had good enough satellite coverage. The verdict: moderate-to-high activity, most streams gaining dirt.

An unnamed stream in Quinn Valley (ID 93) is among the most active: gross flux 11,997.8 m³/yr, with 7,327.6 deposited against 4,670.2 eroded, for a net gain of 2,657.4 m³/yr.

On the coast, an unnamed stream near Hjorth Hill (ID 57) bucks the trend as a net loser: about 413 m³/yr of net erosion on a gross of 1,707.

Remember the caveat from page 139: this satellite-based comparison can't see changes under roughly 0.4–1 m, so these totals are inherently understated.

### Page 151
**Gist:** Figure 7.11 shows per-year elevation-change maps for the most active streams of the 2014–2021/23 window — the recent-era twin of Figure 7.4.

Read them the same way: color shows how fast the ground rose or fell at each 2-meter cell, and the action traces the channels.

Some of the speckle you'll see is exactly the noise her per-stream thresholds were built to screen out of the actual volume numbers.

**On the page:** Two things to look for. First, the balance of colors: in this era most Taylor Valley streams should show more rise than fall — deposition winning. Second, the texture: satellite-derived REMA maps are noisier than lidar, so expect more speckle than in Figure 7.4.

### Page 152
**Gist:** Figure 7.12 charts erosion, deposition, and net flux for all 38 Taylor Valley streams in 2014–2022/23 — and most bars point toward gain: this valley is still accumulating sediment.

It's the recent-era version of Figures 7.5–7.6: positive net bars mean the stream gained dirt; negative means it lost.

**On the page:** Scan for the shapes the next page will narrate: McClintock Point with a huge deposition bar and barely any erosion; the two Quinn gullies with tall bars in both directions (very busy, still net gainers); Commonwealth's upper reach with almost perfectly matched bars (busy but balanced); and the rare streams whose net bar dips negative, like the Hjorth Hill W1 channel.

### Page 153
**Gist:** The recent era's headliners in numbers: McClintock Point (ID 64) is the deposition champion — net +9,403 m³/yr, the region's biggest gain.

McClintock's split: 10,452 m³/yr piled up against just 1,049 eroded.

Two adjacent western tributaries are the busiest overall. Quinn Gully West (ID 53) deposited 9,050 and eroded 2,840, netting +6,210 on a gross of 11,890. Neighboring Quinn Valley (ID 93) posted the group's largest gross flux, 11,998 m³/yr, but kept less (+2,657) because its erosion was higher (4,670).

The upper mapped stretch of Commonwealth Stream (ID 37, glacier side only) is the balance case: 3,443 deposited versus 3,842 eroded, net just −399 — furiously shuffling dirt while barely changing overall.

Note how gross and net tell different stories about the same stream.

### Page 154
**Gist:** An essentially blank layout spacer — just the page number — clearing room for the two-panel Figure 7.13 spread, and a natural spot to catch your breath before the chapter's last act.

Quick recap of where we stand: 2001–2014 showed Denton Hills hemorrhaging sediment and coastal Taylor Valley collecting it; 2014–2021/23 (Taylor only) showed deposition still winning, with McClintock Point and the Quinn gullies as new hotspots.

One question remains, and it's the sharpest one: not "is the landscape changing?" but "is the change itself speeding up?" That's what the acceleration section, starting on page 156, answers.

### Page 155
**Gist:** Figure 7.13 stacks two Taylor Valley maps for 2014–2022/23 — gross sediment flux on top (how busy each stream is, in m³/yr), net flux on the bottom (which way the balance tips).

It's the recent-era counterpart of Figures 7.7 and 7.8, just zoomed to the one valley with satellite coverage.

**On the page:** Find a stream on the top map to see how much dirt it shuffles, then check the same spot below to see whether it's gaining or losing. McClintock Point and the Quinn gullies should stand out on both. Notice the bottom map leans toward the depositional color across most of the valley — the visual version of "Taylor Valley is still collecting sediment."

### Page 156
**Gist:** The chapter's sharpest question — is change speeding up? — gets a yes: where all three snapshots overlap (Taylor Valley), the trend is acceleration.

The fastest: McClintock Point (ID 64), Quinn Valley (ID 93), and Quinn West (ID 53), with gross accelerations of 798, 816, and 809 m³/yr² and net accelerations of +777, +33, and +374 respectively.

Several Hjorth Hill tributaries (IDs 67, 69, and 63) each accelerated past +140 m³/yr² of extra deposition.

In plain terms: the busiest streams of the recent era are also the ones ramping up fastest.

- *geomorphic acceleration* — not water flowing faster; the yearly amount of dirt being moved is itself growing, like a savings account whose deposits keep getting bigger.

### Page 157
**Gist:** Figure 7.14 maps gross geomorphic acceleration for streams spanning 2001 to 2021–23 — the picture behind the chapter's boldest claim: the landscape isn't just changing, it's changing faster than it used to.

Each stream segment is colored by how much its total dirt-moving rate changed between the two eras, in m³/yr² — positive means it got busier, negative means it calmed down.

Reading tip: the map covers only the slices of Taylor Valley where all three elevation snapshots overlap, so don't read gaps as "no change" — they're "couldn't measure."

**On the page:** The accelerating colors dominate; McClintock Point and the Quinn gullies should be the standouts, glowing near the coast.

### Page 158
**Gist:** Figure 7.15, the companion map, shows *net* acceleration for 2001–2021/23 — not "did the stream get busier?" but "is its balance tipping harder toward gaining or losing dirt?"

Positive colors mean deposition is strengthening year over year; negative means erosion is strengthening.

Expect McClintock Point to blaze positive (its +777 m³/yr² was the region's biggest depositional ramp-up), the Hjorth Hill tributaries to show a mix — some accelerating toward gain, a few toward loss — and most other streams to sit in muted, near-zero colors.

**On the page:** Compare mentally with Figure 7.14. Quinn Valley is a good example of the difference: huge on the gross map (816) but almost neutral here (+33) — much busier, but its gains and losses grew nearly in step.

### Page 159
**Gist:** The other side of the ledger: a smaller set of streams is accelerating toward erosion — but the acceleration story is concentrated in hotspots, not a uniform valley-wide surge.

Strongest is Lake Joyce 1 (ID 101) at −371 m³/yr², then Hjorth Hill E5 (ID 68) at −158, followed by Hjorth Hill Cent 2 (ID 65) and Hjorth Hill W 6 (ID 75).

Interesting detail: the Hjorth Hill cluster appears on both lists — some of its tributaries are ramping up deposition while near-neighbors ramp up erosion, a reminder that this landscape changes on a very local scale.

Keep proportion: the large majority of streams are near-balanced, with net accelerations under 30 m³/yr² — Canada Stream, Scar Peak, Doran, and Mummy–Delfie among them.

### Page 160
**Gist:** Another essentially blank spacer page — just the page number — and a good moment to lock in the acceleration section's shape before the Discussion reinterprets everything.

The shape: where all three elevation snapshots overlap, most streams are speeding up or holding steady; a hotspot handful (McClintock Point, the Quinn gullies) are ramping up dramatically; a small club (Lake Joyce 1, some Hjorth Hill tributaries) is accelerating toward erosion; and the majority sit near balance.

Nothing is broadly slowing down — that's the detail the Discussion will lean on when it argues the pattern points to increasing melt rather than a landscape settling back to sleep.

### Page 161
**Gist:** The last figure, 7.16, stacks two Taylor Valley maps of sediment-flux acceleration for 2001–2022 — gross on top, net on the bottom — the summary picture of the chapter's boldest finding.

It's the acceleration twin of Figure 7.13: the top panel asks whether each stream is getting busier or quieter; the bottom asks whether its balance is tipping harder toward gain or loss.

Remember the coverage caveat: only stream sections where all three snapshots overlap appear at all.

**On the page:** Use the two-panel trick again — locate a stream up top to see if its total activity is ramping, then check below for the direction of that ramp. Coastal hotspots — McClintock Point, the Quinn gullies, the Hjorth Hill cluster — should dominate both panels, while most inland segments sit near zero.

### Page 162
**Gist:** The Discussion opens with the big claim: change is widespread across the Dry Valleys and Denton Hills — striking for a region long described as relatively stable — and the pattern fits increasing melt and destabilizing permafrost.

Why is Denton Hills the hotspot? Location and ingredients: it sits in the Coastal Thaw Zone, the warmest climate belt, atop drift deposits stuffed with buried ice. Streams flowing over that ice trigger thermokarst, so banks cave in and huge volumes of sediment move.

A key honest caveat about coastal Taylor Valley's depositional signal: the 2001 map missed upstream reaches, so the erosion that fed all that coastal deposition is undercounted — the gross rates there are likely underestimates.

- *permafrost* — ground that normally stays frozen year-round.
- *thermokarst* — ground collapsing as its internal ice melts.

### Page 163
**Gist:** The geography gets its explanations: Taylor Valley is a glacier-to-sea sediment conveyor with a warm wet coast, sun-facing southern walls slump most, and Wright and Victoria stay calm in the colder Inland Mixed Zone.

Taylor Valley: its streams form a conveyor belt from alpine glaciers to lakes and the Ross Sea, so sediment eroded up-valley gets delivered and dropped on the flat coast. Its coastal zone also has warm summers (average above −5 °C), thawing permafrost into wet, loose, easily moved material.

Central Taylor shifts toward balance and local erosion because the ground there is drier and ice-cemented — less to melt.

The recurring south-wall mystery gets solved: in the Southern Hemisphere, southern valley walls face north, toward the equator, so they catch more sun, melt more snow, stay wetter, and slump more.

Wright and Victoria stay calm because they sit in the colder, drier Inland Mixed Zone — Victoria especially, with the most dry-frozen permafrost and weak stream connectivity.

### Page 164
**Gist:** Findings wrap up — Denton Hills stays the most active region even after the per-area correction — and the honest accounting of REMA's possible errors begins.

In the recent Taylor-only window, coastal tributaries show moderate-to-high flux and net deposition, and where all three epochs overlap, acceleration is mostly positive or near zero — more melt-driven sediment movement, not less.

What could be wrong with REMA, the satellite-derived maps: they're noisier than lidar, especially on steep slopes and low-texture ground; tiny leftover misalignments on steep terrain can fake sideways erosion or deposition; and awkward satellite viewing angles can make channel bottoms look filled in when they aren't.

Her per-stream noise thresholds screen out much of this — but raising thresholds also means the estimates get more conservative.

### Page 165
**Gist:** The final caveats all lean one direction: her numbers are a floor, not a ceiling — the true change is likely bigger.

The two comparison windows aren't perfectly matched: 2001–2014 is longer, and the 2021–23 window mixes multiple years, so an unusually melty year could color the results.

Acceleration was only computed on overlapping stream segments, not whole networks. And the "stable" ground used to calibrate the noise thresholds may itself have shifted subtly over decades — which pushes the thresholds higher and hides real change.

Future work: keep monitoring (especially Denton Hills), use consistent high-resolution sensors, automate the satellite-map alignment, build error models that understand channel depth and terrain, and connect these dirt budgets to the melt and climate drivers behind them.

## Chapter 8 — Wrapping Up & What's Next (PDF pp. 166–171)
**The chapter in one breath:** Barlow sums up what she built — a mostly-automatic way to find dry stream channels and spot where Antarctic valleys are changing — then lists four ideas for what should come next and why any of it matters for the rest of the planet.

### Page 166
**Gist:** The dissertation delivered a semi-automated method that maps stream channels across entire Antarctic valleys and tracks their change — producing the most complete stream map of the Dry Valleys yet.

The victory lap begins. The method maps whole valleys and produced the most complete Dry Valleys stream map to date, including streams nobody had studied before.

The clever trick: it finds streams using only the *shape* of the ground from 3D elevation maps, not color photos. That matters because these streams are usually bone dry — there's no blue water to spot.

And where older studies looked at one channel at a time, hers scans whole regions at once, pointing scientists toward the places changing fastest.

- *semi-automated* — a computer does most of the work, with a human checking it

### Page 167
**Gist:** The Future Work section opens with a four-item to-do list, starting with extending the long-term monitoring of stream change.

First, the payoff sentence from the last page finishes: watching these "stable" valleys matters more and more as climate change speeds up.

Then the four-item to-do list for whoever picks up this research next: (1) keep monitoring stream change over the long haul, (2) teach the model to find meltwater and glacier surface features, (3) connect the change measurements to climate data for prediction, and (4) make the model itself better with more varied training examples.

The page then starts on item 1: her study compared the land at three moments (2001, 2014, 2021–23), and the satellite-made elevation maps (REMA) proved trustworthy enough to extend this watch to more valleys.

### Page 168
**Gist:** Scaling up the monitoring means heavy data-preparation grunt work, with the fast-changing Denton Hills named as the first priority.

Extending the monitoring requires co-registering, cleaning, and error-checking the satellite elevation data. Do that across neighboring valleys and you can compare which areas are speeding up.

She names a priority: the Denton Hills, where change looks most pronounced — study there first.

She also pitches buying a drone (UAV) to scan fragile, restricted zones without humans trampling them, recommends measuring change on multiple clocks (seasonal, yearly, decadal), and suggests teaching a computer to automate the tedious map-alignment work itself.

- *co-registering* — lining up two maps of the same place so they match exactly; otherwise a tiny offset looks like fake change

### Page 169
**Gist:** The same tool that finds dry streams could track meltwater — and in early tests it spontaneously started detecting glacier surface features nobody trained it for.

Future Work item 2 hides a fun surprise. The tool could track pooling meltwater — new ponds signal thawing frozen ground.

The bonus: in early tests with barely any glacier training examples, the model started picking out supraglacial streams and crevasses on its own — a skill nobody trained it for.

That matters because meltwater streams speed up glacier melt: the water carries heat down into cracks and pries them open deeper, destabilizing the ice from inside. Automatically mapping these features could sharpen forecasts of glacier melt and ice sheet stability.

- *supraglacial streams* — streams flowing on *top* of glaciers
- *crevasses* — deep cracks in the ice
- *hydrofracturing* — meltwater carrying heat into cracks and prying them open deeper

### Page 170
**Gist:** Feeding the change measurements into forecasting models could predict stream behavior — and stream behavior reveals hidden melt, permafrost, and ecological processes.

Future Work item 3: turn maps into predictions. Feed her change measurements into forecasting models and you could flag stream sections about to jump their channels, dig deeper, widen, or erode.

Stream behavior is also a spy report on hidden processes: more sediment moving can mean permafrost is destabilizing, and busier streams hint that glaciers are melting from within — meltwater sneaks down through cracks and melts ice where no camera can see.

There's an ecology payoff too: these streams feed the valleys' microbial life, the only "wildlife" around, so plugging this data into water and nutrient models could guide which fragile spots to protect first.

- *avulsion* — a stream jumping its channel
- *permafrost* — permanently frozen ground

**On the page:** Read this page as a chain: stream changes → hidden melt clues → better forecasts → smarter conservation.

### Page 171
**Gist:** To become a worldwide stream-finder, the Antarctic-trained model needs more varied training examples and more sensor types — then the big-picture reflections begin.

Future Work item 4: the model learned mostly from Antarctic examples, so it's an Antarctic specialist. A worldwide stream-finder needs a more varied education — training examples from tropical, temperate, steep, and flat places, from tiny creeks to big rivers.

It would also help to mix in more data types — radar, thermal images, hyperspectral cameras — so where one sensor gets confused, another fills the gap.

Then the big-picture close starts: the Dry Valleys are famous for *never changing*, so measurable change even there is powerful evidence — for the public and policymakers — that climate change reaches everywhere.

- *thermal images* — heat-sensing images
- *hyperspectral cameras* — cameras that see far more colors than our eyes

### Page 172
**Gist:** The dissertation's legacy statement: this research lays the foundation for large-scale, automated monitoring of polar stream landscapes.

Watching odd, remote places like the Dry Valleys will only get more important as the climate warms. The sheer scale of the job means automation isn't optional: computers must do the mapping and modeling so scientists can find at-risk regions, judge ecological impacts, and game out best- and worst-case futures.

Her closing claim: this research lays the foundation for large-scale monitoring of polar stream landscapes. In other words, she's not just finishing a study — she's starting a watch, and she wants others to keep it as the poles keep responding to a changing climate.

### Pages 173–198
**Gist:** The References list — every paper, dataset, and report cited in the dissertation, alphabetical by author.

No new science here — it's the bibliography.

**On the page:** Flip here when a name in the text catches your eye (like the crevasse or meltwater studies cited on pages 169–170) and you want to find the original paper, or when you want to see whose shoulders this work stands on.

### Pages 199–200
**Gist:** Appendix listing which specific REMA satellite image strips went into the analysis and the quality of each — the map's ingredient label.

REMA is the satellite-built 3D elevation map of Antarctica used throughout this work. These pages list the specific satellite image strips used and how good each one is.

**On the page:** Flip here if you ever wonder "which satellite data, exactly, and can I trust it?"

### Pages 201–210
**Gist:** Appendix holding the full co-registration error numbers behind chapter 5 — how precisely each map pair was aligned.

- *co-registration* — lining up two maps of the same terrain so they match exactly; get it slightly wrong and stable ground looks like it moved

**On the page:** Flip here to see how much wiggle room sits behind any reported change.

### Pages 211–213
**Gist:** Appendix tables inventorying the stream boundary dataset behind chapter 6's maps, stream by stream.

Chapter 6 presented the maps of detected stream channels; these tables are the inventory behind them, listing what the dataset contains for each stream.

**On the page:** Flip here if you want the roster — which streams were mapped and what's recorded for each — rather than the picture-book version in the chapter.

### Pages 214–240
**Gist:** Appendix with the raw per-stream change-detection numbers behind chapter 7, for each site and time period.

Chapter 7 told the story of where the land eroded (lost material) and where it deposited (gained material); this long appendix is the raw ledger behind it.

**On the page:** Flip here when you want the exact figures behind a claim in chapter 7, like just how much a particular stream reshaped itself.

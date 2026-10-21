# Do steady bright targets repeat across tracks more than chance? 9t

**Date:** 2026-10-21. **Status:** done. Yes for pairs that include track 162. Weak for tracks 026 and 090.
**Follows:** `docs/iterations/nisar_wells_steel_pads_slopes_9t.md`, section 4.

## Question
The bright-target map has no region of interest. Which of its points are not speckle?

## Method
- Lidar-placed stack (`--slc`): 8, 11 and 14 dates on tracks 026, 090, 162. Same rule as before (D_A < 0.25, 6 dB above 250 m median).
- One point per connected group per track: 769, 1,541 and 176 points.
- Each track has its own dates and look. A point on two tracks within 15 m is a coincidence.
- Null: shift one track's points by a random vector, wrapped at the tile edge, and recount. 10,000 shifts. This keeps point count and density and breaks real alignment.

## Results
| Pair | Coincidences | Chance (mean) | Ratio | p |
|---|---|---|---|---|
| 026 and 090 (descending, ascending) | 46 | 33.0 | 1.4 | 0.032 |
| 026 and 162 (descending, ascending) | 23 | 3.8 | 6.0 | 0.0001 |
| 090 and 162 (both ascending) | 63 | 7.6 | 8.3 | 0.0001 |

- p floor is 0.0001. No shift out of 10,000 matched the 026-162 or 090-162 count.
- About 86 coincidences involve track 162. About 11 are expected by chance. Roughly 87% of them are not chance.
- Tracks 026 and 090 mostly overlap by chance, because they have many points.

## Limits
- The null removes alignment by chance. It does not remove shared real structure such as roads. A repeat means "a stable bright object", not steel.
- 090 and 162 share a look direction. Agreement could include geometry effects that two different looks would not share. The 026-162 pair has different looks and still shows 6 times chance.
- The earlier context check showed these targets sit on roads, pads and wells at about chance. What they are is unknown.

## Reproduce
`python notebooks/wellsight_v2/s5_eval/_nisar_bright_coincidence_9t.py --slc`

Outputs in `data/9t/results/nisar/`: `nisar_bright_coincidence_by_track_pair_9t.csv`, `nisar_bright_coincidence_summary_9t.json`.

# Early PA / Appalachian Oil-Well Parameters → LiDAR Detection Priors

Quantitative, physically-measurable parameters mined from two historical books the
user supplied, scoped to what could leave a **1 m / 0.5 m LiDAR terrain signature**
in western Pennsylvania. Source-faithful: only values actually stated are listed;
gaps are flagged rather than filled from outside knowledge.

**Sources**
- **[W]** Williamson & Daum, *The American Petroleum Industry: The Age of
  Illumination, 1859–1899* (`docs/papers/annas-arch-784c7616f171.pdf`, 888 pp;
  Internet Archive OCR text layer mined). National scope but early chapters are the
  PA Oil Region (Oil Creek, Pithole, Venango/Warren Co.).
- **[A]** Philip W. Ross, *Allegheny Oil: The Historic Petroleum Industry on the
  Allegheny National Forest* (USDA Forest Service, 1996;
  `docs/papers/Allegheny-Oil.pdf`, 69 pp, **image-only scan**, read visually). The
  on-region source — Warren/McKean/Elk/Forest counties, our exact terrain.

## Parameter table

| Parameter | Value / Range | Era | Source | Detectability |
|---|---|---|---|---|
| Well density (crowded) | 150 wells on "a few acres"; wells "a few feet apart" | 1860s PA | [W] | clustering prior |
| Well density | 3–5 wells/acre → mean spacing **~20–28 m** | 1867 PA | [W] | clustering prior |
| Lease/drilling unit | 1–8 acre early → **½ acre** (≤3 wells) → 1/16, 1/32 acre lots | 1859→mid-1860s PA | [W] | ~45 m lot pitch |
| Earthen catch-pit / reservoir | **"several feet deep"** (~0.6–1.5 m), 6-ft plank walls | 1861–65 PA | [W] | **depression prior** (0.5 m DEM) |
| Slush/mud/brine pit L×W×D | **NOT FOUND** in either source | — | — | (source elsewhere: PA DEP) |
| Derrick base (Drake) | **12 ft (~3.7 m) square**, 30-ft timbers, 3-ft sq top | 1859 PA | [W] | ~4 m square pad scar |
| Standard derrick height | not numerically stated (gusher reach 80 ft implies ~20 m+) | 1880 PA | [W],[A] | canopy-gap only |
| Tank — earliest wooden | 6–12 bbl (~2–3 m dia) | 1861 PA | [W] | sub-detectable |
| Tank — field wooden | 1,500–2,000 bbl | mid-1860s PA | [W] | circular pad/ring |
| Still — "cheesebox" | **10 ft high × 30 ft (~9 m) dia** | late 1860s | [W] | **Hough-circle prior** r~4.5 m |
| Engine/boiler/pump-house footprint | **NOT FOUND** (photos only) | — | [A] | small rect pad (0.5 m) |
| Central-power house | "octagon", 330° pull; **no numeric footprint** | ~1900–39 Bradford | [A] | radial rod-line pattern |
| Flowline / lead | 2-inch wrought iron | 1860s+ PA | [W] | not detectable |
| Gathering/trunk pipe | 2-inch → 4-inch | 1865→1880s | [W] | trench scar only |
| Field roads | plank/wagon roads "~1 mi apart"; narrow-gauge RR ~1 mi | 1882 PA | [A] | **linear-feature prior** (existing road model) |
| Cleared lease patch | ½–8 acre (~2,000–32,000 m²) disturbance | 1860s PA | [W] | broad-area patch prior |
| Well depth (context) | Drake 69.5 ft; PA region 200–1,110 ft; Bradford group 1,580–2,830 ft | 1859–80s | [A] | terrain-irrelevant |
| Drive/conductor pipe | ~8 inch dia | ~1880 PA | [A] | — |

## Highest-value priors (ranked)

1. **Earthen catch-pit depth** (~0.6–1.5 m, ~2–6 m wide) — the only explicitly
   dimensioned earthwork; sets the depression depth/size threshold and argues for
   **0.5 m DEM** over 1 m for pit detection. ([W])
2. **Well spacing** (3–5 wells/acre ≈ 20–28 m; ½-acre lots ≈ 45 m) — spatial
   **clustering/periodicity prior**: reward gridded clusters, down-weight isolated
   hits inside known fields. ([W])
3. **Tank-ring diameter** (cheesebox 30 ft ≈ 9 m) — **Hough-circle prior**, r≈4.5 m,
   for tank pads/rings. ([W])
4. **Derrick/well-pad footprint** (~4 m square) — per-well leveled-pad scar, best at
   0.5 m. ([W])
5. **Field roads** (linear cuts/benches, ~1 mi spacing) — reinforces the existing
   `road_unet_1m` with a length/spacing prior. ([A])
6. **Cleared lease patch** (½–8 acre) — broad-area disturbance context. ([W])

## Explicit gaps (do NOT fabricate)
Slush/mud/brine-pit L×W×D; standard derrick numeric height/sill; engine/boiler/
pump-house and central-power footprints; flowline trench widths. Source these from
**PA DEP well-construction standards** or a drilling-engineering text, not these two
books.

## So what (for WellSight)
- The **0.5 m DEM** case is now evidence-backed: the canonical pit depth (~0.6–1.5 m)
  is only 1–3 cells at 1 m but 1–6 cells at 0.5 m. Worth building pit derivatives at
  0.5 m in PA, not just 1 m.
- Add a **spacing/clustering prior** (~20–45 m) to candidate scoring inside known
  field footprints.
- Add a **circular-feature (tank-ring) detector**, r≈3–6 m, distinct from depressions.
- The **road model** already aligns with the linear-feature evidence.

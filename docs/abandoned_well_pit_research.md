# Abandoned Well Pit / Slump Depression Research

## What Are Well Pits?

When an oil or gas well is abandoned and left unplugged, the steel casing eventually rusts away over decades. The surrounding soil collapses inward into the void left by the well bore and cellar, creating a **circular surface depression** typically 1–5 meters across and 0.3–1.5 meters deep. In Pennsylvania's oil region, many of these wells date to the 1860s–1920s, meaning 100–160 years of decay.

These features are also called:
- **Well cellars** — the original excavation around the wellhead, typically 4 feet deep and asymmetrically shaped
- **Collapsed wells** — where the casing has fully rusted and the ground has slumped
- **Circular depressions** — the generic LiDAR/geomorphic term
- **Slump pits** — informal field term

In person, a collapsed well cellar in a PA forest looks like a shallow dip in the leaf litter — visually unremarkable. Under LiDAR, they are unmistakable: a crisp circular depression often surrounded by a slight berm (spoil from the original excavation).

## Physical Characteristics

- **Diameter:** 1–8 meters (most commonly 2–5 m)
- **Depth:** 0.3–1.5 meters below surrounding grade
- **Shape:** Roughly circular, sometimes with an asymmetric spoil mound on one side
- **Surrounding features:** Often co-located with leveled well pads (flat clearings), access roads/trails, and sometimes multiple pits in a cluster
- **Persistence:** These depressions persist for 100+ years under forest canopy. The terrain signature outlasts all surface vegetation and most human memory of the site.
- **In-person appearance:** A subtle bowl-shaped dip in the forest floor, often filled with leaf litter, sometimes holding water. Easy to walk past without noticing.
- **LiDAR appearance:** Clear concentric depression with optional outer rim/berm. Shows up strongly in Local Relief Model (LRM), Topographic Position Index (TPI), and negative topographic openness channels.

## Scale of the Problem

- The US has an estimated **3.2 million orphaned and abandoned wells** (Reuters estimate)
- Pennsylvania alone has the highest concentration in the eastern US:
  - McKean County: 2,385 documented orphan wells
  - Venango County: 2,022 documented orphan wells
  - Warren County: 1,561 documented orphan wells
- PA DEP estimates documented wells capture only ~10% of the true orphan/abandoned well population
- Wells can be in forests, backyards, farm fields, under sidewalks and houses

## Environmental and Safety Hazards

- **Methane emissions:** Unplugged wells leak methane continuously; methane has been observed bubbling out of nearby streams
- **Groundwater contamination:** Oil, gas, drilling mud, or salty water can rise up the well and contaminate aquifers
- **Surface spills:** Crude oil can migrate to the surface and pool
- **Physical hazards:** Collapsed well openings pose fall risks; surface subsidence can affect vehicles and structures
- **Extreme events:** A 30-foot geyser of water and natural gas erupted from an abandoned well in PA; a 200-foot sinkhole formed around an abandoned well in Texas's Permian Basin

## LiDAR-Based Detection Research

### NETL — Oil Creek State Park, Pennsylvania
- Used LiDAR + airborne magnetic survey in the Pioneer Run watershed
- LiDAR identified **290 field locations**, 86% of which were possible well sites
- Identified **141 circular depressions** associated with collapsed abandoned wells after filtering out fallen-tree signatures
- Also detected leveled well pads, service roads, and trails
- First use of LiDAR combined with aeromagnetic survey for underground oil industry feature detection
- **Citation:** Veloski, G.A., et al. (2021). "Historic and modern approaches for discovery of abandoned wells for methane emissions mitigation in Oil Creek State Park, Pennsylvania." *Journal of Environmental Management*, 280, 111856. [PubMed](https://pubmed.ncbi.nlm.nih.gov/33370669/) | [ScienceDirect (paywalled)](https://www.sciencedirect.com/science/article/abs/pii/S0301479720317813)
- **Conference:** Veloski, G.A., et al. "LiDAR mapping of 1860s' oil fields along Pioneer Run, Oil Creek State Park, Titusville, Pennsylvania." [OSTI](https://www.osti.gov/biblio/1569995)
- **Summary:** [NETL Story](https://netl.doe.gov/node/9506)

### USGS EROS — CNN Deep Learning on LiDAR
- Used convolutional neural networks on 0.5 m LiDAR-derived hillshade to detect abandoned wells
- Digital elevation data → geomorphology and local relief layers → CNN model input
- Model outputs: well detection polygons with confidence levels
- Applied to Deep Fork National Wildlife Refuge (Oklahoma) and Hagerman NWR (Texas)
- Key insight: well pad construction creates a **soil berm and neighboring leveled surfaces** that persist under vegetation and are detectable only via LiDAR
- Requires high-quality QL1 LiDAR data (>8 returns/m²) to capture the subtle terrain modifications
- **Best publicly available visualization:** Panel (b) of the 2021 report shows LiDAR hillshade with well terrain features (berms + depressions)
- **Citations:**
  - [2021: CNN for Detecting Abandoned Wells](https://eros.usgs.gov/doi-remote-sensing-activities/2021/fws/convolutional-neural-networks-detecting-abandoned-oil-and-gas-wells) — includes hillshade figure with well terrain features
  - [2022: Deep Learning + LiDAR](https://eros.usgs.gov/doi-remote-sensing-activities/2022/fws/utilizing-deep-learning-algorithms-and-lidar-detect-abandoned-oil-and-gas-wells) — includes 4-panel NAIP vs hillshade comparison
  - [Hispanic Access Foundation write-up](https://www.hispanicaccess.org/news-resources/blog/item/1766-using-lidar-and-deep-learning-to-find-abandoned-wells)

### EDF — Pennsylvania Well Discovery
- Using drone-mounted magnetometers (flying 100 ft above ground) combined with methane sensors
- Harrisburg University students conducting backpack magnetometer surveys in rural PA
- Ground-truth surveys in wooded areas of western PA
- **Citation:** [EDF: Unearthing Pennsylvania's Legacy](https://www.edf.org/unearthing-pennsylvanias-legacy-orphan-and-abandoned-wells)

## Detection Methodology (Our Approach — WellSight)

Our pipeline uses many of the same principles as the NETL and USGS work, with some differences:

1. **Template learning:** Extract LRM/TPI/openness windows around 90 expert-annotated pit locations, cluster into 3 morphological sub-types, build median templates per cluster
2. **Template matching:** Normalized cross-correlation of sub-type templates across the full tile → candidate generation (13k+ candidates per 1.5km × 1.5km tile)
3. **Feature extraction:** Per-candidate window statistics (depth, rim prominence, symmetry, radial profile, Gaussian-bowl fit quality) from 22+ derivative channels across 2019 and 2008 epochs
4. **Classification:** XGBoost + LightGBM ensemble with GroupKFold spatial CV, isotonic calibration
5. **Best performance to date (output3 tile):**
   - PR-AUC 0.72 (with pad/road priors), 0.60 (without priors, cross-tile mode)
   - 77/90 annotated pits recovered at 85% precision (with priors)
   - 35 blind predictions on adjacent tile (output2) with zero documented wells

## Visual References

### Available Online
- [USGS EROS 2021 — LiDAR hillshade with well berms/depressions (Oklahoma)](https://eros.usgs.gov/doi-remote-sensing-activities/2021/fws/convolutional-neural-networks-detecting-abandoned-oil-and-gas-wells) — best freely available visualization
- [USGS EROS 2022 — NAIP vs LiDAR hillshade comparison](https://eros.usgs.gov/doi-remote-sensing-activities/2022/fws/utilizing-deep-learning-algorithms-and-lidar-detect-abandoned-oil-and-gas-wells) — shows how pits are invisible in aerial photos but clear in LiDAR
- [NY DEC — Photos of abandoned well casings](https://dec.ny.gov/environmental-protection/oil-gas/finding-identifying-oil-and-gas-wells) — shows what wells look like when hardware is still visible (not collapsed)
- [Texas sinkhole (extreme example)](https://www.newsweek.com/sinkhole-texas-oil-well-2046579) — 200-foot sinkhole around abandoned well, much larger than typical PA pits

### Not Readily Available
- Ground-level photographs of collapsed well cellars in PA forests are essentially absent from the public internet. The features are too subtle (a shallow leaf-filled bowl) to be visually compelling for photography. Our own LiDAR-derived hillshade is likely among the best visualizations of these features that exist.

## Key Papers and Resources

| Resource | Type | Link |
|----------|------|------|
| Veloski et al. (2021) — Pioneer Run LiDAR study | Journal article (paywalled) | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0301479720317813) |
| NETL Oil Creek story | Summary | [NETL](https://netl.doe.gov/node/9506) |
| USGS CNN well detection (2021) | Report with figures | [USGS EROS](https://eros.usgs.gov/doi-remote-sensing-activities/2021/fws/convolutional-neural-networks-detecting-abandoned-oil-and-gas-wells) |
| USGS deep learning + LiDAR (2022) | Report with figures | [USGS EROS](https://eros.usgs.gov/doi-remote-sensing-activities/2022/fws/utilizing-deep-learning-algorithms-and-lidar-detect-abandoned-oil-and-gas-wells) |
| EDF PA orphan wells | Overview + field methods | [EDF](https://www.edf.org/unearthing-pennsylvanias-legacy-orphan-and-abandoned-wells) |
| PA DEP orphan wells program | Official state resource | [PA.gov](https://www.pa.gov/agencies/dep/programs-and-services/oil-and-gas/legacy-wells) |
| FracTracker PA analysis | Data journalism | [FracTracker](https://www.fractracker.org/2019/08/pa-abandoned-wells/) |
| Well Done Foundation — ID guide | Landowner guide | [Well Done](https://welldonefoundation.org/how-a-landowner-can-identify-and-get-help-fixing-an-orphaned-well/) |
| NY DEC — Finding wells | State guide with photos | [NY DEC](https://dec.ny.gov/environmental-protection/oil-gas/finding-identifying-oil-and-gas-wells) |
| NPR — Finding orphan wells (2025) | News feature | [NPR](https://www.npr.org/2025/07/07/nx-s1-5449162/finding-orphan-oil-wells) |
| Aerial imagery dataset of lost oil wells | Dataset paper | [Nature Scientific Data](https://www.nature.com/articles/s41597-024-03820-0) |
| Orphaned wells Wikipedia | Overview | [Wikipedia](https://en.wikipedia.org/wiki/Orphaned_wells_in_the_United_States) |

---
*Compiled 2026-04-15 for the WellSight LiDAR Analysis project.*

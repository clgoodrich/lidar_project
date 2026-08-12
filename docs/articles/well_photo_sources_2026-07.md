# Ground-photo sources for WellSight study areas (web sweep 2026-07-20)

Georeferenced layer: `data/derivatives/experiments/well_photo_locations/well_photo_locations.gpkg`
(EPSG:6346, styles embedded). Layers: `vpasec_wells` (1,926 GPS'd wells,
categorized by folder), `photo_sources` (10 photo locations, categorized by
`precision`: exact / site / vicinity / area / town). Every feature carries
`dist_9t_km` and `dist_mck_km`. Built by
`notebooks/wellsight_v2/s7_analysis/_photo_source_locations.py` from
`data/external/vpasec/vpasec_wells_venango.kml` (archived 2026-07-20 from the
public VPASEC Google map).

## Key spatial facts

- **No ground photos found inside the 9t tile itself.** VPASEC's 1,926
  points all lie west of it (Oil Creek valley + game lands); nearest is a
  DEP-plugged well **0.56 km** from the tile edge, with 26 DEP-plugged wells
  (API 121-42xxx) within 3 km — the Pithole-side plugging campaign.
- **Pithole City historic site is 0.75 km from the 9t NW corner** — modern
  site photos + 1865–95 archive views.
- **Derrick City (1930 oil field photographs) is INSIDE the mkf/McKean
  block**; the StateImpact McKean stream-well photo is ~1.2 km from it and
  the "south of Bradford" casing photo ~4 km.

## Source list

Venango / 9t side:
- VPASEC Abandoned Wells album (50 photos: wood casing in depression, open
  hole in pit, bare depressions, wooden tanks):
  <http://vpasec.org/albums/AbandonedWells/album/index.html>; project page
  with more photos <https://friendsocsp.org/projects/ow/ow.html>; found-wells
  map (KML archived) — one placemark embeds a casing photo at
  41.517417, −79.685278.
- Pithole: <https://pabucketlist.com/exploring-the-ghost-town-of-pithole-in-venango-county-pa/>,
  <https://beltmag.com/uncovering-america-first-oil-landscape/> (also notes
  pre-colonial dug oil pits as "oblong troughs" along Oil Creek).
- Lloyd's 1865 oil-region map (period well locations incl. Allegheny Twp /
  Pithole Creek): <https://www.loc.gov/item/2012590194/>.
- Drone surveys, Venango (EDF magnetometer flights; President + Victory Twp
  planned spring 2026):
  <https://www.thederrick.com/news/front_page/drones-survey-venango-county-for-abandoned-wells/article_913af7b4-67e3-4e83-84a4-55e46225a2b5.html>.
- Drake Well Museum — John Mather glass-plate archive (1860s–80s Allegheny
  River wells at President; contact for period photos of tile-area wells).

McKean / mkf side:
- StateImpact "Perilous Pathways" (2012): McKean stream casing
  (<https://www.witf.io/wp-content/uploads/2012/10/IMG_2468-1440x1080.jpg>),
  rusty pipe south of Bradford, 1937 Oil City aerial:
  <https://stateimpact.npr.org/pennsylvania/2012/10/11/perilous-pathways-hunting-for-hidden-wells/>.
- Save Our Streams PA (Laurie Barr) GPS-tagged photo galleries incl. Duke
  Center project: <https://saveourstreamspa.org/> (2011-era SmugMug links,
  may be dead); 2024 profile with photos:
  <https://www.bayjournal.com/news/pollution/volunteer-leads-hunt-for-abandoned-oil-and-gas-wells-in-pennsylvania/article_5f2324c8-921c-11ef-81b0-8b945437e69b.html>.
- Derrick City / Foster Twp 1930 oil-field photos: <https://www.mindat.org/loc-424434.html>.
- Penn-Brad Oil Museum standing rig: <https://uncoveringpa.com/visiting-penn-brad-oil-museum>.
- Tuna Valley Trail Association (trails through the block, rig remains
  noted): <https://tunavalleytrail.com/bradford-area/>.

Reference (not local): NETL AGU poster on disk
(`data/external/literature/netl_2024_gorantla_state_lidar_orphan_wells_agu.pdf`)
has three well-site infrastructure field photos (Kentucky site) and validates
lidar access-road tracing; PA DEP legacy-wells page and FracTracker articles
carry generic PA field photos.

## Follow-ups

- VPASEC/DEP layer is field-verified ground truth 0.5–10 km from 9t — usable
  as an out-of-tile validation set for the pit/pad models on the Oil Creek
  side (needs lidar tiles for that area).
- Contact Drake Well Museum re: Mather photos of President Twp river wells.
- Watch for the spring-2026 President/Victory Twp drone-survey results (EDF →
  PA DEP); those would be in-tile magnetometer confirmations.

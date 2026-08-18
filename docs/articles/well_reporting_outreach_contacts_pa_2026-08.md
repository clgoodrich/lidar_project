# Who to contact about reporting wells in PA (compiled 2026-08-18)

People and organizations that take in, hold, or generate abandoned-well
ground truth in western Pennsylvania. Compiled from the 2026-07-19/20 web
sweep, extended 2026-08-18 with the EDF/PAW names. Companion to
`docs/articles/well_photo_sources_2026-07.md`, which covers the photo
archives; this file covers the humans.

Nobody here has been contacted yet. Treat every row as a lead.

## Contacts

One list, ordered by how useful the contact looks for WellSight. The priority
is a judgement call, not a fact.

| # | Who | Contact | Why they matter to WellSight |
|---|---|---|---|
| 1 | **Meg Coleman** — Senior Policy Manager (Energy Transition), EDF; geologist | via <https://www.edf.org/people/meg-coleman> (remote office, no public email) | **Best first contact.** Principal investigator on the Pennsylvania Abandoned Well (PAW) project, which includes the spring-2026 Venango survey. Leads field research on detecting and characterizing undocumented orphan wells. |
| 2 | **Mary Kang** — Assistant Professor, Civil Engineering, McGill University | mary.kang@mcgill.ca | The McGill side of PAW. First author of Kang et al. 2014, already cited in this repo (`docs/articles/kang_2014_explained.md`). Softest academic entry point. |
| 3 | **Adam Peltz** — Director and Senior Attorney, EDF Energy Program | apeltz@edf.org | Public face of PAW and of orphan-well policy. Engineered the bipartisan push behind the $4.7B federal plugging fund. Co-author with Kang on the national orphan-well inventory. |
| 4 | **Dan Brockett** — Penn State Extension Energy Team | dlb14@psu.edu | Runs intake for the $100/well bounty. Reported wells land in the PA DEP database. Penn State Extension is also a PAW partner. |
| 5 | **Summer Boyle** — Penn State Extension | sqw5805@psu.edu | Second intake contact for the bounty program. |
| 6 | **Matt Dracup** — Professional Geologist Manager, PA DEP Southwest Regional Office | via DEP SW regional office | DEP's technical lead on the PAW field work. The right door for DEP data or survey coordination. |
| 7 | **Renee McVay** — EDF | via EDF | Co-author with Kang and Peltz on the documented-orphan-well inventory. Data-side contact. |
| 8 | **Drake Well Museum**, Titusville | <https://www.phmc.pa.gov/museums/drake-well> | Holds the John Mather glass-plate archive (1860s-80s Allegheny River wells at President Twp). A call or email could surface period photos of wells inside our tiles. |
| 9 | **VPASEC** (Venango PA Senior Environmental Corp) / Friends of Oil Creek SP | <http://vpasec.org/albums/AbandonedWells/album/index.html> | Volunteer group, 950+ wells found since 2004. Their 50-photo album shows exactly our target morphologies: wood casing in a depression, open holes in pits, bare-ground depressions. Photos georeferenced to folder level only. |
| 10 | **Laurie Barr** — Save Our Streams PA | GPS-tagged photo galleries (see photo-sources doc) | Independent well hunter, ~100 new wells plotted. Public-land volunteer track. |
| 11 | **Patrice Tomcik** — National Field Director, Moms Clean Air Force | <https://www.momscleanairforce.org> | Runs the citizen-outreach half of PAW. |
| 12 | **Wesley Ramsey** — Executive Director, Penn Soil RC&D Council | via Penn Soil RC&D | Regional partner. Venango-area landowner access. |
| 13 | **Oil Region Alliance** | <https://oilregion.org> | Funds the bounty. Regional organization, not a direct intake point. |
| 14 | **Penn-Brad Oil Museum**, Bradford | <https://uncoveringpa.com/visiting-penn-brad-oil-museum> | Standing period rig and McKean-area oil-field history. Lower priority. |
| 15 | Jacquelyn Kellar-Davis — EDF media contact | (212) 993-0123 | Press only. Not the door for a technical collaboration. |

Verification note: Coleman's title came from her EDF staff page directly. Her
"principal investigator on PAW" role came from a search summary of that page,
not from the page text, so treat it as reported rather than confirmed.

## How the two reporting tracks differ

The bounty pays **private landowners** for wells on their own land. That is
the point of it. DEP cannot enter private property without permission, so
those wells stay undocumented. $100 per confirmed well, $300 for three,
first-come first-served.

Volunteer well-hunting is a separate track. VPASEC's seniors and Laurie
Barr's group document wells on **public** land: state game lands, Oil Creek
State Park, the Allegheny National Forest. That work is unpaid.

Both tracks flow into the PA DEP Abandoned and Orphan Well database. That is
the same layer our `venango_wells_all` ground truth comes from, so newly
reported wells eventually show up in our validation set.

## The PAW project

The spring-2026 Venango drone survey is one piece of the **Pennsylvania
Abandoned Well (PAW) project**. EDF runs it with PA DEP, DOE, McGill
University, Harrisburg University, Indiana University of Pennsylvania, Penn
State Extension, the Oil Region Alliance, University of Maryland/MOAA, and
Moms Clean Air Force. Brockett and the Oil Region Alliance sit inside this
project, so the bounty and the drone survey are not separate efforts.

Their method stack is drone-mounted and backpack magnetometers plus vehicle
methane sniffing. They found and documented roughly 250 orphan and abandoned
wells in northwestern PA between October 2024 and summer 2025. Peltz frames
the goal as handing PA DEP "a blueprint to do this work at scale."

That framing matters for us. PAW detects casings magnetically and we detect
disturbance topographically. The two are complementary rather than
competing, and their confirmed points are exactly the ground truth our tiles
lack. Lead with that when reaching out.

## Open actions

- Contact Drake Well Museum about Mather photos of President Twp river wells.
- Watch for the spring-2026 EDF/DEP drone survey release (President and
  Victory Twp, Venango County).
- Reach out to Meg Coleman (EDF, PAW PI) about the Venango survey and whether
  LiDAR-derived candidates could feed their magnetometer targeting.

## Sources

- PA DEP legacy wells: <https://www.pa.gov/agencies/dep/programs-and-services/oil-and-gas/legacy-wells>
- Penn State Extension, "Rusty Relic or Disaster Waiting to Happen: Legacy Wells": <https://extension.psu.edu/rusty-relic-or-disaster-waiting-to-happen-legacy-wells>
- PA Environment Digest, "$100/Well Bounty Established...": <http://paenvironmentdaily.blogspot.com/2025/06/100well-bounty-established-for.html>
- EDF, "Unearthing Pennsylvania's legacy of orphan and abandoned wells": <https://www.edf.org/unearthing-pennsylvanias-legacy-orphan-and-abandoned-wells>
- Pulitzer Center, "Lost: Hunting for Pennsylvania's Orphaned and Abandoned Wells": <https://pulitzercenter.org/stories/lost-hunting-pennsylvanias-orphaned-and-abandoned-wells>
- EDF, Adam Peltz staff page: <https://www.edf.org/people/adam-peltz>
- EDF, Meg Coleman staff page: <https://www.edf.org/people/meg-coleman>
- Mary Kang research group: <https://sites.google.com/view/subsurface-hydrology-kang/bio>
- Moms Clean Air Force, PAW project: <https://www.momscleanairforce.org/paw-project/>
- WITF, "Boots and drones deployed in hunt for orphan gas wells in Southwest Pa.": <https://www.witf.org/2025/06/27/boots-and-drones-deployed-in-hunt-for-orphan-gas-wells-in-southwest-pa/>
- PA Environment Digest, "Groundbreaking Initiative Using Drones...": <http://paenvironmentdaily.blogspot.com/2024/09/groundbreaking-initiative-using-drones.html>

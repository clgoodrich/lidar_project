# Framework 3.6. California (scoped)

**Tier C.** Deferred. A distinct research project.
**Evidence level.** (a) and (b). Administrative status cannot be read from the surface.

## 1. Problem and objective
California has many idle and orphaned wells beside visible surface equipment. Status is a record, not an observation. Many wells share a pad.

**Objective of the first step.** Define the observable target and its decision use before any data.

## 2. Gate before any build
A committed `docs/iterations/ca_target_definition.md` that states what is observable (for example a pad with surface equipment visible), the unit (pad, with wells per pad), label dates aligned with imagery dates, and the decision the output serves. No labelling of wells as orphaned from imagery.

## 3. Minimum feasibility step
- Inventory CalGEM WellSTAR fields (status, spud, coordinates and method, pad) and licence. Not yet searched.
- Listed lidar: Los Angeles County only met the listing threshold (`CA_LosAngeles_B23`, 35 tiles, 2.90 GB window in the city). Its density is diluted by urban area. Kern and Ventura were not listed and need a separate look.
- Choose one oil-field area with visible pads. Estimate pad counts and imagery availability.

## 4. What a full framework would add
Target-class definition, imagery sources and dates, a prototype scorer with the 3.0 protocol by target class, labelling guide, budget (forty hours is a prototype estimate).

## 5. Inputs, risks, resources
Inputs. CalGEM data, public lidar and imagery (unverified). Risks. Urban terrain, equipment-versus-status mismatch, multiple wells per pad. Resources. 40 hours for a prototype.

## 6. Documentation updates
`ca_target_definition.md`, master plan.

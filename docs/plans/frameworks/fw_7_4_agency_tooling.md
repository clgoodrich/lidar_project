# Framework 7.4. Agency tooling (scoped)

**Tier C.** Deferred.
**Evidence level.** (a) with locally calibrated confidence.

## 1. Problem and objective
An agency needs to run the model on its own lidar without our environment and to know how far to trust the output.

## 2. Gate before any build
A frozen reference pipeline (model, preprocessing, input contract) after 3.0 and 3.1, and a named agency user.

## 3. Minimum feasibility step
- Pin the interpreter and package versions in `requirements_lock.txt` (the project currently depends on user-site installs and plain `python`).
- Write the input contract (CRS, point density, tile size, classification) and tests that report unsupported input separately from low-confidence output.

## 4. What a full framework would add
- `tools/wells_cli.py` taking a lidar folder and writing candidates with scores and provenance.
- A local calibration step using 50 to 100 agency labels. That is a trial size, not a reliability guarantee.
- Documentation for a person who did not write the code, tested by having them run a sample tile from the instructions alone.

## 5. Inputs, risks, resources
Inputs. Frozen models, scripts. Risks. Scientific input contract not yet stable. Resources. 30 hours after the gate.

## 6. Documentation updates
Lock file, input contract doc, master plan.

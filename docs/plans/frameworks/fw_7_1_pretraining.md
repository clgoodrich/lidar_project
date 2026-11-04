# Framework 7.1. Self-supervised pretraining (scoped)

**Tier C.** Deferred.
**Evidence level.** (a).

## 1. Problem and objective
Labels are scarce. Pretraining on unlabelled terrain may help. The benefit depends on which question is asked. There are three. Benefit at a fixed annotation budget. Benefit at a fixed total compute budget. Benefit after counting pretraining cost. They are different experiments.

## 2. Gate before any build
P1 done (baseline integrity). A named primary comparison. A runtime benchmark showing the GTX 1070 Ti (8 GB) can pretrain a model of useful size.

## 3. Minimum feasibility step
`s3_train/_pretrain_benchmark.py` (new) measures time per epoch for a small model and memory use. Write `docs/iterations/pretrain_runtime.md`. Decide the comparison.

## 4. What a full framework would add
- Unlabelled corpus from several areas excluding the test area (unless transductive learning is the question).
- A masked-patch or contrastive objective.
- Fine-tune and random-init arms with identical architecture, budget and seeds.
- Label-efficiency curve at several label counts, repeated across seeds, on a held-out area.
Small compute does not rule out a useful result.

## 5. Inputs, risks, resources
Inputs. Derivative stacks, listed lidar windows. Risks. 8 GB memory limits model size. Resources. Unknown until the benchmark.

## 6. Documentation updates
Runtime doc, master plan.

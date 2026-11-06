from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
plans = root / 'docs/plans'
review = (plans / 'expansion_code_review_20261106.md').read_text(encoding='utf-8')
repairs = (plans / 'expansion_method_repairs_20261106.md').read_text(encoding='utf-8')

def section(text, heading, following):
    return text.split(heading, 1)[1].split(following, 1)[0].strip()

statuses = {
    'F01': 'Corrected for the reproduced CRS bypass. Per-raster exclusion reprojection is regression-tested; complete exposure/provenance and augmentation audits remain outside this assurance.',
    'F04': 'Partially corrected. The reproduced one-cluster success is prevented and returns inconclusive with logical bounds [0,1]. Multi-cluster, weighted and stratified inference still needs design-specific validation.',
    'F05': 'Partially corrected. The 7.1 future-split consumer now uses P1’s hash-checking reader. Benchmark, field-audit and task-buffer contracts remain open.',
    'F06': 'Corrected. The sibling import path is fixed; the actual frozen reader is tested with disjoint lists, audit overlap and insufficient buffer.',
    'F11': 'Partially corrected. 3.0 rejects mismatched void/probability CRS, shape and affine transforms, including half-pixel shifts. Broader unit and compound-CRS requirements remain open.',
    'F12': 'Corrected for the reproduced normalization defect. Masked/nonfinite observations are excluded, valid zero is preserved, and empty channels fail. Admission checks every channel and rejects undersized windows.',
    'F14': 'Corrected. Invalid/reversed bounds cannot succeed; invalid margins raise errors. Both gate types and threshold equality are regression-tested.',
}
header = '''# Consolidated expansion review, repairs and method assessment — 2026-11-06

**The pipeline is not ready for confirmatory scientific use.** The highest-priority open defects are incompatible primary scoring policies (F02), duplicated/clipped seam objects (F03), incorrect regional eligible-area budgets (F07), unenforced baseline/model compatibility (F08), and missing field-to-density exports (F16).

The adversarial review established **16 findings: 10 High and 6 Medium**. Subsequent repairs corrected four demonstrated defects (F01/F06/F12/F14), partially addressed three findings (F04/F05/F11), and left nine open. Severity describes the demonstrated original impact, not residual risk after correction. No Critical severity was assigned; no real checkpoint contamination or new confirmatory scientific result was demonstrated.

**Validation:** the original 238 tests passed despite the reproduced defects. After repairs, 245 tests passed across 38 files; the final audit-guard regression and P1 rerun brought coverage to **246 distinct passing tests** across those runs. Eight regression tests were added. Passing tests do not establish integration, complete isolation or scientific accuracy.

This document consolidates the adversarial review and method-repair addendum. It is self-contained; the source reports remain preserved as historical records. Review baseline: `6aed32b30d77cb22814fd54b274c829afc808791`. Repairs are working-tree changes. No models were retrained, canonical manifests frozen, or scientific result artifacts regenerated. User-owned review prompts were not changed.

## Current finding status

| Status | Findings | Remaining scope |
|---|---|---|
| Open — High | F02, F03, F07, F08, F16 | Scoring policy, seams, eligible footprint, compatibility and field/density handoff |
| Open — Medium | F09, F10, F13, F15 | Numeric ties, truth ID zero, unknown terrain, truth-dependent deduplication |
| Partially corrected | F04, F05, F11 | Full survey inference, remaining artifact consumers, broader spatial contracts |
| Demonstrated defect corrected | F01, F06, F12, F14 | Broader end-to-end isolation/scientific validity still requires evidence |

## Confirmed findings and disposition

The detailed triggers, observed outputs and source line numbers below preserve the **pre-repair evidence**. They are not claims that corrected behavior still exists. Source links open working-tree files, so line positions in edited files can differ from the baseline. Each finding begins with its current disposition; the implemented-corrections section records the new behavior and regression evidence. Unchanged findings retain their original inspected paths and lines. Original numbering is preserved, with consequential open findings first.

'''
raw = section(review, '## Confirmed findings', '## Authority, contradictions and unresolved questions')
findings = {}
for match in re.finditer(r'^### (F\d{2})[^\n]*\n.*?(?=^### F\d{2}|\Z)', raw, re.M | re.S):
    fid = match.group(1)
    title, body = match.group(0).split('\n', 1)
    status = statuses.get(fid, 'Open. No correction or new validating evidence was supplied in the repair pass.')
    findings[fid] = f'{title}\n\n**Current disposition:** {status}\n{body.strip()}\n'
order = ['F02','F03','F07','F08','F16','F04','F05','F09','F10','F11','F13','F15','F01','F06','F12','F14']
assert set(order) == set(findings)
corrections = section(repairs, '## Implemented corrections', '## Better methods and when they help')
methods = section(repairs, '## Better methods and when they help', '## Remaining repair order and readiness')
authority = section(review, '## Authority, contradictions and unresolved questions', '## Coverage')
authority = authority.replace('No external scientific/legal/medical recommendation is made; this is a code/artifact review using repository authority and independent arithmetic counterexamples.', 'The original adversarial review used repository authority and independent arithmetic counterexamples. The method recommendations below additionally cite primary technical sources consulted during the repair pass; they are recommendations, not demonstrated improvements on this dataset.')
coverage = section(review, '## Coverage', '## Test and reproduction log')
coverage = coverage.replace('The suite column is the successful rerun, one fresh pytest process per file.', 'The suite column reports the latest successful per-file run, one fresh pytest process per file. Review-status labels describe inspection coverage; finding dispositions are given above and are not implied approvals.')
for fid, old, new in [('P1',9,10),('3.0',9,10),('7.1',3,7),('7.5',2,3),('_shared',5,6)]:
    lines = coverage.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f'| {fid} |'):
            lines[i] = line.replace(f'[{old} passed]', f'[{new} passed]') + ' '
    coverage = '\n'.join(lines)
log = section(review, '## Test and reproduction log', '### What the existing tests miss')
log = log.replace('Reasons: this review is non-mutating production analysis, many real inputs/preregistration decisions are absent, and synthetic smoke tests cannot supply those scientific facts.', 'Reasons: the original review was non-mutating; the subsequent repairs were tested on synthetic fixtures. Many real inputs/preregistration decisions remain absent, and tests cannot supply those scientific facts.')
log = log.replace('The added probes preserve evidence of current behavior. Each finding specifies the regression assertion that should fail on current code and pass after repair; this review did not modify production tests to make them green.', 'The original probes preserve pre-repair behavior. They were not rerun as a claim that repaired defects persist. Eight independent-expectation regression tests were subsequently added; their results follow.')
log += '\n\n### Repair validation\n\n' + section(repairs, '## Reproduction record', '\nNot run:')
gaps = section(review, '### What the existing tests miss', '## Producer/consumer contracts')
gaps = gaps.replace('* `test_7_1.py` exercises label subsets through the historical option and uses corpus rasters/exclusions in one CRS. The future reader and multi-CRS exclusion path are not established by those tests.', '* The original 7.1 tests covered historical subsets and one CRS only. Added regressions now cover the future manifest/hash, multi-CRS exclusion, masked normalization and complete multichannel windows; historical exposure and the full augmentation chain remain unverified.')
gaps = gaps.replace('* P1 tests call fold statistics and isolated samplers but do not invoke the audit-enabled trainer in a fresh process; F06 is invisible.', '* The original P1 suite missed the audit-enabled guard. The added test exercises the actual frozen reader, overlaps and buffer enforcement in the independently run P1 suite. Full training with production inputs remains untested.')
gaps = gaps.replace('* Field analysis tests assert allowed gate labels and file production but do not challenge one independent cluster passing the precision gate.', '* Original field tests did not challenge one independent cluster passing the precision gate; the new regression does. Full multi-cluster survey coverage remains unresolved.')
contracts = section(review, '## Producer/consumer contracts', '## Runtime and memory')
contracts = contracts.replace('Confirmed: nested task/fold mapping versus top-level fold list | F05; use actual schema and hash-validating reader', 'Partially corrected: 7.1 uses the hashed task-specific schema; 7.3 still expects a top-level fold list | F05; complete benchmark migration and actual-artifact round trip')
contracts = contracts.replace('Confirmed: nonexistent import path | F06; fresh-process integration test', 'Corrected: sibling path now reaches actual frozen reader | F06 regression passes for disjoint lists, overlap and buffer rejection')
runtime = section(review, '## Runtime and memory', '## Repair order')
repair_order = '''1. **Shared contracts and policy lineage:** complete F05/F16, define the isolated checkpoint producer, and enforce reference/target compatibility (F08). Preserve immutable hashes and distinguish canonical from dry-run artifacts.
2. **Shared physical scoring:** unify task cutoffs/matching/budgets, numeric ties, truth-ID encoding, valid support and remaining CRS/unit contracts (F02/F07/F09/F10/F11), then reconcile tile seams (F03). Independently hand-check identical reference/target fixtures.
3. **Complete exposure controls:** build on corrected F01/F06/F12 and trace full training/augmentation windows, checkpoints, caches, normalization, mining and selection. Separate inductive from declared transductive use; do not relabel historical 9t as untouched.
4. **Design-valid inference:** complete F04 beyond the single-cluster guard, resolve small-cluster interval guidance, and validate weighted/paired uncertainty. Retain the corrected F14 bounds validation.
5. **Scientific population and observability:** replace truth-dependent deployment deduplication (F15), supply per-well field accounting (F16), rerun affected density/association consumers, and propagate unknown terrain in sightlines (F13).
6. **Actual artifact integration and pilots:** run fresh-process producer/consumer tests and representative real-data stages before regenerating results or strengthening scientific claims. Do not reconstruct historical inner splits retrospectively.
'''
readiness = '''**Code execution:** 246 distinct tests pass across the full repair suite and final P1 rerun. The audit import and SSL future reader are corrected; benchmark/buffer/field prerequisites still have confirmed executable contract failures. Synthetic tests do not establish a runnable full pipeline.

**Integration:** not ready. Remaining schema errors and missing field exports require code changes; undefined checkpoints and human inputs remain explicit dependencies. No actual frozen benchmark release or complete field-to-density round trip was demonstrated.

**Reproducibility and leakage controls:** improved, not certified. Per-raster exclusions, masked normalization, audit imports and the SSL hashed reader address demonstrated defects. Full-window/augmentation support, exposure history, checkpoint/cache/mining lineage and remaining consumers still require end-to-end verification. No real contaminated checkpoint was demonstrated, and no absence-of-leakage guarantee is made.

**Scientific evidence:** no new confirmatory evidence was produced. Even if every software defect is corrected and all tests pass, terrain-feature recall does not establish well identity, well absence, leakage, methane flux, subsurface integrity, storage suitability, causal slope effects or population well totals. Independent labels, emissions/controls, defensible sampling, acquisition support, frozen policies and design-valid uncertainty remain necessary. Local validation cannot establish national transfer; simulated thinning cannot validate new acquisitions; geometric visibility is not person-detection probability. No model architecture has demonstrated universal superiority in this review.
'''
output = header + '\n'.join(findings[f] for f in order)
for title, body in [
    ('Implemented corrections and regression evidence', corrections),
    ('Authority, documentation contradictions and unresolved questions', authority),
    ('Coverage', coverage), ('Test and reproduction log', log),
    ('Test limitations after repairs', gaps), ('Producer/consumer contracts', contracts),
    ('Runtime and memory', runtime), ('Better methods and when they help', methods),
    ('Highest-priority repairs in dependency order', repair_order), ('Readiness assessment', readiness),
]:
    output += f'\n## {title}\n\n{body.strip()}\n'
output = '\n'.join(line.rstrip() for line in output.splitlines()) + '\n'
dest = plans / 'expansion_consolidated_review_20261106.md'
dest.write_text(output, encoding='utf-8')
assert len(re.findall(r'^### F\d{2}', output, re.M)) == 16
assert '246 distinct' in output
assert len(re.findall(r'^\| (?:P[12]|[3-7]\.\d) \|', coverage, re.M)) == 37
print(f'{dest}\n{len(output.split())} words; 16 findings; 37 expansion coverage rows; shared components retained')

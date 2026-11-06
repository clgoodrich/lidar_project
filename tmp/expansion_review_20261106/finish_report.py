from pathlib import Path
import json,re,importlib.metadata,sys
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
report=ROOT/'docs/plans/expansion_code_review_20261106.md'
suite=json.loads((OUT/'suite_retry.json').read_text())
stages={
'p1':('_split_future_write_9t.py, _split_buffer_derive_9t.py, _pit_unet_iso_train_9t.py, test_p1.py','future JSON, buffer, normalization, audit import','F05/F06; custom probes'),
'p2':('_audit_guard_lib.py, _audit_draw_blocks_9t.py','frozen reader, window guard, actual CSV writer','F05; producer round trip'),
'3_0':('_transfer_score_lib.py, _transfer_score_run.py, _transfer_ref_tables_9t.py, _transfer_decision_report.py, config_3_0.json','scoring, reference handoff, gates; actual reference table','F02/F08/F09/F11; direct probes'),
'3_1':('_xfer_score_k40_wfm.py, _xfer_frozen_infer_wfm.py, _xfer_blocks_roles_wfm.py, _geo_xfer_lib.py, config_3_1.json','seams, inference policy, role/buffer handoff','F03/F05/F08; seam fixture'),
'3_2':('_appal_window_cover_union.py','query states, coverage unions; 3.1 stage reuse','F03/F05/F08 inherited; no live queries'),
'3_3':('_slope_confound_logit_9t.py','association and clustered coefficient resampling','Partial; synthetic suite only'),
'3_4':('_geo_transfer_core.py, test_3_4.py','regional extraction, matching, masks, ranking, resampling, training helpers','F02/F07/F09/F10/F11; direct probes'),
'3_5':('_okks_modality_compare.py, _okks_truth_adjudicate.py','arm scoring, truth IDs, shared core','F02/F07/F09/F11; shared probes; zero-ID producer is safe'),
'3_6':('_ca_pad_recall_by_class.py','class/primary scoring and reference handoff','F02/F07/F09/F10/F11 through core'),
'3_7':('_can_record_assoc.py','shifted-set null, province footprint; regional shared core','F02/F07/F09/F10/F11 through core; no province data'),
'3_8':('_ak_rate_difference_ak1.py','seasonal rates, controls, cluster bootstrap, gate','Partial; LOS units/reference/acquisition chain not fully traced'),
'4_1':('_mag_anomaly_process.py','despiking, base correction, gridding, derivative setup','Partial; no instrument/site validation'),
'4_2':('_thermal_extract_samples_9t.py','LST scaling, scene filtering, site extraction','Partial; upstream pixel QA unresolved'),
'4_3':('_vegstress_extract_sites_9t.py','reflectance extraction, SCL/open-ground masks, seasonal anomalies','Partial; real mask provenance unresolved'),
'4_4':('_methane_gate_limit_pa.py','kg/day conversion, mean/aggregation/tail branch and scope','Partial; no external sensor specification verification'),
'4_5':('_dod_recovery_test_9t.py','DEM-chain injection, registration, recovery summaries','Partial; actual flight dates/vertical datum and full cloud chain unverified'),
'4_6':('_hist_source_verdicts_9t.py','source readiness separated from association','Partial; no independent map-digitisation review'),
'4_7':('_drone_thin_ladder_oc.py','seeds, per-class thinning, position and density checks','Partial; nonnested design noted; no real drone acquisition'),
'4_8':('_leafoff_review_gate_9t.py','usable-share gate and reviewer agreement','Partial; fetch/date/coregistration chain not fully traced'),
'4_9':('_sar_new_score_9t.py','OOF arms, paired gains, strata and multiplicity labels','Partial; real input arms/polarizations and upstream transforms unverified'),
'5_1':('_context_stage2_learner_9t.py','nested tuning, fitted preprocessing and audit gate','Partial; entire upstream checkpoint/exposure lineage unverified'),
'5_2':('_era_core_tools.py','sentinel dates, interval classes, support helpers','Partial; held-out calibration/full label lineage unverified'),
'5_3':('_risk_ranking_core.py','ordinal bands, site assembly, receptor distances','Partial; full sensitivity/bootstrap/claims chain unverified'),
'5_4':('_density_field_bounds_9t.py, config_5_4.json','required field schemas, conditional totals and recall denominator','F16; static contract; no field data'),
'5_5':('_padarea_geometry_tools.py','repair/subtraction, one-to-one pad matching, area interval/gate','Partial; repair scientific-unit invariance and cost MC not exhaustively tested'),
'5_6':('_records_assoc_core.py, _records_full_detector_output_9t.py','full output, dedupe lineage, assignment and weighted interval helpers','F15; direct probe; dense memory bound'),
'6_1':('_co2_screen_counts_9t.py','eligible-area and block-count summaries, claim labeling','Partial; upstream full handoff inherits F15 risk'),
'6_2':('_coal_confusion_coal.py','top-K, missing labels, mine confusion and block rates','Partial; no real coal inventory/training validation'),
'6_3':('_confuser_unet_cv5_9t.py','split lists, negative centers, normalization and forbidden geometry setup','Partial; no training or full audit/mining lineage trace'),
'6_4':('_h2_screen_run_9t.py','hydrogen profile, depth units and record penetration rule','Partial; missing subsurface evidence; F15 handoff risk'),
'6_5':('_methane_field_table.py','visit/site aggregation, background/detection categories and claim limits','Partial; no real instrument calibration or source attribution'),
'6_6':('_sar_viewshed_tool.py, test_6_6.py','grid loading, profile/sweep, voids and cumulative visibility','F13; independent nodata-barrier probe'),
'7_1':('_ssl_corpus_chips_us.py, _ssl_label_subsets_9t.py, test_7_1.py','corpus exclusion, normalization, future split integration','F01/F05/F12; direct probes'),
'7_2':('_al_retrain_round_9t.py','label gathering/burning, exclusions, trainer deferral','Partial; added-label sharing hypothesis; live rounds not run'),
'7_3':('_bench_export_release_9t.py, _bench_evaluate_recall_k.py, test_7_3.py','release schemas, masks, defaults, synthetic fresh-checkout test','F02/F05; actual producer tests'),
'7_4':('_agency_export_formats.py','IDs, budgets, CRS exports, evidence labels','Partial; no real CLI-to-agency import lifecycle test'),
'7_5':('_field_analysis_bounds.py, _field_sample_draw_frames.py, _field_results_ingest.py, test_7_5.py','frames, weights, clusters, outcomes and downstream exports','F04/F05/F16; one-cluster probe'),
'_shared':('expkit.py, test_expkit.py','CRS, ranking, bootstrap and gate helpers','F14; direct gates and timing')}
rows=['| ID | Inspected files / stages | Suite | Status and limits |','|---|---|---|---|']
commands=[]
def link(p,label=None,line=None):
    return f'[{label or p.name}]({p.as_posix()}{":"+str(line) if line else ""})'
for x in suite:
    p=ROOT/Path(x['file']); folder=p.parent.parent
    name=folder.name
    key='_shared' if name=='_shared' else '_'.join(name.split('_')[:2]) if name[0].isdigit() else name.split('_')[0]
    files,desc,note=stages[key]
    fs=[]
    for f in files.split(', '):
        q=p.parent/f
        assert q.exists(),q
        fs.append(link(q))
    n=re.search(r'(\d+) passed',x['output']).group(1)
    status='partial' if note.startswith('Partial') else 'reviewed with findings'
    label=key.replace('_','.') if key[0].isdigit() else key.upper() if key.startswith('p') else key
    rows.append(f'| {label} | '+', '.join(fs)+f'; {desc} | {link(p,n+" passed")} | **{status}** — {note} |')
    commands.append(f'"{sys.executable}" -m pytest -q {p.relative_to(ROOT)} -p no:cacheprovider')
rows.extend([
'| Shared authority/interfaces | '+link(ROOT/'expansions/_shared/INTERFACES.md')+', '+link(ROOT/'expansions/_shared/fw_00_common.md')+', '+link(ROOT/'docs/plans/protocol_gates_and_metrics.md')+' | Contract probes above | **reviewed with findings** — policy/schema drift and unresolved model/field dependencies |',
'| _template | '+link(ROOT/'expansions/_template/README.md')+' and directory inventory | No executable tests applicable | **reviewed with no confirmed findings** — empty skeleton only |'])
s=report.read_text(encoding='utf8').replace('<!-- COVERAGE -->','\n'.join(rows))
def expand(m):
    rel,num=m.group(1),int(m.group(2)); p=ROOT/rel
    lines=p.read_text(encoding='utf8').splitlines()
    assert 1<=num<=len(lines),(rel,num)
    return link(p,f'{rel}:{num}',num)
s=re.sub(r'\[\[([^\]]+):(\d+)\]\]',expand,s)
report.write_text(s,encoding='utf8')
commands+=['python tmp/expansion_review_20261106/reproduce.py > tmp/expansion_review_20261106/reproduce.log 2>&1',
           'python tmp/expansion_review_20261106/contracts.py > tmp/expansion_review_20261106/contracts.log 2>&1','git rev-parse HEAD','git status --short']
(OUT/'commands.txt').write_text('\n'.join(commands),encoding='utf8')
env={'python':sys.version,'executable':sys.executable,'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']}}
(OUT/'environment.json').write_text(json.dumps(env,indent=2),encoding='utf8')
print('report',report,'words',len(s.split()),'coverage rows',len(rows)-2)

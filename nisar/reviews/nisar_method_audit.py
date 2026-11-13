"""Read-only checks of existing NISAR artifacts; writes audit JSON only."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nisar/code/s5_eval'))
import _nisar_feat_common as C

report = {}
idx = pd.read_csv(C.A.INDEX)
used = C.A.usable_stack(idx)
report['default_stack'] = C.A.STACK
report['dates_used'] = used.groupby('track').size().to_dict()
report['known_bad_dates_still_used'] = [dict(date=r.date, track=int(r.track)) for r in used.itertuples() if (str(r.date), int(r.track)) in C.A.BAD_DATES]
report['frequency_hz'] = idx.centre_frequency_hz.unique().tolist()
report['collections_by_month'] = pd.crosstab(idx.date.str[:7], idx.collection).to_dict()
with rasterio.open(C.A.GSLC / idx.file.iloc[0]) as ds:
    tf, shape = ds.transform, ds.shape
grids = C.lidar_grids(tf, shape)
for target, layer, shrink, count in [('pad', 'plat', 5, 49), ('pit', 'pit_outside', 0, 9)]:
    rows = []
    for g in C.ifg.read_layer(C.ifg.ANN, layer).to_crs(C.CRS).geometry:
        core = g.buffer(-shrink) if shrink else g
        px = C.st.pixel_index(core, tf, shape) if not core.is_empty else np.array([], int)
        if len(px) < 4:
            continue
        cov = np.nanmean(grids['cover'].ravel()[px])
        slo = np.nanmean(grids['slope'].ravel()[px])
        if np.isfinite(cov) and np.isfinite(slo):
            rows.append(len(px))
    z = np.load(C.FEAT_DIR / f'nisar_{target}_samples_9t.npz', allow_pickle=True)
    lengths = np.array(rows)
    report[target+'_support'] = dict(reconstructed=len(rows), saved=z['pad'].shape[1])
    if len(rows) == z['pad'].shape[1]:
        lengths = lengths[np.unique(z['dec_pad'])]
        report[target+'_support'].update(matched=len(lengths), fewer_than_decoy=int((lengths<count).sum()), percentiles=np.percentile(np.minimum(lengths,count), [0,25,50,75,100]).tolist())

for suffix in ['', '_local750', '_local1500']:
    z = np.load(C.FEAT_DIR / f'nisar_pad_samples_9t{suffix}.npz', allow_pickle=True)
    pads = np.unique(z['dec_pad'])
    xy = np.vstack([z['pad_xy'][pads], z['dec_xy']])
    y = np.r_[np.ones(len(pads)), np.zeros(len(z['dec_pad']))].astype(int)
    grp = np.r_[z['pad_block'][pads],z['dec_block']]
    nearest = np.full(len(y),np.nan)
    folds = list(GroupKFold(5).split(xy,y,grp))
    for tr, te in folds:
        nearest[te] = cKDTree(xy[tr]).query(xy[te])[0]
    item = dict(n_pads=len(pads), n_decoys=len(z['dec_xy']), unique_decoy_centres=len(np.unique(z['dec_xy'],axis=0)), test_rows_with_train_centre_within_50m=int((nearest<50).sum()), test_rows_with_train_centre_within_100m=int((nearest<100).sum()))
    if suffix == '_local1500':
        X = np.vstack([z['pad'][:,pads].T,z['dec'].T])
        names = np.array([str(n) for n in z['names']])
        good = np.stack([np.isnan(X[y==a]).mean(0) for a in [0,1]]).max(0)<=.2
        good &= np.array([not n.startswith(('control:', 'context:')) for n in names])
        X = X[:,good]
        Xi = np.where(np.isnan(X),np.nanmedian(X,0),X)
        for label, data in [('published_preprocessing',Xi),('fold_imputation',X),('coordinates_only',xy)]:
            pred = np.full(len(y),np.nan)
            for tr,te in folds:
                train,test = data[tr].copy(),data[te].copy()
                if label == 'fold_imputation':
                    med = np.nanmedian(train,0)
                    train=np.where(np.isnan(train),med,train)
                    test=np.where(np.isnan(test),med,test)
                m=HistGradientBoostingClassifier(max_depth=3,learning_rate=.06,max_iter=200,l2_regularization=1.,min_samples_leaf=40,class_weight='balanced',random_state=20261026)
                m.fit(train,y[tr]); pred[te]=m.predict_proba(test)[:,1]
            pmap=dict(zip(pads,pred[:len(pads)]))
            dif=np.array([pmap[k] for k in z['dec_pad']])-pred[len(pads):]
            item[label]=dict(pooled_auc=float(roc_auc_score(y,pred)), own_decoys_concordance=float(((dif>0)+.5*(dif==0)).mean()), fold_aucs=[float(roc_auc_score(y[te],pred[te])) for _,te in folds])
    report['pad'+suffix]=item
    print(suffix or 'default', item, flush=True)

out=ROOT/'nisar/reviews/nisar_method_audit.json'
out.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

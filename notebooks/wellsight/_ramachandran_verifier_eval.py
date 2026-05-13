"""Evaluate trained verifier on test split. Reports precision/recall/F1 +
threshold needed to achieve 99% precision on validation, then transfers
that threshold to test."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import timm
from PIL import Image
from torch.utils.data import DataLoader
from torchvision import transforms
from sklearn.metrics import precision_recall_curve, average_precision_score

from _ramachandran_verifier_train import (
    VerifierDataset, build_index, build_model, OUT, DEVICE, INPUT_PX
)

CKPT = OUT / "verifier_best.pt"


def main():
    idx = build_index()
    test_df = idx[idx.split == "test"]
    valid_df = idx[idx.split == "valid"]

    state = torch.load(CKPT, map_location=DEVICE)
    model = build_model()
    model.load_state_dict(state["model"])
    model.eval()

    def predict(df):
        ds = VerifierDataset(df, training=False)
        dl = DataLoader(ds, batch_size=64, shuffle=False, num_workers=4, pin_memory=True)
        all_p, all_y = [], []
        with torch.no_grad():
            for x, y in dl:
                x = x.to(DEVICE, non_blocking=True)
                p = torch.sigmoid(model(x).squeeze(1)).cpu().numpy()
                all_p.append(p); all_y.append(y.numpy())
        return np.concatenate(all_p), np.concatenate(all_y)

    print("Predicting validation...")
    vp, vy = predict(valid_df)
    print("Predicting test...")
    tp, ty = predict(test_df)

    # Pick threshold on valid that hits 99% precision (if achievable)
    prec, rec, thr = precision_recall_curve(vy, vp)
    target = 0.99
    idx_ok = np.where(prec[:-1] >= target)[0]
    if len(idx_ok):
        # pick threshold with max recall among those at >= target precision
        pick = idx_ok[np.argmax(rec[idx_ok])]
        t99 = thr[pick]
        achieved = prec[pick]
    else:
        pick = np.argmax(prec[:-1])
        t99 = thr[pick]; achieved = prec[pick]
        print(f"  WARN: 99% precision not achieved on valid (max prec={achieved:.4f})")
    print(f"Selected threshold = {t99:.4f}  (valid prec={achieved:.4f}, "
          f"recall={rec[pick]:.4f})")

    # Apply to test
    test_pred = (tp >= t99).astype(int)
    tp_ = ((test_pred == 1) & (ty == 1)).sum()
    fp_ = ((test_pred == 1) & (ty == 0)).sum()
    fn_ = ((test_pred == 0) & (ty == 1)).sum()
    test_prec = tp_ / max(1, tp_ + fp_)
    test_rec = tp_ / max(1, tp_ + fn_)
    test_f1 = 2 * test_prec * test_rec / max(1e-9, test_prec + test_rec)
    test_ap = average_precision_score(ty, tp)

    rows = {
        "n_valid_pos": int((vy == 1).sum()), "n_valid_neg": int((vy == 0).sum()),
        "n_test_pos":  int((ty == 1).sum()), "n_test_neg":  int((ty == 0).sum()),
        "threshold_99prec_valid": float(t99),
        "valid_prec_at_thr": float(achieved),
        "valid_recall_at_thr": float(rec[pick]),
        "test_prec":   float(test_prec),
        "test_recall": float(test_rec),
        "test_f1":     float(test_f1),
        "test_ap":     float(test_ap),
    }
    print("\n=== Verifier test results ===")
    for k, v in rows.items():
        print(f"  {k}: {v}")
    pd.DataFrame([rows]).to_csv(OUT / "verifier_test_metrics.csv", index=False)
    np.savez(OUT / "test_probs.npz", prob=tp, label=ty)


if __name__ == "__main__":
    main()

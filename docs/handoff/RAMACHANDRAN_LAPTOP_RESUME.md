# Ramachandran Verifier — Full Replication Guide (laptop handoff)

Self-contained instructions to run the **full 8-epoch paper-faithful training** + eval on a different machine.

## Status at handoff
- 87,467 / 88,044 NAIP chips downloaded (test split is 100% complete)
- Proof-of-concept 3-epoch run reached **val_acc = 91.0% at epoch 2** → `verifier_best.pt` exists but can be ignored for the full replication
- No eval has been run yet

## Goal of this run

Match the paper's training recipe **exactly** to see how well the verifier replicates against NAIP imagery:

- EfficientNet-B3, ImageNet pretrained, single-logit head
- Input 300×300 RGB
- **Adam, LR 1e-6** (paper)
- **Focal loss α=0.25, γ=2.0** (paper)
- Positives: GT bbox crops from labeled tiles (with 10% padding); Negatives: random 128–256 px crops from no-pad tiles
- **8 epochs** (paper) — vs. the cut-down 3 we did for the PoC
- Mixed-precision (AMP fp16) — speedup only matters on Tensor-Core GPUs (RTX 20-series and up); functionally a no-op on older cards

---

## 1. What to copy from this machine

Total: **~5.2 GB**

| Source path (this machine) | Destination on laptop | Size |
|---|---|---|
| `notebooks/wellsight/_ramachandran_verifier_train.py` | same relative path | 8 KB |
| `notebooks/wellsight/_ramachandran_verifier_eval.py` | same relative path | 3 KB |
| `data/external/ramachandran_2024/permian_denver_data/training/well-pad_dataset.csv` | same relative path | 50 MB |
| `data/external/ramachandran_2024/naip_chips/` (whole tree) | same relative path | 5.1 GB |

You **do not** need to copy `verifier_best.pt` — the full run trains from scratch (paper recipe = ImageNet init, no warm start).

The scripts use hardcoded Windows paths (`C:\Users\colto\Documents\GitHub\lidar_project`). On the laptop, **either**:
- Place the project at that same path, OR
- Edit the `ROOT = Path(...)` constant at the top of both scripts.

## 2. Python environment

Python 3.10+ recommended. From an empty venv/conda env:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install timm pandas numpy pillow scikit-learn
```

Verify CUDA is visible (training on CPU is not feasible for 8 epochs):

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

## 3. Run training (full 8 epochs)

```bash
cd <project_root>
python -u notebooks/wellsight/_ramachandran_verifier_train.py --epochs 8 --batch 48 --workers 4
```

This produces:
- `data/derivatives/experiments/ramachandran_verifier/verifier_best.pt` — best val-loss checkpoint
- `data/derivatives/experiments/ramachandran_verifier/valid_probs_best.npz` — val predictions at best epoch
- `data/derivatives/experiments/ramachandran_verifier/train_history.csv` — per-epoch loss/acc

### Time estimates

Per-epoch time scales linearly with batches × img/s. Train set is 1,399 batches per epoch.

| GPU class | img/s (est) | Per-epoch | Full 8 epochs |
|---|---|---|---|
| RTX 4080/4090 mobile | 80–120 | ~10–15 min | **1.5–2 hr** |
| RTX 3070/3080 mobile | 40–60 | ~20–30 min | **3–4 hr** |
| RTX 30/40-series w/ Tensor Cores | 30–80 | varies | **2–6 hr** |
| GTX 1660 / RTX 2060 mobile | 10–20 | ~60–90 min | **8–12 hr** |
| GTX 1070 Ti (desktop, baseline) | ~7 | ~2.5 hr | **~21 hr** |
| CPU only | <1 | hours | not viable |

### VRAM tuning

Batch size 48 uses ~8 GB VRAM. If your laptop GPU has less:

| VRAM | `--batch` |
|---|---|
| 16 GB+ | 48 (default) — or 64 for faster epochs |
| 8 GB | 48 |
| 6 GB | 24 |
| 4 GB | 16 |

Halving batch size doubles batch count per epoch but per-batch wall time is roughly halved, so total time is similar. (Loss curves may differ slightly — the paper used 48.)

## 4. Run eval

After training completes:

```bash
python -u notebooks/wellsight/_ramachandran_verifier_eval.py
```

Runs in ~5–15 min. Outputs:
- `data/derivatives/experiments/ramachandran_verifier/verifier_test_metrics.csv` — precision, recall, F1, AP, threshold at 99% precision
- `data/derivatives/experiments/ramachandran_verifier/test_probs.npz` — per-sample predictions for further analysis

## 5. What to look for in training output

Each epoch ends with a one-line summary:

```
ep1/8 tr_loss=... tr_acc=... va_loss=... va_acc=...
...
ep8/8 tr_loss=... tr_acc=... va_loss=... va_acc=...
Best valid loss: X -> .../verifier_best.pt
```

Mid-epoch prints fire every 50 batches with running loss / accuracy / img/s — these tell you whether throughput is stable.

**Expected trajectory** (extrapolating from the 3-epoch PoC):
```
ep1 ~ va_acc 0.85       baseline
ep2 ~ va_acc 0.91       fast climb
ep3-4 ~ va_acc 0.92-0.93  plateau begins
ep5-8 ~ va_acc 0.93-0.95  fine convergence
```

The paper-reported verifier operating point is **99% precision at ~90% recall** on test. The eval script reports both.

`va_loss` numbers will look high (~1.0–1.5) because of focal-loss accounting — use `va_acc` and the eval-script outputs as the real signal.

## 6. What the verifier does (for context)

Binary classifier on 300×300 aerial chips: "is there a well pad in this image?" Trained on 8,949 positive + 58,220 negative crops from NAIP 60 cm imagery, replicating Ramachandran et al. 2024 (*Nature Communications* 15:7036). The paper used Google Earth tiles which can't be redistributed; NAIP is the closest public substitute.

In the paper's deployment pipeline, the verifier is the second stage of a two-model setup:
1. **Detector** (RetinaNet+ResNet-50) draws candidate boxes around possible pads
2. **Verifier** (EfficientNet-B3, this model) re-classifies each cropped detection at high precision

Training only the verifier still proves out the methodology — the paper's training code for the detector wasn't released, but the verifier is fully specified.

The eval script picks a probability threshold on the validation set that hits 99% precision, then reports recall at that threshold on the held-out test set (9,193 samples). Matching the paper's ~90% recall at 99% precision validates that the methodology transfers from Google Earth to NAIP.

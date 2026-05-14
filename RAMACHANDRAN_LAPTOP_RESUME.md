# Ramachandran Verifier — Laptop Resume Guide

Self-contained instructions to finish training + eval on a different machine.

## Status at handoff
- 87,467 / 88,044 NAIP chips downloaded (test split is 100% complete)
- Verifier trained through epoch 2 / 3 → `verifier_best.pt`, **val_acc = 91.0%**
- Eval has not been run yet

You have **three options**, in increasing effort:
- **(A) Run only the eval** against the existing checkpoint — fastest, no GPU needed (CPU is fine for 9K test samples)
- **(B) Train 1 more epoch + eval** — restarts training from scratch (no optimizer state saved), but a single epoch on a modern GPU is ~30–60 min
- **(C) Full 3-epoch retrain + eval** — clean replication, ~3–8 hours depending on GPU

---

## 1. What to copy from this machine

Total: **~5.2 GB**

| Source path (this machine) | Destination on laptop | Size |
|---|---|---|
| `notebooks/wellsight/_ramachandran_verifier_train.py` | same relative path | 7 KB |
| `notebooks/wellsight/_ramachandran_verifier_eval.py` | same relative path | 3 KB |
| `data/external/ramachandran_2024/permian_denver_data/training/well-pad_dataset.csv` | same relative path | 50 MB |
| `data/external/ramachandran_2024/naip_chips/` (whole tree) | same relative path | 5.1 GB |
| `data/derivatives/ramachandran_verifier/verifier_best.pt` | same relative path | 43 MB |
| `data/derivatives/ramachandran_verifier/index.csv` | same relative path | 11 MB |

The script uses hardcoded Windows-style paths (`C:\Users\colto\Documents\GitHub\lidar_project`). On the laptop, **either**:
- Put the project at the same `C:\Users\colto\Documents\GitHub\lidar_project` path, OR
- Edit the `ROOT` constant at the top of `_ramachandran_verifier_train.py` and `_ramachandran_verifier_eval.py` to wherever you put it.

## 2. Python environment

Python 3.10+ recommended. From an empty venv/conda env:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install timm pandas numpy pillow scikit-learn
```

Verify CUDA is visible:
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

## 3A. Eval-only (recommended if you just want results)

```bash
cd <project_root>
python -u notebooks/wellsight/_ramachandran_verifier_eval.py
```

Runs in ~5–15 min on CPU, faster on GPU. Outputs to `data/derivatives/ramachandran_verifier/`:
- `verifier_test_metrics.csv` — precision, recall, F1, AP, threshold at 99% precision
- `test_probs.npz` — per-sample predictions for further analysis

## 3B. 1 more epoch + eval

The training script doesn't save optimizer state, so this **restarts from ImageNet weights**, not from the epoch-2 checkpoint. Easiest workflow:

```bash
cd <project_root>
python -u notebooks/wellsight/_ramachandran_verifier_train.py --epochs 1 --batch 48 --workers 4
python -u notebooks/wellsight/_ramachandran_verifier_eval.py
```

If you want to **continue from the existing checkpoint** (skip re-doing epoch 1), add this snippet at the top of `main()` in `_ramachandran_verifier_train.py` immediately after `model = build_model()`:

```python
ckpt = OUT / "verifier_best.pt"
if ckpt.exists():
    state = torch.load(ckpt, map_location=DEVICE)
    model.load_state_dict(state["model"])
    print(f"Resumed from {ckpt}", flush=True)
```

Then run with `--epochs 1` and it will continue training from val_acc 91.0% and likely push to 92–93%.

## 3C. Full retrain + eval

```bash
cd <project_root>
python -u notebooks/wellsight/_ramachandran_verifier_train.py --epochs 3 --batch 48 --workers 4
python -u notebooks/wellsight/_ramachandran_verifier_eval.py
```

Time depends on your GPU:
- RTX 30/40-series laptop GPU with Tensor Cores: ~1.5–3 hr (AMP gives real speedup)
- GTX 16-series / older: ~6–10 hr
- CPU only: don't try; will take days

If laptop VRAM < 8 GB, drop `--batch` to 24 or 16.

## 4. What to look for in training output

Each epoch prints a summary line. Targets:

```
ep1/3 ... va_acc=0.85   # what we got on the desktop
ep2/3 ... va_acc=0.91   # what's saved in verifier_best.pt now
ep3/3 ... va_acc=0.92+  # what one more epoch should give
```

Loss values (`va_loss` ~1.4) look high because of focal loss accounting, not the model being bad. Use `va_acc` as the real signal.

## 5. What the verifier does (for context)

Binary classifier on 300×300 aerial chips: "is there a well pad in this image?" Trained on 8,949 positive + 58,220 negative crops from NAIP 60 cm imagery, replicating Ramachandran et al. 2024 (Nature Communications, 15:7036). Their paper used Google Earth tiles which can't be redistributed; NAIP is the closest public substitute.

The eval picks a probability threshold on the validation set that achieves 99% precision, then reports recall at that threshold on the held-out test set (9,193 samples). The paper's reported verifier precision is ~99%; matching their recall validates the methodology transfer to NAIP.

"""Load iter 01 best.pt and run TTA inference + test eval only.

Use when train.py completed training but inference was interrupted.
"""
import sys
from pathlib import Path
import torch

sys.path.insert(0, str(Path(__file__).parent))
from train import UNet, infer_full, test_eval, OUTDIR, DEVICE, N_CH, N_CLASSES


def main():
    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    print(f"Loaded best from ep {ck['epoch']} (miou={ck['miou_pit']:.3f})")
    model = UNet(in_ch=N_CH, n_classes=N_CLASSES, base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    mu = ck["mu"]; sd = ck["sd"]
    print(f"Running TTA inference...")
    _, argmax = infer_full(model, mu, sd)
    test_eval(argmax)
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()

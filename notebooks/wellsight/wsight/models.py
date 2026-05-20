"""Segmentation models and checkpoint helpers.

- UNet:   the custom 4-level / base-32 U-Net from baseline + iter 01.
- make_smp_unet: factory wrapping segmentation_models_pytorch.Unet, used by iter 02+.
- load_segmentation_checkpoint: convenience for inference scripts.
"""
from pathlib import Path
import torch
import torch.nn as nn


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    """Custom 4-level U-Net.

    Same architecture used by baseline (`_pit_unet_v2`) and iter 01.  ~8 M params at
    base=32, in_ch=7, n_classes=3.  16x max downsampling preserves fine spatial
    detail relative to the SMP-ResNet34 path which downsamples 32x.
    """

    def __init__(self, in_ch: int = 7, n_classes: int = 3, base: int = 32):
        super().__init__()
        self.d1 = _conv_block(in_ch, base)
        self.d2 = _conv_block(base, base * 2)
        self.d3 = _conv_block(base * 2, base * 4)
        self.d4 = _conv_block(base * 4, base * 8)
        self.bot = _conv_block(base * 8, base * 16)
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.u4 = _conv_block(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.u3 = _conv_block(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.u2 = _conv_block(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.u1 = _conv_block(base * 2, base)
        self.out = nn.Conv2d(base, n_classes, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        d1 = self.d1(x)
        d2 = self.d2(self.pool(d1))
        d3 = self.d3(self.pool(d2))
        d4 = self.d4(self.pool(d3))
        b = self.bot(self.pool(d4))
        u4 = self.u4(torch.cat([self.up4(b), d4], dim=1))
        u3 = self.u3(torch.cat([self.up3(u4), d3], dim=1))
        u2 = self.u2(torch.cat([self.up2(u3), d2], dim=1))
        u1 = self.u1(torch.cat([self.up1(u2), d1], dim=1))
        return self.out(u1)


def make_smp_unet(encoder_name: str = "resnet34",
                  encoder_weights: str | None = "imagenet",
                  in_channels: int = 7,
                  classes: int = 3):
    """Build a segmentation_models_pytorch U-Net with the given encoder.

    Pass encoder_weights=None when reloading from a state_dict (the encoder
    weights are already in the checkpoint; downloading ImageNet weights again
    on every load is wasteful).
    """
    import segmentation_models_pytorch as smp
    return smp.Unet(encoder_name=encoder_name, encoder_weights=encoder_weights,
                    in_channels=in_channels, classes=classes)


def load_segmentation_checkpoint(ckpt_path: str | Path, device: torch.device):
    """Load a wsight-trained checkpoint and return (model, mu, sd, metadata).

    Reads the `encoder` field if present (SMP) or assumes custom UNet otherwise.
    Sets the model to eval mode.
    """
    ck = torch.load(Path(ckpt_path), map_location=device, weights_only=False)
    n_ch = len(ck["channels"])
    n_classes = int(ck.get("n_classes", 3))
    encoder = ck.get("encoder")
    if encoder:
        model = make_smp_unet(encoder_name=encoder, encoder_weights=None,
                              in_channels=n_ch, classes=n_classes)
    else:
        model = UNet(in_ch=n_ch, n_classes=n_classes, base=32)
    model.load_state_dict(ck["state_dict"])
    model.to(device).eval()

    import numpy as np
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    meta = {
        "channels": ck["channels"],
        "encoder": encoder,
        "n_classes": n_classes,
        "patch": int(ck.get("patch", 256)),
        "epoch": int(ck.get("epoch", 0)),
        "miou_pit": float(ck.get("miou_pit", 0.0)) if "miou_pit" in ck else None,
        "iou_plat": float(ck.get("iou_plat", 0.0)) if "iou_plat" in ck else None,
        "iou_road": float(ck.get("iou_road", 0.0)) if "iou_road" in ck else None,
    }
    return model, mu, sd, meta

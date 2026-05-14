"""U-Net pit detector on geomorphon + terrain derivative stack.

Input channels (per tile, 1m resolution):
  - lrm_5, lrm_11, tpi_05, tpi_15, openness_neg, slope, hillshade
  - geomorphon_enc_5, geomorphon_enc_8, geomorphon_enc_12

Target: binary mask from annotated pit locations (radius = 4 cells = 4m)

Architecture: lightweight U-Net (4 levels, 32-base filters) sized for
a GTX 1070 Ti (8 GB VRAM). Trained on 128x128 patches with heavy
augmentation (flips, rotations, brightness jitter).

Outputs:
  data/derivatives/pit_unet_pred_<tile>.tif   (probability raster)
  data/derivatives/pit_unet_model.pt          (trained weights)
  data/derivatives/pit_unet_metrics.txt       (performance summary)
"""
import numpy as np, rasterio, geopandas as gpd
from pathlib import Path
from scipy.spatial import cKDTree
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import warnings, time
warnings.filterwarnings('ignore')

DERIV = Path('data/derivatives')
ANNO = Path('data/derivatives/annotations')
CRS = 'EPSG:6346'
RES = 1.0

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Device: {DEVICE}')

# ============================================================
# CONFIG
# ============================================================
PATCH_SIZE = 128
PIT_RADIUS_CELLS = 4
CHANNELS = [
    'lrm_5', 'lrm_11', 'tpi_05', 'tpi_15',
    'openness_neg', 'slope', 'hillshade',
    'geomorphon_enc_5', 'geomorphon_enc_8', 'geomorphon_enc_12',
]
N_CHANNELS = len(CHANNELS)
BASE_FILTERS = 32
EPOCHS = 60
BATCH_SIZE = 16
LR = 1e-3
POS_WEIGHT = 20.0  # heavy weight on pit pixels (they're rare)

TILES = {'9t': '_9t_1m.tif', 'mk5': '_mk5_1m.tif', 'mkf': '_mkf_1m.tif'}

# ============================================================
# DATA LOADING
# ============================================================
def load_tile_stack(suffix):
    arrays = []
    for ch in CHANNELS:
        path = DERIV / f'{ch}{suffix}'
        if not path.exists():
            print(f'  WARNING: {path.name} missing')
            return None, None, None
        with rasterio.open(path) as ds:
            a = ds.read(1).astype(np.float32)
            nd = ds.nodata
            if nd is not None:
                a = np.where(a == nd, np.nan, a)
            arrays.append(a)
            bounds = ds.bounds
            shape = ds.shape
    stack = np.stack(arrays, axis=0)  # (C, H, W)
    return stack, bounds, shape


def make_pit_mask(bounds, shape, pits_gdf):
    H, W = shape
    X0, Y1 = bounds.left, bounds.top
    mask = np.zeros((H, W), dtype=np.float32)
    in_tile = pits_gdf.cx[bounds.left:bounds.right, bounds.bottom:bounds.top]
    for _, row in in_tile.iterrows():
        r = int(round((Y1 - row.geometry.y) / RES))
        c = int(round((row.geometry.x - X0) / RES))
        rr, cc = np.ogrid[max(0, r-PIT_RADIUS_CELLS):min(H, r+PIT_RADIUS_CELLS+1),
                          max(0, c-PIT_RADIUS_CELLS):min(W, c+PIT_RADIUS_CELLS+1)]
        dist = np.sqrt((rr - r)**2 + (cc - c)**2)
        mask[max(0, r-PIT_RADIUS_CELLS):min(H, r+PIT_RADIUS_CELLS+1),
             max(0, c-PIT_RADIUS_CELLS):min(W, c+PIT_RADIUS_CELLS+1)] = np.where(
            dist <= PIT_RADIUS_CELLS, 1.0, mask[
                max(0, r-PIT_RADIUS_CELLS):min(H, r+PIT_RADIUS_CELLS+1),
                max(0, c-PIT_RADIUS_CELLS):min(W, c+PIT_RADIUS_CELLS+1)])
    return mask


# ============================================================
# DATASET
# ============================================================
class PitPatchDataset(Dataset):
    def __init__(self, tile_stacks, tile_masks, patches_per_epoch=2000, augment=True):
        self.stacks = tile_stacks  # list of (C, H, W) arrays
        self.masks = tile_masks    # list of (H, W) arrays
        self.patches_per_epoch = patches_per_epoch
        self.augment = augment
        self.ps = PATCH_SIZE

        # Precompute pit locations for balanced sampling
        self.pit_locs = []  # (tile_idx, r, c)
        self.bg_tiles = []  # tile indices with enough room for random patches
        for t, mask in enumerate(self.masks):
            H, W = mask.shape
            if H >= self.ps and W >= self.ps:
                self.bg_tiles.append(t)
            rs, cs = np.where(mask > 0)
            for r, c in zip(rs, cs):
                if r >= self.ps//2 and r < H - self.ps//2 and c >= self.ps//2 and c < W - self.ps//2:
                    self.pit_locs.append((t, r, c))

        print(f'  Dataset: {len(self.pit_locs)} pit pixel locations across {len(self.stacks)} tiles')

    def __len__(self):
        return self.patches_per_epoch

    def __getitem__(self, idx):
        # 50% chance: center on a pit, 50% chance: random location
        if len(self.pit_locs) > 0 and np.random.rand() < 0.5:
            ti, cr, cc = self.pit_locs[np.random.randint(len(self.pit_locs))]
            # Add jitter so the pit isn't always dead center
            cr += np.random.randint(-self.ps//4, self.ps//4 + 1)
            cc += np.random.randint(-self.ps//4, self.ps//4 + 1)
        else:
            ti = self.bg_tiles[np.random.randint(len(self.bg_tiles))]
            H, W = self.stacks[ti].shape[1:]
            cr = np.random.randint(self.ps//2, H - self.ps//2)
            cc = np.random.randint(self.ps//2, W - self.ps//2)

        stack = self.stacks[ti]
        mask = self.masks[ti]
        H, W = stack.shape[1:]

        r1 = np.clip(cr - self.ps//2, 0, H - self.ps)
        c1 = np.clip(cc - self.ps//2, 0, W - self.ps)
        r2, c2 = r1 + self.ps, c1 + self.ps

        patch = stack[:, r1:r2, c1:c2].copy()
        label = mask[r1:r2, c1:c2].copy()

        # Replace NaN with 0 in each channel
        np.nan_to_num(patch, copy=False, nan=0.0)

        # Augmentation
        if self.augment:
            k = np.random.randint(4)
            if k > 0:
                patch = np.rot90(patch, k, axes=(1, 2)).copy()
                label = np.rot90(label, k).copy()
            if np.random.rand() > 0.5:
                patch = np.flip(patch, axis=1).copy()
                label = np.flip(label, axis=0).copy()
            if np.random.rand() > 0.5:
                patch = np.flip(patch, axis=2).copy()
                label = np.flip(label, axis=1).copy()
            # Brightness jitter per channel
            for ch in range(patch.shape[0]):
                patch[ch] *= (0.9 + 0.2 * np.random.rand())

        return torch.from_numpy(patch), torch.from_numpy(label[np.newaxis])


# ============================================================
# U-NET MODEL
# ============================================================
class ConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )
    def forward(self, x):
        return self.block(x)


class UNet(nn.Module):
    def __init__(self, in_channels, base=32):
        super().__init__()
        # Encoder
        self.enc1 = ConvBlock(in_channels, base)
        self.enc2 = ConvBlock(base, base*2)
        self.enc3 = ConvBlock(base*2, base*4)
        self.enc4 = ConvBlock(base*4, base*8)
        # Bottleneck
        self.bottleneck = ConvBlock(base*8, base*16)
        # Decoder
        self.up4 = nn.ConvTranspose2d(base*16, base*8, 2, stride=2)
        self.dec4 = ConvBlock(base*16, base*8)
        self.up3 = nn.ConvTranspose2d(base*8, base*4, 2, stride=2)
        self.dec3 = ConvBlock(base*8, base*4)
        self.up2 = nn.ConvTranspose2d(base*4, base*2, 2, stride=2)
        self.dec2 = ConvBlock(base*4, base*2)
        self.up1 = nn.ConvTranspose2d(base*2, base, 2, stride=2)
        self.dec1 = ConvBlock(base*2, base)
        self.out_conv = nn.Conv2d(base, 1, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        b = self.bottleneck(self.pool(e4))
        d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        return self.out_conv(d1)


# ============================================================
# TRAINING
# ============================================================
def dice_loss(pred, target, smooth=1.0):
    pred_sig = torch.sigmoid(pred)
    inter = (pred_sig * target).sum()
    union = pred_sig.sum() + target.sum()
    return 1.0 - (2.0 * inter + smooth) / (union + smooth)


def combined_loss(pred, target, pos_weight):
    bce = F.binary_cross_entropy_with_logits(
        pred, target, pos_weight=torch.tensor([pos_weight], device=pred.device))
    dl = dice_loss(pred, target)
    return bce + dl


def train_epoch(model, loader, optimizer, pos_weight):
    model.train()
    total_loss = 0
    for patches, labels in loader:
        patches = patches.to(DEVICE)
        labels = labels.to(DEVICE)
        optimizer.zero_grad()
        preds = model(patches)
        loss = combined_loss(preds, labels, pos_weight)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / len(loader)


@torch.no_grad()
def eval_model(model, loader, pos_weight):
    model.eval()
    total_loss = 0
    for patches, labels in loader:
        patches = patches.to(DEVICE)
        labels = labels.to(DEVICE)
        preds = model(patches)
        loss = combined_loss(preds, labels, pos_weight)
        total_loss += loss.item()
    return total_loss / len(loader)


# ============================================================
# INFERENCE — full tile prediction with overlap
# ============================================================
@torch.no_grad()
def predict_tile(model, stack, patch_size=PATCH_SIZE, overlap=32):
    model.eval()
    C, H, W = stack.shape
    prob = np.zeros((H, W), dtype=np.float32)
    count = np.zeros((H, W), dtype=np.float32)
    step = patch_size - overlap

    # Normalize stack (same as training: NaN → 0)
    stack_clean = np.nan_to_num(stack, nan=0.0)

    for r in range(0, H - patch_size + 1, step):
        for c in range(0, W - patch_size + 1, step):
            patch = stack_clean[:, r:r+patch_size, c:c+patch_size]
            t = torch.from_numpy(patch[np.newaxis]).to(DEVICE)
            pred = torch.sigmoid(model(t)).cpu().numpy()[0, 0]
            prob[r:r+patch_size, c:c+patch_size] += pred
            count[r:r+patch_size, c:c+patch_size] += 1

    # Handle right/bottom edges
    if H % step != 0 or H - patch_size + 1 <= 0:
        for c in range(0, W - patch_size + 1, step):
            r = H - patch_size
            patch = stack_clean[:, r:r+patch_size, c:c+patch_size]
            t = torch.from_numpy(patch[np.newaxis]).to(DEVICE)
            pred = torch.sigmoid(model(t)).cpu().numpy()[0, 0]
            prob[r:r+patch_size, c:c+patch_size] += pred
            count[r:r+patch_size, c:c+patch_size] += 1
    if W % step != 0 or W - patch_size + 1 <= 0:
        for r in range(0, H - patch_size + 1, step):
            c = W - patch_size
            patch = stack_clean[:, r:r+patch_size, c:c+patch_size]
            t = torch.from_numpy(patch[np.newaxis]).to(DEVICE)
            pred = torch.sigmoid(model(t)).cpu().numpy()[0, 0]
            prob[r:r+patch_size, c:c+patch_size] += pred
            count[r:r+patch_size, c:c+patch_size] += 1

    # Average overlapping predictions
    count = np.maximum(count, 1)
    return prob / count


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    pits = gpd.read_file(ANNO / 'wellhead_pits.gpkg').to_crs(CRS)
    print(f'Annotated pits: {len(pits)}')

    # Load all tiles
    print('\nLoading tiles...')
    tile_stacks = []
    tile_masks = []
    tile_metas = []  # (tag, suffix, bounds, shape, profile)
    per_channel_stats = {ch: {'vals': []} for ch in CHANNELS}

    for tag, suffix in TILES.items():
        print(f'  {tag}...', end=' ')
        stack, bounds, shape = load_tile_stack(suffix)
        if stack is None:
            print('SKIPPED (missing channels)')
            continue
        mask = make_pit_mask(bounds, shape, pits)
        pit_count = int(mask.max() > 0) and int(
            pits.cx[bounds.left:bounds.right, bounds.bottom:bounds.top].shape[0])
        print(f'{shape[0]}x{shape[1]}, {pit_count} pits, '
              f'{mask.sum():.0f} pit pixels')

        # Collect stats for normalization
        for i, ch in enumerate(CHANNELS):
            valid = stack[i][np.isfinite(stack[i])]
            if len(valid) > 0:
                per_channel_stats[ch]['vals'].append(valid)

        # Store profile for saving predictions later
        with rasterio.open(DERIV / f'dem{suffix}') as ds:
            profile = ds.profile.copy()
        tile_metas.append((tag, suffix, bounds, shape, profile))
        tile_stacks.append(stack)
        tile_masks.append(mask)

    # Per-channel normalization (z-score)
    print('\nComputing per-channel normalization...')
    ch_means = np.zeros(N_CHANNELS, dtype=np.float32)
    ch_stds = np.zeros(N_CHANNELS, dtype=np.float32)
    for i, ch in enumerate(CHANNELS):
        all_vals = np.concatenate(per_channel_stats[ch]['vals'])
        ch_means[i] = np.mean(all_vals)
        ch_stds[i] = np.std(all_vals)
        if ch_stds[i] < 1e-6:
            ch_stds[i] = 1.0
        print(f'  {ch:25s}  mean={ch_means[i]:.3f}  std={ch_stds[i]:.3f}')

    # Apply normalization
    for stack in tile_stacks:
        for i in range(N_CHANNELS):
            stack[i] = (stack[i] - ch_means[i]) / ch_stds[i]

    # Split: use mk5 as validation if available, else random split
    if len(tile_stacks) >= 2:
        # Use last tile as validation
        train_stacks = tile_stacks[:-1]
        train_masks = tile_masks[:-1]
        val_stacks = [tile_stacks[-1]]
        val_masks = [tile_masks[-1]]
        val_tag = tile_metas[-1][0]
        print(f'\nTrain tiles: {[m[0] for m in tile_metas[:-1]]}, Val tile: {val_tag}')
    else:
        train_stacks = tile_stacks
        train_masks = tile_masks
        val_stacks = tile_stacks
        val_masks = tile_masks
        print('\nSingle tile — training and validating on same data')

    train_ds = PitPatchDataset(train_stacks, train_masks, patches_per_epoch=2000, augment=True)
    val_ds = PitPatchDataset(val_stacks, val_masks, patches_per_epoch=500, augment=False)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False,
                            num_workers=0, pin_memory=True)

    # Model
    model = UNet(in_channels=N_CHANNELS, base=BASE_FILTERS).to(DEVICE)
    param_count = sum(p.numel() for p in model.parameters())
    print(f'\nU-Net: {param_count:,} parameters, base={BASE_FILTERS}')

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=1e-5)

    # Training loop
    print(f'\nTraining for {EPOCHS} epochs...')
    best_val_loss = float('inf')
    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, POS_WEIGHT)
        val_loss = eval_model(model, val_loader, POS_WEIGHT)
        scheduler.step()
        elapsed = time.time() - t0

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save({
                'model_state_dict': model.state_dict(),
                'ch_means': ch_means,
                'ch_stds': ch_stds,
                'channels': CHANNELS,
                'epoch': epoch,
            }, str(DERIV / 'pit_unet_model.pt'))
            marker = ' *'
        else:
            marker = ''

        if epoch % 5 == 0 or epoch == 1:
            print(f'  epoch {epoch:3d}/{EPOCHS}  '
                  f'train={train_loss:.4f}  val={val_loss:.4f}  '
                  f'{elapsed:.1f}s{marker}')

    # Load best model
    ckpt = torch.load(str(DERIV / 'pit_unet_model.pt'), map_location=DEVICE, weights_only=False)
    model.load_state_dict(ckpt['model_state_dict'])
    print(f'\nBest model from epoch {ckpt["epoch"]}, val_loss={best_val_loss:.4f}')

    # Inference on all tiles
    print('\nRunning inference...')
    all_results = []
    for (tag, suffix, bounds, shape, profile), stack, mask in zip(
            tile_metas, tile_stacks, tile_masks):
        print(f'  {tag}...', end=' ')
        t0 = time.time()
        prob = predict_tile(model, stack)
        elapsed = time.time() - t0
        print(f'{elapsed:.1f}s')

        # Save probability raster
        out_profile = profile.copy()
        out_profile.update(dtype='float32', count=1, nodata=-1.0)
        out_path = DERIV / f'pit_unet_pred_{tag}.tif'
        with rasterio.open(out_path, 'w', **out_profile) as dst:
            # Mask NaN areas from original DEM
            dem_path = DERIV / f'dem{suffix}'
            with rasterio.open(dem_path) as dem_ds:
                dem = dem_ds.read(1)
                nd = dem_ds.nodata
                if nd is not None:
                    prob[dem == nd] = -1.0
                prob[np.isnan(dem)] = -1.0
            dst.write(prob.astype(np.float32), 1)
        print(f'    -> {out_path.name}')

        all_results.append((tag, bounds, shape, prob, mask))

    # Validation: check recall at pit locations
    print('\n--- Validation against annotated pits ---')
    pit_xy = np.array([[g.x, g.y] for g in pits.geometry])

    metrics_lines = []
    for tag, bounds, shape, prob, mask in all_results:
        X0, Y1 = bounds.left, bounds.top
        in_tile = pits.cx[bounds.left:bounds.right, bounds.bottom:bounds.top]
        if len(in_tile) == 0:
            continue

        scores = []
        for _, row in in_tile.iterrows():
            r = int(round((Y1 - row.geometry.y) / RES))
            c = int(round((row.geometry.x - X0) / RES))
            if 0 <= r < shape[0] and 0 <= c < shape[1]:
                scores.append(prob[r, c])

        scores = np.array(scores)
        valid = scores[scores >= 0]
        line = (f'  {tag}: {len(in_tile)} pits, '
                f'mean_prob={np.mean(valid):.3f}, '
                f'median_prob={np.median(valid):.3f}, '
                f'recall@0.3={int((valid>0.3).sum())}/{len(valid)}, '
                f'recall@0.5={int((valid>0.5).sum())}/{len(valid)}')
        print(line)
        metrics_lines.append(line)

    # Save metrics
    with open(DERIV / 'pit_unet_metrics.txt', 'w') as f:
        f.write(f'U-Net pit detector results\n')
        f.write(f'Channels: {CHANNELS}\n')
        f.write(f'Patch size: {PATCH_SIZE}, Pit radius: {PIT_RADIUS_CELLS}\n')
        f.write(f'Best epoch: {ckpt["epoch"]}, val_loss: {best_val_loss:.4f}\n\n')
        for line in metrics_lines:
            f.write(line + '\n')

    print(f'\nSaved: pit_unet_model.pt, pit_unet_pred_*.tif, pit_unet_metrics.txt')

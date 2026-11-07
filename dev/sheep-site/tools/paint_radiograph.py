#!/usr/bin/env python3
"""Paint a new radiographic plate inside the existing sheep silhouette.

The normal PNG is not rewritten. The x-ray alpha is copied from it exactly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NORMAL = ROOT / "assets" / "sheep-normal.png"
XRAY = ROOT / "assets" / "sheep-xray.png"
OLD_HASH = "e95f98ae25bf440f"


def capsule(density: np.ndarray, p0, p1, radius: float, gain: float = 1.0) -> None:
    h, w = density.shape
    p0 = np.asarray(p0, np.float32)
    p1 = np.asarray(p1, np.float32)
    vec = p1 - p0
    length = float(np.hypot(vec[0], vec[1])) + 1e-6
    direction = vec / length
    normal = np.array([-direction[1], direction[0]], np.float32)
    pad = int(radius) + 3
    x0 = max(0, int(min(p0[0], p1[0]) - pad))
    x1 = min(w, int(max(p0[0], p1[0]) + pad) + 1)
    y0 = max(0, int(min(p0[1], p1[1]) - pad))
    y1 = min(h, int(max(p0[1], p1[1]) + pad) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    relx = xx - p0[0]
    rely = yy - p0[1]
    t = np.clip((relx * direction[0] + rely * direction[1]) / length, 0, 1)
    cx = p0[0] + t * vec[0]
    cy = p0[1] + t * vec[1]
    dx = xx - cx
    dy = yy - cy
    dist = np.hypot(dx, dy)
    unit = dist / radius
    inside = unit <= 1.0
    # Smooth cross-section: dense cortex, softer marrow, no hard outline.
    cortex = np.exp(-((unit - 0.8) ** 2) / 0.016)
    marrow = np.exp(-(unit ** 2) / 0.36)
    light = 0.78 + 0.22 * np.clip((dx * normal[0] + dy * normal[1]) / max(radius, 1), -1, 1)
    value = (0.7 * marrow + 1.25 * cortex) * light * gain
    density[y0:y1, x0:x1] += np.where(unit <= 1.15, value, 0)


def disc(density: np.ndarray, center, rx: float, ry: float, angle: float, gain: float = 1.0) -> None:
    h, w = density.shape
    cx, cy = center
    pad = int(max(rx, ry)) + 3
    x0 = max(0, int(cx - pad))
    x1 = min(w, int(cx + pad) + 1)
    y0 = max(0, int(cy - pad))
    y1 = min(h, int(cy + pad) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    ang = np.deg2rad(angle)
    dx = xx - cx
    dy = yy - cy
    lx = dx * np.cos(ang) + dy * np.sin(ang)
    ly = -dx * np.sin(ang) + dy * np.cos(ang)
    unit = np.hypot(lx / rx, ly / ry)
    inside = unit <= 1
    cortex = np.exp(-((unit - 0.78) ** 2) / 0.02)
    marrow = np.exp(-(unit ** 2) / 0.34)
    light = 0.78 + 0.22 * np.clip(lx / max(rx, 1), -1, 1)
    value = (0.72 * marrow + 1.2 * cortex) * light * gain
    density[y0:y1, x0:x1] += np.where(unit <= 1.1, value, 0)


def darken(density: np.ndarray, center, rx: float, ry: float, amount: float = 0.72) -> None:
    h, w = density.shape
    cx, cy = center
    x0 = max(0, int(cx - rx - 2))
    x1 = min(w, int(cx + rx + 3))
    y0 = max(0, int(cy - ry - 2))
    y1 = min(h, int(cy + ry + 3))
    yy, xx = np.mgrid[y0:y1, x0:x1]
    unit = np.hypot((xx - cx) / rx, (yy - cy) / ry)
    keep = np.where(unit <= 1, 1 - amount * np.clip(1 - unit, 0, 1), 1)
    density[y0:y1, x0:x1] *= keep


def quad(p0, p1, p2, n=18):
    pts = []
    for t in np.linspace(0, 1, n):
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((float(x), float(y)))
    return pts


def tube(density, pts, r0, r1, gain=1.0):
    """One continuous bone along a curve, not a chain of outlined segments."""
    pts = np.asarray(pts, np.float32)
    if len(pts) < 2:
        return
    h, w = density.shape
    radius_max = max(r0, r1)
    pad = int(radius_max) + 4
    x0 = max(0, int(pts[:, 0].min()) - pad)
    x1 = min(w, int(pts[:, 0].max()) + pad + 1)
    y0 = max(0, int(pts[:, 1].min()) - pad)
    y1 = min(h, int(pts[:, 1].max()) + pad + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    nearest = np.full(yy.shape, 1e9, np.float32)
    travel = np.zeros(yy.shape, np.float32)
    light = np.zeros(yy.shape, np.float32)
    span = 0.0
    lengths = [float(np.hypot(*(pts[i + 1] - pts[i]))) for i in range(len(pts) - 1)]
    total = sum(lengths) + 1e-6
    walked = 0.0
    for i, length in enumerate(lengths):
        p0, p1 = pts[i], pts[i + 1]
        vec = p1 - p0
        direction = vec / (length + 1e-6)
        normal = np.array([-direction[1], direction[0]], np.float32)
        relx = xx - p0[0]
        rely = yy - p0[1]
        t = np.clip((relx * direction[0] + rely * direction[1]) / (length + 1e-6), 0, 1)
        cx = p0[0] + t * vec[0]
        cy = p0[1] + t * vec[1]
        dx = xx - cx
        dy = yy - cy
        dist = np.hypot(dx, dy)
        closer = dist < nearest
        nearest = np.where(closer, dist, nearest)
        travel = np.where(closer, (walked + t * length) / total, travel)
        light = np.where(closer, dx * normal[0] + dy * normal[1], light)
        walked += length
    radius = r0 + (r1 - r0) * travel
    unit = nearest / np.maximum(radius, 1)
    marrow = np.exp(-(unit ** 2) / 0.34)
    cortex = np.exp(-((unit - 0.8) ** 2) / 0.014)
    shade = 0.78 + 0.22 * np.clip(light / np.maximum(radius, 1), -1, 1)
    value = (0.7 * marrow + 1.25 * cortex) * shade * gain
    density[y0:y1, x0:x1] += np.where(unit <= 1.12, value, 0)


def paint_carrot(rgb: np.ndarray, mask: np.ndarray, dist: np.ndarray) -> None:
    """Photograph of a real carrot, placed in the abdomen and clipped to the wool."""
    src = np.array(Image.open(ROOT / "source" / "carrot.jpg").convert("RGB"))
    peak = src.max(axis=2).astype(np.float32)
    alpha = np.clip((peak - 12.0) / 22.0, 0, 1)
    alpha[peak < 16] = 0
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.45)
    cut = Image.fromarray(np.dstack([src, (alpha * 255).astype(np.uint8)]), "RGBA")
    target_h = 268
    cut = cut.resize((max(1, int(cut.width * target_h / cut.height)), target_h), Image.Resampling.LANCZOS)
    cut = cut.rotate(-16, expand=True, resample=Image.Resampling.BICUBIC)
    sprite = np.array(cut).astype(np.float32)
    sh, sw = sprite.shape[:2]
    cx, cy = 910, 1105
    x0, y0 = int(cx - sw / 2), int(cy - sh / 2)
    x1, y1 = x0 + sw, y0 + sh
    h, w = mask.shape
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = sw - max(0, x1 - w), sh - max(0, y1 - h)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    patch = sprite[sy0:sy1, sx0:sx1]
    # A softer belly behind the root, so it sits in the stomach.
    yy, xx = np.mgrid[y0:y1, x0:x1]
    cavity = np.exp(-(((xx - cx) / 92.0) ** 2 + ((yy - (cy + 18)) / 78.0) ** 2))
    under = rgb[y0:y1, x0:x1].astype(np.float32)
    under *= 1.0 - cavity[..., None] * 0.22
    cover = patch[:, :, 3] / 255.0
    cover *= np.clip(dist[y0:y1, x0:x1] / 16.0, 0, 1)
    cover *= mask[y0:y1, x0:x1]
    rgb[y0:y1, x0:x1] = np.clip(under * (1.0 - cover[..., None]) + patch[:, :, :3] * cover[..., None], 0, 255)


def main() -> None:
    normal = Image.open(NORMAL).convert("RGBA")
    arr = np.array(normal)
    alpha = arr[:, :, 3]
    mask = alpha > 32
    rgb = arr[:, :, :3].astype(np.float32)
    gray = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    gray = cv2.GaussianBlur(gray, (0, 0), 0.9)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    dist_n = dist / max(1.0, float(dist.max()))
    grain = gray - cv2.GaussianBlur(gray, (0, 0), 2.6)
    tone = np.clip(0.08 + (gray / 255.0) * 0.55 * (1.12 - 0.42 * dist_n) + grain / 280.0, 0.03, 1)
    tissue = np.zeros_like(rgb)
    tissue[:, :, 0] = 8 + tone * 46
    tissue[:, :, 1] = 18 + tone * 62
    tissue[:, :, 2] = 36 + tone * 78
    rng = np.random.default_rng(19)
    tissue += rng.normal(0, 2.4, tissue.shape) * (0.45 + dist_n[:, :, None])

    h, w = mask.shape
    bone = np.zeros((h, w), np.float32)

    # Spine: neck behind the skull, back under the topline, sacrum in the rump.
    spine = [(640, 880), (700, 740), (790, 620), (900, 530), (1020, 500), (1130, 560), (1190, 680)]
    for a, b in zip(spine, spine[1:]):
        capsule(bone, a, b, 22, 0.9)
    for i, p in enumerate(spine):
        disc(bone, p, 30, 22, -16 + i * 6, 1.05)
        ang = np.deg2rad(-80 + i * 7)
        tip = (p[0] + np.cos(ang) * 34, p[1] + np.sin(ang) * 28)
        capsule(bone, p, tip, 8, 0.75)

    for i in range(13):
        t = i / 12
        root = (720 + t * 400, 770 - t * 210)
        end = (root[0] - 30 - i * 5, root[1] + 190 + i * 14)
        ctrl = (root[0] - 150, root[1] + 100 + i * 5)
        tube(bone, quad(root, ctrl, end, 28), 16, 8, 1.05)
        # Far-side rib, offset and fainter, so the cage has depth.
        root2 = (root[0] + 28, root[1] + 18)
        end2 = (end[0] + 36, end[1] + 22)
        ctrl2 = (ctrl[0] + 18, ctrl[1] + 16)
        tube(bone, quad(root2, ctrl2, end2, 28), 11, 6, 0.48)
        disc(bone, root, 9, 7, 20, 0.7)

    # Sternum and costal cartilage, softer than cortical bone.
    tube(bone, quad((690, 980), (820, 1120), (980, 1185), 16), 15, 9, 0.55)
    disc(bone, (760, 980), 78, 120, -28, 0.42)
    disc(bone, (650, 1140), 46, 96, -22, 0.8)
    disc(bone, (910, 1100), 42, 90, 14, 0.75)

    disc(bone, (1125, 700), 92, 48, 16, 0.78)
    capsule(bone, (1040, 640), (1230, 620), 16, 0.85)
    capsule(bone, (1085, 720), (1230, 820), 14, 0.8)

    limbs = [
        [(620, 1260), (600, 1420), (588, 1565), (580, 1685), (590, 1775)],
        [(860, 1230), (845, 1400), (828, 1545), (812, 1655), (804, 1725)],
    ]
    for chain in limbs:
        radii = [22, 18, 15, 13, 16]
        for a, b, ra, rb in zip(chain, chain[1:], radii, radii[1:]):
            mid = ((a[0] + b[0]) / 2 - 4, (a[1] + b[1]) / 2)
            tube(bone, quad(a, mid, b, 10), ra, rb, 1.0)
        for p, r in zip(chain, radii):
            disc(bone, p, r + 4, r + 3, 0, 1.05)
        hoof = chain[-1]
        disc(bone, (hoof[0], hoof[1] + 10), 18, 12, 6, 0.9)

    disc(bone, (515, 870), 92, 74, -8, 1.0)
    disc(bone, (498, 980), 44, 50, 8, 0.88)
    tube(bone, quad((425, 970), (495, 1105), (610, 1035), 18), 12, 7, 0.95)
    for x in range(446, 604, 22):
        capsule(bone, (x, 1032), (x, 1084), 8.0, 1.25)
        capsule(bone, (x + 1, 1080), (x + 2, 1112), 4.2, 0.9)
    darken(bone, (462, 905), 22, 16, 0.88)
    darken(bone, (558, 892), 18, 14, 0.84)
    darken(bone, (500, 1005), 14, 20, 0.6)

    # Fine grain, then a tight unsharp so a phone loupe stays crisp.
    noise = rng.random((h // 2, w // 2)).astype(np.float32)
    noise = cv2.resize(noise, (w, h), interpolation=cv2.INTER_CUBIC)
    noise = cv2.GaussianBlur(noise, (0, 0), 0.55)
    soft = cv2.GaussianBlur(bone, (0, 0), 0.9)
    edge = np.clip(bone - cv2.GaussianBlur(bone, (0, 0), 2.0), 0, None)
    bone = soft * (0.84 + 0.28 * noise) + edge * 1.35
    bone *= mask
    film = 1.0 - np.exp(-np.clip(bone, 0, None) * 0.72)
    low = cv2.GaussianBlur(film, (0, 0), 1.35)
    film = np.clip(film + (film - low) * 1.05, 0, 1)

    k = film[..., None]
    bone_rgb = np.zeros_like(tissue)
    bone_rgb[:, :, 0] = 150 + film * 95
    bone_rgb[:, :, 1] = 190 + film * 60
    bone_rgb[:, :, 2] = 220 + film * 35
    out_rgb = tissue * (1 - k * 0.9) + bone_rgb * (k * 0.9)
    out_rgb = np.clip(out_rgb, 0, 255).astype(np.uint8)
    before = out_rgb.copy()
    paint_carrot(out_rgb, mask, dist)
    # Solid bone stays in front of the stomach so the root reads as inside.
    cover = np.clip((film - 0.55) / 0.35, 0, 1)[..., None]
    out_rgb = np.clip(out_rgb * (1.0 - cover) + before * cover, 0, 255).astype(np.uint8)
    out = np.dstack([out_rgb, alpha])
    out[alpha == 0] = 0
    if not np.array_equal(out[:, :, 3], alpha):
        raise SystemExit("alpha drifted")
    image = Image.fromarray(out, "RGBA")
    image.save(XRAY, "PNG")
    digest = hashlib.sha256(XRAY.read_bytes()).hexdigest()
    if digest.startswith(OLD_HASH):
        raise SystemExit("x-ray hash did not change")
    print("xray", digest[:16], XRAY.stat().st_size)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Isolate the user's sheep and paint a registered mechanical scan.

Both outputs share one canvas and one alpha mask, so the hero crosshair
reveals skeleton only where the sheep itself has pixels.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT_NORMAL = ROOT / "assets" / "sheep-normal.png"
OUT_XRAY = ROOT / "assets" / "sheep-xray.png"
PREVIEW = ROOT / "assets" / "sheep-preview.png"
CANVAS = (1600, 2000)


def find_photo() -> Path:
    names = ("sheep-side.jpg", "sheep-side.jpeg", "sheep-side.png")
    roots = [
        Path("/workspace/sheep-site/photos"),
        Path("/workspace/dev/sheep-site/source"),
        Path("/workspace"),
        Path("/tmp"),
        Path("/home/ubuntu/.cursor/projects/workspace/uploads"),
    ]
    deadline = time.time() + 20
    while True:
        for root in roots:
            if not root.exists():
                continue
            for name in names:
                hit = root / name
                if hit.is_file() and hit.stat().st_size > 10000:
                    return hit
            if root == Path("/workspace"):
                for hit in root.rglob("sheep-side.*"):
                    if hit.is_file() and hit.stat().st_size > 10000:
                        return hit
        if time.time() > deadline:
            break
        time.sleep(1)
    raise SystemExit("sheep-side.jpg was not found")


def fill_holes(alpha: np.ndarray) -> np.ndarray:
    binary = alpha > 24
    h, w = binary.shape
    bg = np.where(binary, 0, 255).astype(np.uint8)
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(bg, flood_mask, (0, 0), 128)
    # Also flood other corners in case the subject touches (0, 0).
    for seed in ((w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if bg[seed[1], seed[0]] == 255:
            cv2.floodFill(bg, flood_mask, seed, 128)
    holes = bg == 255
    out = alpha.copy()
    out[holes] = 255
    return out


def keep_largest(alpha: np.ndarray) -> np.ndarray:
    mask = (alpha > 24).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return alpha
    keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    cleaned = alpha.copy()
    cleaned[labels != keep] = 0
    return fill_holes(cleaned)


def isolate(path: Path) -> Image.Image:
    from rembg import new_session, remove

    session = new_session("u2net")
    raw = Image.open(path).convert("RGB")
    # Work at a size that keeps wool detail without exhausting memory.
    scale = min(1.0, 1800 / max(raw.size))
    if scale < 1:
        raw = raw.resize(
            (int(raw.width * scale), int(raw.height * scale)),
            Image.Resampling.LANCZOS,
        )
    cut = remove(raw, session=session).convert("RGBA")
    arr = np.array(cut)
    arr[:, :, 3] = keep_largest(arr[:, :, 3])
    # Knock back green fence/grass spill on semi-transparent wool.
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
    green = (rgb[:, :, 1] > rgb[:, :, 0] + 12) & (rgb[:, :, 1] > rgb[:, :, 2] + 8)
    spill = (green & (alpha[:, :, 0] < 0.98)).astype(np.float32)[..., None]
    rgb[:, :, 1] -= spill[:, :, 0] * 28
    rgb = np.clip(rgb, 0, 255)
    arr[:, :, :3] = rgb.astype(np.uint8)
    # Soften only the outermost matte so wool stays, halos go.
    soft = cv2.GaussianBlur(arr[:, :, 3], (0, 0), 0.6)
    arr[:, :, 3] = np.maximum(np.where(arr[:, :, 3] > 240, arr[:, :, 3], soft), 0)
    return Image.fromarray(arr, "RGBA")


def frame_subject(cut: Image.Image) -> Image.Image:
    arr = np.array(cut)
    ys, xs = np.where(arr[:, :, 3] > 12)
    if len(xs) == 0:
        raise SystemExit("cutout was empty")
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    # Keep a few source pixels of margin, but do not invent body past the crop.
    crop = cut.crop((x0, y0, x1 + 1, y1 + 1))
    ow, oh = crop.size
    # Pigeon opaque box is about 892×1745 on this same canvas. A side-on
    # sheep is wider, so width is the limit and the animal stays fully in frame.
    # Keep the animal in the central gap between the headlines, like the pigeon.
    max_w, max_h = 980, 1680
    scale = min(max_w / ow, max_h / oh)
    nw, nh = max(1, int(ow * scale)), max(1, int(oh * scale))
    resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ox = (CANVAS[0] - nw) // 2
    oy = (CANVAS[1] - nh) // 2 + 30
    canvas.alpha_composite(resized, (ox, oy))
    return canvas


def draw_camera(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float) -> None:
    body = [
        cx - 34 * s,
        cy - 26 * s,
        cx + 34 * s,
        cy + 26 * s,
    ]
    draw.rounded_rectangle(body, radius=6 * s, outline=(226, 242, 255, 230), width=max(2, int(3 * s)))
    draw.ellipse(
        [cx - 16 * s, cy - 16 * s, cx + 16 * s, cy + 16 * s],
        outline=(210, 230, 245, 240),
        width=max(2, int(3 * s)),
    )
    draw.ellipse(
        [cx - 7 * s, cy - 7 * s, cx + 7 * s, cy + 7 * s],
        fill=(186, 24, 18, 255),
    )
    draw.ellipse(
        [cx - 2.2 * s, cy - 2.2 * s, cx + 2.2 * s, cy + 2.2 * s],
        fill=(255, 220, 210, 255),
    )
    # Viewfinder hump.
    draw.rectangle(
        [cx - 10 * s, cy - 36 * s, cx + 8 * s, cy - 24 * s],
        outline=(226, 242, 255, 210),
        width=max(1, int(2 * s)),
    )


def mechanical_layer(normal: Image.Image) -> Image.Image:
    arr = np.array(normal)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]
    mask = alpha > 20
    if not np.any(mask):
        raise SystemExit("framed sheep has no pixels")

    gray = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    gray = cv2.GaussianBlur(gray, (0, 0), 1.2)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    dist_n = dist / max(1.0, float(dist.max()))
    # Thinner wool reads brighter, the way an X-ray plate does.
    tone = np.clip(0.55 + gray / 255.0 * 0.85 - dist_n * 0.55, 0.08, 1.0)
    tissue = np.zeros_like(rgb)
    tissue[:, :, 0] = 18 + tone * 78
    tissue[:, :, 1] = 42 + tone * 118
    tissue[:, :, 2] = 78 + tone * 150
    # Keep a little of the real wool grain so the scan is this animal.
    grain = (gray - cv2.GaussianBlur(gray, (0, 0), 3.5)) * 0.35
    tissue += grain[:, :, None]
    tissue = np.clip(tissue, 0, 255)

    skel = np.zeros(mask.shape, np.uint8)
    work = mask.astype(np.uint8) * 255
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(work):
        eroded = cv2.erode(work, element)
        skel = cv2.bitwise_or(skel, cv2.subtract(work, cv2.dilate(eroded, element)))
        work = eroded
    bone = cv2.dilate(skel, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    glow = cv2.GaussianBlur(bone, (0, 0), 2.2).astype(np.float32) / 255.0
    core = bone.astype(np.float32) / 255.0
    tissue[:, :, 0] = np.clip(tissue[:, :, 0] + glow * 80 + core * 150, 0, 255)
    tissue[:, :, 1] = np.clip(tissue[:, :, 1] + glow * 110 + core * 180, 0, 255)
    tissue[:, :, 2] = np.clip(tissue[:, :, 2] + glow * 130 + core * 200, 0, 255)

    plate = Image.fromarray(tissue.astype(np.uint8), "RGB").convert("RGBA")
    overlay = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    bw, bh = x1 - x0 + 1, y1 - y0 + 1

    # Torso columns: tall, and not the narrow head on the left.
    col_h = mask.sum(axis=0)
    torso_cols = np.where(col_h > col_h.max() * 0.42)[0]
    torso_cols = torso_cols[torso_cols > x0 + bw * 0.28]
    if len(torso_cols) > 8:
        spine_y = []
        for x in torso_cols[:: max(1, len(torso_cols) // 80)]:
            column = dist[:, x]
            yy = int(np.argmax(column))
            spine_y.append((int(x), yy))
        if len(spine_y) > 2:
            draw.line(spine_y, fill=(232, 246, 255, 210), width=4)
            # Ribs hang across the upper body, stopping before the legs.
            for i, (x, sy) in enumerate(spine_y[3:-3]):
                if i % 3:
                    continue
                rows = np.where(mask[:, x])[0]
                if len(rows) < 10:
                    continue
                top, bot = int(rows.min()), int(rows.max())
                reach = int((sy - top) * 0.92)
                draw.arc(
                    [x - reach, top + 4, x + reach, sy + reach * 0.15],
                    start=200,
                    end=340,
                    fill=(214, 236, 250, 180),
                    width=2,
                )
                _ = bot

    # Eye camera, in the head (left, upper).
    head = mask[:, x0 : x0 + int(bw * 0.34)]
    hys, hxs = np.where(head)
    if len(hxs):
        hx = x0 + int(np.median(hxs))
        hy = int(np.percentile(hys, 38))
        draw_camera(draw, hx, hy, 0.55)

    # Chest camera on the medial axis of the torso.
    if len(torso_cols):
        cx = int(np.median(torso_cols[: max(1, len(torso_cols) // 2)]))
        cy = int(np.argmax(dist[:, cx]))
        draw_camera(draw, cx, cy, 1.15)
        # Leads and a small lock, clipped later by the silhouette.
        draw.line([(cx, cy + 28), (cx, cy + 90), (cx - 18, cy + 120)], fill=(190, 220, 235, 180), width=2)
        draw.rounded_rectangle(
            [cx - 10, cy + 118, cx + 10, cy + 142],
            radius=2,
            outline=(220, 236, 248, 200),
            width=2,
        )
        draw.arc([cx - 8, cy + 104, cx + 8, cy + 124], 200, 340, fill=(220, 236, 248, 200), width=2)
        # A short run of circuit pads.
        for i, dx in enumerate((-48, -24, 24, 48)):
            px, py = cx + dx, cy + 18 + (i % 2) * 16
            draw.rectangle([px - 4, py - 3, px + 4, py + 3], outline=(160, 210, 190, 200), width=1)
            if i:
                draw.line([(cx, cy), (px, py)], fill=(120, 190, 170, 140), width=1)

    composed = plate.copy()
    composed.alpha_composite(overlay)
    out = np.array(composed)
    out[:, :, 3] = alpha
    out[alpha == 0] = 0
    return Image.fromarray(out, "RGBA")


def main() -> None:
    photo = Path(sys.argv[1]) if len(sys.argv) > 1 else find_photo()
    print("source", photo, photo.stat().st_size)
    source_copy = ROOT / "source" / "sheep-side.jpg"
    if photo.resolve() != source_copy.resolve():
        source_copy.write_bytes(photo.read_bytes())
    cut = isolate(photo)
    normal = frame_subject(cut)
    xray = mechanical_layer(normal)
    # Exact registration check.
    na = np.array(normal)[:, :, 3]
    xa = np.array(xray)[:, :, 3]
    if not np.array_equal(na, xa):
        raise SystemExit("x-ray alpha does not match the sheep silhouette")
    OUT_NORMAL.parent.mkdir(parents=True, exist_ok=True)
    normal.save(OUT_NORMAL, "PNG")
    xray.save(OUT_XRAY, "PNG")
    # Contact sheet on black, for review.
    sheet = Image.new("RGB", (1600, 1000), (0, 0, 0))
    small_n = normal.resize((800, 1000), Image.Resampling.LANCZOS)
    small_x = xray.resize((800, 1000), Image.Resampling.LANCZOS)
    sheet.paste(small_n, (0, 0), small_n)
    sheet.paste(small_x, (800, 0), small_x)
    sheet.save(PREVIEW, "PNG")
    ys, xs = np.where(na > 12)
    print(
        "opaque",
        int(xs.min()),
        int(ys.min()),
        int(xs.max()),
        int(ys.max()),
        "size",
        int(xs.max() - xs.min()),
        int(ys.max() - ys.min()),
    )
    print("wrote", OUT_NORMAL, OUT_XRAY)


if __name__ == "__main__":
    main()

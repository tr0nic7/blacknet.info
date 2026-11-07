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


def defringe(arr: np.ndarray) -> np.ndarray:
    """Pull the pale matte halo back into the wool color and tighten the edge."""
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float32)
    weight = (alpha > 210).astype(np.float32)
    for _ in range(6):
        blur_rgb = cv2.blur(rgb * weight[:, :, None], (7, 7))
        blur_w = cv2.blur(weight, (7, 7))
        filled = blur_rgb / np.maximum(blur_w[:, :, None], 1e-3)
        fringe = (alpha > 0) & (alpha < 230)
        rgb[fringe] = filled[fringe]
        weight = np.maximum(weight, ((alpha > 0) & (blur_w > 0)).astype(np.float32))
    # Drop the outermost faint pixels. Ears stay, the white rim goes.
    contracted = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=1)
    soft = cv2.GaussianBlur(contracted, (0, 0), 0.7)
    tightened = np.where(alpha > 235, alpha, np.minimum(alpha, soft))
    tightened[tightened < 28] = 0
    out = arr.copy()
    out[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[:, :, 3] = tightened.astype(np.uint8)
    return out


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
    arr = defringe(arr)
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


def vertical_runs(column: np.ndarray) -> list[tuple[int, int]]:
    runs = []
    start = None
    for i, on in enumerate(column):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(column) - 1))
    return runs


def mechanical_layer(normal: Image.Image) -> Image.Image:
    """Stylized spy-scan. Bones and hardware are drawn inside the sheep, not a color filter."""
    arr = np.array(normal)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]
    mask = alpha > 24
    if not np.any(mask):
        raise SystemExit("framed sheep has no pixels")

    gray = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    gray = cv2.GaussianBlur(gray, (0, 0), 1.1)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    dist_n = dist / max(1.0, float(dist.max()))
    grain = gray - cv2.GaussianBlur(gray, (0, 0), 2.2)
    # Keep this sheep's fleece in the plate, the way the pigeon scan still shows feathers.
    tone = np.clip(0.16 + (gray / 255.0) * 0.70 * (1.05 - dist_n * 0.28) + grain / 255.0 * 0.35, 0.05, 1.0)
    tissue = np.zeros_like(rgb)
    tissue[:, :, 0] = 16 + tone * 72
    tissue[:, :, 1] = 28 + tone * 96
    tissue[:, :, 2] = 46 + tone * 118
    tissue = np.clip(tissue, 0, 255)

    h, w = mask.shape
    body = np.zeros_like(mask)
    legs = np.zeros_like(mask)
    body_span = {}
    for x in range(w):
        runs = vertical_runs(mask[:, x])
        if not runs:
            continue
        longest = max(runs, key=lambda run: run[1] - run[0])
        body[longest[0] : longest[1] + 1, x] = True
        body_span[x] = longest
        for run in runs:
            if run != longest and run[0] > longest[0]:
                legs[run[0] : run[1] + 1, x] = True

    bone = np.zeros((h, w), np.uint8)
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    bw = x1 - x0 + 1

    # Spine sits inside the torso, under the topline, from the neck to the rump.
    torso_xs = [x for x, (top, bot) in body_span.items() if bot - top > bw * 0.18 and x > x0 + bw * 0.22]
    spine = []
    for x in torso_xs:
        top, bot = body_span[x]
        sy = int(top + (bot - top) * 0.18)
        if body[sy, x]:
            spine.append((x, sy))
    if len(spine) > 2:
        cv2.polylines(bone, [np.array(spine, np.int32)], False, 255, 5, cv2.LINE_AA)

    # A handful of solid ribs through the chest, not a dotted screen.
    chest_xs = [x for x in torso_xs if x0 + int(bw * 0.30) < x < x0 + int(bw * 0.60)]
    if chest_xs:
        picks = np.linspace(0, len(chest_xs) - 1, 7).astype(int)
        sternum = []
        for n, idx in enumerate(picks):
            x = int(chest_xs[idx])
            top, bot = body_span[x]
            sy = int(top + (bot - top) * 0.18)
            end = min(sy + 120, bot - 6)
            pts = []
            for t in np.linspace(0, 1, 24):
                yy = int(sy + (end - sy) * t)
                xx = int(round(x + np.sin(t * np.pi) * (8 + n % 3)))
                if 0 <= yy < h and 0 <= xx < w and body[yy, xx]:
                    pts.append((xx, yy))
            if len(pts) > 3:
                cv2.polylines(bone, [np.array(pts, np.int32)], False, 255, 3, cv2.LINE_AA)
                sternum.append(pts[-1])
        if len(sternum) > 2:
            cv2.polylines(bone, [np.array(sternum, np.int32)], False, 255, 3, cv2.LINE_AA)

    # Leg bones follow each limb.
    leg_count, leg_labels = cv2.connectedComponents((legs.astype(np.uint8) * 255), connectivity=8)
    cross = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    for label in range(1, leg_count):
        limb = np.where(leg_labels == label, 255, 0).astype(np.uint8)
        if int(cv2.countNonZero(limb)) < 80:
            continue
        work = limb.copy()
        skel = np.zeros_like(work)
        while cv2.countNonZero(work):
            eroded = cv2.erode(work, cross)
            skel = cv2.bitwise_or(skel, cv2.subtract(work, cv2.dilate(eroded, cross)))
            work = eroded
        bone = cv2.bitwise_or(bone, cv2.dilate(skel, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))))

    bone_f = bone.astype(np.float32) / 255.0
    glow = cv2.GaussianBlur(bone_f, (0, 0), 2.6)
    core = bone_f
    tissue[:, :, 0] = np.clip(tissue[:, :, 0] + glow * 90 + core * 170, 0, 255)
    tissue[:, :, 1] = np.clip(tissue[:, :, 1] + glow * 120 + core * 200, 0, 255)
    tissue[:, :, 2] = np.clip(tissue[:, :, 2] + glow * 140 + core * 220, 0, 255)

    plate = Image.fromarray(tissue.astype(np.uint8), "RGB").convert("RGBA")
    overlay = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    ink = (236, 246, 255, 230)

    # Skull in the head, inset so it reads as bone rather than an outline of the face.
    head_right = x0 + int(bw * 0.30)
    head = mask[:, x0:head_right]
    hys, hxs = np.where(head)
    eye = None
    if len(hxs):
        hx0, hx1 = x0 + int(hxs.min()), x0 + int(hxs.max())
        hy0, hy1 = int(hys.min()), int(hys.max())
        draw.ellipse(
            [hx0 + 18, hy0 + 10, hx1 - 8, hy0 + int((hy1 - hy0) * 0.58)],
            outline=ink,
            width=3,
        )
        jaw_y = hy0 + int((hy1 - hy0) * 0.72)
        draw.arc([hx0 + 10, hy0 + 20, hx1 - 4, jaw_y + 30], 20, 200, fill=ink, width=2)
        # The real eye is the darkest compact spot in the upper face.
        # Place the sensor on the eye, inward from the floppy ear.
        draw_camera(
            draw,
            hx0 + int((hx1 - hx0) * 0.64),
            hy0 + int((hy1 - hy0) * 0.40),
            0.42,
        )

    if spine:
        chest_pts = [p for p in spine if x0 + bw * 0.28 < p[0] < x0 + bw * 0.55]
        if chest_pts:
            cx, cy = chest_pts[len(chest_pts) // 2]
            cy = int(cy + 36)
            draw_camera(draw, cx, cy, 1.35)
            draw.line([(cx, cy + 34), (cx + 8, cy + 78)], fill=ink, width=2)
            draw.rounded_rectangle([cx - 16, cy + 76, cx + 22, cy + 104], radius=3, outline=(170, 220, 190, 220), width=2)
            for row in range(3):
                for col in range(4):
                    px = cx - 10 + col * 8
                    py = cy + 82 + row * 6
                    draw.point((px, py), fill=(150, 230, 170, 230))
            draw.line([(cx + 4, cy + 104), (cx + 4, cy + 132)], fill=ink, width=2)
            draw.rounded_rectangle([cx - 8, cy + 128, cx + 16, cy + 152], radius=2, outline=ink, width=2)
            draw.arc([cx - 6, cy + 116, cx + 14, cy + 136], 200, 340, fill=ink, width=2)

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

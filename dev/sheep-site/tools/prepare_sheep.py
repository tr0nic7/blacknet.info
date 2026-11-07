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
    contracted = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=2)
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
    """Detailed radiographic sheep. Bones are drawn to this pose and clipped to its alpha."""
    arr = np.array(normal)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]
    mask = alpha > 28
    if not np.any(mask):
        raise SystemExit("framed sheep has no pixels")

    gray = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    gray = cv2.GaussianBlur(gray, (0, 0), 0.8)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    dist_n = dist / max(1.0, float(dist.max()))
    grain = gray - cv2.GaussianBlur(gray, (0, 0), 2.4)
    tone = np.clip(0.10 + (gray / 255.0) * 0.62 * (1.08 - dist_n * 0.35) + grain / 255.0 * 0.28, 0.04, 1)
    tissue = np.zeros_like(rgb)
    tissue[:, :, 0] = 12 + tone * 58
    tissue[:, :, 1] = 22 + tone * 78
    tissue[:, :, 2] = 40 + tone * 96
    rng = np.random.default_rng(11)
    tissue += rng.normal(0, 3.2, tissue.shape) * (0.35 + dist_n[:, :, None] * 0.4)
    tissue = np.clip(tissue, 0, 255)

    h, w = mask.shape
    soft = np.zeros((h, w), np.uint8)
    hard = np.zeros((h, w), np.uint8)

    def ok(pt):
        x, y = int(pt[0]), int(pt[1])
        return 0 <= x < w and 0 <= y < h and mask[y, x]

    def snap(pt, reach=48):
        if ok(pt):
            return (int(pt[0]), int(pt[1]))
        x, y = int(pt[0]), int(pt[1])
        for rad in range(1, reach):
            for dy in range(-rad, rad + 1, 2):
                for dx in range(-rad, rad + 1, 2):
                    q = (x + dx, y + dy)
                    if ok(q):
                        return q
        return None

    def curve(p0, p1, p2, n=22):
        pts = []
        for t in np.linspace(0, 1, n):
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
            pts.append((int(round(x)), int(round(y))))
        return pts

    def paint(pts, thick, layer):
        kept = [p for p in pts if ok(p)]
        if len(kept) < 2:
            return
        cv2.polylines(layer, [np.array(kept, np.int32)], False, 255, thick, cv2.LINE_AA)

    def joint(pt, rad):
        p = snap(pt)
        if p is None:
            return
        cv2.circle(soft, p, rad + 4, 255, -1, cv2.LINE_AA)
        cv2.circle(hard, p, max(2, rad - 1), 255, 2, cv2.LINE_AA)
        cv2.circle(hard, p, max(1, rad // 3), 255, -1, cv2.LINE_AA)

    # Spine of this front-three-quarter pose: neck behind the skull,
    # back under the topline, sacrum toward the rounded rump.
    spine_raw = [
        (600, 860), (660, 740), (740, 620), (840, 530),
        (960, 490), (1080, 520), (1160, 600), (1210, 700),
    ]
    spine = [p for p in (snap(q) for q in spine_raw) if p]
    paint(spine, 16, soft)
    paint(spine, 7, hard)
    for i, p in enumerate(spine):
        cv2.ellipse(soft, p, (16, 11), -18 + i * 4, 0, 360, 255, -1, cv2.LINE_AA)
        cv2.ellipse(hard, p, (16, 11), -18 + i * 4, 0, 360, 255, 2, cv2.LINE_AA)
        # Dorsal process.
        ang = np.deg2rad(-70 + i * 6)
        tip = (int(p[0] + np.cos(ang) * 18), int(p[1] + np.sin(ang) * 18))
        paint([p, tip], 3, hard)

    # Curved ribs from the thoracic vertebrae down into the chest.
    rib_roots = spine[1:8]
    for i, root in enumerate(rib_roots):
        drop = 120 + i * 36
        bow = 90 + i * 12
        end = snap((root[0] - 40 - i * 18, root[1] + drop))
        if end is None:
            continue
        ctrl = (root[0] - bow, root[1] + drop * 0.45)
        rib = curve(root, ctrl, end)
        paint(rib, 11, soft)
        paint(rib, 4, hard)
        # A shorter mate just beside it, so the cage reads as pairs.
        mate_end = snap((end[0] + 22, end[1] - 10))
        if mate_end:
            mate = curve((root[0] + 16, root[1] + 8), (ctrl[0] + 24, ctrl[1]), mate_end)
            paint(mate, 3, hard)

    # Sternum linking the lower rib ends, slightly inside the chest.
    sternum = [snap((640 + i * 18, 980 + i * 22)) for i in range(6)]
    paint([p for p in sternum if p], 5, hard)

    # Shoulder blades: long flat bones over each forelimb, not geometric kites.
    for center, angle in (((640, 1160), -28), ((900, 1120), 18)):
        c = snap(center, 50)
        if c is None:
            continue
        cv2.ellipse(soft, c, (28, 70), angle, 0, 360, 255, -1, cv2.LINE_AA)
        cv2.ellipse(hard, c, (28, 70), angle, 0, 360, 255, 3, cv2.LINE_AA)
        cv2.ellipse(hard, c, (10, 40), angle, 0, 360, 255, 2, cv2.LINE_AA)

    # Pelvis in the rounded rump: sacral bar plus two ilium wings.
    sacrum = [p for p in (snap(q) for q in ((1040, 560), (1140, 620), (1180, 740))) if p]
    paint(sacrum, 10, soft)
    paint(sacrum, 4, hard)
    for wing in (
        curve((1080, 600), (1220, 540), (1230, 700)),
        curve((1100, 680), (1220, 760), (1140, 860)),
    ):
        paint(wing, 12, soft)
        paint(wing, 4, hard)
    joint((1120, 760), 12)

    # Foreleg bones and joints, traced to the hooves that are actually in frame.
    for chain, rads in (
        ([(620, 1240), (600, 1400), (590, 1540), (575, 1660), (580, 1760)], [14, 11, 9, 8, 10]),
        ([(860, 1200), (840, 1380), (820, 1540), (800, 1660), (790, 1740)], [14, 11, 9, 8, 10]),
    ):
        pts = [snap(q, 55) for q in chain]
        pts = [p for p in pts if p]
        for a, b, ra, rb in zip(pts, pts[1:], rads, rads[1:]):
            paint([a, b], max(ra, rb) + 6, soft)
            paint([a, b], max(6, (ra + rb) // 2), hard)
        for p, r in zip(pts, rads):
            joint(p, r)

    # Skull, jaw, orbits and nasal opening on the face.
    skull = snap((505, 880))
    if skull:
        cv2.ellipse(soft, skull, (72, 58), -8, 0, 360, 255, -1, cv2.LINE_AA)
        cv2.ellipse(hard, skull, (72, 58), -8, 0, 360, 255, 3, cv2.LINE_AA)
        # Cranial sutures, not a face.
        cv2.line(hard, (skull[0] - 10, skull[1] - 40), (skull[0] + 8, skull[1] + 20), 255, 2, cv2.LINE_AA)
        for orbit, rad in (((468, 905), 15), ((548, 895), 13)):
            o = snap(orbit, 28)
            if o:
                cv2.circle(soft, o, rad, 180, -1, cv2.LINE_AA)
                cv2.circle(hard, o, rad, 255, 3, cv2.LINE_AA)
                cv2.circle(hard, o, 4, 255, -1, cv2.LINE_AA)
        nose = snap((508, 990))
        if nose:
            cv2.ellipse(hard, nose, (10, 18), 8, 0, 360, 255, 2, cv2.LINE_AA)
        jaw = curve((440, 960), (500, 1045), (590, 990))
        paint(jaw, 5, hard)
        paint(curve((455, 1005), (510, 1035), (565, 1000)), 2, hard)

    # Volume: soft bone bodies under crisp cortices.
    shade = cv2.GaussianBlur(soft, (0, 0), 3.5).astype(np.float32) / 255.0
    cortex = hard.astype(np.float32) / 255.0
    cortex = cv2.GaussianBlur(cortex, (0, 0), 0.6)
    tissue[:, :, 0] = np.clip(tissue[:, :, 0] + shade * 70 + cortex * 150, 0, 255)
    tissue[:, :, 1] = np.clip(tissue[:, :, 1] + shade * 96 + cortex * 185, 0, 255)
    tissue[:, :, 2] = np.clip(tissue[:, :, 2] + shade * 120 + cortex * 210, 0, 255)

    plate = Image.fromarray(tissue.astype(np.uint8), "RGB").convert("RGBA")
    # One surveillance camera in the chest, the original scan's hardware note.
    overlay = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cam = snap((760, 860))
    if cam:
        draw_camera(draw, cam[0], cam[1], 1.05)
    composed = plate.copy()
    composed.alpha_composite(overlay)
    out = np.array(composed)
    out[:, :, 3] = alpha
    out[alpha == 0] = 0
    return Image.fromarray(out, "RGBA")


def main() -> None:
    photo = Path(sys.argv[1]) if len(sys.argv) > 1 else find_photo()
    print("source", photo, photo.stat().st_size)
    source_name = "sheep-front.jpg" if "front" in photo.name.lower() else "sheep-side.jpg"
    source_copy = ROOT / "source" / source_name
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

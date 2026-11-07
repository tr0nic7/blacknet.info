# Wollwölklein vom Berg

Static hero. HTML, CSS, JavaScript, and local files. No Node runtime and no remote requests.

Image, stylesheet, script, and font URLs carry a version query so a warm browser does not reuse a seven-day cache of an older file. The sheep pictures themselves are unchanged: `sheep-normal.png?v=116eeb948f4f6912` and `sheep-xray.png?v=e95f98ae25bf440f`.

Open `index.html` through any static server. For nginx, point a location at this directory.

```bash
cd dev/sheep-site
python3 -m http.server 8765
```

## Interaction

The lens follows the pointer with no click and hides when the pointer leaves. On a phone, press and drag; the lens sits above the finger and closes on release. Touching the sheep does not scroll the page. The document ends at the arrow.

## Assets

The page ends at the down arrow under the hero. `assets/sheep-normal.png` and `assets/sheep-xray.png` share one alpha mask, cut from `source/sheep-front.jpg`, which shows the whole animal. The side photo crops the rump at the frame, so it is not the hero. Rebuild with:

```bash
python3 tools/prepare_sheep.py source/sheep-front.jpg
```

The headline face is IBM Plex Mono Medium, the font the original page served under the name `custom_186012`. It is included under the SIL Open Font License; see `assets/fonts/OFL.txt`.

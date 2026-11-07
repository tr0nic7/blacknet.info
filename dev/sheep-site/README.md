# Is That Sheep a Fed?

Static recreation of the ReadyMag page “Is That Pigeon a Fed?”, with the pigeon replaced by the supplied sheep. The page is HTML, CSS, JavaScript, and local files. It does not need Node, and it does not call any analytics or remote hosts.

Open `index.html` through any static server. For nginx, point a location at this directory.

```bash
cd dev/sheep-site
python3 -m http.server 8765
```

## Interaction

Desktop (viewport at least 600px wide): the hero lens follows the pointer with no click. A circular orange crosshair and a soft trail reveal the mechanical scan, and only sheep pixels inside the circle change. Releasing the button leaves the lens up while the pointer remains in the hero. Leaving the hero hides it.

Phone (under 600px): press the sheep and drag. The lens sits above the finger. Lifting the finger closes the reveal. Touching the sheep does not scroll the page; scrolling still works below the hero.

The evidence desk accepts a local image and never uploads it.

## Assets

The page ends at the down arrow under the hero. `assets/sheep-normal.png` and `assets/sheep-xray.png` share one alpha mask, cut from `source/sheep-front.jpg`, which shows the whole animal. The side photo crops the rump at the frame, so it is not the hero. Rebuild with:

```bash
python3 tools/prepare_sheep.py source/sheep-front.jpg
```

The headline face is IBM Plex Mono Medium, the font the original page served under the name `custom_186012`. It is included under the SIL Open Font License; see `assets/fonts/OFL.txt`.

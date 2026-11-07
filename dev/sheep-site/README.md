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

`assets/sheep-normal.png` and `assets/sheep-xray.png` must be the same canvas and the same alpha mask. Generate them from the side photo:

```bash
python3 tools/prepare_sheep.py /path/to/sheep-side.jpg
```

The script copies the photo to `source/sheep-side.jpg`, cuts out the grass and fence, and paints the mechanical scan inside that exact silhouette.

The headline face is IBM Plex Mono Medium, the font the original page served under the name `custom_186012`. It is included under the SIL Open Font License; see `assets/fonts/OFL.txt`.

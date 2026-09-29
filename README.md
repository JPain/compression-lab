# Image Compression Lab

What happens to a 7.5 MB 4K screenshot on its way to 128 KB, and how the
settings for a self-hosted image host were chosen: WebP, JPEG, AVIF and JPEG XL
compared side by side, scored with a perceptual metric, with a viewer that lets
you hold to swap each setting against the lossless original.

**Read it:** the write-up is [Learning about image compression: chroma subsampling, with interactive demos](https://jpain.io/chroma-subsampling/)
on James Pain's blog, and this page is hosted beside it at
[jpain.io/chroma-subsampling/lab/](https://jpain.io/chroma-subsampling/lab/).
The page is the comparison tool; the post is the explanation. Or run it locally:

```sh
cd docs && python3 -m http.server 8000   # then open http://localhost:8000
```

(It has to be served, not opened as a file, because it loads `data.json`.)

The page loads nothing from other sites (IBM Plex is in `docs/fonts/`) and uses no
inline scripts or `style="…"` attributes, so it works under a strict
Content-Security-Policy.

**Embed mode:** `?embed=<row id>[,<row id>]&region=<van|sky|tower|trees|gauges>` shows
only those rows, with region buttons and a link to the full page, for a blog post to
frame. It posts `{labHeight: n}` to its parent page so the frame can fit its content.
Row ids are in `docs/data.json` (e.g. `avif_q60_444`).

## What's inside

| | |
|---|---|
| `docs/` | The page (GitHub Pages serves this folder): `index.html`, `lab.js`, `style.css`, and everything generated |
| `docs/data.json` | Every setting's size, score and encode time, the size budget, the metric comparison and tool versions |
| `docs/tiles/` | Lossless PNG crops: five regions × 35 settings, plus references |
| `docs/figs/` | The brightness/colour step images (the blog post's figures are cut from these and `tiles/`) |
| `docs/curve.json` | Size against score across quality settings for the host's four formats: the post's chart |
| `docs/fonts/` | IBM Plex (SIL Open Font License) |
| `tools/generate.py` | Rebuilds the page's data, tiles and figures from one screenshot |
| `tools/curve.py` | Rebuilds `curve.json`; JPEG XL can run on the host (`--jxl-ssh`), because cjxl versions differ |

## Findings, in brief

* **Where the bytes go:** 24.9 MB of raw pixels → 7.49 MB lossless PNG →
  1.90 MB resized to 1920 × 1080 → **112 KB** lossy AVIF. The last step is 16.5×.
* **Measure with SSIMULACRA 2, not SSIM.** SSIM misranked formats badly here:
  it scored JPEG XL at "visually lossless" barely above plain JPEG.
* **Halving colour caps quality.** Standard JPEG, lossy WebP and default AVIF
  store colour at half resolution (4:2:0). On this screenshot that step alone,
  with the ordinary conversion, scores 79.9, so none of them can get much above
  80. WebP's sharp YUV loses less in the halving and reaches 85.9. Full colour
  (4:4:4) lifts the ceiling to 92.1, and spending bytes on colour beats spending
  them on quality.
* **Chosen:** one `.jpg` link that the host answers with the best copy each
  browser lists in its `Accept` header: AVIF q60 with full colour (112 KB, 76.9),
  then JPEG XL d2.5 for Safari 17+ (133 KB, 78.5), then WebP q82 with sharp YUV
  (128 KB, 72.9), then JPEG q82 with full colour (260 KB, 79.7), which every
  browser decodes. Apple's browsers never get AVIF: full-colour AVIF needs AV1's
  High profile, which wasn't tested in Safari.

## Reproduce

```sh
python -m venv .venv
.venv/bin/pip install -r tools/requirements.txt
curl -o src.png https://example.com/your-screenshot.png   # any 16:9 image, ideally 3840×2160
.venv/bin/python tools/generate.py src.png --out docs
```

Needs `cwebp` (libwebp's encoder; `apt install webp`) for sharp YUV and
near-lossless, which Pillow doesn't expose, and `ffmpeg` built with libjxl for
the JPEG XL rows. The page's prose describes the Outbound screenshot; with
another image the tables and viewer update but the text won't.

The chart's data comes from a separate script, which encodes each format the way the
image host does:

```sh
.venv/bin/python tools/curve.py src/outbound-tower.png --jxl-ssh james@arctic
```

Measured on 2026-09-28, it reproduced every number the blog post quotes.

## Credits and licence

* **Screenshot:** [Outbound](https://www.squareglade.games/outbound) © Square
  Glade Games, captured in play and used only to illustrate image compression.
  Only crops and a 960-pixel overview are included; the full frame isn't
  redistributed. It isn't covered by this project's licence.
* **By** [James Pain](https://github.com/JPain).
* **Licence:** text and figures [CC BY 4.0](LICENSE-CONTENT.md); code
  (`tools/`, `docs/lab.js`) [MIT](LICENSE). A note if you republish would be
  appreciated but isn't required.

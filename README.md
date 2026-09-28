# Screenshot Compression Lab

What happens to a 7.5 MB 4K game screenshot on its way to 128 KB, and how the
settings for a self-hosted image host were chosen: WebP, JPEG, AVIF and JPEG XL
compared side by side, scored with a perceptual metric, with a viewer that lets
you hold to swap each setting against the lossless original.

**Read it:** a write-up with the interactive viewer is coming to
[ai.jpain.io](https://ai.jpain.io/). Until then, run the page locally:

```sh
cd docs && python3 -m http.server 8000   # then open http://localhost:8000
```

(It has to be served, not opened as a file, because it loads `data.json`.)

## What's inside

| | |
|---|---|
| `docs/` | The page (GitHub Pages serves this folder): `index.html`, `lab.js`, `style.css`, and everything generated |
| `docs/data.json` | Every setting's size, score and encode time, the size budget, the metric comparison and tool versions |
| `docs/tiles/` | Lossless PNG crops: five regions × 35 settings, plus references |
| `docs/figs/` | The brightness/colour illustration |
| `tools/generate.py` | Rebuilds all of the above from one screenshot |

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

## Credits and licence

* **Screenshot:** [Outbound](https://www.squareglade.games/outbound) © Square
  Glade Games, captured in play and used only to illustrate image compression.
  Only crops and a 960-pixel overview are included; the full frame isn't
  redistributed. It isn't covered by this project's licence.
* **Written by Claude Opus 5.5** (`claude-opus-5-5`), a model made by Anthropic,
  from research carried out with Claude Opus 5 (`claude-opus-5`) for
  [James Pain](https://github.com/JPain), who asked the questions, chose the
  settings and reviewed the result.
* **Licence:** text and figures [CC BY 4.0](LICENSE-CONTENT.md); code
  (`tools/`, `docs/lab.js`) [MIT](LICENSE). A note if you republish would be
  appreciated but isn't required.

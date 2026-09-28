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
| `docs/tiles/` | Lossless PNG crops: five regions × 34 settings, plus references |
| `docs/figs/` | The brightness/colour illustration |
| `tools/generate.py` | Rebuilds all of the above from one screenshot |

## Findings, in brief

* **Where the bytes go:** 24.9 MB of raw pixels → 7.49 MB lossless PNG →
  1.90 MB resized to 1920 × 1080 → **128 KB** lossy. The last step is 14.5×.
* **Measure with SSIMULACRA 2, not SSIM.** SSIM misranked formats badly here:
  it scored JPEG XL at "visually lossless" barely above plain JPEG.
* **Halving colour caps quality.** Standard JPEG, lossy WebP and default AVIF
  store colour at half resolution (4:2:0). On this screenshot that step alone
  scores 79.9, so none of them can get much above 80. Full colour (4:4:4) lifts
  the ceiling to 92.1, and spending bytes on colour beats spending them on quality.
* **Chosen:** WebP quality 82 with sharp YUV at 1920 wide, 128 KB, score 72.9.
  Full-colour AVIF scores higher at a smaller size, but a reader whose browser
  can't decode it sees a broken image, so universally supported WebP wins for
  posting to forums.

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

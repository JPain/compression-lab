#!/usr/bin/env python3
"""
Rebuild every image and number on the Image Compression Lab page from one
screenshot.

    python tools/generate.py src/outbound-tower.png           # writes docs/
    python tools/generate.py my-screenshot.png --out /tmp/lab  # any 16:9 image

Needs: Pillow 12.3+ (with AVIF), ssimulacra2 and numpy from PyPI (see
requirements.txt); `cwebp` (libwebp's command-line encoder, for sharp YUV and
near-lossless, which Pillow doesn't expose); `ffmpeg` built with libjxl (JPEG
XL rows) and the ssim filter.

What it produces, under --out:
  data.json      every row's size, score, encode time, plus the step-by-step
                 budget, the SSIM-vs-SSIMULACRA 2 comparison and tool versions
  frame.png      the whole frame, small, for the region map
  tiles/*.png    lossless crops: <region>_<setting>.png, plus the references
  figs/*.png     the brightness/colour illustration

Every crop is lossless PNG so the page adds no compression of its own. Scores
are SSIMULACRA 2 (100 = identical, 90 visually lossless, 70 high, 50 medium),
measured on the whole image against the lossless reference at the same size.
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import PIL
from PIL import Image, features
from ssimulacra2 import compute_ssimulacra2

W, H = 1920, 1080                     # the size the host resizes to; every lossy row is judged here
REGIONS = {                           # 1080p coordinates, each 441x270; all divisible by 3 so they
    "van":    (1479, 810, 1920, 1080),  # scale cleanly to 1280, 2560 and 3840 wide
    "sky":    (666, 18, 1107, 288),
    "tower":  (861, 540, 1302, 810),
    "trees":  (18, 204, 459, 474),
    "gauges": (0, 810, 441, 1080),
}


def scaled(box, width):
    f = width / W
    return tuple(round(v * f) for v in box)


class Lab:
    def __init__(self, src: Path, out: Path):
        self.out = out
        self.tiles = out / "tiles"
        self.figs = out / "figs"
        self.work = Path(tempfile.mkdtemp(prefix="lab-"))
        for d in (self.tiles, self.figs):
            d.mkdir(parents=True, exist_ok=True)
        self.src_bytes = src.stat().st_size
        self.orig = Image.open(src).convert("RGB")
        if self.orig.size != (3840, 2160):
            self.orig = self.orig.resize((3840, 2160), Image.LANCZOS)
        self.orig_path = self.work / "orig4k.png"
        self.orig.save(self.orig_path)
        self.ref = self.orig.resize((W, H), Image.LANCZOS)      # exactly what the host does
        self.ref_path = self.work / "ref1080.png"
        self.ref.save(self.ref_path)
        self.rows = []

    # --- encoders -----------------------------------------------------------
    def pil(self, img, fmt, **kw):
        t = time.perf_counter(); b = io.BytesIO(); img.save(b, fmt, **kw); dt = time.perf_counter() - t
        return b.getvalue(), dt

    def cwebp(self, args):
        dst = self.work / "cw.webp"
        t = time.perf_counter()
        subprocess.run(["cwebp", "-quiet", *args, str(self.ref_path), "-o", str(dst)], check=True)
        return dst.read_bytes(), time.perf_counter() - t

    def jxl(self, distance):
        dst = self.work / "x.jxl"
        t = time.perf_counter()
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(self.ref_path),
                        "-c:v", "libjxl", "-distance", str(distance), "-effort", "7", str(dst)], check=True)
        dt = time.perf_counter() - t
        dec = self.work / "x_jxl.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(dst), str(dec)], check=True)
        return dst.read_bytes(), dt, Image.open(dec).convert("RGB")

    # --- measuring ----------------------------------------------------------
    def ssim(self, path):
        e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(self.ref_path), "-i", str(path),
                            "-lavfi", "ssim", "-f", "null", "-"], capture_output=True, text=True).stderr
        return float(re.search(r"All:([\d.]+)", e).group(1))

    def add(self, section, vid, label, note="", data=None, dt=None, decoded=None, vs4k=False,
            served=None, keep_ssim=False):
        img = decoded if decoded is not None else Image.open(io.BytesIO(data)).convert("RGB")
        path = self.work / f"{vid}.png"
        img.save(path)
        # Resolution rows are judged as a 4K screen would show them, against the 4K
        # original -- all of them, including 1920. Deciding this from the width
        # instead once scored the 1920 row against the 1080p copy (70.2, not 49).
        if not vs4k:
            score = compute_ssimulacra2(str(self.ref_path), str(path))
            ref = "1080"
        else:
            up = self.work / f"{vid}_4k.png"
            img.resize((3840, 2160), Image.LANCZOS).save(up)
            score = compute_ssimulacra2(str(self.orig_path), str(up))
            ref = "4k"
        for r, box in REGIONS.items():
            img.crop(scaled(box, img.width)).save(self.tiles / f"{r}_{vid}.png", optimize=True)
        row = dict(section=section, id=vid, label=label, note=note,
                   bytes=len(data) if data is not None else None,
                   ratio=round(self.src_bytes / len(data), 1) if data else None,
                   ms=round(dt * 1000) if dt is not None else None,
                   score=round(score, 1), ref=ref, dims=f"{img.width}×{img.height}", served=served)
        if keep_ssim:
            row["ssim"] = round(self.ssim(path), 4)
        self.rows.append(row)
        size = f"{len(data)/1024:8.1f} KB" if data else "   (none)  "
        print(f"  {vid:16s} {size}  {score:5.1f}", flush=True)

    # --- the page's sections ------------------------------------------------
    def run(self):
        print("references + map")
        for r, box in REGIONS.items():
            self.ref.crop(box).save(self.tiles / f"{r}_ref1080.png", optimize=True)
            self.orig.crop(scaled(box, 3840)).save(self.tiles / f"{r}_ref4k.png", optimize=True)
        self.orig.resize((960, 540), Image.LANCZOS).save(self.out / "frame.png", optimize=True)

        print("WebP quality")
        d, t = self.pil(self.ref, "WEBP", lossless=True, method=6)
        self.add("webp-quality", "webp_lossless", "WebP lossless", "Every pixel exact. The ceiling for quality.", d, t)
        for q in (95, 90, 85, 82, 80, 75, 70, 60, 50):
            d, t = self.pil(self.ref, "WEBP", quality=q, method=6)
            note = {82: "The quality of the host's WebP copy, which adds sharp YUV (next section).",
                    75: "cwebp's own default.", 50: "Where it visibly breaks: grass turns to smears."}.get(q, "")
            self.add("webp-quality", f"webp_q{q}", f"WebP quality {q}", note, d, t, keep_ssim=(q == 82))

        print("other WebP options")
        d, t = self.pil(self.ref, "WEBP", quality=82, method=4)
        self.add("webp-options", "webp_m4", "WebP q82, method 4",
                 "Pillow's default effort. Faster to encode than method 6, a little larger.", d, t)
        d, t = self.cwebp(["-q", "82", "-m", "6", "-sharp_yuv"])
        self.add("webp-options", "webp_sharpyuv", "WebP q82, sharp YUV",
                 "A slower, more careful colour conversion before the colour is halved, so thin coloured "
                 "edges keep their colour. The host's copy for browsers that take WebP but not AVIF or "
                 "JPEG XL. Output is ordinary WebP.", d, t, served=3)
        d, t = self.cwebp(["-q", "90", "-m", "6", "-sharp_yuv"])
        self.add("webp-options", "webp_q90_sharpyuv", "WebP q90, sharp YUV",
                 "Past the 79.9 colour ceiling while still halving colour: that ceiling assumes the "
                 "ordinary conversion, and sharp YUV loses less in the halving.", d, t)
        d, t = self.cwebp(["-near_lossless", "60", "-m", "6"])
        self.add("webp-options", "webp_nl60", "WebP near-lossless 60",
                 "Lossless mode after lightly adjusting hard-to-compress pixels.", d, t)

        print("colour resolution")
        y, cb, cr = self.ref.convert("YCbCr").split()
        self.add("colour", "ycc_only", "Brightness and colour, nothing removed",
                 "Converted to brightness + colour and back at 8 bits. Rounding alone costs a little: "
                 "this is the ceiling for every format that works this way.",
                 decoded=self.ref.convert("YCbCr").convert("RGB"))
        half = lambda c: c.resize((W // 2, H // 2), Image.BOX).resize((W, H), Image.BILINEAR)
        self.add("colour", "sub_only", "Colour halved, nothing else",
                 "Colour stored at half resolution each way (4:2:0), then scaled back up. No compression. "
                 "The ceiling for standard JPEG, lossy WebP and default AVIF with the ordinary "
                 "conversion. WebP with sharp YUV gets past it (Other WebP options).",
                 decoded=Image.merge("YCbCr", (y, half(cb), half(cr))).convert("RGB"))
        for sub, vid, label, note in ((2, "jpeg_q100", "JPEG quality 100", "Maximum quality, halved colour: stopped by the ceiling above."),
                                      (0, "jpeg_q100_444", "JPEG quality 100, full-resolution colour", "Maximum quality, full colour: lands on the brightness-and-colour ceiling.")):
            d, t = self.pil(self.ref, "JPEG", quality=100, subsampling=sub, optimize=True, progressive=True)
            self.add("colour", vid, label, note, d, t)

        print("JPEG")
        for q in (95, 90, 82, 75):
            d, t = self.pil(self.ref, "JPEG", quality=q, optimize=True, progressive=True)
            self.add("jpeg", f"jpeg_q{q}", f"JPEG quality {q}", "Standard JPEG: colour halved." if q == 82 else "",
                     d, t, keep_ssim=(q == 82))
        d, t = self.pil(self.ref, "JPEG", quality=82, subsampling=0, optimize=True, progressive=True)
        self.add("jpeg", "jpeg_q82_444", "JPEG quality 82, full-resolution colour",
                 "4:4:4: larger, but coloured edges keep their colour. The host's copy for every other "
                 "browser: every browser decodes JPEG.", d, t, served=4)

        print("AVIF")
        for q in (80, 70, 60, 50):
            d, t = self.pil(self.ref, "AVIF", quality=q, speed=6)
            self.add("avif", f"avif_q{q}", f"AVIF quality {q}", "", d, t, keep_ssim=(q == 60))
        d, t = self.pil(self.ref, "AVIF", quality=60, speed=6, subsampling="4:4:4")
        self.add("avif", "avif_q60_444", "AVIF quality 60, full-resolution colour",
                 "4:4:4: full-resolution colour. The host's first choice, sent to browsers that list "
                 "AVIF, apart from Apple's.", d, t, served=1)

        print("JPEG XL")
        for dist in (1.0, 2.0, 3.0):
            d, t, dec = self.jxl(dist)
            self.add("jxl", f"jxl_d{str(dist).replace('.', '')}", f"JPEG XL distance {dist}",
                     "Aimed at visually lossless." if dist == 1.0 else "", d, t, decoded=dec, keep_ssim=(dist == 1.0))

        print("resolution")
        for w in (3840, 2560, 1920, 1280):
            h = w * 9 // 16
            src = self.orig if w == 3840 else self.orig.resize((w, h), Image.LANCZOS)
            d, t = self.pil(src, "WEBP", quality=82, method=6)
            self.add("resolution", f"res_{w}", f"{w}×{h}, WebP quality 82",
                     {3840: "No resize at all.", 1920: "The host's width.", 1280: "Still wider than a forum column."}.get(w, ""),
                     d, t, vs4k=True)

        print("figures")
        self.figures()
        self.write()

    # --- brightness / colour illustration ------------------------------------
    def figures(self):
        box = REGIONS["van"]
        crop = self.ref.crop(box)
        y, cb, cr = crop.convert("YCbCr").split()
        crop.save(self.figs / "01-original.png", optimize=True)
        y.save(self.figs / "02-brightness.png", optimize=True)
        neutral = Image.new("L", crop.size, 128)
        hw, hh = crop.width // 2, crop.height // 2
        cb_h, cr_h = cb.resize((hw, hh), Image.BOX), cr.resize((hw, hh), Image.BOX)
        # Each colour plane on its own, shown on mid-grey brightness so only the
        # colour information is visible, then blown back up with NEAREST so the
        # half-resolution blocks are plain to see.
        vis = lambda c_b, c_r: Image.merge("YCbCr", (neutral.resize(c_b.size), c_b, c_r)).convert("RGB")
        n128 = Image.new("L", (hw, hh), 128)
        vis(cb_h, n128).resize(crop.size, Image.NEAREST).save(self.figs / "03-colour-blue.png", optimize=True)
        vis(n128, cr_h).resize(crop.size, Image.NEAREST).save(self.figs / "04-colour-red.png", optimize=True)
        vis(cb, cr).save(self.figs / "05-colour-full.png", optimize=True)
        vis(cb_h, cr_h).resize(crop.size, Image.NEAREST).save(self.figs / "06-colour-half.png", optimize=True)
        rec = Image.merge("YCbCr", (y, cb_h.resize(crop.size, Image.BILINEAR), cr_h.resize(crop.size, Image.BILINEAR))).convert("RGB")
        rec.save(self.figs / "07-recombined.png", optimize=True)
        diff = np.abs(np.asarray(crop, dtype=np.int16) - np.asarray(rec, dtype=np.int16)).sum(axis=2)
        heat = np.clip(diff * 6, 0, 255).astype(np.uint8)
        Image.fromarray(heat, "L").save(self.figs / "08-difference.png", optimize=True)

    def write(self):
        by = {r["id"]: r for r in self.rows}
        ref_png = io.BytesIO(); self.ref.save(ref_png, "PNG", optimize=True)
        budget = [
            {"step": "Raw pixels, 3840×2160 × 3 bytes", "bytes": 3840 * 2160 * 3},
            {"step": "The screenshot as a PNG (lossless)", "bytes": self.src_bytes},
            {"step": "Resized to 1920×1080, still lossless", "bytes": len(ref_png.getvalue())},
            {"step": "AVIF quality 60, full-resolution colour", "bytes": by["avif_q60_444"]["bytes"]},
        ]
        metrics = [{"id": k, "label": by[k]["label"], "bytes": by[k]["bytes"], "ssim": by[k]["ssim"],
                    "ssimulacra2": by[k]["score"]} for k in ("jpeg_q82", "webp_q82", "avif_q60", "jxl_d10")]
        cw = subprocess.run(["cwebp", "-version"], capture_output=True, text=True).stdout.split()[0]
        ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split()[2]
        data = {
            "source": {"bytes": self.src_bytes, "size": "3840×2160"},
            "budget": budget, "metrics": metrics, "rows": self.rows,
            "regions": {k: list(v) for k, v in REGIONS.items()},
            "tools": {"pillow": PIL.__version__, "libwebp": features.version("webp"),
                      "libavif": features.version("avif"), "cwebp": cw, "ffmpeg": ff,
                      "python": platform.python_version(), "cpu": platform.processor() or platform.machine()},
            "generated": time.strftime("%Y-%m-%d"),
        }
        (self.out / "data.json").write_text(json.dumps(data, indent=1))
        shutil.rmtree(self.work, ignore_errors=True)
        print(f"wrote {self.out / 'data.json'}: {len(self.rows)} settings, "
              f"{len(list(self.tiles.glob('*.png')))} tiles, {len(list(self.figs.glob('*.png')))} figures")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="a 16:9 screenshot, ideally 3840×2160 PNG")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "docs")
    a = ap.parse_args()
    for tool in ("cwebp", "ffmpeg"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH")
    if not features.check("avif"):
        sys.exit("this Pillow has no AVIF support; install Pillow 12.3 or newer from PyPI")
    Lab(a.source, a.out).run()


if __name__ == "__main__":
    main()

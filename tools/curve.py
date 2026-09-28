#!/usr/bin/env python3
"""Measure size against SSIMULACRA 2 for the four formats the image host serves, across
their quality settings, and write docs/curve.json (the chart in the blog post and here).

Same reference and metric as generate.py: the source resized to 1920 x 1080 with Lanczos,
exactly as the host does, and SSIMULACRA 2 against that. Each format is encoded the way
the host encodes it (ops/filehost/gateway):
  AVIF      Pillow, full-resolution colour (4:4:4), speed 6
  JPEG XL   cjxl, effort 7 -- the host's cjxl, so run on the host (--jxl-ssh), because
            cjxl versions differ: 0.7 and 0.11 give different sizes and scores
  WebP      cwebp -sharp_yuv -m 6
  JPEG      Pillow, full-resolution colour (subsampling 0), optimised, progressive

    .venv/bin/python tools/curve.py src/outbound-tower.png [--jxl-ssh james@arctic]
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from ssimulacra2 import compute_ssimulacra2

HERE = Path(__file__).resolve().parent.parent
QUALITIES = {
    "avif": [40, 45, 50, 55, 60, 65, 70, 75, 80],
    "jxl": [4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0],        # distance: lower is better
    "webp": [50, 60, 70, 75, 82, 85, 90, 95],
    "jpg": [50, 60, 70, 75, 82],            # q90 (372.8 KB, 84.7) left off: past the chart
}
SERVED = {"avif": 60, "jxl": 2.5, "webp": 82, "jpg": 82}   # what the host sends, rank 1 to 4
CEILING = 79.9     # generate.py's "colour halved, nothing else" row: the 4:2:0 limit


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--jxl-ssh", help="user@host whose cjxl/djxl to use (the image host)")
    args = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="curve-"))
    src = Image.open(args.source).convert("RGB")
    if src.size != (3840, 2160):
        src = src.resize((3840, 2160), Image.LANCZOS)
    ref = src.resize((1920, 1080), Image.LANCZOS)
    ref_path = work / "ref.png"
    ref.save(ref_path)

    def score(img: Image.Image, name: str) -> float:
        p = work / f"{name}.png"
        img.save(p)
        return round(compute_ssimulacra2(str(ref_path), str(p)), 1)

    def pil(fmt: str, **kw) -> bytes:
        b = io.BytesIO(); ref.save(b, fmt, **kw); return b.getvalue()

    out: dict[str, list] = {k: [] for k in QUALITIES}
    for q in QUALITIES["avif"]:
        data = pil("AVIF", quality=q, speed=6, subsampling="4:4:4")
        out["avif"].append({"q": q, "bytes": len(data), "score": score(Image.open(io.BytesIO(data)).convert("RGB"), f"avif{q}")})
    for q in QUALITIES["jpg"]:
        data = pil("JPEG", quality=q, subsampling=0, optimize=True, progressive=True)
        out["jpg"].append({"q": q, "bytes": len(data), "score": score(Image.open(io.BytesIO(data)).convert("RGB"), f"jpg{q}")})
    for q in QUALITIES["webp"]:
        dst = work / f"w{q}.webp"
        subprocess.run(["cwebp", "-quiet", "-q", str(q), "-m", "6", "-sharp_yuv", str(ref_path), "-o", str(dst)], check=True)
        out["webp"].append({"q": q, "bytes": dst.stat().st_size, "score": score(Image.open(dst).convert("RGB"), f"webp{q}")})

    run = (lambda cmd: subprocess.run(["ssh", args.jxl_ssh, cmd], check=True, capture_output=True, text=True).stdout) \
        if args.jxl_ssh else (lambda cmd: subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout)
    remote = "/tmp/curve-jxl"
    if args.jxl_ssh:
        run(f"rm -rf {remote} && mkdir -p {remote}")
        subprocess.run(["scp", "-q", str(ref_path), f"{args.jxl_ssh}:{remote}/ref.png"], check=True)
    else:
        remote = str(work)
    cjxl_version = run("cjxl --version 2>&1 | head -1").strip()
    for d in QUALITIES["jxl"]:
        run(f"cjxl {remote}/ref.png {remote}/x{d}.jxl -d {d} -e 7 --quiet && djxl {remote}/x{d}.jxl {remote}/x{d}.png --quiet")
        size = int(run(f"stat -c %s {remote}/x{d}.jxl"))
        dec = work / f"jxl{d}.png"
        if args.jxl_ssh:
            subprocess.run(["scp", "-q", f"{args.jxl_ssh}:{remote}/x{d}.png", str(dec)], check=True)
        out["jxl"].append({"q": d, "bytes": size, "score": score(Image.open(dec).convert("RGB"), f"jxl{d}")})
    if args.jxl_ssh:
        run(f"rm -rf {remote}")

    cwebp = subprocess.run(["cwebp", "-version"], capture_output=True, text=True).stdout.strip()
    result = {"ceiling": CEILING, "served": SERVED, "points": out,
              "tools": {"pillow": Image.__version__, "cwebp": cwebp, "cjxl": cjxl_version}}
    (HERE / "docs" / "curve.json").write_text(json.dumps(result, indent=1) + "\n")
    for k, pts in out.items():
        print(k, " ".join(f"{p['q']}:{p['bytes']/1024:.1f}KB/{p['score']}" for p in pts))


if __name__ == "__main__":
    main()

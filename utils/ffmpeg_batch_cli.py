"""Simple CLI runner for VideoProcessor.

Usage examples:
  python ffmpeg_batch_cli.py --input-dir downloads --output-dir downloads_out
  python ffmpeg_batch_cli.py --inputs a.mp4 b.mp4 --output-dir out

This is optional, but useful as a smoke test outside FastAPI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core import video_processing as vp


def iter_video_files(input_dir: Path):
    exts = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
    for p in input_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", type=Path, default=None)
    ap.add_argument("--inputs", nargs="*", default=None)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--speed", type=float, default=1.07)
    ap.add_argument("--contrast", type=float, default=1.06)
    ap.add_argument("--saturation", type=float, default=1.10)
    args = ap.parse_args()

    if not args.input_dir and not args.inputs:
        ap.error("Provide --input-dir or --inputs")

    inputs = []
    if args.input_dir:
        inputs.extend(list(iter_video_files(args.input_dir)))
    if args.inputs:
        inputs.extend([Path(p) for p in args.inputs])

    vp_instance = vp.VideoProcessor()
    settings = vp.VideoTransformSettings(
        mirror_horizontal=True,
        speed=args.speed,
        color=vp.ColorGradeSettings(contrast=args.contrast, saturation=args.saturation),
    )

    results = vp_instance.process_batch(inputs, args.output_dir, settings=settings, overwrite=args.overwrite)
    print(f"Processed {len(results)} file(s) -> {args.output_dir}")


if __name__ == "__main__":
    main()

"""Video splitting utility using FFmpeg.

Contract:
- Input: a video file path
- If duration > threshold_seconds: split into segments of segment_seconds
- Output: list of created segment paths (sorted)

Notes:
- Requires ffmpeg + ffprobe in PATH.
- Uses stream copy to be fast (no re-encode).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import List


def _probe_duration_seconds(file_path: Path, *, ffprobe: str = "ffprobe") -> float:
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(file_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip() or "ffprobe failed")
    data = json.loads(proc.stdout or "{}")
    duration = float((data.get("format") or {}).get("duration") or 0)
    return duration


def split_if_longer_than(
    input_path: str | os.PathLike,
    *,
    threshold_seconds: int,
    segment_seconds: int,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    output_dir: str | os.PathLike | None = None,
) -> List[str]:
    """Split a video into multiple parts if it's longer than threshold.

    Returns list of segment file paths. If not split, returns [original_path].
    """
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(str(in_path))

    if threshold_seconds <= 0 or segment_seconds <= 0:
        return [str(in_path)]

    duration = _probe_duration_seconds(in_path, ffprobe=ffprobe)
    if duration <= float(threshold_seconds):
        return [str(in_path)]

    out_dir = Path(output_dir) if output_dir else in_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Keep same extension; segment muxer will create multiple files.
    out_pattern = out_dir / f"{in_path.stem}_part%03d{in_path.suffix}"

    # -reset_timestamps 1 for clean playback, -map 0 to keep streams.
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(in_path),
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(int(segment_seconds)),
        "-reset_timestamps",
        "1",
        str(out_pattern),
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip() or "ffmpeg split failed")

    # Collect output segments
    segments = sorted(str(p) for p in out_dir.glob(f"{in_path.stem}_part*{in_path.suffix}"))
    return segments if segments else [str(in_path)]


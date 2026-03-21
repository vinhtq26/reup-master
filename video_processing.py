"""video_processing.py

OOP wrapper around FFmpeg for batch video processing.

Features:
- Mirroring (horizontal flip)
- Speed adjustment to 1.07x while preserving audio pitch
- Light color grading (contrast & saturation)
- Strip all metadata and write to a new file

Designed to be easy to integrate into FastAPI (sync + async helpers).

Notes:
- Requires ffmpeg + ffprobe available in PATH.
- Uses only stdlib.
"""

from __future__ import annotations

__all__ = [
    "FFmpegNotFoundError",
    "FFmpegCommandError",
    "ColorGradeSettings",
    "VideoTransformSettings",
    "ProcessResult",
    "FFmpegLocator",
    "VideoProcessor",
]

import asyncio
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence


class FFmpegNotFoundError(RuntimeError):
    pass


class FFmpegCommandError(RuntimeError):
    def __init__(self, message: str, *, command: Sequence[str], stderr: str | None = None):
        super().__init__(message)
        self.command = list(command)
        self.stderr = stderr


@dataclass(frozen=True)
class ColorGradeSettings:
    """Small, safe defaults that work for most sources."""

    contrast: float = 1.06  # 1.0 = unchanged
    saturation: float = 1.10  # 1.0 = unchanged


@dataclass(frozen=True)
class VideoTransformSettings:
    mirror_horizontal: bool = True
    speed: float = 1.07
    color: ColorGradeSettings = ColorGradeSettings()


@dataclass(frozen=True)
class ProcessResult:
    input_path: Path
    output_path: Path
    returncode: int
    stderr: str = ""


class FFmpegLocator:
    """Resolves ffmpeg/ffprobe executables."""

    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe

    def assert_available(self) -> None:
        for exe in (self.ffmpeg, self.ffprobe):
            try:
                subprocess.run([exe, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except FileNotFoundError as e:
                raise FFmpegNotFoundError(f"Executable not found in PATH: {exe}") from e
            except subprocess.CalledProcessError as e:
                raise FFmpegNotFoundError(f"Executable exists but failed to run: {exe}") from e


class VideoProcessor:
    """Batch video processor built on FFmpeg.

    Contract:
    - Input: a video file path
    - Output: a new file at output_path (never overwrites unless overwrite=True)
    - Audio pitch: preserved while changing speed (via `atempo`)
    - Metadata: stripped with -map_metadata -1 and -map_chapters -1
    """

    def __init__(
        self,
        *,
        locator: Optional[FFmpegLocator] = None,
        default_settings: VideoTransformSettings = VideoTransformSettings(),
    ):
        self.locator = locator or FFmpegLocator()
        self.default_settings = default_settings

    # ---------- public API ----------
    def process_one(
        self,
        input_path: str | os.PathLike,
        output_path: str | os.PathLike,
        *,
        settings: Optional[VideoTransformSettings] = None,
        overwrite: bool = False,
        extra_ffmpeg_args: Optional[Sequence[str]] = None,
    ) -> ProcessResult:
        self.locator.assert_available()

        in_path = Path(input_path)
        out_path = Path(output_path)
        if not in_path.exists():
            raise FileNotFoundError(str(in_path))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and not overwrite:
            raise FileExistsError(str(out_path))

        s = settings or self.default_settings
        cmd = self._build_ffmpeg_command(in_path, out_path, s, overwrite=overwrite, extra_ffmpeg_args=extra_ffmpeg_args)

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise FFmpegCommandError(
                "FFmpeg processing failed",
                command=cmd,
                stderr=(proc.stderr or "")[-4000:],
            )

        return ProcessResult(input_path=in_path, output_path=out_path, returncode=proc.returncode, stderr=proc.stderr or "")

    async def process_one_async(self, *args, **kwargs) -> ProcessResult:
        """Async-friendly wrapper for FastAPI (runs ffmpeg in a thread)."""

        return await asyncio.to_thread(self.process_one, *args, **kwargs)

    def process_batch(
        self,
        inputs: Iterable[str | os.PathLike],
        output_dir: str | os.PathLike,
        *,
        suffix: str = "_processed",
        settings: Optional[VideoTransformSettings] = None,
        overwrite: bool = False,
    ) -> list[ProcessResult]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        results: list[ProcessResult] = []
        for p in inputs:
            in_path = Path(p)
            out_path = out_dir / f"{in_path.stem}{suffix}{in_path.suffix}"
            results.append(self.process_one(in_path, out_path, settings=settings, overwrite=overwrite))
        return results

    # ---------- internals ----------
    def _probe_has_audio(self, input_path: Path) -> bool:
        cmd = [
            self.locator.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(input_path),
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            # If probing fails, assume audio exists; ffmpeg will handle mapping.
            return True
        try:
            data = json.loads(proc.stdout or "{}")
            return len(data.get("streams", []) or []) > 0
        except json.JSONDecodeError:
            return True

    def _build_filter_complex(self, input_path: Path, s: VideoTransformSettings) -> tuple[str, list[str]]:
        """Returns (filter_complex, output_maps)."""

        has_audio = self._probe_has_audio(input_path)

        v_filters: list[str] = []
        if s.mirror_horizontal:
            v_filters.append("hflip")

        if s.speed and abs(s.speed - 1.0) > 1e-6:
            v_filters.append(f"setpts=PTS/{s.speed}")

        v_filters.append(f"eq=contrast={s.color.contrast}:saturation={s.color.saturation}")

        v_chain = ",".join(v_filters)

        if not has_audio:
            return f"[0:v]{v_chain}[v]", ["-map", "[v]", "-map", "0:s?", "-map", "0:d?"]

        # atempo time-stretches without changing pitch (0.5..2.0)
        a_chain = ""
        if s.speed and abs(s.speed - 1.0) > 1e-6:
            a_chain = f"atempo={s.speed}"

        if a_chain:
            return (
                f"[0:v]{v_chain}[v];[0:a]{a_chain}[a]",
                ["-map", "[v]", "-map", "[a]", "-map", "0:s?", "-map", "0:d?"],
            )

        return f"[0:v]{v_chain}[v]", ["-map", "[v]", "-map", "0:a?", "-map", "0:s?", "-map", "0:d?"]

    def _build_ffmpeg_command(
        self,
        input_path: Path,
        output_path: Path,
        s: VideoTransformSettings,
        *,
        overwrite: bool,
        extra_ffmpeg_args: Optional[Sequence[str]],
    ) -> list[str]:
        filter_complex, maps = self._build_filter_complex(input_path, s)

        cmd: list[str] = [self.locator.ffmpeg]
        cmd += ["-hide_banner", "-y" if overwrite else "-n"]
        cmd += ["-i", str(input_path)]

        # Strip metadata, chapters.
        cmd += ["-map_metadata", "-1", "-map_chapters", "-1"]

        cmd += ["-filter_complex", filter_complex]
        cmd += maps

        # Re-encode to ensure filters apply.
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]
        cmd += ["-pix_fmt", "yuv420p"]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += ["-movflags", "+faststart"]

        if extra_ffmpeg_args:
            cmd += list(extra_ffmpeg_args)

        cmd += [str(output_path)]
        return cmd

    @staticmethod
    def format_command(cmd: Sequence[str]) -> str:
        return " ".join(shlex.quote(c) for c in cmd)

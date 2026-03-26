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
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import ffmpeg
import unidecode

# NEW: optional OpenCV-based logo/corner detection
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore


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
    # NEW: attempt to detect static corner logo(s) and blur them
    blur_static_corner_logos: bool = True
    # fraction of width/height used for each corner ROI
    corner_roi_frac: float = 0.14
    # blur strength (sigma) for gaussian blur
    logo_blur_sigma: float = 2.2
    # detection params
    logo_detect_frames: int = 24
    logo_detect_sample_every: int = 15  # sample every N frames
    logo_static_threshold: float = 6.0  # lower = more aggressive detection


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

        # Optional: detect static corner logo boxes
        corner_boxes: list[tuple[int, int, int, int]] = []
        if getattr(s, "blur_static_corner_logos", False):
            corner_boxes = self._detect_static_corner_logos(
                in_path,
                corner_roi_frac=float(getattr(s, "corner_roi_frac", 0.14)),
                max_samples=int(getattr(s, "logo_detect_frames", 24)),
                sample_every=int(getattr(s, "logo_detect_sample_every", 15)),
                static_threshold=float(getattr(s, "logo_static_threshold", 6.0)),
            )

        # Build ffmpeg-python graph
        stream = ffmpeg.input(str(in_path))

        # Video filters
        v = stream.video
        if s.mirror_horizontal:
            v = v.hflip()

        if s.speed and abs(s.speed - 1.0) > 1e-6:
            v = v.filter("setpts", f"PTS/{s.speed}")

        v = v.filter("eq", contrast=s.color.contrast, saturation=s.color.saturation)

        # If detected: blur those corners by blurring full frame and overlaying in ROIs
        if corner_boxes:
            v = self._apply_corner_blur_ffmpeg(v, corner_boxes, sigma=float(getattr(s, "logo_blur_sigma", 2.2)))

        # Audio filters (optional)
        a = stream.audio
        if s.speed and abs(s.speed - 1.0) > 1e-6:
            a = a.filter("atempo", s.speed)

        # Output options
        # IMPORTANT: strip all metadata/chapters.
        # Also, avoid passing any metadata via -metadata (none here).
        output_kwargs = {
            "vcodec": "libx264",
            "preset": "medium",
            "crf": 20,
            "pix_fmt": "yuv420p",
            "acodec": "aac",
            "audio_bitrate": "192k",
            "movflags": "+faststart",
            "map_metadata": -1,
            "map_chapters": -1,
        }

        # Build output with/without audio depending on probe
        has_audio = self._probe_has_audio(in_path)
        if has_audio:
            out = ffmpeg.output(v, a, str(out_path), **output_kwargs)
        else:
            out = ffmpeg.output(v, str(out_path), **output_kwargs)

        # Extra raw args if needed
        if extra_ffmpeg_args:
            out = out.global_args(*list(extra_ffmpeg_args))

        # Overwrite control
        try:
            if overwrite:
                out = out.overwrite_output()
            else:
                # ffmpeg-python has no direct -n helper; use global args.
                out = out.global_args("-n")

            out = out.global_args("-hide_banner")

            out.run(cmd=self.locator.ffmpeg, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            stderr = ""
            try:
                stderr = (e.stderr or b"").decode("utf-8", errors="replace")
            except Exception:
                stderr = str(getattr(e, "stderr", "") or "")

            raise FFmpegCommandError(
                "FFmpeg processing failed",
                command=[self.locator.ffmpeg, "<ffmpeg-python graph>"],
                stderr=stderr[-4000:],
            )

        return ProcessResult(input_path=in_path, output_path=out_path, returncode=0, stderr="")

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

    def extract_assets(
        self,
        input_path: str | os.PathLike,
        output_folder: str | os.PathLike,
    ) -> tuple[Path, Path]:
        """Extract a muted MP4 (stream copy) and a high-quality MP3 from a source video.

        Outputs:
        - <name>_muted.mp4: video-only, lossless stream copy (-c:v copy -an)
        - <name>.mp3: audio-only, libmp3lame @ 192k

        Returns:
            (muted_video_path, audio_path)
        """
        self.locator.assert_available()

        in_path = Path(input_path)
        if not in_path.exists():
            raise FileNotFoundError(str(in_path))

        out_dir = Path(output_folder)
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_stem = sanitize_filename(in_path.stem)
        muted_video_path = out_dir / f"{safe_stem}_muted.mp4"
        audio_path = out_dir / f"{safe_stem}.mp3"

        stream = ffmpeg.input(str(in_path))

        # 1) Muted video: copy video stream, drop audio for max speed / zero quality loss
        try:
            (
                ffmpeg.output(
                    stream.video,
                    str(muted_video_path),
                    vcodec="copy",
                    an=None,
                    movflags="+faststart",
                )
                .overwrite_output()
                .global_args("-hide_banner")
                .run(cmd=self.locator.ffmpeg, capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            stderr = ""
            try:
                stderr = (e.stderr or b"").decode("utf-8", errors="replace")
            except Exception:
                stderr = str(getattr(e, "stderr", "") or "")
            raise FFmpegCommandError(
                "FFmpeg muted-video extraction failed",
                command=[self.locator.ffmpeg, "-i", str(in_path), "-c:v", "copy", "-an", str(muted_video_path)],
                stderr=stderr[-4000:],
            )

        # 2) Audio: high-quality MP3 192k
        try:
            (
                ffmpeg.output(
                    stream.audio,
                    str(audio_path),
                    acodec="libmp3lame",
                    audio_bitrate="192k",
                )
                .overwrite_output()
                .global_args("-hide_banner")
                .run(cmd=self.locator.ffmpeg, capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            stderr = ""
            try:
                stderr = (e.stderr or b"").decode("utf-8", errors="replace")
            except Exception:
                stderr = str(getattr(e, "stderr", "") or "")
            raise FFmpegCommandError(
                "FFmpeg audio extraction failed",
                command=[self.locator.ffmpeg, "-i", str(in_path), "-c:a", "libmp3lame", "-b:a", "192k", str(audio_path)],
                stderr=stderr[-4000:],
            )

        return muted_video_path, audio_path

    def make_video_mute_and_clean(self, input_path: str | os.PathLike, output_path: str | os.PathLike, overwrite: bool = False) -> ProcessResult:
        """
        Tạo video không âm thanh, không metadata từ file input_path.
        """
        self.locator.assert_available()
        in_path = Path(input_path)
        out_path = Path(output_path)
        if not in_path.exists():
            raise FileNotFoundError(str(in_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and not overwrite:
            raise FileExistsError(str(out_path))
        # FFmpeg command: strip audio, strip metadata
        cmd = [
            self.locator.ffmpeg,
            '-y' if overwrite else '-n',
            '-i', str(in_path),
            '-an',  # remove all audio
            '-map_metadata', '-1',
            '-map_chapters', '-1',
            '-c:v', 'copy',
            str(out_path)
        ]
        proc = subprocess.run(cmd, capture_output=True)
        return ProcessResult(
            input_path=in_path,
            output_path=out_path,
            returncode=proc.returncode,
            stderr=proc.stderr.decode(errors='ignore')
        )

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
        """Legacy helper retained for compatibility/debugging.

        The processor now uses ffmpeg-python; this remains for callers that were
        previously formatting commands for logging.
        """
        filter_complex, maps = self._build_filter_complex(input_path, s)

        cmd: list[str] = [self.locator.ffmpeg]
        cmd += ["-hide_banner", "-y" if overwrite else "-n"]
        cmd += ["-i", str(input_path)]
        cmd += ["-map_metadata", "-1", "-map_chapters", "-1"]
        cmd += ["-filter_complex", filter_complex]
        cmd += maps
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

    def _detect_static_corner_logos(
        self,
        input_path: Path,
        *,
        corner_roi_frac: float,
        max_samples: int,
        sample_every: int,
        static_threshold: float,
    ) -> list[tuple[int, int, int, int]]:
        """Detects whether any corner has a near-static overlay (logo/watermark).

        Heuristic:
        - Read frames with OpenCV.
        - For each corner ROI, compute mean abs diff between consecutive sampled frames.
        - If the ROI changes much less than the rest of the frame, treat as static overlay.

        Returns list of boxes (x, y, w, h) in pixels.
        """
        if cv2 is None or np is None:
            return []

        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            return []

        try:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if w <= 0 or h <= 0:
                return []

            roi_w = max(16, int(w * corner_roi_frac))
            roi_h = max(16, int(h * corner_roi_frac))

            corners = {
                "tl": (0, 0, roi_w, roi_h),
                "tr": (w - roi_w, 0, roi_w, roi_h),
                "bl": (0, h - roi_h, roi_w, roi_h),
                "br": (w - roi_w, h - roi_h, roi_w, roi_h),
            }

            prev_gray = None
            corner_diffs = {k: [] for k in corners}
            global_diffs: list[float] = []

            frame_idx = 0
            samples = 0
            while samples < max_samples:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_idx += 1
                if sample_every > 1 and (frame_idx % sample_every) != 0:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if prev_gray is not None:
                    diff = cv2.absdiff(gray, prev_gray)
                    global_diffs.append(float(np.mean(diff)))
                    for name, (x, y, ww, hh) in corners.items():
                        roi = diff[y : y + hh, x : x + ww]
                        corner_diffs[name].append(float(np.mean(roi)))

                prev_gray = gray
                samples += 1

            if len(global_diffs) < 3:
                return []

            global_med = float(np.median(np.array(global_diffs)))
            if global_med <= 0.01:
                # Near-static video; don't blur anything.
                return []

            boxes: list[tuple[int, int, int, int]] = []
            for name, vals in corner_diffs.items():
                if not vals:
                    continue
                corner_med = float(np.median(np.array(vals)))

                # Corner considered "static overlay" if it changes substantially less
                # than the frame overall.
                ratio = corner_med / (global_med + 1e-6)
                if ratio * 100.0 <= static_threshold:
                    boxes.append(corners[name])

            return boxes
        finally:
            try:
                cap.release()
            except Exception:
                pass

    def _apply_corner_blur_ffmpeg(
        self,
        vstream,
        boxes: list[tuple[int, int, int, int]],
        *,
        sigma: float,
    ):
        """Apply blur to corner boxes by creating a blurred copy and overlaying cropped regions."""
        # IMPORTANT:
        # ffmpeg-python requires an explicit split when a node has multiple outgoing edges.
        # We branch the stream into:
        #   - base (unmodified)
        #   - for_blur (used to create blurred patches)
        split = vstream.split()
        base = split[0]
        for_blur = split[1]

        blurred = for_blur.filter("gblur", sigma=max(0.1, float(sigma)))

        out = base
        for (x, y, w, h) in boxes:
            patch = blurred.crop(x, y, w, h)
            out = ffmpeg.overlay(out, patch, x=x, y=y)
        return out


def extract_audio_from_video(input_path: str, output_folder: str = None) -> str:
    """
    Tách âm thanh mp3 từ video, trả về đường dẫn file mp3.
    Nếu không truyền output_folder sẽ lưu cùng thư mục với input_path.
    """
    processor = VideoProcessor()
    if output_folder is None:
        output_folder = str(Path(input_path).parent)
    _, audio_path = processor.extract_assets(input_path, output_folder)
    return str(audio_path) if audio_path and os.path.exists(audio_path) else None


def process(input_path: str, output_folder: str = None, overwrite: bool = True) -> str:
    """
    Chỉnh sửa video (mirror, speed, color, ...), trả về đường dẫn file đã chỉnh sửa.
    Nếu không truyền output_folder sẽ lưu cùng thư mục với input_path.
    """
    processor = VideoProcessor()
    in_path = Path(input_path)
    if output_folder is None:
        output_folder = str(in_path.parent)
    out_path = Path(output_folder) / f"{in_path.stem}_processed{in_path.suffix}"
    result = processor.process_one(str(in_path), str(out_path), overwrite=overwrite)
    return str(result.output_path) if result and os.path.exists(result.output_path) else None


def sanitize_filename(name: str, max_length: int = 20) -> str:
    # Convert to ASCII (English only)
    name = unidecode.unidecode(name)
    # Remove invalid characters
    name = re.sub(r'[^\w\-_. ]', '', name)
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Truncate to max_length
    return name[:max_length]

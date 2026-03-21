import os
from pathlib import Path

import pytest

from video_processing import VideoProcessor, VideoTransformSettings, ColorGradeSettings, FFmpegNotFoundError


@pytest.mark.skipif(os.environ.get("SKIP_FFMPEG_TESTS") == "1", reason="ffmpeg tests skipped")
def test_build_and_basic_run_tmp(tmp_path: Path):
    """This is a smoke test.

    It generates a tiny synthetic clip with ffmpeg, then processes it.
    Skip if ffmpeg isn't installed.
    """

    vp = VideoProcessor()

    try:
        vp.locator.assert_available()
    except FFmpegNotFoundError:
        pytest.skip("ffmpeg/ffprobe not available")

    # Create a 1s sample mp4 with audio
    src = tmp_path / "src.mp4"
    dst = tmp_path / "dst.mp4"

    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=128x128:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=44100",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(src),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    settings = VideoTransformSettings(
        mirror_horizontal=True,
        speed=1.07,
        color=ColorGradeSettings(contrast=1.05, saturation=1.08),
    )

    res = vp.process_one(src, dst, settings=settings, overwrite=True)
    assert res.returncode == 0
    assert dst.exists()
    assert dst.stat().st_size > 0


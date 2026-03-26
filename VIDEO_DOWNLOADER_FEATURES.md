hiện tại tải video tiktok thì nó đang không cho vào theo tên ví dụ tôi tải video này: https://www.tiktok.com/@anh.nh.em3463/video/7595225981959343380 tại sao ns không tạo folder anh.nh.em3463. thứ 2 là chưa thấy update lên drive# Video Downloader – Feature Summary (Project FastAPIProject)

> Generated on: 2026-03-21 (macOS)

This document summarizes the current download + post-processing pipeline and what it changes (speed/edit/metadata, etc.).

## 1) Download features (yt-dlp)

### 1.1 Supported platforms
- Managed via `config.py` (`SUPPORTED_PLATFORMS`).
- UI entry point: `video_downloader.py` (CustomTkinter GUI).

### 1.2 Single video download
- Core implementation: `downloader_core.py` (`VideoDownloader`).
- Uses `yt-dlp` to fetch metadata (`extract_info(download=False)`) and then download.

### 1.3 Progress reporting + monitor stop hook
- `downloader_core.py` attaches `progress_hooks`.
- When running under `ChannelMonitor`, a hook checks `monitor.is_running`.
  - yt-dlp cannot reliably stop mid-download, but the hook logs and stops after the current operation.

### 1.4 Playlist / list normalization (avoid `string indices must be integers`)
- `downloader_core.py` normalizes `info` when `extract_info()` returns a list/playlist, to avoid treating list entries as dicts.

### 1.5 Folder organization by platform/channel
- Enabled in `video_downloader.py` via `self.downloader.set_organize_by_channel(True)`.
- Output structure can be organized by Platform/Account under the chosen root download folder.

### 1.6 Subtitle download (optional)
- Present as commented options in `downloader_core.py`:
  - `writesubtitles`, `writeautomaticsub`, `subtitleslangs`.

## 2) Channel monitoring (auto-check for new videos)

- Implemented in `downloader_core.py` (`ChannelMonitor`).
- Polling interval controlled by `config.py` (`CHECK_INTERVAL`).
- Flow:
  1) Periodically checks tracked channels.
  2) Detects new uploads.
  3) Downloads new videos.
  4) Optionally calls `postprocess_callback(file_path, video_info)` for edit/split/upload.

## 3) Post-processing (FFmpeg pipeline)

Primary module: `video_processing.py` (`VideoProcessor`).

### 3.1 Edits currently applied (when postprocess/edit is enabled)

#### A) Mirror (horizontal flip)
- Default: enabled (`mirror_horizontal=True`).
- Filter: `hflip`.

#### B) Speed-up
- Default: enabled at **1.07x** (`speed=1.07`).
- Video: `setpts=PTS/speed`.
- Audio: `atempo=speed` (pitch-preserving time-stretch within ffmpeg limits).

#### C) Light color grading
- Default: enabled.
- Filter: `eq` with:
  - `contrast=1.06`
  - `saturation=1.10`

#### D) Static corner logo detection + blur (optional)
- Default: enabled (`blur_static_corner_logos=True`).
- Uses OpenCV to sample frames and detect corners that are unusually static vs. global motion.
- If detected:
  - Creates a blurred stream (`gblur sigma=...`).
  - Crops blurred patches for detected corners.
  - Overlays patches back on top of the original video stream (corner-only blur).
- Tunables (in `VideoTransformSettings`):
  - `corner_roi_frac` (ROI size)
  - `logo_blur_sigma`
  - `logo_detect_frames`, `logo_detect_sample_every`
  - `logo_static_threshold`

### 3.2 Metadata stripping (YES)
- When producing the processed output, metadata is stripped via:
  - `map_metadata=-1`
  - `map_chapters=-1`

Important:
- This applies to the **processed output** created by `VideoProcessor`.
- The raw file produced directly by yt-dlp may still contain metadata if no postprocess step runs.

## 4) Split long videos (optional)

- Module: `video_splitter.py`.
- Config:
  - `SPLIT_IF_LONGER_THAN_SECONDS`
  - `SPLIT_SEGMENT_SECONDS`
- Imported/used from `video_downloader.py`.

## 5) Upload to Google Drive (optional)

- Module: `drive_uploader.py`.
- Controlled by UI flags (loaded from `user_settings.json`).

## 6) Asset extraction for downstream pipeline (Sanitization / Pitch Shifting)

Method: `VideoProcessor.extract_assets(input_path, output_folder)` in `video_processing.py`.

Outputs two files:
1) **Muted video (MP4)**
   - Stream copy for max speed and zero quality loss:
   - `-c:v copy` and `-an`
   - Filename: `<stem>_muted.mp4`

2) **Audio (MP3 192k)**
   - `libmp3lame` at `192k`
   - Filename: `<stem>.mp3`

Returns:
- `(muted_video_path: Path, audio_path: Path)`

## 7) Dependencies relevant to these features

From `requirements.txt`:
- `yt-dlp` (downloading)
- `ffmpeg-python` (FFmpeg graph building)
- `opencv-python`, `numpy` (corner logo detection)

System requirements:
- `ffmpeg` + `ffprobe` available in PATH.

## 8) Where to toggle behaviors

- UI flags are loaded in `video_downloader.py` via `user_settings.py`:
  - `edit_after_download` (controls whether `VideoProcessor` runs)
  - `upload_to_drive`
- Monitor behavior: `ChannelMonitor(..., postprocess_callback=...)` in `video_downloader.py`.

---

## Quick checklist (what you asked)

- **Đã tăng tốc độ chưa?** ✅ Yes, **1.07x** in `VideoProcessor` (postprocess).
- **Edit những gì?** ✅ Mirror, speed-up, light grading, optional corner-logo blur.
- **Đã xóa metadata chưa?** ✅ Yes on processed outputs (`map_metadata=-1`, `map_chapters=-1`).
- **Nếu không edit thì có xóa metadata không?** ⚠️ Not guaranteed; depends if postprocess runs.


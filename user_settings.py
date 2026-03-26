"""Lưu/đọc setting người dùng (thư mục lưu video, ...)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")


@dataclass
class UserSettings:
    download_root: str | None = None
    edit_after_download: bool = False
    upload_to_drive: bool = False
    split_after_download: bool = False


def load_settings() -> UserSettings:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return UserSettings(
            download_root=data.get("download_root"),
            edit_after_download=bool(data.get("edit_after_download", False)),
            upload_to_drive=bool(data.get("upload_to_drive", False)),
            split_after_download=bool(data.get("split_after_download", False)),
        )
    except FileNotFoundError:
        return UserSettings()
    except Exception:
        return UserSettings()


def save_settings(settings: UserSettings) -> None:
    data = {
        "download_root": settings.download_root,
        "edit_after_download": bool(settings.edit_after_download),
        "upload_to_drive": bool(getattr(settings, "upload_to_drive", False)),
        "split_after_download": bool(getattr(settings, "split_after_download", False)),
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

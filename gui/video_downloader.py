"""
Ứng dụng tải video đa nền tảng với giao diện GUI
Hỗ trợ: YouTube, TikTok, Douyin, Facebook
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import time

from core.database import DownloadHistory
from core.downloader_core import VideoDownloader, ChannelMonitor
from config.config import (
    SUPPORTED_PLATFORMS,
    MAX_CHANNELS_PER_PLATFORM,
    CHECK_INTERVAL
)
# Cấu hình split video
from config.config import SPLIT_IF_LONGER_THAN_SECONDS, SPLIT_SEGMENT_SECONDS

from user_settings import load_settings, save_settings, UserSettings

# Thêm module xử lý video (FFmpeg)
from core.video_processing import VideoProcessor, VideoTransformSettings
from core.video_splitter import split_if_longer_than


class VideoDownloaderApp(ctk.CTk):
    """Ứng dụng chính với giao diện GUI"""

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # Cấu hình cửa sổ chính
        self.title("Studio Reup - Video Pipeline")
        self.geometry("1380x860")
        self.minsize(1180, 760)

        self.theme = {
            "bg": "#F4EEE7",
            "panel": "#FBF7F2",
            "panel_alt": "#F7F0E8",
            "sidebar": "#11263B",
            "sidebar_alt": "#1A3552",
            "accent": "#C86A4A",
            "accent_hover": "#B55B3C",
            "accent_soft": "#EFD4CA",
            "text": "#13263A",
            "muted": "#6D7986",
            "line": "#D8CBBE",
            "success": "#2F7A68",
            "warning": "#C68432",
            "chip": "#E9DED1",
        }
        self.page_meta = {
            "download": {
                "title": "Download Studio",
                "subtitle": "Nhanh, gọn, đẹp. Tải video, xử lý hậu kỳ và chuẩn bị asset cho reup.",
            },
            "monitor": {
                "title": "Channel Radar",
                "subtitle": "Theo dõi kênh, phát hiện video mới và kiểm soát trạng thái monitor theo phiên.",
            },
            "stats": {
                "title": "Data Vault",
                "subtitle": "Xem tải xuống, thư mục đang chạy và danh sách kênh dưới cùng một visual language.",
            },
        }
        self.nav_buttons = {}
        self.current_page = "download"

        # Khởi tạo các components
        self.database = DownloadHistory()

        settings = load_settings()
        default_root = settings.download_root or os.path.join(os.getcwd(), "downloads")

        # Thư mục gốc hiện tại
        self.download_path = default_root

        # Flag: có edit video sau khi tải không?
        self.edit_after_download = bool(getattr(settings, "edit_after_download", False))
        # Flag: có upload lên Google Drive sau khi tải không?
        self.upload_to_drive = bool(getattr(settings, "upload_to_drive", False))
        # NEW: Flag: có tách video sau khi tải không?
        self.split_after_download = bool(getattr(settings, "split_after_download", False))

        # Khởi tạo downloader với đúng download_path
        self.downloader = VideoDownloader(download_path=self.download_path)
        # BẬT phân cấp Platform/Account bên trong thư mục user chọn
        self.downloader.set_organize_by_channel(True)

        # Video processor (FFmpeg)
        self.video_processor = VideoProcessor()
        self.video_edit_settings = VideoTransformSettings()  # default: mirror + 1.07x + grade nhẹ

        self.channel_monitor = ChannelMonitor(
            self.downloader,
            self.database,
            CHECK_INTERVAL,
            # callback nhận (file_path, video_info) từ ChannelMonitor
            postprocess_callback=self._channel_monitor_postprocess,
        )

        # Biến lưu trạng thái
        self.is_monitoring = False

        # Tạo giao diện
        self.create_widgets()

        # Mousewheel/trackpad UX: scroll mượt khi hover trên các scrollable frame
        self._wheel_bindings = []  # lưu để unbind nếu cần

    def _bind_mousewheel_for_scrollable(self, scrollable: "ctk.CTkScrollableFrame"):
        """Bind scroll wheel/trackpad cho CTkScrollableFrame.

        Mục tiêu: khi con trỏ đang nằm ở vùng scroll, wheel/trackpad sẽ cuộn đúng vùng đó,
        kể cả khi focus ở widget con hoặc có scrollable frame lồng nhau.
        """
        try:
            canvas = scrollable._parent_canvas  # customtkinter implementation detail
        except Exception:
            return

        def _on_mousewheel(event):
            # Windows/Linux: event.delta (±120), macOS: delta nhỏ hơn; X11 dùng Button-4/5.
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            else:
                d = getattr(event, "delta", 0)
                if d == 0:
                    return
                delta = -1 if d > 0 else 1

            try:
                canvas.yview_scroll(delta, "units")
            except Exception:
                pass

            return "break"  # tránh scroll "lọt" ra widget khác

        # Bind khi hover vào scrollable, unbind khi rời để tránh ảnh hưởng toàn app
        def _bind(_evt=None):
            # macOS/Windows
            self.bind_all("<MouseWheel>", _on_mousewheel)
            # Linux/X11
            self.bind_all("<Button-4>", _on_mousewheel)
            self.bind_all("<Button-5>", _on_mousewheel)

        def _unbind(_evt=None):
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")

        # bind trên chính scrollable + canvas để bắt event cả vùng trống
        scrollable.bind("<Enter>", _bind)
        scrollable.bind("<Leave>", _unbind)
        try:
            canvas.bind("<Enter>", _bind)
            canvas.bind("<Leave>", _unbind)
        except Exception:
            pass

    def _create_metric_card(self, parent, title: str, value: str, note: str, accent: str = None):
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme["panel"],
            corner_radius=22,
            border_width=1,
            border_color=self.theme["line"],
        )
        ctk.CTkLabel(
            card,
            text=title,
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        value_label = ctk.CTkLabel(
            card,
            text=value,
            text_color=accent or self.theme["text"],
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        value_label.pack(anchor="w", padx=18)
        ctk.CTkLabel(
            card,
            text=note,
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(6, 16))
        card.value_label = value_label
        return card

    def _create_nav_button(self, parent, key: str, label: str):
        button = ctk.CTkButton(
            parent,
            text=label,
            anchor="w",
            height=44,
            corner_radius=14,
            fg_color="transparent",
            hover_color=self.theme["sidebar_alt"],
            text_color="#EDE5DD",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda page=key: self.show_page(page),
        )
        button.pack(fill="x", pady=4)
        self.nav_buttons[key] = button
        return button

    def _update_navigation_state(self):
        for key, button in self.nav_buttons.items():
            if key == self.current_page:
                button.configure(
                    fg_color=self.theme["accent"],
                    hover_color=self.theme["accent_hover"],
                    text_color="#FFF6F2",
                )
            else:
                button.configure(
                    fg_color="transparent",
                    hover_color=self.theme["sidebar_alt"],
                    text_color="#EDE5DD",
                )

    def show_page(self, page: str):
        self.current_page = page
        if hasattr(self, "page_frames") and page in self.page_frames:
            self.page_frames[page].tkraise()
        meta = self.page_meta.get(page, {})
        if hasattr(self, "page_title_label"):
            self.page_title_label.configure(text=meta.get("title", "Studio Reup"))
        if hasattr(self, "page_subtitle_label"):
            self.page_subtitle_label.configure(text=meta.get("subtitle", ""))
        self._update_navigation_state()

    def update_shell_snapshot(self):
        if hasattr(self, "snapshot_root_value"):
            current_root = os.path.basename(self.download_path.rstrip(os.sep)) or self.download_path
            self.snapshot_root_value.configure(text=current_root)
        if hasattr(self, "snapshot_pipeline_value"):
            pipeline_parts = [
                "Edit On" if self.edit_after_download else "Edit Off",
                "Split On" if self.split_after_download else "Split Off",
                "Drive On" if self.upload_to_drive else "Drive Off",
            ]
            self.snapshot_pipeline_value.configure(text=" | ".join(pipeline_parts))
        if hasattr(self, "snapshot_monitor_value"):
            try:
                all_channels = self.database.get_monitored_channels(only_active=False)
                active_channels = self.database.get_monitored_channels(only_active=True)
                self.snapshot_monitor_value.configure(text=f"{len(active_channels)}/{len(all_channels)} active")
            except Exception:
                self.snapshot_monitor_value.configure(text="0/0 active")
        if hasattr(self, "download_profile_label"):
            outputs = ["video processed"]
            outputs.append("part files" if self.split_after_download else "single file")
            outputs.append("drive sync" if self.upload_to_drive else "local only")
            self.download_profile_label.configure(
                text=(
                    f"Root: {self.download_path}\n"
                    f"Folder: ROOT/Platform/Channel\n"
                    f"Pipeline: {', '.join(outputs)}"
                )
            )
        if hasattr(self, "monitor_summary_label"):
            self.monitor_summary_label.configure(
                text=(
                    f"Quét mỗi {CHECK_INTERVAL // 60} phút. "
                    f"Tối đa {MAX_CHANNELS_PER_PLATFORM} kênh mỗi nền tảng."
                )
            )

    def create_widgets(self):
        """Tạo các widget cho giao diện"""
        self.configure(fg_color=self.theme["bg"])

        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(
            shell,
            width=258,
            corner_radius=30,
            fg_color=self.theme["sidebar"],
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 16))
        sidebar.grid_propagate(False)

        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=22, pady=(24, 18))
        ctk.CTkLabel(
            brand_frame,
            text="Studio Reup",
            text_color="#FFF5EC",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_frame,
            text="Premium desktop pipeline cho đội reup và internal ops.",
            text_color="#B8C6D4",
            font=ctk.CTkFont(size=12),
            wraplength=205,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=18, pady=(6, 18))
        self._create_nav_button(nav_frame, "download", "Download Studio")
        self._create_nav_button(nav_frame, "monitor", "Channel Radar")
        self._create_nav_button(nav_frame, "stats", "Data Vault")

        snapshot_card = ctk.CTkFrame(sidebar, fg_color=self.theme["sidebar_alt"], corner_radius=24)
        snapshot_card.pack(fill="x", padx=18, pady=(8, 0))
        ctk.CTkLabel(
            snapshot_card,
            text="Live Snapshot",
            text_color="#FFF5EC",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 12))

        def add_snapshot_row(label_text: str):
            row = ctk.CTkFrame(snapshot_card, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=4)
            ctk.CTkLabel(
                row,
                text=label_text,
                text_color="#B8C6D4",
                font=ctk.CTkFont(size=12),
            ).pack(side="left")
            value = ctk.CTkLabel(
                row,
                text="-",
                text_color="#FFF5EC",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            value.pack(side="right")
            return value

        self.snapshot_root_value = add_snapshot_row("Root")
        self.snapshot_pipeline_value = add_snapshot_row("Pipeline")
        self.snapshot_monitor_value = add_snapshot_row("Monitor")

        ctk.CTkLabel(
            snapshot_card,
            text="Thiết kế theo hướng demo khách hàng: dữ liệu rõ, trạng thái rõ, thao tác chính luôn nổi bật.",
            text_color="#B8C6D4",
            font=ctk.CTkFont(size=11),
            wraplength=200,
            justify="left",
        ).pack(anchor="w", padx=18, pady=(12, 18))

        footer_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer_frame.pack(side="bottom", fill="x", padx=18, pady=18)
        ctk.CTkLabel(
            footer_frame,
            text="YouTube • TikTok • Douyin • Facebook",
            text_color="#90A0B1",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w")

        main = ctk.CTkFrame(shell, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        header_card = ctk.CTkFrame(
            main,
            fg_color=self.theme["panel"],
            corner_radius=30,
            border_width=1,
            border_color=self.theme["line"],
        )
        header_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header_card.grid_columnconfigure(0, weight=1)

        title_wrap = ctk.CTkFrame(header_card, fg_color="transparent")
        title_wrap.grid(row=0, column=0, sticky="w", padx=24, pady=(20, 10))
        self.page_title_label = ctk.CTkLabel(
            title_wrap,
            text="Download Studio",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=30, weight="bold"),
        )
        self.page_title_label.pack(anchor="w")
        self.page_subtitle_label = ctk.CTkLabel(
            title_wrap,
            text="Nhanh, gọn, đẹp. Tải video, xử lý hậu kỳ và chuẩn bị asset cho reup.",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=13),
        )
        self.page_subtitle_label.pack(anchor="w", pady=(6, 0))

        chips_wrap = ctk.CTkFrame(header_card, fg_color="transparent")
        chips_wrap.grid(row=0, column=1, sticky="e", padx=24, pady=(20, 10))
        self.monitoring_indicator = ctk.CTkLabel(
            chips_wrap,
            text="●",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.monitoring_indicator.pack(side="left", padx=(0, 10))
        self.runtime_chip = ctk.CTkLabel(
            chips_wrap,
            text="Internal Tool",
            fg_color=self.theme["chip"],
            text_color=self.theme["text"],
            corner_radius=16,
            padx=14,
            pady=8,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.runtime_chip.pack(side="left", padx=6)
        self.status_label = ctk.CTkLabel(
            chips_wrap,
            text="San sang",
            fg_color=self.theme["accent_soft"],
            text_color=self.theme["accent"],
            corner_radius=16,
            padx=14,
            pady=8,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_label.pack(side="left", padx=6)

        controls_card = ctk.CTkFrame(
            main,
            fg_color=self.theme["panel_alt"],
            corner_radius=26,
            border_width=1,
            border_color=self.theme["line"],
        )
        controls_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        controls_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            controls_card,
            text="Storage Root",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(24, 12), pady=(18, 10), sticky="w")

        self.path_entry = ctk.CTkEntry(
            controls_card,
            height=40,
            corner_radius=16,
            fg_color=self.theme["panel"],
            border_color=self.theme["line"],
            text_color=self.theme["text"],
        )
        self.path_entry.insert(0, self.download_path)
        self.path_entry.grid(row=0, column=1, padx=0, pady=(18, 10), sticky="ew")

        browse_btn = ctk.CTkButton(
            controls_card,
            text="Chon thu muc",
            width=132,
            height=40,
            corner_radius=16,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
            command=self.browse_folder,
        )
        browse_btn.grid(row=0, column=2, padx=16, pady=(18, 10))

        toggle_row = ctk.CTkFrame(controls_card, fg_color="transparent")
        toggle_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 18))

        self.edit_var = ctk.BooleanVar(value=self.edit_after_download)
        edit_cb = ctk.CTkCheckBox(
            toggle_row,
            text="Edit after download",
            variable=self.edit_var,
            command=self.on_toggle_edit_after_download,
            text_color=self.theme["text"],
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
            border_color=self.theme["accent"],
        )
        edit_cb.pack(side="left", padx=6)

        self.upload_drive_var = ctk.BooleanVar(value=self.upload_to_drive)
        upload_drive_cb = ctk.CTkCheckBox(
            toggle_row,
            text="Google Drive sync",
            variable=self.upload_drive_var,
            command=self.on_toggle_upload_drive,
            text_color=self.theme["text"],
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
            border_color=self.theme["accent"],
        )
        upload_drive_cb.pack(side="left", padx=14)

        self.split_var = ctk.BooleanVar(value=self.split_after_download)
        split_cb = ctk.CTkCheckBox(
            toggle_row,
            text=f"Auto split > {int(SPLIT_IF_LONGER_THAN_SECONDS)}s",
            variable=self.split_var,
            command=self.on_toggle_split_after_download,
            text_color=self.theme["text"],
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
            border_color=self.theme["accent"],
        )
        split_cb.pack(side="left", padx=14)

        self.pages_container = ctk.CTkFrame(main, fg_color="transparent")
        self.pages_container.grid(row=2, column=0, sticky="nsew")
        self.pages_container.grid_rowconfigure(0, weight=1)
        self.pages_container.grid_columnconfigure(0, weight=1)

        self.tab_download = ctk.CTkFrame(self.pages_container, fg_color="transparent")
        self.tab_monitor = ctk.CTkFrame(self.pages_container, fg_color="transparent")
        self.tab_stats = ctk.CTkFrame(self.pages_container, fg_color="transparent")
        self.page_frames = {
            "download": self.tab_download,
            "monitor": self.tab_monitor,
            "stats": self.tab_stats,
        }
        for frame in self.page_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self.create_download_tab()
        self.create_monitor_tab()
        self.create_stats_tab()
        self.show_page("download")
        self.update_shell_snapshot()

    def on_toggle_edit_after_download(self):
        """Lưu setting khi user bật/tắt edit."""
        self.edit_after_download = bool(self.edit_var.get())
        current = load_settings()
        # Lưu thêm upload_to_drive nếu có
        self.upload_to_drive = bool(getattr(current, "upload_to_drive", False))
        self.split_after_download = bool(getattr(current, "split_after_download", False))
        save_settings(
            UserSettings(
                download_root=current.download_root,
                edit_after_download=self.edit_after_download,
                upload_to_drive=self.upload_to_drive,
                split_after_download=self.split_after_download,
            )
        )
        self.update_shell_snapshot()
        self.log_message(f"✂️ Edit sau khi tải: {'BẬT' if self.edit_after_download else 'TẮT'}")

    def on_toggle_upload_drive(self):
        """Lưu setting khi user bật/tắt upload Google Drive."""
        self.upload_to_drive = bool(self.upload_drive_var.get())
        current = load_settings()
        save_settings(
            UserSettings(
                download_root=current.download_root,
                edit_after_download=bool(getattr(current, "edit_after_download", False)),
                upload_to_drive=self.upload_to_drive,
                split_after_download=bool(getattr(current, "split_after_download", False)),
            )
        )
        self.update_shell_snapshot()
        self.log_message(f"☁️ Upload Google Drive sau khi tải: {'BẬT' if self.upload_to_drive else 'TẮT'}")

    def on_toggle_split_after_download(self):
        """Lưu setting khi user bật/tắt tách video."""
        self.split_after_download = bool(self.split_var.get())
        current = load_settings()
        save_settings(
            UserSettings(
                download_root=current.download_root,
                edit_after_download=bool(getattr(current, "edit_after_download", False)),
                upload_to_drive=bool(getattr(current, "upload_to_drive", False)),
                split_after_download=self.split_after_download,
            )
        )
        self.update_shell_snapshot()
        self.log_message(f"✂️ Tách video sau khi tải: {'BẬT' if self.split_after_download else 'TẮT'}")

    def _postprocess_master(self, file_path: str) -> str:
        """Apply the basic edit (if enabled) and return the master output path.

        This is the file considered 'gốc' per requirement (after basic edits).
        No splitting is performed here.
        """
        if not file_path:
            return file_path
        src = os.path.abspath(file_path)
        if not os.path.exists(src):
            return file_path

        # If edit is disabled, master is the downloaded file.
        if not self.edit_after_download:
            return src

        base, ext = os.path.splitext(src)
        out = base + "_edited" + (ext or ".mp4")

        self.log_message("✂️ Đang edit video bằng FFmpeg...")
        self.update_status("✂️ Đang edit video...")

        self.video_processor.process_one(
            src,
            out,
            settings=self.video_edit_settings,
            overwrite=True,
        )
        self.log_message(f"✓ Edit xong: {os.path.basename(out)}")
        return out

    def _maybe_post_process_downloaded_file(self, file_path: str) -> str:
        """Legacy wrapper: basic edit (if enabled) then optional split.

        Returns path used for DB compatibility (first part if split happens).
        """
        try:
            master = self._postprocess_master(file_path)
            return self._maybe_split_long_video(master)
        except Exception as e:
            self.log_message(f"⚠️ Edit thất bại, giữ file gốc. Lỗi: {e}")
            return self._maybe_split_long_video(file_path)

    def _channel_monitor_postprocess(self, file_path: str, video_info: dict) -> str:
        """Callback cho ChannelMonitor: xử lý giống logic tải theo link (edit + split + upload nếu bật)."""
        # Sử dụng đúng luồng xử lý như bên tải theo link
        try:
            result = self.downloader.process_and_upload(
                video_info.get("url", None) or video_info.get("video_url", None),
                split=self.split_after_download,
                extract_audio=self.edit_after_download,
                progress_callback=None,
                quality="best",
                monitor=None,
                channel_url=video_info.get("channel_url", None),
                platform=video_info.get("platform", None),
                log_callback=self.log_message
            )
            # Lấy file đầu ra (giống bên download_single_video)
            uploaded_videos = result.get('video_files', [])
            video_paths = [f['file'] for f in uploaded_videos]
            processed_path = video_paths[0] if video_paths else file_path
            return processed_path
        except Exception as e:
            self.log_message(f"⚠️ Xử lý hậu tải (monitor) lỗi: {e}")
            return file_path

    def download_single_video(self):
        """Tải một video từ URL"""
        url = self.url_entry.get().strip()
        selected_quality = (self.quality_selector.get() if hasattr(self, "quality_selector") else "Best").lower()
        quality_map = {
            "best": "best",
            "4k": "4k",
            "1080p": "1080p",
            "720p": "720p",
            "480p": "480p",
        }
        quality = quality_map.get(selected_quality, "best")

        if not url:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập URL video!")
            return

        # Disable nút tải
        self.download_btn.configure(state="disabled", text="⏳ Đang tải...")
        self.progress_bar.set(0.3)

        # Tải video trong thread riêng
        def download_thread():
            self.log_message(f"📁 ROOT hiện tại: {self.download_path}")
            self.log_message(f"🔄 Bắt đầu tải: {url}")
            self.update_status("⏳ Đang tải video...")
            self.log_message(f"URL đang tải: {url}")

            # Sử dụng process_and_upload để đảm bảo đúng luồng xử lý
            result = self.downloader.process_and_upload(
                url,
                split=self.split_after_download,
                extract_audio=self.edit_after_download,  # hoặc thêm flag riêng nếu muốn tách âm độc lập
                progress_callback=None,
                quality=quality,
                monitor=None,
                channel_url=None
            )

            if result.get('success'):
                # Lấy file video và audio đã upload (nếu có)
                uploaded_videos = result.get('video_files', [])
                uploaded_audios = result.get('audio_files', [])
                video_paths = [f['file'] for f in uploaded_videos]
                audio_paths = [f['file'] for f in uploaded_audios]
                processed_path = video_paths[0] if video_paths else None

                # Lưu vào database
                video_id = self.downloader.extract_video_id(
                    url,
                    result.get('video_files', [{}])[0].get('file', 'Unknown') if result.get('video_files') else 'Unknown'
                )

                self.database.add_downloaded_video(
                    video_id=video_id,
                    video_url=url,
                    platform=result.get('url', 'Unknown'),
                    title=result.get('url', ''),
                    file_path=processed_path
                )

                self.log_message(f"✅ Tải thành công: {url}")
                self.update_status("✓ Tải thành công!")
                self.progress_bar.set(1.0)
                messagebox.showinfo("Thành công", f"Đã tải xong: {url}")
            else:
                error_msg = result.get('error', 'Lỗi không xác định')
                self.log_message(f"❌ Lỗi: {error_msg}")
                self.update_status("✗ Lỗi tải video")
                self.progress_bar.set(0)

                messagebox.showerror("Lỗi", f"Không thể tải video:\n{error_msg}")

            # Enable lại nút tải
            self.download_btn.configure(state="normal", text="⬇️ Tải Video")
            self.url_entry.delete(0, "end")

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def toggle_monitoring(self):
        """Bật/tắt chế độ theo dõi kênh"""
        if not self.is_monitoring:
            # Chỉ chạy monitor nếu có ít nhất 1 kênh active
            active_channels = self.database.get_monitored_channels(only_active=True)
            if not active_channels:
                messagebox.showwarning(
                    "Chưa có kênh Active",
                    "Bạn chưa tick Active cho kênh nào.\n\n"
                    "Hãy tick checkbox Active ở danh sách kênh để bắt đầu tải video từ kênh đó."
                )
                return

            # Bắt đầu monitoring
            self.is_monitoring = True
            self.channel_monitor.start_monitoring(status_callback=self.monitoring_callback)

            self.monitor_btn.configure(
                text="DUNG THEO DOI",
                fg_color="#B5483D",
                hover_color="#91372F"
            )
            self.monitoring_indicator.configure(text_color=self.theme["success"])
            if hasattr(self, "monitor_feed_label"):
                self.monitor_feed_label.configure(text="Monitor đang chạy. Hệ thống sẽ quét theo cadence hiện tại.")
            self.log_message("▶️ Đã bắt đầu theo dõi kênh tự động")
            self.update_status("🔴 Đang theo dõi kênh...")
        else:
            # Dừng monitoring
            self.is_monitoring = False
            self.channel_monitor.stop_monitoring()

            self.monitor_btn.configure(
                text="BAT DAU THEO DOI",
                fg_color=self.theme["success"],
                hover_color="#266657"
            )
            self.monitoring_indicator.configure(text_color=self.theme["muted"])
            if hasattr(self, "monitor_feed_label"):
                self.monitor_feed_label.configure(text="Monitor đã dừng. Chỉ còn thao tác quản trị và xem dữ liệu.")
            self.log_message("⏸️ Đã dừng theo dõi kênh")
            self.update_status("✓ Đã dừng theo dõi")
        self.update_shell_snapshot()

    def monitoring_callback(self, message: str):
        """Callback từ channel monitor"""
        self.log_message(message)
        if hasattr(self, "monitor_feed_label"):
            self.monitor_feed_label.configure(text=message)

        # Auto-refresh danh sách khi có video mới được tải
        if "✓ Đã tải:" in message or "✅ Hoàn thành lần quét đầu" in message:
            # Dùng after để refresh UI trong main thread
            self.after(500, self.refresh_channel_list)

    def browse_folder(self):
        """Mở dialog chọn thư mục"""
        folder = filedialog.askdirectory(initialdir=self.download_path)
        if folder:
            self.download_path = folder
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

            self.downloader.download_path = folder
            self.downloader.create_download_folder()
            self.downloader.set_organize_by_channel(True)

            # Lưu setting để lần sau mở app không bị quay về ./downloads
            current = load_settings()
            save_settings(
                UserSettings(
                    download_root=folder,
                    edit_after_download=bool(getattr(current, 'edit_after_download', False)),
                    upload_to_drive=bool(getattr(current, 'upload_to_drive', False)),
                    split_after_download=bool(getattr(current, 'split_after_download', False)),
                )
            )

            self.update_shell_snapshot()
            self.log_message(f"✓ Đã chọn thư mục gốc: {folder}")

    def log_message(self, message: str):
        """Thêm message vào log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")
        if hasattr(self, "activity_label"):
            self.activity_label.configure(text=message)

    def clear_log(self):
        """Xóa toàn bộ nội dung log trên UI."""
        try:
            self.log_textbox.delete("1.0", "end")
        except Exception:
            return
        # Sau khi clear, thêm 1 dòng xác nhận để user biết thao tác đã chạy
        timestamp = time.strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] 🧹 Đã xóa log\n")
        self.log_textbox.see("end")

    def update_status(self, message: str):
        """Cập nhật status bar"""
        self.status_label.configure(text=message)
        self.runtime_chip.configure(text="Monitoring" if self.is_monitoring else "Internal Tool")

    def update_platform_example(self, choice):
        """Cập nhật ví dụ URL theo platform được chọn."""
        example = SUPPORTED_PLATFORMS.get(choice, {}).get("example", "")
        # fallback nếu data config thiếu
        if not example:
            example = "(Không có ví dụ)"
        try:
            self.platform_example_label.configure(text=f"VD: {example}")
        except Exception:
            # Trong trường hợp UI chưa init xong
            pass

    def create_download_tab(self):
        """Tạo tab tải video theo link"""
        container = ctk.CTkFrame(self.tab_download, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)
        container.grid_columnconfigure(0, weight=3)
        container.grid_columnconfigure(1, weight=2)
        container.grid_rowconfigure(1, weight=1)

        hero = ctk.CTkFrame(
            container,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        hero.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ctk.CTkLabel(
            hero,
            text="Download Studio",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            hero,
            text="Một màn cho cả tải, chọn chất lượng, branding và trạng thái pipeline.",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=22)

        platform_row = ctk.CTkFrame(hero, fg_color="transparent")
        platform_row.pack(fill="x", padx=18, pady=(16, 10))
        for platform_name, data in SUPPORTED_PLATFORMS.items():
            ctk.CTkLabel(
                platform_row,
                text=platform_name,
                fg_color=data.get("color", self.theme["chip"]),
                text_color="#FFFFFF" if platform_name != "TikTok" else "#FFFFFF",
                corner_radius=14,
                padx=12,
                pady=6,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="left", padx=4)

        self.url_entry = ctk.CTkEntry(
            hero,
            placeholder_text="Dán link video từ YouTube, TikTok, Douyin hoặc Facebook...",
            height=46,
            corner_radius=16,
            fg_color="#FFFFFF",
            border_color=self.theme["line"],
            text_color=self.theme["text"],
        )
        self.url_entry.pack(fill="x", padx=22, pady=(0, 14))

        quality_frame = ctk.CTkFrame(hero, fg_color=self.theme["panel_alt"], corner_radius=18)
        quality_frame.pack(fill="x", padx=22, pady=(0, 14))
        ctk.CTkLabel(
            quality_frame,
            text="Quality preset",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))
        self.quality_selector = ctk.CTkSegmentedButton(
            quality_frame,
            values=["Best", "4K", "1080p", "720p", "480p"],
            fg_color=self.theme["chip"],
            selected_color=self.theme["accent"],
            selected_hover_color=self.theme["accent_hover"],
            unselected_color=self.theme["chip"],
            unselected_hover_color=self.theme["accent_soft"],
            text_color=self.theme["text"],
            corner_radius=12,
        )
        self.quality_selector.pack(fill="x", padx=16, pady=(0, 16))
        self.quality_selector.set("Best")

        logo_frame = ctk.CTkFrame(hero, fg_color="transparent")
        logo_frame.pack(fill="x", padx=22, pady=(0, 16))

        self.logo_path = None
        self.logo_position = ctk.StringVar(value="top-left")

        def choose_logo_file():
            file_path = filedialog.askopenfilename(
                title="Chọn file logo",
                filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
            )
            if file_path:
                self.logo_path = file_path
                logo_label.configure(text=f"Logo: {os.path.basename(file_path)}")
            else:
                self.logo_path = None
                logo_label.configure(text="Logo: khong chon")

        logo_btn = ctk.CTkButton(
            logo_frame,
            text="Chon logo",
            command=choose_logo_file,
            width=120,
            corner_radius=14,
            fg_color=self.theme["panel_alt"],
            hover_color=self.theme["accent_soft"],
            text_color=self.theme["text"],
        )
        logo_btn.pack(side="left", padx=(0, 10))
        logo_label = ctk.CTkLabel(
            logo_frame,
            text="Logo: khong chon",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
        )
        logo_label.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            logo_frame,
            text="Vi tri",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(10, 6))
        logo_pos_menu = ctk.CTkOptionMenu(
            logo_frame,
            values=["top-left", "top-right", "bottom-left", "bottom-right"],
            variable=self.logo_position,
            corner_radius=14,
            fg_color=self.theme["accent"],
            button_color=self.theme["accent"],
            button_hover_color=self.theme["accent_hover"],
        )
        logo_pos_menu.pack(side="left", padx=(0, 10))

        action_row = ctk.CTkFrame(hero, fg_color="transparent")
        action_row.pack(fill="x", padx=22, pady=(0, 20))
        self.download_btn = ctk.CTkButton(
            action_row,
            text="Tai video ngay",
            height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=16,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
            command=self.download_single_video
        )
        self.download_btn.pack(side="left", padx=(0, 14))

        self.progress_bar = ctk.CTkProgressBar(
            action_row,
            progress_color=self.theme["accent"],
            fg_color=self.theme["chip"],
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, pady=8)
        self.progress_bar.set(0)

        right_panel = ctk.CTkFrame(
            container,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        right_panel.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        ctk.CTkLabel(
            right_panel,
            text="Pipeline Profile",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=22, pady=(20, 4))
        self.download_profile_label = ctk.CTkLabel(
            right_panel,
            text="",
            text_color=self.theme["muted"],
            justify="left",
            wraplength=320,
            font=ctk.CTkFont(size=12),
        )
        self.download_profile_label.pack(anchor="w", padx=22, pady=(0, 18))

        profile_cards = ctk.CTkFrame(right_panel, fg_color="transparent")
        profile_cards.pack(fill="x", padx=18, pady=(0, 8))
        self._create_metric_card(
            profile_cards,
            "Branding",
            "Logo + corner",
            "Watermark sẽ đi cùng file processed nếu bạn chọn logo trước khi tải.",
            accent=self.theme["accent"],
        ).pack(fill="x", pady=6)
        self._create_metric_card(
            profile_cards,
            "Output",
            "MP4 first",
            "Giữ cấu trúc rõ: file processed, part files nếu split và asset audio khi luồng yêu cầu.",
            accent=self.theme["success"],
        ).pack(fill="x", pady=6)

        activity_card = ctk.CTkFrame(
            right_panel,
            fg_color=self.theme["panel_alt"],
            corner_radius=20,
        )
        activity_card.pack(fill="x", padx=18, pady=(8, 18))
        ctk.CTkLabel(
            activity_card,
            text="Live activity",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))
        self.activity_label = ctk.CTkLabel(
            activity_card,
            text="San sang nhan link moi.",
            text_color=self.theme["muted"],
            justify="left",
            wraplength=320,
            font=ctk.CTkFont(size=12),
        )
        self.activity_label.pack(anchor="w", padx=16, pady=(0, 14))

        log_frame = ctk.CTkFrame(
            container,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=18, pady=(18, 8))
        ctk.CTkLabel(
            log_header,
            text="Download feed",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        clear_log_btn = ctk.CTkButton(
            log_header,
            text="Clear log",
            width=104,
            height=32,
            corner_radius=12,
            command=self.clear_log,
            fg_color=self.theme["panel_alt"],
            hover_color=self.theme["accent_soft"],
            text_color=self.theme["text"],
        )
        clear_log_btn.pack(side="right")

        self.log_textbox = ctk.CTkTextbox(
            log_frame,
            height=220,
            corner_radius=20,
            fg_color="#FFFDFC",
            border_width=0,
            text_color=self.theme["text"],
        )
        self.log_textbox.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.update_shell_snapshot()

    def create_monitor_tab(self):
        """Tạo tab theo dõi kênh"""
        container = ctk.CTkFrame(self.tab_monitor, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)

        summary_row = ctk.CTkFrame(container, fg_color="transparent")
        summary_row.pack(fill="x", pady=(0, 12))
        for column in range(3):
            summary_row.grid_columnconfigure(column, weight=1)

        self.monitor_channels_card = self._create_metric_card(
            summary_row,
            "Tracked channels",
            "0",
            "Toàn bộ kênh đang lưu trong database, bao gồm active và inactive.",
            accent=self.theme["accent"],
        )
        self.monitor_channels_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.monitor_active_card = self._create_metric_card(
            summary_row,
            "Live monitor",
            "0 active",
            "Những kênh được tick active sẽ được monitor đưa vào phiên quét.",
            accent=self.theme["success"],
        )
        self.monitor_active_card.grid(row=0, column=1, sticky="ew", padx=8)
        self.monitor_interval_card = self._create_metric_card(
            summary_row,
            "Cadence",
            f"{CHECK_INTERVAL // 60} min",
            "Tần suất quét hiện tại của monitor. Dùng để cân bằng tốc độ và độ ổn định.",
            accent=self.theme["warning"],
        )
        self.monitor_interval_card.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        body = ctk.CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(1, weight=1)

        add_frame = ctk.CTkFrame(
            body,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        add_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        ctk.CTkLabel(
            add_frame,
            text="Channel intake",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=22, pady=(20, 4))
        self.monitor_summary_label = ctk.CTkLabel(
            add_frame,
            text="",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self.monitor_summary_label.pack(anchor="w", padx=22, pady=(0, 12))

        self.monitor_btn = ctk.CTkButton(
            add_frame,
            text="BAT DAU THEO DOI",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=16,
            fg_color=self.theme["success"],
            hover_color="#266657",
            command=self.toggle_monitoring
        )
        self.monitor_btn.pack(fill="x", padx=22, pady=(0, 16))

        platform_frame = ctk.CTkFrame(add_frame, fg_color=self.theme["panel_alt"], corner_radius=18)
        platform_frame.pack(fill="x", padx=22, pady=(0, 12))

        ctk.CTkLabel(
            platform_frame,
            text="Platform",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=14, pady=14)

        self.platform_var = ctk.StringVar(value="YouTube")
        self.platform_menu = ctk.CTkOptionMenu(
            platform_frame,
            values=list(SUPPORTED_PLATFORMS.keys()),
            variable=self.platform_var,
            command=self.update_platform_example,
            corner_radius=14,
            fg_color=self.theme["accent"],
            button_color=self.theme["accent"],
            button_hover_color=self.theme["accent_hover"],
        )
        self.platform_menu.pack(side="left", padx=6, pady=10)

        self.platform_example_label = ctk.CTkLabel(
            platform_frame,
            text="VD: https://www.youtube.com/@channelname",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=11)
        )
        self.platform_example_label.pack(side="left", padx=10)

        self.channel_url_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="Nhập URL kênh...",
            height=42,
            corner_radius=16,
            fg_color="#FFFFFF",
            border_color=self.theme["line"],
            text_color=self.theme["text"],
        )
        self.channel_url_entry.pack(fill="x", padx=22, pady=(0, 12))

        self.channel_logo_path = None
        self.channel_logo_position = ctk.StringVar(value="top-left")

        def choose_channel_logo_file():
            file_path = filedialog.askopenfilename(
                title="Chọn file logo cho kênh",
                filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
            )
            if file_path:
                self.channel_logo_path = file_path
                channel_logo_label.configure(text=f"Logo: {os.path.basename(file_path)}")
            else:
                self.channel_logo_path = None
                channel_logo_label.configure(text="Logo: khong chon")

        logo_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        logo_frame.pack(fill="x", padx=22, pady=(0, 14))
        channel_logo_btn = ctk.CTkButton(
            logo_frame,
            text="Chon logo kenh",
            command=choose_channel_logo_file,
            width=138,
            corner_radius=14,
            fg_color=self.theme["panel_alt"],
            hover_color=self.theme["accent_soft"],
            text_color=self.theme["text"],
        )
        channel_logo_btn.pack(side="left", padx=(0, 10))
        channel_logo_label = ctk.CTkLabel(
            logo_frame,
            text="Logo: khong chon",
            text_color=self.theme["muted"],
        )
        channel_logo_label.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            logo_frame,
            text="Vi tri",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(10, 4))
        channel_logo_pos_menu = ctk.CTkOptionMenu(
            logo_frame,
            values=["top-left", "top-right", "bottom-left", "bottom-right"],
            variable=self.channel_logo_position,
            corner_radius=14,
            fg_color=self.theme["accent"],
            button_color=self.theme["accent"],
            button_hover_color=self.theme["accent_hover"],
        )
        channel_logo_pos_menu.pack(side="left")

        add_channel_btn = ctk.CTkButton(
            add_frame,
            text="Them kenh vao radar",
            command=self.add_channel,
            height=42,
            corner_radius=16,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
        )
        add_channel_btn.pack(fill="x", padx=22, pady=(0, 20))

        monitor_feed = ctk.CTkFrame(
            body,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        monitor_feed.grid(row=0, column=1, sticky="nsew", pady=(0, 12))
        ctk.CTkLabel(
            monitor_feed,
            text="Radar notes",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=22, pady=(20, 6))
        ctk.CTkLabel(
            monitor_feed,
            text=(
                "UI đang ưu tiên rõ ràng cho sales demo: start monitor, cadence, "
                "tracked channels và trạng thái active phải nhìn ra ngay."
            ),
            text_color=self.theme["muted"],
            wraplength=300,
            justify="left",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=22)
        self.monitor_feed_label = ctk.CTkLabel(
            monitor_feed,
            text="Monitor chưa chạy.",
            text_color=self.theme["text"],
            fg_color=self.theme["panel_alt"],
            corner_radius=18,
            wraplength=290,
            justify="left",
            padx=16,
            pady=16,
            font=ctk.CTkFont(size=12),
        )
        self.monitor_feed_label.pack(fill="x", padx=22, pady=(18, 22))

        list_frame = ctk.CTkFrame(
            body,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")

        header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkLabel(
            header_frame,
            text="Tracked channel cards",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        refresh_btn = ctk.CTkButton(
            header_frame,
            text="Refresh",
            width=96,
            height=32,
            command=self.refresh_channel_list,
            corner_radius=12,
            fg_color=self.theme["panel_alt"],
            hover_color=self.theme["accent_soft"],
            text_color=self.theme["text"],
        )
        refresh_btn.pack(side="right", padx=5)

        self.channels_scrollframe = ctk.CTkScrollableFrame(
            list_frame,
            height=280,
            fg_color="transparent",
        )
        self.channels_scrollframe.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._bind_mousewheel_for_scrollable(self.channels_scrollframe)

        self.refresh_channel_list()
        self.update_shell_snapshot()

    def create_stats_tab(self):
        """Tạo tab thống kê"""
        stats_frame = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        stats_frame.pack(fill="both", expand=True, padx=4, pady=4)

        header = ctk.CTkFrame(
            stats_frame,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            header,
            text="Data Vault",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            header,
            text="Nhìn tải xuống, cấu trúc thư mục và tracked channels dưới góc nhìn sản phẩm.",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=22, pady=(0, 12))
        refresh_btn = ctk.CTkButton(
            header,
            text="Lam moi thong ke",
            command=self.update_stats,
            height=40,
            width=170,
            corner_radius=14,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
        )
        refresh_btn.pack(anchor="w", padx=22, pady=(0, 18))

        self.stats_container = ctk.CTkScrollableFrame(
            stats_frame,
            fg_color="transparent",
        )
        self.stats_container.pack(fill="both", expand=True)
        self._bind_mousewheel_for_scrollable(self.stats_container)
        self.update_stats()

    def update_stats(self):
        """Cập nhật thống kê"""
        # Xóa stats cũ
        for widget in self.stats_container.winfo_children():
            widget.destroy()

        stats = self.database.get_download_stats()
        channels = self.database.get_monitored_channels(only_active=False)
        active_channels = self.database.get_monitored_channels(only_active=True)

        summary_row = ctk.CTkFrame(self.stats_container, fg_color="transparent")
        summary_row.pack(fill="x", padx=2, pady=(4, 12))
        for column in range(3):
            summary_row.grid_columnconfigure(column, weight=1)

        self._create_metric_card(
            summary_row,
            "Total downloads",
            str(stats["total"]),
            "Tổng số bản ghi video đã đi qua hệ thống local/database.",
            accent=self.theme["accent"],
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._create_metric_card(
            summary_row,
            "Platform mix",
            str(len(stats["by_platform"])),
            "Số nền tảng hiện đang có dữ liệu tải xuống trong kho.",
            accent=self.theme["success"],
        ).grid(row=0, column=1, sticky="ew", padx=8)
        self._create_metric_card(
            summary_row,
            "Tracked channels",
            f"{len(active_channels)}/{len(channels)}",
            "Tỷ lệ kênh active trên tổng số kênh đã lưu để monitor.",
            accent=self.theme["warning"],
        ).grid(row=0, column=2, sticky="ew", padx=(8, 0))

        root_frame = ctk.CTkFrame(
            self.stats_container,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        root_frame.pack(fill="x", padx=2, pady=(0, 12))
        ctk.CTkLabel(
            root_frame,
            text="Storage root",
            text_color=self.theme["muted"],
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=22, pady=(18, 4))
        ctk.CTkLabel(
            root_frame,
            text=self.download_path,
            text_color=self.theme["text"],
            justify="left",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=22)
        ctk.CTkLabel(
            root_frame,
            text="Cấu trúc đích hiện tại là ROOT/Platform/Channel để việc mở folder và đối soát file rõ ràng hơn.",
            text_color=self.theme["muted"],
            wraplength=760,
            justify="left",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=22, pady=(6, 14))
        ctk.CTkButton(
            root_frame,
            text="Mo thu muc",
            width=120,
            height=36,
            corner_radius=14,
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
            command=self.open_download_folder,
        ).pack(anchor="w", padx=22, pady=(0, 18))

        platform_frame = ctk.CTkFrame(
            self.stats_container,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        platform_frame.pack(fill="both", expand=True, padx=2, pady=(0, 12))

        ctk.CTkLabel(
            platform_frame,
            text="Platform breakdown",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=22, pady=(18, 10))

        for platform, count in stats['by_platform'].items():
            pf_frame = ctk.CTkFrame(
                platform_frame,
                fg_color=self.theme["panel_alt"],
                corner_radius=18,
            )
            pf_frame.pack(fill="x", padx=18, pady=5)

            color = SUPPORTED_PLATFORMS.get(platform, {}).get('color', 'gray')

            ctk.CTkLabel(
                pf_frame,
                text=platform,
                width=100,
                fg_color=color,
                corner_radius=5
            ).pack(side="left", padx=12, pady=12)

            ctk.CTkLabel(
                pf_frame,
                text=f"{count} video",
                text_color=self.theme["text"],
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(side="left", padx=10)
        if not stats["by_platform"]:
            ctk.CTkLabel(
                platform_frame,
                text="Chưa có dữ liệu tải xuống để hiển thị.",
                text_color=self.theme["muted"],
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=22, pady=(4, 18))

        channel_info_frame = ctk.CTkFrame(
            self.stats_container,
            fg_color=self.theme["panel"],
            corner_radius=28,
            border_width=1,
            border_color=self.theme["line"],
        )
        channel_info_frame.pack(fill="x", padx=2, pady=(0, 12))

        ctk.CTkLabel(
            channel_info_frame,
            text=f"Folder navigator ({len(channels)} channels)",
            text_color=self.theme["text"],
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=22, pady=(18, 8))

        if channels:
            folders_frame = ctk.CTkScrollableFrame(
                channel_info_frame,
                height=300,
                fg_color="transparent",
            )
            folders_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            self._bind_mousewheel_for_scrollable(folders_frame)

            ctk.CTkLabel(
                folders_frame,
                text="Mở nhanh thư mục theo dõi theo từng nền tảng và tài khoản:",
                text_color=self.theme["muted"],
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(anchor="w", padx=12, pady=(12, 10))

            by_platform = {}
            for channel_url, platform, *_ in channels:
                by_platform.setdefault(platform, []).append(channel_url)

            for pf, urls in by_platform.items():
                section = ctk.CTkFrame(folders_frame, fg_color=self.theme["panel_alt"], corner_radius=20)
                section.pack(fill="x", padx=10, pady=6)

                is_open = {"v": False}
                inner_ref = {"frame": None}

                def toggle(pf_name=pf, url_list=urls, container=section):
                    is_open["v"] = not is_open["v"]
                    if is_open["v"]:
                        btn.configure(text="▼")
                        inner = ctk.CTkFrame(container, fg_color=self.theme["panel"])
                        inner.pack(fill="x", padx=10, pady=(0, 10))
                        inner_ref["frame"] = inner

                        for u in url_list:
                            row = ctk.CTkFrame(inner, fg_color="#FFFDFC", corner_radius=16)
                            row.pack(fill="x", padx=5, pady=2)

                            ch_name = self.downloader.extract_channel_name(u, pf_name)
                            ctk.CTkLabel(
                                row,
                                text=f"{ch_name}"[:24],
                                width=160,
                                anchor="w",
                                text_color=self.theme["text"],
                                font=ctk.CTkFont(size=12, weight="bold"),
                            ).pack(side="left", padx=10, pady=10)
                            ctk.CTkLabel(
                                row,
                                text=u[:95] + ("..." if len(u) > 95 else ""),
                                text_color=self.theme["muted"],
                                anchor="w"
                            ).pack(side="left", fill="x", expand=True, padx=10)

                            open_btn = ctk.CTkButton(
                                row,
                                text="Mo folder",
                                width=40,
                                command=lambda cu=u, cp=pf_name: self.open_channel_folder(cu, cp),
                                corner_radius=12,
                                fg_color=self.theme["accent"],
                                hover_color=self.theme["accent_hover"],
                            )
                            open_btn.pack(side="right", padx=10, pady=8)
                    else:
                        btn.configure(text="▶")
                        if inner_ref["frame"]:
                            inner_ref["frame"].destroy()
                            inner_ref["frame"] = None

                header = ctk.CTkFrame(section, fg_color="transparent")
                header.pack(fill="x", padx=10, pady=10)

                btn = ctk.CTkButton(
                    header,
                    text="▶",
                    width=30,
                    fg_color="transparent",
                    hover_color=self.theme["accent_soft"],
                    text_color=self.theme["text"],
                    command=toggle,
                )
                btn.pack(side="left", padx=5)

                ctk.CTkLabel(
                    header,
                    text=f"{pf}",
                    text_color=self.theme["text"],
                    font=ctk.CTkFont(size=13, weight="bold")
                ).pack(side="left", padx=5)
                ctk.CTkLabel(
                    header,
                    text=f"({len(urls)} kênh)",
                    text_color=self.theme["muted"]
                ).pack(side="left", padx=5)

        else:
            ctk.CTkLabel(
                channel_info_frame,
                text="Chưa có kênh theo dõi để hiển thị navigator.",
                text_color=self.theme["muted"]
            ).pack(anchor="w", padx=22, pady=(0, 20))
        self.update_shell_snapshot()

    # =========================================================
    # Theo dõi kênh + thao tác file/video
    # (Các hàm này cần cho callback của UI; trước đó bị thiếu nên gây AttributeError)
    # =========================================================

    def add_channel(self):
        """Thêm kênh vào danh sách theo dõi."""
        channel_url = self.channel_url_entry.get().strip() if hasattr(self, "channel_url_entry") else ""
        platform = self.platform_var.get() if hasattr(self, "platform_var") else ""

        if not channel_url:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập URL kênh!")
            return

        # Kiểm tra giới hạn số kênh
        try:
            current_channels = self.database.get_monitored_channels(platform)
            if len(current_channels) >= MAX_CHANNELS_PER_PLATFORM:
                messagebox.showwarning(
                    "Giới hạn",
                    f"Đã đạt giới hạn {MAX_CHANNELS_PER_PLATFORM} kênh cho {platform}!"
                )
                return
        except Exception:
            # Nếu DB chưa sẵn sàng, vẫn thử add và để DB throw nếu có
            pass

        success = self.database.add_monitored_channel(
            channel_url,
            platform,
            self.channel_logo_path,
            self.channel_logo_position.get() if hasattr(self, "channel_logo_position") else None,
        )
        if success:
            self.log_message(f"✅ Đã thêm kênh: {channel_url} ({platform})")
            try:
                self.channel_url_entry.delete(0, "end")
            except Exception:
                pass
            self.channel_logo_path = None
            self.refresh_channel_list()
            messagebox.showinfo("Thành công", "Đã thêm kênh vào danh sách theo dõi!")
        else:
            messagebox.showinfo("Thông báo", "Kênh này đã có trong danh sách!")

    def remove_channel(self, channel_url: str, platform: str):
        """Xóa kênh khỏi danh sách theo dõi."""
        self.database.remove_monitored_channel(channel_url, platform)
        self.log_message(f"🗑️ Đã xóa kênh: {channel_url}")
        self.refresh_channel_list()

    def refresh_channel_list(self):
        """Làm mới danh sách kênh đang theo dõi."""
        if not hasattr(self, "channels_scrollframe"):
            return

        for widget in self.channels_scrollframe.winfo_children():
            widget.destroy()

        channels = self.database.get_monitored_channels(only_active=False)
        if not channels:
            ctk.CTkLabel(
                self.channels_scrollframe,
                text="Chưa có kênh nào được theo dõi",
                text_color=self.theme["muted"]
            ).pack(pady=20)
            if hasattr(self, "monitor_channels_card"):
                self.monitor_channels_card.value_label.configure(text="0")
            if hasattr(self, "monitor_active_card"):
                self.monitor_active_card.value_label.configure(text="0 active")
            self.update_shell_snapshot()
            return

        for channel_url, platform, is_active, logo_path, logo_position in channels:
            self._create_channel_item(channel_url, platform, bool(int(is_active)), logo_path, logo_position)
        active_channels = self.database.get_monitored_channels(only_active=True)
        if hasattr(self, "monitor_channels_card"):
            self.monitor_channels_card.value_label.configure(text=str(len(channels)))
        if hasattr(self, "monitor_active_card"):
            self.monitor_active_card.value_label.configure(text=f"{len(active_channels)} active")
        if hasattr(self, "monitor_interval_card"):
            self.monitor_interval_card.value_label.configure(text=f"{CHECK_INTERVAL // 60} min")
        self.update_shell_snapshot()

    def _create_channel_item(self, channel_url: str, platform: str, is_active: bool = True, logo_path=None, logo_position=None):
        """Tạo item kênh (expand/collapse + active/inactive + mở folder + xóa)."""
        channel_container = ctk.CTkFrame(
            self.channels_scrollframe,
            fg_color=self.theme["panel_alt"],
            corner_radius=22,
            border_width=1,
            border_color=self.theme["line"],
        )
        channel_container.pack(fill="x", padx=5, pady=5)

        header_frame = ctk.CTkFrame(channel_container, fg_color="transparent")
        header_frame.pack(fill="x", padx=0, pady=0)

        is_expanded = {"value": False}
        videos_frame_ref = {"frame": None}

        def toggle_expand():
            is_expanded["value"] = not is_expanded["value"]
            if is_expanded["value"]:
                expand_btn.configure(text="▼")
                videos_frame_ref["frame"] = self.show_channel_videos(channel_container, channel_url, platform)
            else:
                expand_btn.configure(text="▶")
                if videos_frame_ref["frame"]:
                    videos_frame_ref["frame"].destroy()
                    videos_frame_ref["frame"] = None

        def on_toggle_active():
            new_state = self.database.toggle_channel_active(channel_url, platform)
            active_var.set(1 if new_state else 0)
            url_label.configure(text_color=(self.theme["text"] if new_state else self.theme["muted"]))
            active_badge.configure(
                text=("ACTIVE" if new_state else "OFF"),
                text_color=(self.theme["success"] if new_state else self.theme["muted"]),
            )
            self.refresh_channel_list()

        expand_btn = ctk.CTkButton(
            header_frame,
            text="▶",
            width=30,
            command=toggle_expand,
            fg_color="transparent",
            hover_color=self.theme["accent_soft"],
            text_color=self.theme["text"],
        )
        expand_btn.pack(side="left", padx=5, pady=5)

        active_var = ctk.IntVar(value=1 if is_active else 0)
        active_cb = ctk.CTkCheckBox(header_frame, text="", width=20, variable=active_var, command=on_toggle_active)
        active_cb.pack(side="left", padx=(2, 6), pady=5)

        active_badge = ctk.CTkLabel(
            header_frame,
            text=("ACTIVE" if is_active else "OFF"),
            width=55,
            text_color=(self.theme["success"] if is_active else self.theme["muted"]),
            anchor="w",
        )
        active_badge.pack(side="left", padx=(0, 6))

        badge_color = SUPPORTED_PLATFORMS.get(platform, {}).get("color", "gray")
        ctk.CTkLabel(header_frame, text=platform, width=80, fg_color=badge_color, corner_radius=5).pack(
            side="left", padx=5, pady=5
        )

        url_label = ctk.CTkLabel(
            header_frame,
            text=channel_url[:50] + ("..." if len(channel_url) > 50 else ""),
            anchor="w",
            text_color=(self.theme["text"] if is_active else self.theme["muted"]),
        )
        url_label.pack(side="left", fill="x", expand=True, padx=5)

        videos = self.database.get_videos_by_channel(channel_url, platform)
        ctk.CTkLabel(header_frame, text=f"📹 {len(videos)}", width=60, text_color="gray").pack(side="left", padx=5)

        ctk.CTkButton(
            header_frame,
            text="📂",
            width=40,
            command=lambda url=channel_url, p=platform: self.open_channel_folder(url, p),
            fg_color=self.theme["accent"],
            hover_color=self.theme["accent_hover"],
        ).pack(side="left", padx=2, pady=5)

        ctk.CTkButton(
            header_frame,
            text="🗑️",
            width=40,
            command=lambda url=channel_url, p=platform: self.remove_channel(url, p),
            fg_color="red",
            hover_color="darkred",
        ).pack(side="left", padx=2, pady=5)

    def show_channel_videos(self, parent, channel_url: str, platform: str):
        """Hiển thị danh sách video của kênh (từ DB)."""
        videos_frame = ctk.CTkFrame(parent, fg_color=self.theme["panel"])
        videos_frame.pack(fill="x", padx=10, pady=(0, 5))

        videos = self.database.get_videos_by_channel(channel_url, platform)
        if not videos:
            ctk.CTkLabel(
                videos_frame,
                text="Chưa có video nào được tải",
                text_color=self.theme["muted"],
            ).pack(pady=10)
            return videos_frame

        for video_id, title, file_path, downloaded_at in videos:
            video_frame = ctk.CTkFrame(videos_frame, fg_color="#FFFDFC", corner_radius=16)
            video_frame.pack(fill="x", padx=5, pady=2)

            ctk.CTkLabel(video_frame, text="🎬", width=30).pack(side="left", padx=5)

            ctk.CTkButton(
                video_frame,
                text=title[:60] + ("..." if len(title) > 60 else ""),
                anchor="w",
                fg_color="transparent",
                hover_color=self.theme["accent_soft"],
                text_color=self.theme["text"],
                command=lambda fp=file_path: self.open_video(fp),
            ).pack(side="left", fill="x", expand=True, padx=5)

            ctk.CTkLabel(
                video_frame,
                text=(downloaded_at[:16] if downloaded_at else ""),
                text_color=self.theme["muted"],
                width=120,
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                video_frame,
                text="🗑️",
                width=35,
                fg_color="red",
                hover_color="darkred",
                command=lambda vid=video_id, t=title, p=platform, ch_url=channel_url: self.delete_video_item(vid, t, p, ch_url),
            ).pack(side="left", padx=2)

        return videos_frame

    def open_video(self, file_path: str):
        """Mở video bằng ứng dụng mặc định."""
        import platform
        import subprocess

        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Lỗi", f"Không tìm thấy file:\n{file_path}")
            return

        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.run(["open", file_path])
            elif system == "Windows":
                os.startfile(file_path)
            else:
                subprocess.run(["xdg-open", file_path])
            self.log_message(f"✓ Đã mở video: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở video:\n{str(e)}")

    def open_download_folder(self):
        """Mở thư mục downloads (root)."""
        import platform
        import subprocess

        if not os.path.exists(self.download_path):
            messagebox.showerror("Lỗi", "Thư mục downloads không tồn tại")
            return

        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.run(["open", self.download_path])
            elif system == "Windows":
                os.startfile(self.download_path)
            else:
                subprocess.run(["xdg-open", self.download_path])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục:\n{str(e)}")

    def open_channel_folder(self, channel_url: str, platform: str):
        """Mở thư mục kênh: ROOT/Platform/ChannelName."""
        import platform as _platform
        import subprocess

        channel_name = self.downloader.extract_channel_name(channel_url, platform)
        folder_path = os.path.join(self.download_path, platform, channel_name)

        if not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
            except Exception:
                folder_path = os.path.join(self.download_path, platform)

        try:
            system = _platform.system()
            if system == "Darwin":
                subprocess.run(["open", folder_path])
            elif system == "Windows":
                os.startfile(folder_path)
            else:
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở thư mục kênh:\n{str(e)}")

    def delete_video_item(self, video_id: str, title: str, platform: str, channel_url: str):
        """Xóa video khỏi database và disk (nếu hỗ trợ trong database.py)."""
        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa video này?\n\n📹 {title}\n\nHành động này không thể hoàn tác!",
        )
        if not confirm:
            return

        # Thử dùng API mới (nếu có) để xóa cả file. Nếu không có, fallback sang delete DB.
        try:
            result = self.database.delete_video(video_id, platform, delete_file=True, base_dir=self.download_path)
        except TypeError:
            # Signature cũ
            result = self.database.delete_video(video_id, platform)

        if isinstance(result, dict) and not result.get("success", True):
            messagebox.showerror("Lỗi", result.get("message", "Không thể xóa"))
            return

        self.log_message("🗑️ Đã xóa video")
        self.update_channel_video_count(channel_url, platform)
    def update_channel_video_count(self, channel_url: str, platform: str):
        """Refresh lại list để cập nhật count một cách đơn giản."""
        try:
            self.refresh_channel_list()
        except Exception:
            pass

    def on_closing(self):
        """Xử lý khi đóng ứng dụng"""
        if self.is_monitoring:
            self.channel_monitor.stop_monitoring()

        self.database.close()
        self.destroy()

    def _collect_split_parts(self, any_part_path: str) -> list[str]:
        """Collect all split part files for a split output.

        - Input is usually the first part returned by _maybe_split_long_video().
        - Returns absolute file paths sorted by filename.
        """
        try:
            if not any_part_path:
                return []
            ap = os.path.abspath(any_part_path)
            if not os.path.exists(ap):
                return []

            # Heuristic: parts are in same folder and share the same stem prefix.
            # Example: video_edited_part001.mp4 / video_edited_part002.mp4 ...
            folder = os.path.dirname(ap)
            fname = os.path.basename(ap)

            # Common patterns: "part" within filename.
            # Use prefix up to "part" (inclusive) as grouping key.
            lower = fname.lower()
            idx = lower.rfind("part")
            if idx <= 0:
                return []

            prefix = fname[: idx + 4]  # include "part"
            matches = []
            for f in os.listdir(folder):
                if f.startswith(prefix):
                    full = os.path.join(folder, f)
                    if os.path.isfile(full):
                        matches.append(full)

            matches.sort()
            return matches
        except Exception:
            return []

    def _extract_upload_and_cleanup_assets(self, video_path: str, *, platform: str | None, channel_url: str | None) -> None:
        """Extract (muted mp4 + mp3) for a video, upload them to Drive, then delete local assets.

        Local disk policy (per request): keep only original/part videos locally; do not keep extracted assets.
        """
        # Only meaningful when Drive upload is enabled (assets are short-lived).
        if not self.upload_to_drive:
            return
        # Assets are only requested in the "split" flow.
        if not self.split_after_download:
            return

        try:
            if not video_path or not os.path.exists(video_path):
                return

            out_dir = os.path.dirname(os.path.abspath(video_path))
            muted_path = None
            audio_path = None

            try:
                muted_p, audio_p = self.video_processor.extract_assets(video_path, out_dir)
                muted_path = str(muted_p)
                audio_path = str(audio_p)
            except Exception as e:
                self.log_message(f"⚠️ Tách audio/muted thất bại (bỏ qua): {e}")
                return

            # Upload both assets
            if muted_path and os.path.exists(muted_path):
                self._upload_to_google_drive(muted_path, platform=platform, channel_url=channel_url, category="Assets")
            if audio_path and os.path.exists(audio_path):
                self._upload_to_google_drive(audio_path, platform=platform, channel_url=channel_url, category="Assets")

        finally:
            # Always cleanup local assets
            for p in (muted_path, audio_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    def _maybe_split_long_video(self, file_path: str) -> str:
        """Split the video into parts if the user enabled splitting and the video is longer than the configured threshold.

        Returns:
            - If split is disabled or not needed: the original file_path
            - If split happens: the first part path (DB compatibility)

        Note: all parts are still created on disk by the splitter.
        """
        try:
            if not getattr(self, "split_after_download", False):
                return file_path
            if not file_path:
                return file_path

            threshold = int(SPLIT_IF_LONGER_THAN_SECONDS)
            segment = int(SPLIT_SEGMENT_SECONDS)
            if threshold <= 0 or segment <= 0:
                return file_path

            parts = split_if_longer_than(
                file_path,
                threshold_seconds=threshold,
                segment_seconds=segment,
            )
            if len(parts) <= 1:
                return file_path

            self.log_message(f"✂️ Video dài hơn {threshold}s → đã cắt thành {len(parts)} part (mỗi ~{segment}s)")
            for p in parts[:6]:
                self.log_message(f"   • {os.path.basename(p)}")
            if len(parts) > 6:
                self.log_message(f"   … và {len(parts) - 6} part khác")

            return parts[0]
        except Exception as e:
            self.log_message(f"⚠️ Cắt video thất bại (bỏ qua): {e}")
            return file_path


# def main():
#     """Hàm chính khởi chạy ứng dụng"""
#     app = VideoDownloaderApp()
#     app.protocol("WM_DELETE_WINDOW", app.on_closing)
#     app.mainloop()
#
#
# if __name__ == "__main__":
#     main()

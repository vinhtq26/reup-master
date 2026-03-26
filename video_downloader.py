"""
Ứng dụng tải video đa nền tảng với giao diện GUI
Hỗ trợ: YouTube, TikTok, Douyin, Facebook
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import time

from database import DownloadHistory
from downloader_core import VideoDownloader, ChannelMonitor
from config import (
    SUPPORTED_PLATFORMS,
    MAX_CHANNELS_PER_PLATFORM,
    CHECK_INTERVAL
)
# Cấu hình split video
from config import SPLIT_IF_LONGER_THAN_SECONDS, SPLIT_SEGMENT_SECONDS

from user_settings import load_settings, save_settings, UserSettings

# Thêm module xử lý video (FFmpeg)
from video_processing import VideoProcessor, VideoTransformSettings
from video_splitter import split_if_longer_than
from drive_uploader import upload_file_to_drive


class VideoDownloaderApp(ctk.CTk):
    """Ứng dụng chính với giao diện GUI"""

    def __init__(self):
        super().__init__()

        # Cấu hình cửa sổ chính
        self.title("Video Downloader - Tải Video Đa Nền Tảng")
        self.geometry("1000x700")

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

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

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

    def create_widgets(self):
        """Tạo các widget cho giao diện"""

        # ========== HEADER ==========
        header_frame = ctk.CTkFrame(self, corner_radius=0)
        header_frame.pack(fill="x", padx=0, pady=0)

        title_label = ctk.CTkLabel(
            header_frame,
            text="🎬 VIDEO DOWNLOADER",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=15)

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Hỗ trợ: YouTube | TikTok | Douyin | Facebook",
            font=ctk.CTkFont(size=12)
        )
        subtitle_label.pack(pady=(0, 10))

        # ========== SETTINGS FRAME ==========
        settings_frame = ctk.CTkFrame(self)
        settings_frame.pack(fill="x", padx=20, pady=10)

        # Chọn thư mục lưu
        path_label = ctk.CTkLabel(settings_frame, text="📁 Thư mục lưu:")
        path_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.path_entry = ctk.CTkEntry(settings_frame, width=400)
        self.path_entry.insert(0, self.download_path)
        self.path_entry.grid(row=0, column=1, padx=10, pady=10)

        browse_btn = ctk.CTkButton(
            settings_frame,
            text="Chọn thư mục",
            width=120,
            command=self.browse_folder
        )
        browse_btn.grid(row=0, column=2, padx=10, pady=10)

        # Checkbox: edit video sau khi tải
        self.edit_var = ctk.BooleanVar(value=self.edit_after_download)
        edit_cb = ctk.CTkCheckBox(
            settings_frame,
            text="✂️ Edit video sau khi tải (mirror + 1.07x + color grade + xoá metadata)",
            variable=self.edit_var,
            command=self.on_toggle_edit_after_download,
        )
        edit_cb.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="w")

        # Checkbox: upload Google Drive sau khi tải
        self.upload_drive_var = ctk.BooleanVar(value=self.upload_to_drive)
        upload_drive_cb = ctk.CTkCheckBox(
            settings_frame,
            text="☁️ Tự động upload lên Google Drive sau khi tải xong",
            variable=self.upload_drive_var,
            command=self.on_toggle_upload_drive,
        )
        upload_drive_cb.grid(row=2, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="w")

        # NEW: Checkbox: tách video nếu dài (chỉ chạy khi user bật)
        self.split_var = ctk.BooleanVar(value=self.split_after_download)
        split_cb = ctk.CTkCheckBox(
            settings_frame,
            text=f"✂️ Tách video nếu dài hơn {int(SPLIT_IF_LONGER_THAN_SECONDS)}s (mỗi part ~{int(SPLIT_SEGMENT_SECONDS)}s)",
            variable=self.split_var,
            command=self.on_toggle_split_after_download,
        )
        split_cb.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="w")

        # ========== TAB VIEW ==========
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        # Tạo các tab
        self.tab_download = self.tabview.add("📥 Tải theo Link")
        self.tab_monitor = self.tabview.add("👁️ Theo dõi Kênh")
        self.tab_stats = self.tabview.add("📊 Thống kê")

        # Tạo nội dung cho từng tab
        self.create_download_tab()
        self.create_monitor_tab()
        self.create_stats_tab()

        # ========== STATUS BAR ==========
        self.status_frame = ctk.CTkFrame(self, corner_radius=0)
        self.status_frame.pack(fill="x", side="bottom", padx=0, pady=0)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="✓ Sẵn sàng",
            font=ctk.CTkFont(size=11)
        )
        self.status_label.pack(pady=8, padx=10, side="left")

        self.monitoring_indicator = ctk.CTkLabel(
            self.status_frame,
            text="●",
            text_color="gray",
            font=ctk.CTkFont(size=20)
        )
        self.monitoring_indicator.pack(pady=5, padx=10, side="right")

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
                quality="best",
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
                text="⏸️ DỪNG THEO DÕI",
                fg_color="red",
                hover_color="darkred"
            )
            self.monitoring_indicator.configure(text_color="green")
            self.log_message("▶️ Đã bắt đầu theo dõi kênh tự động")
            self.update_status("🔴 Đang theo dõi kênh...")
        else:
            # Dừng monitoring
            self.is_monitoring = False
            self.channel_monitor.stop_monitoring()

            self.monitor_btn.configure(
                text="▶️ BẮT ĐẦU THEO DÕI",
                fg_color="green",
                hover_color="darkgreen"
            )
            self.monitoring_indicator.configure(text_color="gray")
            self.log_message("⏸️ Đã dừng theo dõi kênh")
            self.update_status("✓ Đã dừng theo dõi")

    def monitoring_callback(self, message: str):
        """Callback từ channel monitor"""
        self.log_message(message)

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

            self.log_message(f"✓ Đã chọn thư mục gốc: {folder}")

    def log_message(self, message: str):
        """Thêm message vào log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")

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

        # Frame nhập URL
        url_frame = ctk.CTkFrame(self.tab_download)
        url_frame.pack(fill="x", padx=20, pady=20)

        url_label = ctk.CTkLabel(
            url_frame,
            text="🔗 Nhập link video:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        url_label.pack(anchor="w", padx=10, pady=(10, 5))

        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="Dán link video từ YouTube, TikTok, Douyin hoặc Facebook...",
            height=40
        )
        self.url_entry.pack(fill="x", padx=10, pady=(0, 10))

        # Nút tải
        self.download_btn = ctk.CTkButton(
            url_frame,
            text="⬇️ Tải Video",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.download_single_video
        )
        self.download_btn.pack(fill="x", padx=10, pady=(0, 10))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(url_frame)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.progress_bar.set(0)

        # Log frame
        log_frame = ctk.CTkFrame(self.tab_download)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        log_label = ctk.CTkLabel(
            log_frame,
            text="📝 Nhật ký tải xuống:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_label.pack(anchor="w", padx=10, pady=(10, 5), side="left")

        clear_log_btn = ctk.CTkButton(
            log_frame,
            text="🧹 Clear log",
            width=110,
            height=28,
            command=self.clear_log,
            fg_color="gray25",
            hover_color="gray35",
        )
        clear_log_btn.pack(anchor="e", padx=10, pady=(10, 5), side="right")

        self.log_textbox = ctk.CTkTextbox(log_frame, height=200)
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def create_monitor_tab(self):
        """Tạo tab theo dõi kênh"""

        # Control frame
        control_frame = ctk.CTkFrame(self.tab_monitor)
        control_frame.pack(fill="x", padx=20, pady=20)

        title_label = ctk.CTkLabel(
            control_frame,
            text="👁️ Tự động theo dõi và tải video mới từ kênh",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(pady=(10, 5))

        info_label = ctk.CTkLabel(
            control_frame,
            text=f"Giới hạn: {MAX_CHANNELS_PER_PLATFORM} kênh/nền tảng | Kiểm tra mỗi {CHECK_INTERVAL//60} phút",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        info_label.pack(pady=(0, 10))

        # Nút Start/Stop
        self.monitor_btn = ctk.CTkButton(
            control_frame,
            text="▶️ BẮT ĐẦU THEO DÕI",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="green",
            hover_color="darkgreen",
            command=self.toggle_monitoring
        )
        self.monitor_btn.pack(fill="x", padx=10, pady=(0, 10))

        # Add channel frame
        add_frame = ctk.CTkFrame(self.tab_monitor)
        add_frame.pack(fill="x", padx=20, pady=(0, 10))

        add_label = ctk.CTkLabel(
            add_frame,
            text="➕ Thêm kênh mới:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        add_label.pack(anchor="w", padx=10, pady=(10, 5))

        # Chọn platform
        platform_frame = ctk.CTkFrame(add_frame)
        platform_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(platform_frame, text="Nền tảng:").pack(side="left", padx=5)

        self.platform_var = ctk.StringVar(value="YouTube")
        self.platform_menu = ctk.CTkOptionMenu(
            platform_frame,
            values=list(SUPPORTED_PLATFORMS.keys()),
            variable=self.platform_var,
            command=self.update_platform_example
        )
        self.platform_menu.pack(side="left", padx=5)

        self.platform_example_label = ctk.CTkLabel(
            platform_frame,
            text="VD: https://www.youtube.com/@channelname",
            text_color="gray",
            font=ctk.CTkFont(size=10)
        )
        self.platform_example_label.pack(side="left", padx=10)

        # Nhập URL kênh
        self.channel_url_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="Nhập URL kênh...",
            height=35
        )
        self.channel_url_entry.pack(fill="x", padx=10, pady=5)

        add_channel_btn = ctk.CTkButton(
            add_frame,
            text="Thêm kênh",
            command=self.add_channel,
            height=35
        )
        add_channel_btn.pack(fill="x", padx=10, pady=(5, 10))

        # Danh sách kênh đang theo dõi
        list_frame = ctk.CTkFrame(self.tab_monitor)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Header với nút refresh
        header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))

        list_label = ctk.CTkLabel(
            header_frame,
            text="📋 Danh sách kênh đang theo dõi:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        list_label.pack(side="left", anchor="w")

        refresh_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Refresh",
            width=100,
            height=28,
            command=self.refresh_channel_list,
            fg_color="green",
            hover_color="darkgreen"
        )
        refresh_btn.pack(side="right", padx=5)

        # ScrollableFrame cho danh sách kênh
        self.channels_scrollframe = ctk.CTkScrollableFrame(list_frame, height=200)
        self.channels_scrollframe.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Cập nhật danh sách kênh
        self.refresh_channel_list()

    def create_stats_tab(self):
        """Tạo tab thống kê"""

        stats_frame = ctk.CTkFrame(self.tab_stats)
        # Giảm padding 2 bên để tab Thống kê rộng hơn, đặc biệt là danh sách kênh theo dõi
        stats_frame.pack(fill="both", expand=True, padx=10, pady=20)

        title_label = ctk.CTkLabel(
            stats_frame,
            text="📊 Thống kê tải xuống",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=(10, 10))

        # Nút refresh
        refresh_btn = ctk.CTkButton(
            stats_frame,
            text="🔄 Làm mới thống kê",
            command=self.update_stats,
            height=35
        )
        refresh_btn.pack(pady=(0, 10))

        # Stats container (scrollable): bọc toàn bộ nội dung để có thể scroll xuống dưới
        # NOTE: đặt height để scrollbar hoạt động ổn định trên macOS.
        self.stats_container = ctk.CTkScrollableFrame(stats_frame)
        # Giảm padding để nội dung (đặc biệt scroll list) ăn gần hết chiều ngang
        self.stats_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Bắt scroll wheel/trackpad mượt cho tab Thống kê
        self._bind_mousewheel_for_scrollable(self.stats_container)

        # Load stats ban đầu
        self.update_stats()

    def update_stats(self):
        """Cập nhật thống kê"""
        # Xóa stats cũ
        for widget in self.stats_container.winfo_children():
            widget.destroy()

        # ========== ROOT FOLDER INFO ==========
        root_frame = ctk.CTkFrame(self.stats_container)
        root_frame.pack(fill="x", padx=20, pady=(10, 5))

        ctk.CTkLabel(
            root_frame,
            text="📁 Thư mục lưu hiện tại:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=15, pady=15)

        root_path_label = ctk.CTkLabel(
            root_frame,
            text=self.download_path,
            text_color="gray",
            anchor="w"
        )
        root_path_label.pack(side="left", fill="x", expand=True, padx=10)

        open_root_btn = ctk.CTkButton(
            root_frame,
            text="📂 Mở",
            width=80,
            command=self.open_download_folder
        )
        open_root_btn.pack(side="right", padx=15, pady=10)

        # ========== STATS ==========
        stats = self.database.get_download_stats()

        # Tổng số video
        total_frame = ctk.CTkFrame(self.stats_container)
        total_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            total_frame,
            text="📹 Tổng số video đã tải:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=20, pady=20)

        ctk.CTkLabel(
            total_frame,
            text=str(stats['total']),
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="green"
        ).pack(side="right", padx=20, pady=20)

        # Theo từng nền tảng
        platform_frame = ctk.CTkFrame(self.stats_container)
        platform_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            platform_frame,
            text="📊 Phân chia theo nền tảng:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))

        for platform, count in stats['by_platform'].items():
            pf_frame = ctk.CTkFrame(platform_frame)
            pf_frame.pack(fill="x", padx=20, pady=5)

            color = SUPPORTED_PLATFORMS.get(platform, {}).get('color', 'gray')

            ctk.CTkLabel(
                pf_frame,
                text=platform,
                width=100,
                fg_color=color,
                corner_radius=5
            ).pack(side="left", padx=10, pady=10)

            ctk.CTkLabel(
                pf_frame,
                text=f"{count} video",
                font=ctk.CTkFont(size=14)
            ).pack(side="left", padx=10)

        # ========== EXPAND FOLDER BY PLATFORM/CHANNEL ==========
        # dùng ALL channels (cả active + inactive) để thống kê đúng
        channels = self.database.get_monitored_channels(only_active=False)

        channel_info_frame = ctk.CTkFrame(self.stats_container)
        channel_info_frame.pack(fill="x", padx=20, pady=(10, 5))

        ctk.CTkLabel(
            channel_info_frame,
            text=f"👁️ Số kênh đang theo dõi: {len(channels)}",
            font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=20, pady=15)

        if channels:
            # NOTE: danh sách kênh có thể rất dài, dùng scrollable frame để tránh tràn UI
            # Giảm padding 2 bên để danh sách rộng hơn, tránh bị các phần phía trên "ép" gây khó nhìn.
            folders_frame = ctk.CTkScrollableFrame(
                self.stats_container,
                height=300
            )
            folders_frame.pack(fill="both", expand=True, padx=8, pady=(5, 15))

            # Scroll lồng nhau: bind wheel/trackpad để hover vùng danh sách kênh sẽ cuộn vùng đó
            self._bind_mousewheel_for_scrollable(folders_frame)

            ctk.CTkLabel(
                folders_frame,
                text="📂 Mở nhanh thư mục theo dõi (Platform/Account):",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=12, pady=(15, 10))

            # Render expandable list by platform
            by_platform = {}
            for channel_url, platform, _ in channels:
                by_platform.setdefault(platform, []).append(channel_url)

            for pf, urls in by_platform.items():
                section = ctk.CTkFrame(folders_frame)
                section.pack(fill="x", padx=10, pady=6)

                is_open = {"v": False}
                inner_ref = {"frame": None}

                def toggle(pf_name=pf, url_list=urls, container=section):
                    is_open["v"] = not is_open["v"]
                    if is_open["v"]:
                        btn.configure(text="▼")
                        inner = ctk.CTkFrame(container, fg_color="gray15")
                        inner.pack(fill="x", padx=10, pady=(0, 10))
                        inner_ref["frame"] = inner

                        for u in url_list:
                            row = ctk.CTkFrame(inner, fg_color="gray20")
                            row.pack(fill="x", padx=5, pady=2)

                            ch_name = self.downloader.extract_channel_name(u, pf_name)
                            # Giới hạn độ rộng label để phần URL + nút mở thư mục luôn có chỗ.
                            ctk.CTkLabel(row, text=f"{ch_name}"[:24], width=160, anchor="w").pack(side="left", padx=10, pady=8)
                            ctk.CTkLabel(
                                row,
                                text=u[:95] + ("..." if len(u) > 95 else ""),
                                text_color="gray",
                                anchor="w"
                            ).pack(side="left", fill="x", expand=True, padx=10)

                            open_btn = ctk.CTkButton(
                                row,
                                text="📂",
                                width=40,
                                command=lambda cu=u, cp=pf_name: self.open_channel_folder(cu, cp)
                            )
                            open_btn.pack(side="right", padx=10, pady=6)
                    else:
                        btn.configure(text="▶")
                        if inner_ref["frame"]:
                            inner_ref["frame"].destroy()
                            inner_ref["frame"] = None

                header = ctk.CTkFrame(section)
                header.pack(fill="x", padx=10, pady=10)

                btn = ctk.CTkButton(header, text="▶", width=30, fg_color="transparent", hover_color="gray20", command=toggle)
                btn.pack(side="left", padx=5)

                ctk.CTkLabel(header, text=f"{pf}", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=5)
                ctk.CTkLabel(header, text=f"({len(urls)} kênh)", text_color="gray").pack(side="left", padx=5)

        else:
            # Không có kênh theo dõi
            no_folder_frame = ctk.CTkFrame(self.stats_container)
            no_folder_frame.pack(fill="x", padx=20, pady=(5, 15))
            ctk.CTkLabel(no_folder_frame, text="ℹ️ Chưa có kênh theo dõi để hiển thị thư mục.", text_color="gray").pack(padx=20, pady=15)

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

        success = self.database.add_monitored_channel(channel_url, platform)
        if success:
            self.log_message(f"✅ Đã thêm kênh: {channel_url} ({platform})")
            try:
                self.channel_url_entry.delete(0, "end")
            except Exception:
                pass
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
                text_color="gray"
            ).pack(pady=20)
            return

        for channel_url, platform, is_active in channels:
            self._create_channel_item(channel_url, platform, bool(int(is_active)))

    def _create_channel_item(self, channel_url: str, platform: str, is_active: bool = True):
        """Tạo item kênh (expand/collapse + active/inactive + mở folder + xóa)."""
        channel_container = ctk.CTkFrame(self.channels_scrollframe)
        channel_container.pack(fill="x", padx=5, pady=5)

        header_frame = ctk.CTkFrame(channel_container)
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
            new_state = bool(active_var.get())
            self.database.set_channel_active(channel_url, platform, new_state)
            url_label.configure(text_color=("white" if new_state else "gray"))
            active_badge.configure(text=("ACTIVE" if new_state else "OFF"), text_color=("#00c853" if new_state else "gray"))

        expand_btn = ctk.CTkButton(
            header_frame,
            text="▶",
            width=30,
            command=toggle_expand,
            fg_color="transparent",
            hover_color="gray20",
        )
        expand_btn.pack(side="left", padx=5, pady=5)

        active_var = ctk.IntVar(value=1 if is_active else 0)
        active_cb = ctk.CTkCheckBox(header_frame, text="", width=20, variable=active_var, command=on_toggle_active)
        active_cb.pack(side="left", padx=(2, 6), pady=5)

        active_badge = ctk.CTkLabel(
            header_frame,
            text=("ACTIVE" if is_active else "OFF"),
            width=55,
            text_color=("#00c853" if is_active else "gray"),
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
            text_color=("white" if is_active else "gray"),
        )
        url_label.pack(side="left", fill="x", expand=True, padx=5)

        videos = self.database.get_videos_by_channel(channel_url, platform)
        ctk.CTkLabel(header_frame, text=f"📹 {len(videos)}", width=60, text_color="gray").pack(side="left", padx=5)

        ctk.CTkButton(
            header_frame,
            text="📂",
            width=40,
            command=lambda url=channel_url, p=platform: self.open_channel_folder(url, p),
            fg_color="blue",
            hover_color="darkblue",
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
        videos_frame = ctk.CTkFrame(parent, fg_color="gray15")
        videos_frame.pack(fill="x", padx=10, pady=(0, 5))

        videos = self.database.get_videos_by_channel(channel_url, platform)
        if not videos:
            ctk.CTkLabel(videos_frame, text="Chưa có video nào được tải", text_color="gray").pack(pady=10)
            return videos_frame

        for video_id, title, file_path, downloaded_at in videos:
            video_frame = ctk.CTkFrame(videos_frame, fg_color="gray20")
            video_frame.pack(fill="x", padx=5, pady=2)

            ctk.CTkLabel(video_frame, text="🎬", width=30).pack(side="left", padx=5)

            ctk.CTkButton(
                video_frame,
                text=title[:60] + ("..." if len(title) > 60 else ""),
                anchor="w",
                fg_color="transparent",
                hover_color="gray30",
                command=lambda fp=file_path: self.open_video(fp),
            ).pack(side="left", fill="x", expand=True, padx=5)

            ctk.CTkLabel(
                video_frame,
                text=(downloaded_at[:16] if downloaded_at else ""),
                text_color="gray",
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

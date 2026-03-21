"""
Video Downloader CLI - Phiên bản Command Line (không cần GUI)
Hỗ trợ: YouTube, TikTok, Douyin, Facebook
"""

import os
import time

from database import DownloadHistory
from downloader_core import VideoDownloader, ChannelMonitor
from config import SUPPORTED_PLATFORMS, MAX_CHANNELS_PER_PLATFORM, CHECK_INTERVAL


class VideoDownloaderCLI:
    """Ứng dụng CLI để tải video"""

    def __init__(self):
        self.database = DownloadHistory()
        self.downloader = VideoDownloader()
        self.channel_monitor = None
        self.download_path = os.path.join(os.getcwd(), "downloads")
        self.downloader.download_path = self.download_path
        self.downloader.create_download_folder()
        self.downloader.set_organize_by_channel(True)
        self.is_monitoring = False

    def clear_screen(self):
        """Xóa màn hình console"""
        os.system('clear' if os.name != 'nt' else 'cls')

    def print_header(self):
        """In header của ứng dụng"""
        self.clear_screen()
        print("=" * 60)
        print("🎬 VIDEO DOWNLOADER CLI".center(60))
        print("Tải Video Đa Nền Tảng".center(60))
        print("=" * 60)
        print()

    def print_menu(self):
        """In menu chính"""
        print("\n📋 MENU CHÍNH:")
        print("-" * 60)
        print("1. 📥 Tải video theo link")
        print("2. 👁️  Quản lý kênh theo dõi")
        print("3. ▶️  Bắt đầu/Dừng theo dõi tự động")
        print("4. 📊 Xem thống kê")
        print("5. ⚙️  Cài đặt")
        print("0. 🚪 Thoát")
        print("-" * 60)

    def download_video(self):
        """Tải một video từ URL"""
        print("\n" + "=" * 60)
        print("📥 TẢI VIDEO THEO LINK")
        print("=" * 60)

        print("\n🌐 Hỗ trợ: YouTube, TikTok, Douyin, Facebook")
        print("VD: https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")

        url = input("🔗 Nhập URL video (Enter để quay lại): ").strip()

        if not url:
            return

        # Chọn chất lượng video
        print("\n📺 Chọn chất lượng video:")
        print("1. 🏆 Cao nhất (Best - Khuyến nghị)")
        print("2. 🎬 4K (2160p)")
        print("3. 📺 Full HD (1080p)")
        print("4. 💿 HD (720p)")
        print("5. 📀 SD (480p)")

        quality_choice = input("\n👉 Chọn (1-5, Enter = Cao nhất): ")


        quality_map = {
            "1": "best",
            "2": "4k",
            "3": "1080p",
            "4": "720p",
            "5": "480p",
            "": "best"
        }

        quality = quality_map.get(quality_choice, "best")
        quality_name = {
            "best": "Cao nhất",
            "4k": "4K (2160p)",
            "1080p": "Full HD (1080p)",
            "720p": "HD (720p)",
            "480p": "SD (480p)"
        }.get(quality, "Cao nhất")

        print(f"\n⏳ Đang tải video chất lượng {quality_name}...")
        print(f"🔗 URL: {url}")
        print("⏱️  Vui lòng chờ...\n")

        result = self.downloader.download_video(url, quality=quality, channel_url=None)

        if result.get('success'):
            video_id = self.downloader.extract_video_id(
                url,
                result.get('platform', 'Unknown')
            )

            self.database.add_downloaded_video(
                video_id=video_id,
                video_url=url,
                platform=result.get('platform', 'Unknown'),
                title=result.get('title', ''),
                file_path=result.get('file_path', '')
            )

            print("✅ THÀNH CÔNG!")
            print(f"📝 Tiêu đề: {result.get('title', 'Unknown')}")
            print(f"🎬 Nền tảng: {result.get('platform', 'Unknown')}")
            print(f"💾 Lưu tại: {result.get('file_path', 'Unknown')}")
        else:
            print("❌ LỖI!")
            print(f"⚠️  {result.get('error', 'Lỗi không xác định')}")

        input("\n📌 Nhấn Enter để tiếp tục...")

    def manage_channels(self):
        """Quản lý kênh theo dõi"""
        while True:
            self.print_header()
            print("👁️  QUẢN LÝ KÊNH THEO DÕI")
            print("=" * 60)

            # Hiển thị danh sách kênh hiện tại
            self.show_channels()

            print("\n📋 MENU:")
            print("-" * 60)
            print("1. ➕ Thêm kênh mới")
            print("2. 🗑️  Xóa kênh")
            print("3. ✅ Tick/Untick kênh (Active để tải)")
            print("0. ◀️  Quay lại")
            print("-" * 60)

            choice = input("\n👉 Chọn chức năng: ").strip()

            if choice == "1":
                self.add_channel()
            elif choice == "2":
                self.remove_channel()
            elif choice == "3":
                self.toggle_channel_active_cli()
            elif choice == "0":
                break

    def show_channels(self):
        """Hiển thị danh sách kênh đang theo dõi (kèm trạng thái active)"""
        channels = self.database.get_monitored_channels(only_active=False)

        if not channels:
            print("\n⚠️  Chưa có kênh nào được theo dõi.")
            return

        active_count = sum(1 for _, __, a in channels if int(a) == 1)
        print(f"\n📺 Đang theo dõi {len(channels)} kênh (Active: {active_count}):")
        print("-" * 60)

        by_platform = {}
        for channel_url, platform, is_active in channels:
            by_platform.setdefault(platform, []).append((channel_url, int(is_active)))

        for platform, items in by_platform.items():
            print(f"\n🎯 {platform} ({len(items)}/{MAX_CHANNELS_PER_PLATFORM}):")
            for i, (url, is_active) in enumerate(items, 1):
                short_url = url[:50] + "..." if len(url) > 50 else url
                mark = "✅" if is_active else "⬜"
                print(f"   {i}. {mark} {short_url}")

    def toggle_channel_active_cli(self):
        """Tick/untick trạng thái active của kênh"""
        channels = self.database.get_monitored_channels(only_active=False)

        if not channels:
            print("\n⚠️  Không có kênh nào!")
            input("\n📌 Nhấn Enter để tiếp tục...")
            return

        print("\n" + "=" * 60)
        print("✅ TICK/UNTICK KÊNH (ACTIVE)")
        print("=" * 60)
        print("\n📺 Danh sách kênh:")

        for i, (channel_url, platform, is_active) in enumerate(channels, 1):
            short_url = channel_url[:50] + "..." if len(channel_url) > 50 else channel_url
            mark = "✅" if int(is_active) == 1 else "⬜"
            print(f"{i}. {mark} [{platform}] {short_url}")

        choice = input("\n👉 Chọn kênh để tick/untick (0 để hủy): ").strip()

        try:
            idx = int(choice) - 1
            if idx < 0:
                return
            if idx >= len(channels):
                print("❌ Lựa chọn không hợp lệ!")
                input("\n📌 Nhấn Enter để tiếp tục...")
                return

            channel_url, platform, _ = channels[idx]
            new_state = self.database.toggle_channel_active(channel_url, platform)
            print(f"\n✅ Đã cập nhật: {'ACTIVE' if new_state else 'INACTIVE'}")
        except ValueError:
            print("❌ Vui lòng nhập số!")

        input("\n📌 Nhấn Enter để tiếp tục...")

    def toggle_monitoring(self):
        """Bật/tắt theo dõi tự động"""
        self.print_header()
        print("▶️  THEO DÕI TỰ ĐỘNG")
        print("=" * 60)

        # CHỈ theo dõi kênh đang active
        channels = self.database.get_monitored_channels(only_active=True)

        if not channels:
            print("\n⚠️  Chưa có kênh nào được tick Active để theo dõi!")
            print("📝 Vào 'Quản lý kênh theo dõi' -> 'Tick/Untick kênh' để bật Active.")
            input("\n📌 Nhấn Enter để tiếp tục...")
            return

        if not self.is_monitoring:
            print(f"\n📺 Sẽ theo dõi {len(channels)} kênh")
            print(f"⏰ Kiểm tra mỗi {CHECK_INTERVAL // 60} phút")
            print("\n⚠️  Lưu ý: Nhấn Ctrl+C để dừng\n")

            confirm = input("👉 Bắt đầu theo dõi? (y/n): ").strip().lower()

            if confirm == 'y':
                self.is_monitoring = True
                print("✅ Đã bật chế độ theo dõi tự động!")
                input("\n📌 Nhấn Enter để tiếp tục...")
            else:
                print("❌ Đã hủy bỏ!")
                input("\n📌 Nhấn Enter để tiếp tục...")
        else:
            self.is_monitoring = False
            print("✅ Đã tắt chế độ theo dõi tự động!")
            input("\n📌 Nhấn Enter để tiếp tục...")

    def view_statistics(self):
        """Xem thống kê tải video"""
        self.print_header()
        print("📊 THỐNG KÊ TẢI VIDEO")
        print("=" * 60)

        total_downloaded = self.database.get_total_downloaded_videos()
        total_size = self.database.get_total_downloaded_size()

        print(f"✅ Tổng số video đã tải: {total_downloaded}")
        print(f"📦 Tổng dung lượng: {total_size / (1024 * 1024):.2f} MB")

        input("\n📌 Nhấn Enter để tiếp tục...")

    def settings(self):
        """Cài đặt ứng dụng"""
        self.print_header()
        print("⚙️  CÀI ĐẶT")
        print("=" * 60)

        print("1. 📁 Thay đổi thư mục lưu video")
        print("2. ⏰ Thay đổi khoảng thời gian kiểm tra kênh")
        print("0. Quay lại")

        choice = input("\n👉 Chọn chức năng: ").strip()

        if choice == "1":
            self.change_download_folder()
        elif choice == "2":
            self.change_check_interval()
        elif choice == "0":
            return

    def change_download_folder(self):
        """Thay đổi thư mục lưu video"""
        print("\n" + "=" * 60)
        print("📁 THAY ĐỔI THƯ MỤC LƯU VIDEO")
        print("=" * 60)

        new_path = input(f"🔄 Nhập đường dẫn thư mục mới (hiện tại: {self.download_path}): ").strip()

        if not new_path:
            return

        # Kiểm tra thư mục hợp lệ
        if not os.path.isdir(new_path):
            print("❌ Thư mục không hợp lệ!")
            input("\n📌 Nhấn Enter để tiếp tục...")
            return

        self.download_path = new_path
        self.downloader.download_path = new_path

        # Cập nhật lại thư mục lưu trong database
        self.database.update_download_path(new_path)

        print("✅ Đã thay đổi thư mục lưu video!")
        input("\n📌 Nhấn Enter để tiếp tục...")

    def change_check_interval(self):
        """Thay đổi khoảng thời gian kiểm tra kênh"""
        global CHECK_INTERVAL
        print("\n" + "=" * 60)
        print("⏰ THAY ĐỔI KHOẢNG THỜI GIAN KIỂM TRA KÊNH")
        print("=" * 60)

        current_interval = CHECK_INTERVAL // 60
        new_interval = input(f"🔄 Nhập khoảng thời gian mới (phút, hiện tại: {current_interval} phút): ").strip()

        if not new_interval:
            return

        try:
            new_interval = int(new_interval)
            if new_interval <= 0:
                print("❌ Giá trị không hợp lệ!")
                input("\n📌 Nhấn Enter để tiếp tục...")
                return

            CHECK_INTERVAL = new_interval * 60

            print("✅ Đã thay đổi khoảng thời gian kiểm tra kênh!")
            input("\n📌 Nhấn Enter để tiếp tục...")
        except ValueError:
            print("❌ Vui lòng nhập số nguyên!")
            input("\n📌 Nhấn Enter để tiếp tục...")

    def run(self):
        """Chạy ứng dụng"""
        while True:
            self.print_header()
            self.print_menu()

            choice = input("\n👉 Chọn chức năng: ").strip()

            if choice == "1":
                self.download_video()
            elif choice == "2":
                self.manage_channels()
            elif choice == "3":
                self.toggle_monitoring()
            elif choice == "4":
                self.view_statistics()
            elif choice == "5":
                self.settings()
            elif choice == "0":
                print("🚪 Thoát ứng dụng. Hẹn gặp lại!")
                break
            else:
                print("❌ Lựa chọn không hợp lệ! Vui lòng chọn lại.")
                time.sleep(1)


if __name__ == "__main__":
    cli = VideoDownloaderCLI()
    cli.run()

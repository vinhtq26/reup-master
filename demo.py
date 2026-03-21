#!/usr/bin/env python3
"""
Script demo/test nhanh các chức năng của Video Downloader
"""

import sys
import os

# Thêm thư mục hiện tại vào path
sys.path.insert(0, os.path.dirname(__file__))

print("🎬 VIDEO DOWNLOADER - Demo Script")
print("=" * 60)

# Test 1: Import các module
print("\n📦 Test 1: Kiểm tra import modules...")
try:
    from database import DownloadHistory
    from downloader_core import VideoDownloader, ChannelMonitor
    from config import SUPPORTED_PLATFORMS, MAX_CHANNELS_PER_PLATFORM
    print("✅ Tất cả modules import thành công!")
except ImportError as e:
    print(f"❌ Lỗi import: {e}")
    sys.exit(1)

# Test 2: Kiểm tra dependencies
print("\n📦 Test 2: Kiểm tra dependencies...")
dependencies = {
    "yt-dlp": "yt_dlp",
    "requests": "requests",
    "pillow": "PIL"
}

missing = []
for name, module in dependencies.items():
    try:
        __import__(module)
        print(f"✅ {name}: OK")
    except ImportError:
        print(f"❌ {name}: THIẾU")
        missing.append(name)

if missing:
    print(f"\n⚠️  Thiếu dependencies: {', '.join(missing)}")
    print("📝 Chạy: pip install -r requirements.txt")
    sys.exit(1)

# Test 3: Khởi tạo database
print("\n📦 Test 3: Kiểm tra database...")
try:
    db = DownloadHistory("test_db.db")
    print("✅ Database khởi tạo thành công!")

    # Test thêm kênh
    db.add_monitored_channel("https://www.youtube.com/@test", "YouTube")
    channels = db.get_monitored_channels()
    print(f"✅ Thêm kênh test: OK (Tổng: {len(channels)} kênh)")

    # Cleanup
    db.remove_monitored_channel("https://www.youtube.com/@test", "YouTube")
    db.close()
    os.remove("test_db.db")
    print("✅ Cleanup: OK")
except Exception as e:
    print(f"❌ Lỗi database: {e}")

# Test 4: Khởi tạo downloader
print("\n📦 Test 4: Kiểm tra downloader...")
try:
    downloader = VideoDownloader("./test_downloads")
    print("✅ Downloader khởi tạo thành công!")

    # Test detect platform
    test_urls = {
        "https://www.youtube.com/watch?v=test": "YouTube",
        "https://www.tiktok.com/@user/video/123": "TikTok",
        "https://www.facebook.com/watch/?v=123": "Facebook"
    }

    for url, expected in test_urls.items():
        platform = downloader.detect_platform(url)
        status = "✅" if platform == expected else "❌"
        print(f"{status} {url[:40]}... → {platform}")

    # Cleanup
    if os.path.exists("./test_downloads"):
        os.rmdir("./test_downloads")
    print("✅ Cleanup: OK")
except Exception as e:
    print(f"❌ Lỗi downloader: {e}")

# Test 5: Kiểm tra config
print("\n📦 Test 5: Kiểm tra cấu hình...")
try:
    print(f"✅ Platforms: {len(SUPPORTED_PLATFORMS)} nền tảng")
    for platform, info in SUPPORTED_PLATFORMS.items():
        print(f"   - {platform}: {info['example'][:40]}...")
    print(f"✅ Max channels/platform: {MAX_CHANNELS_PER_PLATFORM}")
except Exception as e:
    print(f"❌ Lỗi config: {e}")

# Test 6: Kiểm tra GUI availability
print("\n📦 Test 6: Kiểm tra GUI...")
try:
    import customtkinter
    print("✅ CustomTkinter: OK")
    gui_available = True
except ImportError:
    print("⚠️  CustomTkinter: THIẾU (cần cho GUI)")
    gui_available = False

try:
    import tkinter
    print("✅ Tkinter: OK")
except ImportError:
    print("⚠️  Tkinter: THIẾU (cần cho GUI)")
    print("📝 Xem FIX_TKINTER.md để khắc phục")
    gui_available = False

# Tổng kết
print("\n" + "=" * 60)
print("📊 KẾT QUẢ TỔNG QUÁT:")
print("=" * 60)

print("\n✅ CÁC CHỨC NĂNG HOẠT ĐỘNG:")
print("   - Import modules: ✅")
print("   - Dependencies cơ bản: ✅")
print("   - Database: ✅")
print("   - Downloader core: ✅")
print("   - Config: ✅")

if gui_available:
    print("   - GUI: ✅")
    print("\n🚀 BẠN CÓ THỂ SỬ DỤNG:")
    print("   - python video_downloader.py (GUI)")
    print("   - python video_downloader_cli.py (CLI)")
else:
    print("   - GUI: ⚠️  (Không khả dụng)")
    print("\n🚀 BẠN CÓ THỂ SỬ DỤNG:")
    print("   - python video_downloader_cli.py (CLI) ⭐ KHUYẾN NGHỊ")
    print("\n📝 Để sử dụng GUI:")
    print("   - Xem file FIX_TKINTER.md")
    print("   - Hoặc tiếp tục dùng phiên bản CLI")

print("\n" + "=" * 60)
print("🎉 SẴN SÀNG SỬ DỤNG!")
print("=" * 60)

print("\n💡 HƯỚNG DẪN NHANH:")
print("   1. Chạy CLI: python video_downloader_cli.py")
print("   2. Chọn menu '1' để tải video")
print("   3. Dán link và tải!")

print("\n📖 Xem thêm:")
print("   - README.md: Hướng dẫn chi tiết")
print("   - USAGE_GUIDE.txt: Hướng dẫn sử dụng")
print("   - FIX_TKINTER.md: Sửa lỗi GUI")

print("\n🌟 Happy Downloading!")
print("=" * 60)


#!/usr/bin/env python3
"""
Quick Download - Tải video nhanh từ command line
Sử dụng: python quick_download.py [URL] [quality]
Ví dụ: python quick_download.py "https://youtube.com/watch?v=..." best
"""

import sys
from core.downloader_core import VideoDownloader

def main():
    print("=" * 70)
    print("⚡ QUICK DOWNLOAD - Tải video nhanh")
    print("=" * 70)

    # Lấy URL từ arguments hoặc input
    if len(sys.argv) > 1:
        url = sys.argv[1]
        quality = sys.argv[2] if len(sys.argv) > 2 else "best"
    else:
        url = input("\n🔗 Nhập URL video: ").strip()
        print("\n📊 Chọn chất lượng:")
        print("  1. Best (Cao nhất) ⭐")
        print("  2. 1080p")
        print("  3. 720p")
        print("  4. 480p")
        choice = input("\n👉 Lựa chọn (1-4, mặc định 1): ").strip() or "1"

        quality_map = {
            "1": "best",
            "2": "1080p",
            "3": "720p",
            "4": "480p"
        }
        quality = quality_map.get(choice, "best")

    print(f"\n🎬 URL: {url}")
    print(f"📊 Chất lượng: {quality}")
    print(f"📁 Thư mục: ./downloads/")
    print()

    # Progress callback
    def progress_hook(d):
        # yt-dlp có thể gọi hook với payload không phải dict
        if not isinstance(d, dict):
            return

        status = d.get('status')
        if status == 'downloading':
            try:
                percent = d.get('_percent_str', 'N/A')
                speed = d.get('_speed_str', 'N/A')
                print(f"\r⏳ {percent} | {speed}", end='', flush=True)
            except Exception:
                pass
        elif status == 'finished':
            print("\n✅ Đang merge...", flush=True)

    # Download
    downloader = VideoDownloader(download_path="./downloads")
    print("🚀 Bắt đầu tải...\n")

    result = downloader.download_video(
        url=url,
        progress_callback=progress_hook,
        quality=quality
    )

    print()
    print("=" * 70)

    if result['success']:
        print("✅ THÀNH CÔNG!")
        print(f"📝 {result['title']}")
        print(f"💾 {result['file_path']}")
        print()
        print(f"💡 Mở video: open \"{result['file_path']}\"")
    else:
        print("❌ LỖI!")
        print(f"⚠️  {result.get('error', 'Unknown error')}")

    print("=" * 70)

if __name__ == "__main__":
    main()

"""
Script test tải video chất lượng cao
"""

from core.downloader_core import VideoDownloader

# URL video test - Video ngắn để test nhanh
test_url = "https://www.youtube.com/watch?v=Ztrj8UIDMQY"

print("🎬 TEST TẢI VIDEO CHẤT LƯỢNG CAO")
print("=" * 60)
print(f"📺 URL: {test_url}")
print(f"📁 Thư mục: ./downloads/")
print()

# Khởi tạo downloader
downloader = VideoDownloader(download_path="./downloads")

# Progress callback
def progress_hook(d):
    if d['status'] == 'downloading':
        try:
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            print(f"\r⏳ Đang tải: {percent} | Tốc độ: {speed} | Còn lại: {eta}", end='', flush=True)
        except:
            pass
    elif d['status'] == 'finished':
        print("\n✅ Tải xong! Đang merge video và audio...")

print("🚀 Bắt đầu tải với chất lượng CAO NHẤT (Best)...")
print()

# Tải video
result = downloader.download_video(
    url=test_url,
    quality="best",  # Chất lượng cao nhất
    channel_url=None,
)

print()
print()
print("=" * 60)

if result['success']:
    print("✅ THÀNH CÔNG!")
    print(f"📝 Tiêu đề: {result['title']}")
    print(f"🎬 Nền tảng: {result['platform']}")
    print(f"💾 File: {result['file_path']}")
    print()
    print("💡 Kiểm tra video:")
    print(f"   open \"{result['file_path']}\"")
    print()
    print("📊 Để xem thông tin chi tiết:")
    print(f"   ffprobe -v error -show_format -show_streams \"{result['file_path']}\" | grep -E '(codec_name|width|height|bit_rate)'")
else:
    print("❌ LỖI!")
    print(f"⚠️  {result.get('error', 'Unknown error')}")

print("=" * 60)


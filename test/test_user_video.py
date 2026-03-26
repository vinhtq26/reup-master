"""
Test tải video từ link YouTube của user
URL: https://www.youtube.com/watch?v=Ztrj8UIDMQY&list=RDZtrj8UIDMQY&start_radio=1
"""

from core.downloader_core import VideoDownloader

# Link YouTube của user
url = "https://www.youtube.com/watch?v=Ztrj8UIDMQY"

print("=" * 70)
print("🎬 TẢI VIDEO TỪ LINK CỦA BẠN")
print("=" * 70)
print(f"🔗 URL: {url}")
print()

downloader = VideoDownloader(download_path="./downloads")

def progress_hook(d):
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
        print("\n✅ Merge video+audio...", flush=True)

print("🚀 Đang tải với chất lượng CAO NHẤT (VP9 codec)...")
print()

result = downloader.download_video(
    url,
    channel_url=None,
)

print()
print("=" * 70)
if result['success']:
    print("✅ THÀNH CÔNG! VIDEO RÕ NÉT!")
    print(f"📝 {result['title']}")
    print(f"💾 {result['file_path']}")
    print()
    print("💡 Mở video để xem:")
    print(f"   open \"{result['file_path']}\"")
else:
    print(f"❌ LỖI: {result.get('error')}")
print("=" * 70)

#!/usr/bin/env python3
"""
Test logic giới hạn video khi lần đầu theo dõi kênh
"""

from database import DownloadHistory
from downloader_core import VideoDownloader, ChannelMonitor

print("=" * 70)
print("🧪 TEST LOGIC GIỚI HẠN VIDEO LẦN ĐẦU THEO DÕI KÊNH")
print("=" * 70)
print()

# Khởi tạo
db = DownloadHistory()
downloader = VideoDownloader(download_path="./downloads")

# Test case: Kênh mới
test_channel = "https://www.youtube.com/@test_channel"
test_platform = "YouTube"

print(f"📺 Kênh test: {test_channel}")
print()

# Kiểm tra first_scan
is_first = db.is_first_scan(test_channel, test_platform)
print(f"🔍 Kiểm tra first_scan: {is_first}")

if is_first:
    print("   → ✅ Là lần đầu quét")
    print("   → 📊 Sẽ chỉ tải 5 video mới nhất")
else:
    print("   → ✅ Đã quét rồi")
    print("   → 📊 Sẽ kiểm tra tất cả video mới")

print()

# Thêm kênh vào monitoring
print("➕ Thêm kênh vào monitoring...")
success = db.add_monitored_channel(test_channel, test_platform)
if success:
    print("   ✅ Đã thêm thành công")
else:
    print("   ℹ️  Kênh đã tồn tại")

print()

# Kiểm tra lại
is_first = db.is_first_scan(test_channel, test_platform)
print(f"🔍 Kiểm tra lại first_scan: {is_first}")
print(f"   → {'Sẽ giới hạn 5 video' if is_first else 'Không giới hạn'}")

print()

# Giả lập đánh dấu đã hoàn thành
print("✅ Giả lập hoàn thành lần quét đầu...")
db.mark_first_scan_done(test_channel, test_platform)

print()

# Kiểm tra lần cuối
is_first = db.is_first_scan(test_channel, test_platform)
print(f"🔍 Kiểm tra sau khi đánh dấu: {is_first}")
if not is_first:
    print("   ✅ THÀNH CÔNG! Đã đánh dấu hoàn thành")
    print("   → Lần sau sẽ không giới hạn nữa")
else:
    print("   ❌ LỖI! Chưa đánh dấu được")

print()
print("=" * 70)
print("🎉 TEST HOÀN TẤT!")
print()
print("📝 Tóm tắt logic:")
print("   1. Lần đầu thêm kênh: first_scan_done = 0 → Giới hạn 5 video")
print("   2. Sau khi tải xong: first_scan_done = 1 → Không giới hạn")
print("   3. Lần monitoring tiếp: Chỉ tải video mới thật sự")
print("=" * 70)

# Cleanup
db.remove_monitored_channel(test_channel, test_platform)
db.close()


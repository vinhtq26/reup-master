#!/usr/bin/env python3
"""
Test instant stop - Kiểm tra việc dừng ngay lập tức khi nhấn Stop
"""

import time
from database import DownloadHistory
from downloader_core import VideoDownloader, ChannelMonitor

print("=" * 70)
print("🧪 TEST INSTANT STOP - DỪNG NGAY LẬP TỨC")
print("=" * 70)
print()

# Khởi tạo
db = DownloadHistory()
downloader = VideoDownloader(download_path="./downloads")
monitor = ChannelMonitor(downloader, db, check_interval=10)

# Status callback
def status_update(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

# Test case
print("📝 Kịch bản test:")
print("   1. Bắt đầu monitoring")
print("   2. Chờ 3 giây")
print("   3. Nhấn Stop")
print("   4. Kiểm tra xem có dừng ngay không")
print()

# Thêm kênh test (không tải thật)
test_channel = "https://www.youtube.com/@test"
db.add_monitored_channel(test_channel, "YouTube")

print("1️⃣ Bắt đầu monitoring...")
monitor.start_monitoring(status_callback=status_update)
print("   ✅ Đã bắt đầu")
print()

print("2️⃣ Chờ 3 giây...")
time.sleep(3)
print("   ✅ Đã chờ 3 giây")
print()

print("3️⃣ Nhấn STOP ngay bây giờ...")
start_time = time.time()
monitor.stop_monitoring()
stop_time = time.time()
elapsed = stop_time - start_time

print()
print("=" * 70)
print(f"⏱️  THỜI GIAN DỪNG: {elapsed:.2f} giây")
print()

if elapsed < 1.0:
    print("✅ THÀNH CÔNG! Dừng NGAY LẬP TỨC (< 1 giây)")
elif elapsed < 3.0:
    print("⚠️  CHẤP NHẬN ĐƯỢC! Dừng trong 1-3 giây")
else:
    print("❌ CHẬM! Dừng lâu hơn 3 giây")

print()
print("📊 Kết luận:")
if elapsed < 1.0:
    print("   → App sẽ dừng ngay khi nhấn Stop")
    print("   → Không tải thêm video nào nữa")
    print("   → Video đang tải (nếu có) sẽ hoàn thành rồi dừng")
else:
    print("   → Cần cải thiện thêm để dừng nhanh hơn")

print("=" * 70)

# Cleanup
db.remove_monitored_channel(test_channel, "YouTube")
db.close()


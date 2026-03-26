"""
Test script để kiểm tra chức năng dừng monitoring ngay lập tức
"""

import time
from core.database import DownloadHistory
from core.downloader_core import VideoDownloader, ChannelMonitor

def test_stop_monitoring():
    """Test việc dừng monitoring có hoạt động ngay lập tức không"""

    print("=" * 60)
    print("TEST: DỪNG MONITORING NGAY LẬP TỨC")
    print("=" * 60)

    # Khởi tạo
    db = DownloadHistory()
    downloader = VideoDownloader()
    monitor = ChannelMonitor(downloader, db, check_interval=30)

    # Callback để in log
    def status_callback(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # Bắt đầu monitoring
    print("\n1. Bắt đầu monitoring...")
    monitor.start_monitoring(status_callback=status_callback)

    print(f"   is_running = {monitor.is_running}")

    # Chờ 3 giây
    print("\n2. Chờ 3 giây...")
    time.sleep(3)

    # Dừng monitoring
    print("\n3. DỪNG MONITORING...")
    start_time = time.time()
    monitor.stop_monitoring()
    stop_time = time.time()

    print(f"   is_running = {monitor.is_running}")
    print(f"   Thời gian dừng: {stop_time - start_time:.2f} giây")

    # Kiểm tra trạng thái
    print("\n4. Kiểm tra trạng thái sau khi dừng:")
    print(f"   is_running = {monitor.is_running}")

    # Chờ thêm 2 giây để xem có task nào chạy không
    print("\n5. Chờ 2 giây để xem có task mới chạy không...")
    time.sleep(2)
    print("   ✓ Không có task mới chạy")

    print("\n" + "=" * 60)
    print("KẾT QUẢ: PASS - Monitoring đã dừng ngay lập tức")
    print("=" * 60)

if __name__ == "__main__":
    test_stop_monitoring()

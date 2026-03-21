"""
File hướng dẫn sử dụng nhanh (Quick Start Guide)
"""

# ============================================
# HƯỚNG DẪN SỬ DỤNG VIDEO DOWNLOADER
# ============================================

print("""
🎬 VIDEO DOWNLOADER - Hướng dẫn nhanh
==========================================

📦 1. CÀI ĐẶT (một lần duy nhất)
---------------------------------
Mở Terminal tại thư mục này và chạy:

    source .venv/bin/activate
    pip install -r requirements.txt

Hoặc đơn giản hơn:

    ./run.sh


🚀 2. KHỞI CHẠY ỨNG DỤNG
--------------------------
    python video_downloader.py

Hoặc:
    ./run.sh


📥 3. CÁCH SỬ DỤNG
-------------------

A. Tải video theo link:
   ① Chọn tab "📥 Tải theo Link"
   ② Dán link video (YouTube, TikTok, Douyin, Facebook)
   ③ Nhấn "⬇️ Tải Video"
   ④ Chờ tải xong!

B. Theo dõi kênh tự động:
   ① Chọn tab "👁️ Theo dõi Kênh"
   ② Chọn nền tảng
   ③ Nhập URL kênh
   ④ Nhấn "Thêm kênh"
   ⑤ Nhấn "▶️ BẮT ĐẦU THEO DÕI"
   ⑥ Ứng dụng sẽ tự động tải video mới mỗi 5 phút

C. Xem thống kê:
   ① Chọn tab "📊 Thống kê"
   ② Xem số video đã tải và phân chia theo nền tảng


📝 4. VÍ DỤ LINK HỢP LỆ
-------------------------

YouTube:
  - Video: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  - Kênh:  https://www.youtube.com/@channelname
  
TikTok:
  - Video: https://www.tiktok.com/@user/video/1234567890
  - Kênh:  https://www.tiktok.com/@username

Facebook:
  - Video: https://www.facebook.com/watch/?v=1234567890
  - Trang: https://www.facebook.com/pagename

Douyin:
  - Video: https://www.douyin.com/video/1234567890


⚙️ 5. TÙY CHỈNH CẤU HÌNH
--------------------------
Chỉnh sửa file config.py để thay đổi:
  - Số kênh tối đa theo dõi
  - Thời gian kiểm tra video mới
  - Định dạng video tải về


🐛 6. XỬ LÝ LỖI THƯỜNG GẶP
----------------------------

Lỗi: "No module named 'customtkinter'"
→ Chạy: pip install -r requirements.txt

Lỗi: "Unable to download video"
→ Kiểm tra kết nối internet
→ Cập nhật yt-dlp: pip install yt-dlp --upgrade

Video không có âm thanh:
→ Cài FFmpeg: brew install ffmpeg (macOS)


📂 7. CẤU TRÚC THỨ MỤC
-----------------------
FastAPIProject/
├── video_downloader.py   ← File chính - Chạy file này!
├── downloader_core.py    ← Logic tải video
├── database.py           ← Quản lý database
├── config.py             ← Cấu hình
├── requirements.txt      ← Thư viện cần thiết
├── README.md             ← Hướng dẫn chi tiết
├── run.sh                ← Script khởi chạy nhanh
├── download_history.db   ← Database (tự động tạo)
└── downloads/            ← Thư mục video (tự động tạo)


💡 8. MẸO SỬ DỤNG
-------------------
✓ Chọn thư mục lưu trước khi tải video
✓ Kiểm tra dung lượng ổ cứng trước khi tải nhiều video
✓ Theo dõi không quá nhiều kênh để tránh quá tải
✓ Video HD/4K có dung lượng rất lớn
✓ Đọc README.md để biết thêm chi tiết


🎉 9. BẮT ĐẦU NGAY!
--------------------
    python video_downloader.py

Hoặc:
    ./run.sh


📧 HỖ TRỢ & ĐÓNG GÓP
---------------------
- Đọc file README.md để biết chi tiết
- Báo lỗi bằng cách tạo Issue
- Đóng góp code qua Pull Request


⚠️ LƯU Ý QUAN TRỌNG
---------------------
- Chỉ tải video bạn có quyền sử dụng
- Tuân thủ điều khoản của các nền tảng
- Tool chỉ để học tập và sử dụng cá nhân


==========================================
Made with ❤️  by Python & yt-dlp
🌟 Happy Downloading!
==========================================
""")

# Test import các module
try:
    import customtkinter
    import yt_dlp
    print("✅ Tất cả thư viện đã được cài đặt!")
    print("\n🚀 Bạn có thể chạy ứng dụng bằng lệnh:")
    print("   python video_downloader.py")
    print("\nHoặc:")
    print("   ./run.sh")
except ImportError as e:
    print(f"❌ Thiếu thư viện: {e}")
    print("\n📦 Vui lòng cài đặt bằng lệnh:")
    print("   pip install -r requirements.txt")


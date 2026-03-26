#!/bin/bash
# Script khởi chạy nhanh ứng dụng Video Downloader

echo "🎬 Khởi động Video Downloader..."
echo ""

# Kích hoạt môi trường ảo
source .venv/bin/activate

# Kiểm tra xem đã cài đặt dependencies chưa
if ! python -c "import customtkinter" 2>/dev/null; then
    echo "📦 Đang cài đặt dependencies..."
    pip install -r requirements.txt
    echo "✅ Hoàn tất cài đặt!"
    echo ""
fi

# Khởi chạy ứng dụng
echo "🚀 Đang mở ứng dụng..."
python gui.video_downloader.py

# Deactivate khi thoát
deactivate


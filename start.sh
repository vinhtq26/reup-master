1
#!/bin/bash

# Script chạy dự án Video Downloader
# Tự động chọn phương thức phù hợp

echo "======================================================================"
echo "🎬 VIDEO DOWNLOADER - AUTO LAUNCHER"
echo "======================================================================"
echo ""

# Kiểm tra môi trường ảo
if [ ! -d ".venv" ]; then
    echo "❌ Không tìm thấy môi trường ảo .venv"
    echo "⚠️  Tạo môi trường ảo..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
    echo "✅ Đã kích hoạt môi trường ảo"
fi

echo ""
echo "======================================================================"
echo "Chọn phương thức chạy:"
echo "======================================================================"
echo "1. 🖥️  GUI (Giao diện đồ họa) - Khuyến nghị"
echo "2. 💻 CLI (Dòng lệnh)"
echo "3. ⚡ Test nhanh (tải 1 video)"
echo "4. 📖 Xem hướng dẫn"
echo "5. 🚪 Thoát"
echo "======================================================================"
echo ""

read -p "Nhập lựa chọn (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Đang khởi động GUI..."
        echo ""

        # Kiểm tra Tkinter
        python -c "import tkinter" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "⚠️  CẢNH BÁO: Tkinter chưa được cài đặt!"
            echo ""
            echo "Để cài Tkinter trên macOS:"
            echo "  brew install python-tk@3.12"
            echo ""
            echo "Hoặc cài Python từ python.org (đã bao gồm Tkinter)"
            echo ""
            echo "📖 Xem thêm: FIX_TKINTER.md"
            echo ""
            read -p "Nhấn Enter để chạy CLI thay thế..."
            python video_downloader_cli.py
        else
            python video_downloader.py
        fi
        ;;
    2)
        echo ""
        echo "🚀 Đang khởi động CLI..."
        echo ""
        python video_downloader_cli.py
        ;;
    3)
        echo ""
        echo "⚡ Test tải video nhanh..."
        echo ""
        python test_user_video.py
        ;;
    4)
        echo ""
        echo "📖 Xem hướng dẫn..."
        echo ""
        if command -v bat &> /dev/null; then
            bat HUONG_DAN_CHAY.md
        elif command -v less &> /dev/null; then
            less HUONG_DAN_CHAY.md
        else
            cat HUONG_DAN_CHAY.md
        fi
        ;;
    5)
        echo ""
        echo "👋 Tạm biệt!"
        exit 0
        ;;
    *)
        echo ""
        echo "❌ Lựa chọn không hợp lệ!"
        exit 1
        ;;
esac


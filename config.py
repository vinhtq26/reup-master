"""
File cấu hình cho ứng dụng Video Downloader
"""

# Số lượng kênh tối đa có thể theo dõi cho mỗi nền tảng
MAX_CHANNELS_PER_PLATFORM = 3

# Các nền tảng được hỗ trợ
SUPPORTED_PLATFORMS = {
    "YouTube": {
        "name": "YouTube",
        "color": "#FF0000",
        "example": "https://www.youtube.com/@channelname"
    },
    "TikTok": {
        "name": "TikTok",
        "color": "#000000",
        "example": "https://www.tiktok.com/@username"
    },
    "Douyin": {
        "name": "Douyin",
        "color": "#FE2C55",
        "example": "https://www.douyin.com/user/..."
    },
    "Facebook": {
        "name": "Facebook",
        "color": "#1877F2",
        "example": "https://www.facebook.com/pagename"
    }
}

# Thời gian kiểm tra video mới (giây)
CHECK_INTERVAL = 300  # 5 phút

# Số lượng video tối đa để kiểm tra mỗi lần quét
MAX_VIDEOS_TO_CHECK = 10

# Số video tải khi LẦN ĐẦU theo dõi kênh (để tránh tải hết video cũ)
# Ví dụ: Kênh có 500 video cũ → Chỉ tải 5 video mới nhất
FIRST_SCAN_VIDEO_LIMIT = 5

# TẢI SONG SONG (Parallel Download)
# Số lượng video tải đồng thời (1 = tuần tự, 2-4 = song song)
PARALLEL_DOWNLOADS = 2  # Tải 2 video cùng lúc → Nhanh gấp đôi!
# Lưu ý: Không nên > 4 để tránh quá tải mạng và bị block

# Tên file lưu lịch sử
HISTORY_FILE = "download_history.db"

# Định dạng video mặc định - Chất lượng cao nhất THỰC SỰ!
# Format string cho yt-dlp:
# - Ưu tiên VP9 codec (webm) vì chất lượng tốt hơn H.264 (mp4) trên YouTube
# - Kết hợp với audio Opus chất lượng cao
# - FFmpeg sẽ tự động merge và convert về mp4
# - KHÔNG giới hạn ext=mp4 vì sẽ bỏ lỡ chất lượng cao nhất!
DEFAULT_VIDEO_FORMAT = "bestvideo[vcodec^=vp9]+bestaudio[acodec=opus]/bestvideo[vcodec^=av01]+bestaudio/bestvideo+bestaudio/best"

# Các tùy chọn chất lượng khác (có thể thay đổi)
VIDEO_FORMAT_OPTIONS = {
    "best_quality": "bestvideo[vcodec^=vp9]+bestaudio[acodec=opus]/bestvideo+bestaudio/best",  # Chất lượng cao nhất - VP9/Opus
    "4k": "bestvideo[height>=2160][vcodec^=vp9]+bestaudio[acodec=opus]/bestvideo[height>=2160]+bestaudio/best[height>=2160]",  # 4K với VP9
    "1080p": "bestvideo[height>=1080]+bestaudio/best[height>=1080]",  # Full HD
    "720p": "bestvideo[height>=720]+bestaudio/best[height>=720]",  # HD
    "480p": "bestvideo[height>=480]+bestaudio/best[height>=480]",  # SD
    "best_mp4": "best[ext=mp4]/best",  # Best MP4 only
}

# ================== VIDEO SPLIT CONFIG ==================
# Nếu video dài hơn ngưỡng này (giây) thì sẽ tự động cắt nhỏ.
# Mặc định 2 phút = 120s.
SPLIT_IF_LONGER_THAN_SECONDS = 120

# Độ dài mỗi đoạn sau khi cắt (giây).
# Có thể để bằng 120 để cắt thành các đoạn 2 phút.
SPLIT_SEGMENT_SECONDS = 120

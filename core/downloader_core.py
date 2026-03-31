"""
Module xử lý logic tải video sử dụng yt-dlp
"""

import yt_dlp
import os
import re
from typing import Optional, List, Dict, Callable
import threading
import time
import random
import string
from core.video_processing import sanitize_filename
from core.video_processing import process, extract_audio_from_video, VideoProcessor
from core.drive_uploader import upload_file_to_drive
from core.video_splitter import split_if_longer_than
class VideoDownloader:
    """Class xử lý tải video từ các nền tảng"""

    def __init__(self, download_path: str = "./downloads"):
        """
        Khởi tạo downloader

        Args:
            download_path: Đường dẫn thư mục lưu video
        """
        self.download_path = download_path
        # Mặc định: KHÔNG chia thư mục theo Platform/Channel.
        # Nếu muốn chia, set True (xem set_organize_by_channel)
        self.organize_by_channel = False
        self.create_download_folder()

    def create_download_folder(self):
        """Tạo thư mục download nếu chưa tồn tại"""
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def extract_video_id(self, url: str, platform: str) -> Optional[str]:
        """Trích xuất video ID từ URL"""
        try:
            # YouTube
            if "youtube.com" in url or "youtu.be" in url:
                patterns = [
                    r"(?:v=|/)([0-9A-Za-z_-]{11}).*",
                    r"youtu\.be/([0-9A-Za-z_-]{11})",
                ]
                for pattern in patterns:
                    match = re.search(pattern, url)
                    if match:
                        return match.group(1)

            # TikTok
            elif "tiktok.com" in url:
                match = re.search(r"/video/(\d+)", url)
                if match:
                    return match.group(1)

            # Douyin
            elif "douyin.com" in url:
                match = re.search(r"/video/(\d+)", url)
                if match:
                    return match.group(1)

            # Facebook
            elif "facebook.com" in url or "fb.watch" in url:
                patterns = [
                    r"/videos/(\d+)",
                    r"/(\d+)/",
                    r"v=(\d+)",
                ]
                for pattern in patterns:
                    match = re.search(pattern, url)
                    if match:
                        return match.group(1)

            return url

        except Exception as e:
            print(f"Lỗi khi trích xuất video ID: {e}")
            return url

    def set_organize_by_channel(self, enabled: bool):
        """Bật/tắt chế độ chia thư mục theo Platform/Channel"""
        self.organize_by_channel = bool(enabled)

    def download_video(self, url: str, progress_callback: Callable = None, quality: str = "best", monitor=None, channel_url: str = None) -> Dict:
        """
        Tải một video từ URL

        Args:
            url: URL video cần tải
            progress_callback: Hàm callback để cập nhật tiến trình
            quality: Chất lượng video (best, 4k, 1080p, 720p, 480p)
            monitor: ChannelMonitor instance để kiểm tra is_running
            channel_url: URL kênh (để tạo folder riêng cho kênh)

        Returns:
            Dict chứa thông tin kết quả tải
        """
        try:
            # KIỂM TRA TRƯỚC KHI BẮT ĐẦU - Dừng nếu monitor đã stop
            if monitor and hasattr(monitor, 'is_running') and not monitor.is_running:
                return {
                    'success': False,
                    'error': 'Download cancelled - monitoring stopped',
                    'url': url
                }

            # Xác định platform
            platform = self.detect_platform(url)

            # Quyết định thư mục output
            # Luôn tạo folder theo tên tài khoản (nếu lấy được), nếu không thì random 4 ký tự
            channel_name = None
            if channel_url:
                channel_name = self.extract_channel_name(channel_url, platform)
            else:
                # Thử lấy từ url video nếu không có channel_url
                channel_name = self.extract_channel_name(url, platform)

            # Kiểm tra channel_name hợp lệ (không None, không rỗng, không chứa ký tự cấm)
            def is_valid_channel_name(name):
                if not name or not isinstance(name, str):
                    return False
                # Không chứa ký tự cấm cho tên folder
                return re.match(r'^[\w\-\s\.]+$', name) is not None

            if not is_valid_channel_name(channel_name):
                # Sinh folder ngẫu nhiên 4 ký tự nếu không hợp lệ
                channel_name = ''.join(random.choices(string.ascii_letters + string.digits, k=4))

            output_dir = os.path.join(self.download_path, platform, channel_name)
            os.makedirs(output_dir, exist_ok=True)

            # Xác định format string dựa trên quality
            # CHIẾN LƯỢC MỚI: Ưu tiên BITRATE CAO NHẤT, không ưu tiên codec!
            # Lý do: Một số video H.264 có bitrate cao hơn VP9
            # yt-dlp sẽ tự động chọn video có bitrate/chất lượng cao nhất

            if quality == "4k":
                # 4K - Lấy video bitrate cao nhất ở 4K
                format_string = "bestvideo[height>=2160]+bestaudio/best[height>=2160]"
            elif quality == "1080p":
                # 1080p - Lấy video bitrate cao nhất ở 1080p
                format_string = "bestvideo[height>=1080][height<=1440]+bestaudio/best[height>=1080]"
            elif quality == "720p":
                # 720p - Lấy video bitrate cao nhất ở 720p
                format_string = "bestvideo[height>=720][height<=900]+bestaudio/best[height>=720]"
            elif quality == "480p":
                # 480p - Tiết kiệm dung lượng
                format_string = "bestvideo[height>=480][height<=600]+bestaudio/best[height>=480]"
            else:
                # BEST - BITRATE CAO NHẤT TUYỆT ĐỐI!
                # Sắp xếp theo: filesize (tương ứng bitrate) > bitrate > resolution
                # Ưu tiên file lớn nhất = chất lượng tốt nhất
                format_string = "bv*[vcodec!^=av01][vcodec!^=vp9.2]+ba/bv*+ba/b"

            # Cấu hình yt-dlp với chất lượng cao nhất - TỐI ƯU HÓA!
            # Lưu ý: yt-dlp expects outtmpl to be a dict with key 'default' (can accept str at init,
            # nhưng nội bộ thường normalize thành dict; ta luôn dùng dict để tránh lỗi TypeError)
            ydl_opts = {
                'format': format_string,
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': True,
                'merge_output_format': 'mp4',

                # # YouTube: cần JS runtime để extract đủ format (yt-dlp cảnh báo nếu thiếu)
                # # Máy bạn có Node.js => dùng node để tránh thiếu format/không tải được với một số video dài/playlist
                # 'js_runtimes': ['node'],
                #
                # # Nếu user dán link có &list=... thì mặc định chỉ tải video hiện tại (tránh tải cả playlist "Mix")
                # 'noplaylist': True,

                # QUAN TRỌNG: Sử dụng FFmpeg với tham số tối ưu
                # yt-dlp mong đợi kiểu dict[str, list[str]]
                'postprocessor_args': {
                    'ffmpeg': [
                        '-c:v', 'copy',
                        '-c:a', 'aac',
                        '-b:a', '320k',
                        '-ar', '48000',
                        '-movflags', '+faststart',
                    ]
                },

                # Tùy chọn nâng cao
                'prefer_free_formats': False,  # Ưu tiên chất lượng > format mở

                # Bỏ VideoConvertor vì nó có thể re-encode và làm giảm chất lượng!
                # Chỉ dùng FFmpeg native merge

                # Debug: Giữ file gốc để so sánh (uncomment nếu cần)
                # 'keepvideo': True,
            }

            # Xác định tên file an toàn, ngắn gọn cho outtmpl (nếu quá dài thì chỉ lấy video_id)
            try:
                info_dict = yt_dlp.YoutubeDL({'quiet': True}).extract_info(url, download=False)
                video_id = info_dict.get('id', 'video')
                title = info_dict.get('title', 'Unknown')
                safe_title = self.sanitize_filename(title, 40)
                outtmpl_filename = f"{video_id}_{safe_title}.%(ext)s"
                if len(outtmpl_filename) > 80:
                    outtmpl_filename = f"{video_id}.%(ext)s"
            except Exception:
                outtmpl_filename = 'video.%(ext)s'
            ydl_opts['outtmpl'] = {'default': os.path.join(output_dir, outtmpl_filename)}

            # Thêm progress hook để kiểm tra monitor
            progress_hooks = []

            if progress_callback:
                # progress_callback (nhất là từ UI) đôi khi assume d là dict và dùng d['status'].
                # yt-dlp có thể gọi hook với payload không phải dict => wrap để tránh lỗi
                def safe_progress_hook(d):
                    if not isinstance(d, dict):
                        return
                    try:
                        progress_callback(d)
                    except Exception as hook_err:
                        # Không để lỗi từ callback làm fail toàn bộ quá trình tải
                        print(f"⚠️ progress_callback error: {hook_err}")

                progress_hooks.append(safe_progress_hook)

            # Thêm hook để kiểm tra is_running
            if monitor:
                def check_monitor_hook(d):
                    # d có thể không phải dict trong một số trường hợp, nên kiểm tra an toàn
                    if not isinstance(d, dict):
                        return
                    status = d.get('status')
                    if hasattr(monitor, 'is_running') and not monitor.is_running:
                        # Không thể dừng yt-dlp giữa chừng, nhưng ít nhất log ra
                        if status == 'downloading':
                            print("⚠️ Monitor stopped nhưng download đang chạy - Sẽ dừng sau khi hoàn thành")
                progress_hooks.append(check_monitor_hook)

            if progress_hooks:
                ydl_opts['progress_hooks'] = progress_hooks

            # Tải subtitle (optional) - uncomment nếu muốnKhông thể tải video:
            # string indices must be integers, not 'str'
            # ydl_opts['writesubtitles'] = True
            # ydl_opts['writeautomaticsub'] = True
            # ydl_opts['subtitleslangs'] = ['vi', 'en']  # Tiếng Việt và Tiếng Anh

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # KIỂM TRA LẦN CUỐI TRƯỚC KHI TẢI
                if monitor and hasattr(monitor, 'is_running') and not monitor.is_running:
                    return {
                        'success': False,
                        'error': 'Download cancelled before starting',
                        'url': url
                    }

                # Lấy thông tin video trước
                info = ydl.extract_info(url, download=False)

                # Nếu yt-dlp trả về None thì dừng
                if info is None:
                    return {
                        'success': False,
                        'error': 'Không thể lấy thông tin video',
                        'url': url
                    }

                # Nếu là list hoặc playlist, chuẩn hóa thành 1 entry dict để tránh lỗi string indices
                if isinstance(info, list):
                    if not info:
                        return {
                            'success': False,
                            'error': 'Không tìm thấy video trong danh sách',
                            'url': url
                        }
                    info = info[0]
                elif isinstance(info, dict) and info.get('_type') == 'playlist':
                    entries = info.get('entries') or []
                    if not entries:
                        return {
                            'success': False,
                            'error': 'Playlist không có video nào',
                            'url': url
                        }
                    info = entries[0]

                # Chỉ suy luận channel_url nếu info là dict
                if not channel_url and isinstance(info, dict):
                    channel_url = (
                        info.get('channel_url')
                        or info.get('uploader_url')
                        or info.get('webpage_url')
                    )

                # Sau khi có (hoặc không có) channel_url, quyết định thư mục output
                platform = self.detect_platform(url)
                if self.organize_by_channel:
                    # Luôn lấy tên tài khoản từ link download ban đầu (url), không lấy từ channel_url (có thể là sec_uid)
                    channel_name = self.extract_channel_name(url, platform)
                    channel_name = sanitize_filename(channel_name)
                    output_dir = os.path.join(self.download_path, platform, channel_name)
                else:
                    output_dir = self.download_path

                os.makedirs(output_dir, exist_ok=True)
                # KHÔNG overwrite outtmpl thành string; yt-dlp cần dict: self.params['outtmpl']['default']
                if isinstance(ydl.params.get('outtmpl'), dict):
                    ydl.params['outtmpl']['default'] = os.path.join(output_dir, '%(title)s.%(ext)s')
                else:
                    # fallback: set đúng kiểu dict
                    ydl.params['outtmpl'] = {'default': os.path.join(output_dir, '%(title)s.%(ext)s')}

                # KIỂM TRA TRƯỚC KHI TẢI THẬT SỰ
                if monitor and hasattr(monitor, 'is_running') and not monitor.is_running:
                    return {
                        'success': False,
                        'error': 'Download cancelled',
                        'url': url
                    }

                # Tải video
                try:
                    ydl.download([url])
                except TypeError as te:
                    # Một số trường hợp lỗi đến từ progress_hooks/callback bên ngoài hoặc payload không đúng kiểu.
                    # Thử lại 1 lần không có progress_hooks để tránh crash toàn bộ.
                    msg = str(te)
                    if "string indices must be integers" in msg:
                        try:
                            # clone, bỏ hooks
                            ydl2_opts = dict(ydl_opts)
                            ydl2_opts.pop('progress_hooks', None)
                            with yt_dlp.YoutubeDL(ydl2_opts) as ydl2:
                                ydl2.download([url])
                        except Exception as te2:
                            raise te2
                    else:
                        raise

                # Luôn dùng tên file đã sanitize, ngắn, tiếng Anh cho outtmpl
                if isinstance(info, dict):
                    video_id = info.get('id', 'video')
                    title = info.get('title', 'Unknown')
                    safe_title = sanitize_filename(title, 20)
                    if not safe_title:
                        safe_title = 'video'
                    ext = info.get('ext', 'mp4')
                    outtmpl_filename = f"{video_id}_{safe_title}.%(ext)s"
                    ydl.params['outtmpl']['default'] = os.path.join(output_dir, outtmpl_filename)
                else:
                    video_id = ''
                    title = 'Unknown'
                    outtmpl_filename = 'video.%(ext)s'
                    ydl.params['outtmpl']['default'] = os.path.join(output_dir, outtmpl_filename)

                # KIỂM TRA TRƯỚC KHI TẢI THẬT SỰ
                if monitor and hasattr(monitor, 'is_running') and not monitor.is_running:
                    return {
                        'success': False,
                        'error': 'Download cancelled',
                        'url': url
                    }

                # Tải video
                try:
                    ydl.download([url])
                except TypeError as te:
                    # Một số trường hợp lỗi đến từ progress_hooks/callback bên ngoài hoặc payload không đúng kiểu.
                    # Thử lại 1 lần không có progress_hooks để tránh crash toàn bộ.
                    msg = str(te)
                    if "string indices must be integers" in msg:
                        try:
                            # clone, bỏ hooks
                            ydl2_opts = dict(ydl_opts)
                            ydl2_opts.pop('progress_hooks', None)
                            with yt_dlp.YoutubeDL(ydl2_opts) as ydl2:
                                ydl2.download([url])
                        except Exception as te2:
                            raise te2
                    else:
                        raise

                # Chỉ dùng .get nếu info là dict, tránh lỗi "string indices must be integers"
                if isinstance(info, dict):
                    video_id = info.get('id', '')
                    title = info.get('title', 'Unknown')
                    safe_title = sanitize_filename(title, 40)
                    if not safe_title:
                        safe_title = 'video'
                    ext = info.get('ext', 'mp4')
                    file_path = os.path.join(output_dir, f"{video_id}_{safe_title}.{ext}")
                else:
                    video_id = ''
                    title = 'Unknown'
                    file_path = ''

                return {
                    'success': True,
                    'video_id': video_id,
                    'title': title,
                    'url': url,
                    'platform': platform,
                    'channel_url': channel_url,
                    'file_path': file_path
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url': url
            }

    def get_channel_videos(self, channel_url: str, max_videos: int = 10) -> List[Dict]:
        """
        Lấy danh sách video từ một kênh

        Args:
            channel_url: URL kênh
            max_videos: Số lượng video tối đa cần lấy

        Returns:
            List các dict chứa thông tin video
        """
        try:
            # Chuẩn hóa URL kênh cho một số nền tảng (đặc biệt Douyin)
            normalized_url = channel_url
            platform = self.detect_platform(channel_url)

            # Douyin: yt-dlp thường không hỗ trợ trực tiếp /user/<sec_uid>
            # nhưng hỗ trợ tốt hơn dạng tab video `?mode=1` (video posts)
            if platform == "Douyin":
                if "/user/" in normalized_url and "mode=" not in normalized_url:
                    # giữ nguyên query khác (nếu có) thì nối thêm &mode=1
                    normalized_url = normalized_url + ("&" if "?" in normalized_url else "?") + "mode=1"

            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False,
                'playlistend': max_videos,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(normalized_url, download=False)

                if not playlist_info:
                    return []

                videos = []
                entries = playlist_info.get('entries', [])

                for entry in entries[:max_videos]:
                    if entry:
                        video_info = {
                            'video_id': entry.get('id', ''),
                            'title': entry.get('title', 'Unknown'),
                            'url': entry.get('url', '') or entry.get('webpage_url', ''),
                            'platform': platform
                        }
                        videos.append(video_info)

                return videos

        except Exception as e:
            print(f"Lỗi khi lấy video từ kênh {channel_url}: {e}")
            return []

    def detect_platform(self, url: str) -> str:
        """
        Phát hiện nền tảng từ URL

        Args:
            url: URL cần kiểm tra

        Returns:
            Tên nền tảng
        """
        if "youtube.com" in url or "youtu.be" in url:
            return "YouTube"
        elif "tiktok.com" in url:
            return "TikTok"
        elif "douyin.com" in url:
            return "Douyin"
        elif "facebook.com" in url or "fb.watch" in url:
            return "Facebook"
        else:
            return "Unknown"

    def extract_channel_name(self, url: str, platform: str) -> str:
        """Trích xuất tên tài khoản/kênh từ URL, nếu không có thì random 4 ký tự"""
        try:
            # TikTok, Douyin: /@username/ hoặc /@username/video... (lấy toàn bộ sau @, chỉ giữ chữ và số và dấu chấm)
            match = re.search(r"/@([\w\.]+)", url)
            if match:
                username = match.group(1)
                username_clean = re.sub(r"[^a-zA-Z0-9.]", "", username)
                print(f"[LOG] extract_channel_name: TikTok username raw='{username}', clean='{username_clean}' from url={url}")
                if hasattr(self, 'status_callback') and callable(getattr(self, 'status_callback', None)):
                    self.status_callback(f"[LOG] extract_channel_name: TikTok username raw='{username}', clean='{username_clean}' from url={url}")
                if username_clean:
                    return username_clean
            # YouTube: /channel/UCxxxx, /c/Name, /user/Name
            match = re.search(r"/(channel|c|user)/([\w\-\.]+)", url)
            if match:
                username = match.group(2)
                username_clean = re.sub(r"[^a-zA-Z0-9]", "", username)
                print(f"[LOG] extract_channel_name: YouTube username raw='{username}', clean='{username_clean}' from url={url}")
                if hasattr(self, 'status_callback') and callable(getattr(self, 'status_callback', None)):
                    self.status_callback(f"[LOG] extract_channel_name: YouTube username raw='{username}', clean='{username_clean}' from url={url}")
                if username_clean:
                    return username_clean
            # Facebook: /username/ hoặc /videos/
            match = re.search(r"facebook.com/([\w\.]+)/", url)
            if match:
                username = match.group(1)
                username_clean = re.sub(r"[^a-zA-Z0-9]", "", username)
                print(f"[LOG] extract_channel_name: Facebook username raw='{username}', clean='{username_clean}' from url={url}")
                if hasattr(self, 'status_callback') and callable(getattr(self, 'status_callback', None)):
                    self.status_callback(f"[LOG] extract_channel_name: Facebook username raw='{username}', clean='{username_clean}' from url={url}")
                if username_clean:
                    return username_clean
        except Exception as e:
            print(f"[LOG] Exception in extract_channel_name: {e} (url={url})")
            if hasattr(self, 'status_callback') and callable(getattr(self, 'status_callback', None)):
                self.status_callback(f"[LOG] Exception in extract_channel_name: {e} (url={url})")
        # Nếu không lấy được thì trả về 'unknown'
        print(f"[LOG] extract_channel_name: unknown for url={url}")
        if hasattr(self, 'status_callback') and callable(getattr(self, 'status_callback', None)):
            self.status_callback(f"[LOG] extract_channel_name: unknown for url={url}")
        return "unknown"

    def get_channel_name(self, url: str) -> str:
        """
        Lấy tên tài khoản từ url. Nếu không xác định được thì trả về 'unknown'.
        Chỉ được phép trả về 'unknown' nếu thực sự không lấy được tên tài khoản.
        """
        try:
            # TikTok, Douyin: /@username/ hoặc /@username/video... (lấy toàn bộ sau @, chỉ giữ chữ và số và dấu chấm)
            match = re.search(r"/@([\w\.]+)", url)
            if match:
                username = match.group(1)
                # Loại bỏ mọi ký tự không phải chữ, số hoặc dấu chấm
                username = re.sub(r"[^a-zA-Z0-9.]", "", username)
                if username:
                    print(f"[DEBUG] TikTok username detected: {username}")
                    return username
            # YouTube: /channel/UCxxxx, /c/Name, /user/Name
            match = re.search(r"/(channel|c|user)/([\w\-\.]+)", url)
            if match:
                username = match.group(2)
                username = re.sub(r"[^a-zA-Z0-9]", "", username)
                if username:
                    print(f"[DEBUG] YouTube username detected: {username}")
                    return username
            # Facebook: /username/ hoặc /videos/
            match = re.search(r"facebook.com/([\w\.]+)/", url)
            if match:
                username = match.group(1)
                username = re.sub(r"[^a-zA-Z0-9]", "", username)
                if username:
                    print(f"[DEBUG] Facebook username detected: {username}")
                    return username
        except Exception as e:
            print(f"[DEBUG] Exception in get_channel_name: {e}")
        # Nếu không lấy được thì trả về 'unknown'
        print("[DEBUG] Channel name unknown for url:", url)
        return "unknown"

    def process_and_upload(self, url: str, split: bool = False, extract_audio: bool = False, progress_callback: Callable = None, quality: str = "best", monitor=None, channel_url: str = None, platform: str = None, log_callback: Callable = None, logo_path: str = None, logo_position: str = None) -> Dict:
        """
        Luồng chuẩn: Tải video -> Chỉnh sửa -> (Cắt nếu cần) -> (Tách âm nếu chọn) -> Upload file đã chỉnh sửa/cắt và file âm thanh tách ra từ các file này.
        TUYỆT ĐỐI không upload file gốc hoặc tách âm từ file gốc.
        """
        # Bước 1: Tải video gốc
        download_result = self.download_video(url, progress_callback=progress_callback, quality=quality, monitor=monitor, channel_url=channel_url)
        if not download_result.get('success'):
            return download_result
        file_goc = download_result.get('file_path')
        # Nếu file_goc là đường dẫn tương đối, chuyển sang tuyệt đối
        if file_goc and not os.path.isabs(file_goc):
            file_goc = os.path.abspath(file_goc)
        # Nếu vẫn không tồn tại, thử tìm file mp4 mới nhất trong thư mục output
        if not file_goc or not os.path.exists(file_goc):
            search_dir = self.download_path
            found_file = None
            latest_time = 0
            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if f.lower().endswith('.mp4') and not f.endswith('.part'):
                        full_path = os.path.join(root, f)
                        mtime = os.path.getmtime(full_path)
                        if mtime > latest_time:
                            latest_time = mtime
                            found_file = full_path
            if found_file and os.path.exists(found_file):
                file_goc = found_file
            else:
                # Ghi log các file mp4 thực tế để debug
                debug_files = []
                for root, dirs, files in os.walk(search_dir):
                    for f in files:
                        if f.lower().endswith('.mp4'):
                            debug_files.append(os.path.join(root, f))
                print(f"[DEBUG] Không tìm thấy file gốc. Các file mp4 hiện có: {debug_files}")
                return {'success': False, 'error': 'Không tìm thấy file gốc sau khi tải', 'url': url}
        # Bước 2: Chỉnh sửa video (mirror, speed, color, ...) VÀ chèn logo nếu có
        file_da_chinh_sua = process(file_goc, logo_path=logo_path, logo_position=logo_position)
        if not file_da_chinh_sua or not os.path.exists(file_da_chinh_sua):
            return {'success': False, 'error': 'Không tạo được file đã chỉnh sửa', 'url': url}

        # Bước 3: Tạo video sạch không âm thanh, không metadata
        processor = VideoProcessor()
        file_mute_clean = os.path.splitext(file_da_chinh_sua)[0] + '_mute_clean.mp4'
        mute_result = processor.make_video_mute_and_clean(file_da_chinh_sua, file_mute_clean, overwrite=True)
        if mute_result.returncode != 0 or not os.path.exists(file_mute_clean):
            file_mute_clean = None

        # Bước 4: Nếu cần cắt, cắt video đã chỉnh sửa thành nhiều phần
        file_cac_phan = [file_da_chinh_sua]
        if split:
            threshold_seconds = 60  # Ví dụ: cắt nếu dài hơn 60s
            segment_seconds = 60    # Ví dụ: mỗi phần 60s
            file_cac_phan = split_if_longer_than(
                file_da_chinh_sua,
                threshold_seconds=threshold_seconds,
                segment_seconds=segment_seconds
            )
            if not file_cac_phan:
                return {'success': False, 'error': 'Không cắt được video', 'url': url}

        # Bước 5: Nếu chọn tách âm, chỉ tách âm từ file đã chỉnh sửa/cắt
        file_audio = []
        if extract_audio:
            for f in file_cac_phan:
                audio = extract_audio_from_video(f)
                if audio:
                    file_audio.append(audio)

        # Bước 6: Upload file đã chỉnh sửa/cắt, file âm thanh, file mute sạch
        uploaded_files = []
        # Lấy tên tài khoản cho upload (chỉ cho phép 'unknown' nếu thực sự không xác định được)
        # Lấy platform nếu truyền vào (ưu tiên đối số), nếu không thì detect lại
        platform_name = platform or getattr(self, 'platform', None) or self.detect_platform(url)
        channel_name_upload = self.get_channel_name(url)
        if not channel_name_upload or channel_name_upload.strip() == "":
            channel_name_upload = "unknown"
        folder_parts = [platform_name, channel_name_upload]
        # Lấy log_callback nếu truyền vào
        log_callback = locals().get('log_callback') or locals().get('status_callback') or None
        for f in file_cac_phan:
            file_id = upload_file_to_drive(f, folder_parts, status_callback=log_callback)
            uploaded_files.append({'file': f, 'drive_id': file_id})
        uploaded_audios = []
        for a in file_audio:
            file_id = upload_file_to_drive(a, folder_parts, status_callback=log_callback)
            uploaded_audios.append({'file': a, 'drive_id': file_id})
        uploaded_mute_clean = None
        if file_mute_clean and os.path.exists(file_mute_clean):
            file_id = upload_file_to_drive(file_mute_clean, folder_parts, status_callback=log_callback)
            uploaded_mute_clean = {'file': file_mute_clean, 'drive_id': file_id}

        return {
            'success': True,
            'video_files': uploaded_files,
            'audio_files': uploaded_audios,
            'mute_clean_file': uploaded_mute_clean,
            'url': url
        }

    def sanitize_filename(name: str, max_length: int = 60) -> str:
        """
        Hàm chuẩn hóa tên file: loại bỏ ký tự đặc biệt, thay thế khoảng trắng bằng dấu gạch dưới, và giới hạn độ dài.

        Args:
            name: Tên file gốc
            max_length: Độ dài tối đa của tên file sau khi chuẩn hóa

        Returns:
            Tên file đã được chuẩn hóa
        """
        name = re.sub(r'[^\w\-_. ]', '', name)
        name = name.replace(' ', '_')
        return name[:max_length]


class ChannelMonitor:
    """Class quản lý việc theo dõi và tải video tự động từ các kênh"""

    def __init__(self, downloader: VideoDownloader, database, check_interval: int = 300, postprocess_callback=None):
        """Khởi tạo channel monitor

        Args:
            downloader: Instance của VideoDownloader
            database: Instance của DownloadHistory
            check_interval: Thời gian giữa các lần kiểm tra (giây)
            postprocess_callback: Optional callable(file_path:str, video_info:dict) -> str
                - Dùng để xử lý file sau khi tải (ví dụ FFmpeg edit, upload Drive).
                - video_info chứa tối thiểu: url, platform, channel_url, title, video_id.
                - Nên return đường dẫn file cuối cùng để lưu DB.
        """
        self.downloader = downloader
        self.database = database
        self.check_interval = check_interval
        self.is_running = False
        self.monitor_thread = None
        self.status_callback = None
        self.postprocess_callback = postprocess_callback

    def start_monitoring(self, status_callback: Callable = None):
        """
        Bắt đầu theo dõi các kênh

        Args:
            status_callback: Hàm callback để cập nhật trạng thái
        """
        if self.is_running:
            return

        self.is_running = True
        self.status_callback = status_callback
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Dừng theo dõi các kênh - NGAY LẬP TỨC"""
        if not self.is_running:
            if self.status_callback:
                self.status_callback("ℹ️ Monitoring đã dừng từ trước")
            return  # Đã dừng rồi

        if self.status_callback:
            self.status_callback("=" * 60)
            self.status_callback("⛔ ĐANG DỪNG MONITORING NGAY LẬP TỨC...")
            self.status_callback("=" * 60)

        # Đặt flag để tất cả task kiểm tra và dừng NGAY
        self.is_running = False

        # Thông báo đang dừng
        if self.status_callback:
            self.status_callback("⏹️ Đã gửi tín hiệu dừng (0.00s)")
            self.status_callback("")
            self.status_callback("✅ ĐÃ DỪNG THEO DÕI:")
            self.status_callback("   • Không kiểm tra kênh mới")
            self.status_callback("   • Không bắt đầu download mới")
            self.status_callback("   • Không lưu kết quả mới vào database")
            self.status_callback("")
            self.status_callback("⚠️ LƯU Ý:")
            self.status_callback("   • Download đang chạy sẽ hoàn thành (giới hạn kỹ thuật)")
            self.status_callback("   • NHƯNG kết quả sẽ bị bỏ qua, KHÔNG lưu vào lịch sử")
            self.status_callback("   • Thời gian chờ: < 30 giây")
            self.status_callback("=" * 60)

    def _monitor_loop(self):
        """Vòng lặp chính của monitor"""
        while self.is_running:
            try:
                # Lấy danh sách tất cả các kênh đang theo dõi
                channels = self.database.get_monitored_channels()

                for channel_url, platform, is_active in channels:
                    if not self.is_running:
                        break

                    self._check_channel(channel_url, platform)

                    # Cập nhật thời gian kiểm tra
                    self.database.update_channel_check_time(channel_url, platform)

                # Chờ đến lần kiểm tra tiếp theo (chia nhỏ để có thể dừng nhanh)
                # Thay vì chờ cả check_interval cùng lúc, chờ từng giây và kiểm tra is_running
                for _ in range(self.check_interval):
                    if not self.is_running:
                        if self.status_callback:
                            self.status_callback("⛔ Đã nhận tín hiệu dừng - Thoát monitor loop")
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"Lỗi trong monitor loop: {e}")
                if self.is_running:  # Chỉ sleep nếu vẫn đang chạy
                    time.sleep(10)

    def _check_channel(self, channel_url: str, platform: str):
        """
        Kiểm tra và tải video mới từ một kênh

        Args:
            channel_url: URL kênh
            platform: Nền tảng
        """
        try:
            # KIỂM TRA NGAY ĐẦU - Dừng nếu đã nhấn Stop ⚡
            if not self.is_running:
                if self.status_callback:
                    self.status_callback("⛔ Đã dừng - Bỏ qua kênh này")
                return

            if self.status_callback:
                self.status_callback(f"Đang kiểm tra kênh: {channel_url}")

            # Kiểm tra xem có phải lần đầu quét kênh này không
            is_first_scan = self.database.is_first_scan(channel_url, platform)

            # Nếu là lần đầu quét → Chỉ lấy N video mới nhất (tránh tải hết video cũ!)
            # Nếu không phải lần đầu → Lấy tất cả video để kiểm tra
            if is_first_scan:
                from config import FIRST_SCAN_VIDEO_LIMIT
                max_videos = FIRST_SCAN_VIDEO_LIMIT
                if self.status_callback:
                    self.status_callback(f"🆕 Lần đầu theo dõi kênh - Chỉ tải {max_videos} video mới nhất")
            else:
                from config import MAX_VIDEOS_TO_CHECK
                max_videos = MAX_VIDEOS_TO_CHECK

            # KIỂM TRA TRƯỚC KHI LẤY VIDEO - Dừng nếu đã nhấn Stop ⚡
            if not self.is_running:
                if self.status_callback:
                    self.status_callback("⛔ Đã dừng - Hủy quét kênh")
                return

            # Lấy danh sách video từ kênh
            videos = self.downloader.get_channel_videos(channel_url, max_videos=max_videos)

            # Lọc video chưa tải
            videos_to_download = []
            for video in videos:
                if not self.is_running:
                    break
                video_id = video.get('video_id', '')
                if not self.database.is_video_downloaded(video_id, platform):
                    videos_to_download.append(video)

            if not videos_to_download:
                if self.status_callback:
                    self.status_callback("ℹ️ Không có video mới để tải")
                # Đánh dấu first_scan nếu cần
                if is_first_scan:
                    self.database.mark_first_scan_done(channel_url, platform)
                return

            # KIỂM TRA - Dừng nếu đã nhấn Stop ⚡
            if not self.is_running:
                if self.status_callback:
                    self.status_callback(f"⛔ Đã dừng - Bỏ qua {len(videos_to_download)} video")
                return

            # TẢI SONG SONG (PARALLEL DOWNLOAD) 🚀
            from config import PARALLEL_DOWNLOADS
            import concurrent.futures

            if self.status_callback:
                if PARALLEL_DOWNLOADS > 1:
                    self.status_callback(f"🚀 Bắt đầu tải {len(videos_to_download)} video (song song {PARALLEL_DOWNLOADS} video/lần)")
                else:
                    self.status_callback(f"📥 Bắt đầu tải {len(videos_to_download)} video (tuần tự)")

            videos_downloaded = 0

            # Hàm tải 1 video (để chạy trong thread pool)
            def download_single_video(video):
                # Kiểm tra ngay đầu
                if not self.is_running:
                    return None

                try:
                    video_id = video.get('video_id', '')

                    # Kiểm tra lại trước khi bắt đầu download
                    if not self.is_running:
                        return None

                    if self.status_callback:
                        self.status_callback(f"📥 Đang tải: {video.get('title', 'Unknown')}")

                    # Pass monitor reference để download_video có thể kiểm tra is_running
                    # và channel_url để lưu theo folder riêng của kênh
                    result = self.downloader.download_video(video['url'], monitor=self, channel_url=channel_url)

                    # QUAN TRỌNG: Kiểm tra lại sau khi download xong, TRƯỚC KHI lưu database
                    if not self.is_running:
                        if self.status_callback:
                            self.status_callback(f"⛔ Bỏ qua kết quả: {video.get('title', 'Unknown')} (đã dừng)")
                        return None

                    if result.get('success'):
                        final_path = result.get('file_path', '')

                        # Optional postprocess (FFmpeg edit, strip metadata, upload Drive, ...)
                        if self.postprocess_callback and final_path:
                            try:
                                if self.status_callback:
                                    self.status_callback(f"✂️ Đang xử lý hậu kỳ: {video.get('title', 'Unknown')}")

                                video_info = {
                                    'video_id': video_id,
                                    'title': video.get('title', ''),
                                    'url': video.get('url', ''),
                                    'platform': platform,
                                    'channel_url': channel_url,
                                }

                                final_path = self.postprocess_callback(final_path, video_info) or final_path
                            except Exception as e:
                                if self.status_callback:
                                    self.status_callback(f"⚠️ Hậu kỳ lỗi (bỏ qua): {video.get('title', 'Unknown')} - {str(e)}")

                        # Lưu vào lịch sử
                        self.database.add_downloaded_video(
                            video_id=video_id,
                            video_url=video['url'],
                            platform=platform,
                            channel_url=channel_url,
                            title=video.get('title', ''),
                            file_path=final_path
                        )
                        if self.status_callback:
                            self.status_callback(f"✓ Đã tải: {video.get('title', 'Unknown')}")
                        return True
                    else:
                        if self.status_callback:
                            self.status_callback(f"✗ Lỗi: {video.get('title', 'Unknown')}")
                        return False
                except Exception as e:
                    if self.status_callback:
                        self.status_callback(f"✗ Lỗi: {video.get('title', 'Unknown')} - {str(e)}")
                    return False

            # Tải song song với ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_DOWNLOADS) as executor:
                # Submit tất cả tasks
                futures = []
                for video in videos_to_download:
                    if not self.is_running:
                        if self.status_callback:
                            self.status_callback("⛔ Đã dừng - Không submit task mới")
                        break
                    future = executor.submit(download_single_video, video)
                    futures.append(future)

                # Nếu không có futures nào (đã dừng trước khi submit), thoát luôn
                if not futures:
                    if self.status_callback:
                        self.status_callback("⛔ Đã dừng - Không có download nào được bắt đầu")
                    return

                # Đợi kết quả
                try:
                    for future in concurrent.futures.as_completed(futures, timeout=1):
                        # Kiểm tra TRƯỚC KHI xử lý kết quả
                        if not self.is_running:
                            # DỪNG NGAY LẬP TỨC
                            if self.status_callback:
                                self.status_callback("⛔ ĐANG DỪNG - Hủy tất cả download còn lại...")

                            # Cancel TẤT CẢ các future còn lại
                            cancelled_count = 0
                            for f in futures:
                                if f.cancel():  # Chỉ cancel được nếu chưa bắt đầu chạy
                                    cancelled_count += 1

                            if self.status_callback:
                                self.status_callback(f"⛔ Đã hủy {cancelled_count} download chưa bắt đầu")
                                running_count = len(futures) - cancelled_count
                                if running_count > 0:
                                    self.status_callback(f"⚠️ {running_count} download đang chạy sẽ được bỏ qua khi hoàn thành")

                            # Thoát vòng lặp ngay lập tức
                            break

                        try:
                            result = future.result(timeout=0.1)
                            if result:
                                videos_downloaded += 1
                        except concurrent.futures.TimeoutError:
                            continue
                        except Exception as e:
                            print(f"Lỗi khi lấy kết quả: {e}")

                except Exception as e:
                    if not self.is_running:
                        if self.status_callback:
                            self.status_callback("⛔ Đã dừng monitoring")
                    print(f"Lỗi trong download loop: {e}")

            # KIỂM TRA TRƯỚC KHI ĐÁNH DẤU - Dừng nếu đã nhấn Stop ⚡
            if not self.is_running:
                return

            # Nếu là lần đầu quét, đánh dấu đã hoàn thành
            if is_first_scan and videos_downloaded > 0:
                self.database.mark_first_scan_done(channel_url, platform)
                if self.status_callback:
                    self.status_callback(f"✅ Hoàn thành lần quét đầu ({videos_downloaded} video). Lần sau sẽ chỉ tải video mới!")

        except Exception as e:
            print(f"Lỗi khi kiểm tra kênh {channel_url}: {e}")
            if self.status_callback:
                self.status_callback(f"Lỗi kiểm tra kênh: {str(e)}")

"""
Module quản lý database lưu trữ lịch sử tải video
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional


class DownloadHistory:
    """Quản lý lịch sử tải video sử dụng SQLite"""

    def __init__(self, db_file: str = "download_history.db"):
        """
        Khởi tạo kết nối database

        Args:
            db_file: Đường dẫn file database
        """
        self.db_file = db_file
        self.connection = None
        self.init_database()

    def init_database(self):
        """Tạo bảng database nếu chưa tồn tại"""
        self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
        cursor = self.connection.cursor()

        # Bảng lưu lịch sử video đã tải
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloaded_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                video_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                channel_url TEXT,
                title TEXT,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                UNIQUE(video_id, platform)
            )
        ''')

        # Bảng lưu thông tin kênh đang theo dõi (thêm logo_path, logo_position)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitored_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_url TEXT NOT NULL,
                platform TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                first_scan_done INTEGER DEFAULT 0,
                last_check TIMESTAMP,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logo_path TEXT,
                logo_position TEXT,
                UNIQUE(channel_url, platform)
            )
        ''')

        # Migration: Thêm cột logo_path, logo_position nếu bảng cũ chưa có
        try:
            cursor.execute("ALTER TABLE monitored_channels ADD COLUMN logo_path TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE monitored_channels ADD COLUMN logo_position TEXT")
        except Exception:
            pass

        self.connection.commit()

    def is_video_downloaded(self, video_id: str, platform: str) -> bool:
        """
        Kiểm tra xem video đã được tải chưa

        Args:
            video_id: ID của video
            platform: Nền tảng (YouTube, TikTok, etc.)

        Returns:
            True nếu video đã được tải, False nếu chưa
        """
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM downloaded_videos WHERE video_id = ? AND platform = ?",
            (video_id, platform)
        )
        count = cursor.fetchone()[0]
        return count > 0

    def add_downloaded_video(self, video_id: str, video_url: str, platform: str,
                            channel_url: str = None, title: str = None,
                            file_path: str = None):
        """
        Thêm video vào lịch sử đã tải

        Args:
            video_id: ID của video
            video_url: URL của video
            platform: Nền tảng
            channel_url: URL kênh (optional)
            title: Tiêu đề video (optional)
            file_path: Đường dẫn file đã tải (optional)
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO downloaded_videos 
                (video_id, video_url, platform, channel_url, title, file_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (video_id, video_url, platform, channel_url, title, file_path))
            self.connection.commit()
        except Exception as e:
            print(f"Lỗi khi thêm video vào lịch sử: {e}")

    def add_monitored_channel(self, channel_url: str, platform: str, logo_path: str = None, logo_position: str = None) -> bool:
        """
        Thêm kênh vào danh sách theo dõi, kèm logo và vị trí nếu có

        Args:
            channel_url: URL kênh
            platform: Nền tảng
            logo_path: Đường dẫn logo kênh (optional)
            logo_position: Vị trí logo trên giao diện (optional)

        Returns:
            True nếu thêm thành công, False nếu thất bại
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO monitored_channels (channel_url, platform, logo_path, logo_position)
                VALUES (?, ?, ?, ?)
            ''', (channel_url, platform, logo_path, logo_position))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Lỗi khi thêm kênh: {e}")
            return False

    def remove_monitored_channel(self, channel_url: str, platform: str):
        """Xóa kênh khỏi danh sách theo dõi"""
        cursor = self.connection.cursor()
        cursor.execute(
            "DELETE FROM monitored_channels WHERE channel_url = ? AND platform = ?",
            (channel_url, platform)
        )
        self.connection.commit()

    def get_monitored_channels(self, platform: str = None, only_active: bool = False):
        """Lấy danh sách kênh đang theo dõi, kèm logo và vị trí

        Args:
            platform: lọc theo nền tảng (None = tất cả)
            only_active: True => chỉ lấy kênh đang active; False => lấy tất cả

        Returns:
            List tuple (channel_url, platform, is_active, logo_path, logo_position)
        """
        cursor = self.connection.cursor()
        query = 'SELECT channel_url, platform, is_active, logo_path, logo_position FROM monitored_channels'
        params = []
        if platform:
            query += ' WHERE platform = ?'
            params.append(platform)
        if only_active:
            query += (' AND' if platform else ' WHERE') + ' is_active = 1'
        cursor.execute(query, params)
        return cursor.fetchall()

    def get_channel_logo_config(self, channel_url: str, platform: str):
        """Lấy thông tin logo và vị trí của kênh"""
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT logo_path, logo_position FROM monitored_channels WHERE channel_url = ? AND platform = ?
        ''', (channel_url, platform))
        return cursor.fetchone() or (None, None)

    def update_channel_logo_config(self, channel_url: str, platform: str, logo_path: str, logo_position: str):
        """Cập nhật logo và vị trí cho kênh"""
        cursor = self.connection.cursor()
        cursor.execute('''
            UPDATE monitored_channels SET logo_path = ?, logo_position = ? WHERE channel_url = ? AND platform = ?
        ''', (logo_path, logo_position, channel_url, platform))
        self.connection.commit()

    def toggle_channel_active(self, channel_url: str, platform: str) -> bool:
        """Đảo trạng thái active cho 1 kênh. Return trạng thái mới."""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT is_active FROM monitored_channels WHERE channel_url = ? AND platform = ?",
            (channel_url, platform)
        )
        row = cursor.fetchone()
        if not row:
            return False
        new_val = 0 if int(row[0]) == 1 else 1
        cursor.execute(
            "UPDATE monitored_channels SET is_active = ? WHERE channel_url = ? AND platform = ?",
            (new_val, channel_url, platform)
        )
        self.connection.commit()
        return bool(new_val)

    def get_videos_by_channel(self, channel_url: str, platform: str) -> List[tuple]:
        """
        Lấy danh sách video đã tải từ một kênh

        Args:
            channel_url: URL kênh
            platform: Nền tảng

        Returns:
            List các tuple (video_id, title, file_path, download_date)
        """
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT video_id, title, file_path, download_date 
            FROM downloaded_videos 
            WHERE channel_url = ? AND platform = ?
            ORDER BY download_date DESC
        ''', (channel_url, platform))
        return cursor.fetchall()

    def is_first_scan(self, channel_url: str, platform: str) -> bool:
        """
        Kiểm tra xem kênh này có phải lần đầu quét không

        Args:
            channel_url: URL kênh
            platform: Nền tảng

        Returns:
            True nếu là lần đầu quét, False nếu đã quét rồi
        """
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT first_scan_done FROM monitored_channels WHERE channel_url = ? AND platform = ?",
            (channel_url, platform)
        )
        result = cursor.fetchone()
        if result:
            return result[0] == 0  # 0 = chưa scan, 1 = đã scan
        return True  # Nếu không tìm thấy, coi như là lần đầu

    def mark_first_scan_done(self, channel_url: str, platform: str):
        """
        Đánh dấu kênh đã hoàn thành lần quét đầu tiên

        Args:
            channel_url: URL kênh
            platform: Nền tảng
        """
        cursor = self.connection.cursor()
        cursor.execute('''
            UPDATE monitored_channels 
            SET first_scan_done = 1 
            WHERE channel_url = ? AND platform = ?
        ''', (channel_url, platform))
        self.connection.commit()

    def delete_video(self, video_id: str, platform: str, delete_file: bool = True, base_dir: str = None, force_db_delete: bool = False) -> dict:
        """
        Xóa video khỏi database và file khỏi disk.

        Nếu file_path trong DB không còn đúng (do người dùng đổi thư mục gốc),
        có thể truyền base_dir để tự dò file theo basename.

        Args:
            video_id: ID của video
            platform: Nền tảng
            delete_file: Có xóa file không (default: True)
            base_dir: Thư mục gốc hiện tại (optional) để tìm lại file nếu file_path không tồn tại
            force_db_delete: nếu True thì xóa record DB ngay cả khi không xóa được file

        Returns:
            dict với keys: success, file_deleted, message
        """
        cursor = self.connection.cursor()

        try:
            cursor.execute(
                "SELECT file_path, title FROM downloaded_videos WHERE video_id = ? AND platform = ?",
                (video_id, platform)
            )
            result = cursor.fetchone()
            if not result:
                return {"success": False, "file_deleted": False, "message": "Video không tồn tại trong database"}

            file_path, title = result
            resolved_path = file_path

            # Resolve path nếu đổi root
            if delete_file and resolved_path and (not os.path.exists(resolved_path)) and base_dir:
                basename = os.path.basename(resolved_path)
                for root, _, files in os.walk(base_dir):
                    if basename in files:
                        resolved_path = os.path.join(root, basename)
                        break

            file_deleted = False
            if delete_file:
                if resolved_path and os.path.exists(resolved_path):
                    try:
                        os.remove(resolved_path)
                        file_deleted = True
                    except Exception as e:
                        return {
                            "success": False,
                            "file_deleted": False,
                            "resolved_path": resolved_path,
                            "message": f"Không thể xóa file: {e}",
                        }
                else:
                    # Không tìm thấy file
                    if not force_db_delete:
                        return {
                            "success": False,
                            "file_deleted": False,
                            "resolved_path": resolved_path,
                            "message": "Không tìm thấy file video để xóa. Hãy kiểm tra lại thư mục lưu.",
                        }

            # Xóa DB (nếu file đã xóa, hoặc user force)
            cursor.execute(
                "DELETE FROM downloaded_videos WHERE video_id = ? AND platform = ?",
                (video_id, platform)
            )
            self.connection.commit()

            return {
                "success": True,
                "file_deleted": file_deleted,
                "resolved_path": resolved_path,
                "message": f"Đã xóa video: {title}",
                "title": title,
            }

        except Exception as e:
            return {"success": False, "file_deleted": False, "message": f"Lỗi: {str(e)}"}

    def get_download_stats(self) -> dict:
        """Lấy thống kê tải video"""
        cursor = self.connection.cursor()

        # Tổng số video đã tải
        cursor.execute("SELECT COUNT(*) FROM downloaded_videos")
        total = cursor.fetchone()[0]

        # Số video theo từng nền tảng
        cursor.execute("SELECT platform, COUNT(*) FROM downloaded_videos GROUP BY platform")
        by_platform = dict(cursor.fetchall())

        return {
            "total": total,
            "by_platform": by_platform
        }

    def close(self):
        """Đóng kết nối database"""
        if self.connection:
            self.connection.close()

    def update_channel_check_time(self, channel_url: str, platform: str):
        """Cập nhật thời gian kiểm tra cuối cùng của kênh"""
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE monitored_channels SET last_check = CURRENT_TIMESTAMP WHERE channel_url = ? AND platform = ?",
            (channel_url, platform)
        )
        self.connection.commit()

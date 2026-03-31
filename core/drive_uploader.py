"""Google Drive uploader helper.

- Sử dụng OAuth2 (credentials.json) để tạo service Drive.
- Tự động lưu token vào token.json để lần sau dùng lại.
- Hỗ trợ tạo cây thư mục theo cấu trúc local (Platform/Channel/...)

YÊU CẦU:
- Đặt file credentials trong `config/credentials.json` (ưu tiên) hoặc root project.
- Cài thư viện: google-api-python-client, google-auth-httplib2, google-auth-oauthlib
"""

from __future__ import annotations

import os
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Chỉ cần quyền làm việc với Drive của user
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Các file cấu hình OAuth/token
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")


def _resolve_credentials_file() -> Optional[str]:
    """Tìm file credentials theo thứ tự ưu tiên."""
    env_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE")
    candidate_paths = [
        env_path,
        os.path.join(CONFIG_DIR, "credentials.json"),
        os.path.join(CONFIG_DIR, "credential.json"),
        os.path.join(PROJECT_ROOT, "credentials.json"),
        os.path.join(os.path.dirname(__file__), "credentials.json"),
    ]
    for path in candidate_paths:
        if path and os.path.exists(path):
            return path
    return None


def _resolve_token_file() -> str:
    """Ưu tiên token trong config, fallback tương thích ngược ở core."""
    legacy_core_token = os.path.join(os.path.dirname(__file__), "token.json")
    if os.path.exists(legacy_core_token):
        return legacy_core_token
    return os.path.join(CONFIG_DIR, "token.json")


def get_drive_service():
    """Tạo service Google Drive, tự xử lý refresh token / login lần đầu.

    Trả về: googleapiclient.discovery.Resource
    """
    creds: Optional[Credentials] = None
    token_file = _resolve_token_file()
    credentials_file = _resolve_credentials_file()

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_file:
                searched = [
                    os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE"),
                    os.path.join(CONFIG_DIR, "credentials.json"),
                    os.path.join(CONFIG_DIR, "credential.json"),
                    os.path.join(PROJECT_ROOT, "credentials.json"),
                    os.path.join(os.path.dirname(__file__), "credentials.json"),
                ]
                raise FileNotFoundError(
                    "Không tìm thấy credentials file. Đã tìm tại: "
                    + ", ".join([p for p in searched if p])
                    + ". Hãy tải credentials.json từ Google Cloud Console và đặt vào thư mục config."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)
    return service


def find_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    """Tìm folder theo tên trong parent_id; nếu không có thì tạo mới.

    Lưu ý: Để đơn giản, nếu có nhiều folder trùng tên, hàm sẽ dùng folder đầu tiên.
    """
    # Escape single quotes in folder name for the Drive query
    safe_name = name.replace("'", "\\'")
    query_parts = [
        "mimeType='application/vnd.google-apps.folder'",
        f"name='{safe_name}'",
        "trashed = false",  # Chỉ lấy folder chưa bị xoá
    ]
    if parent_id:
        query_parts.append(f"'{parent_id}' in parents")
    else:
        query_parts.append("'root' in parents")

    query = " and ".join(query_parts)

    resp = service.files().list(q=query, spaces="drive", fields="files(id, name)", pageSize=1).execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]

    # Tạo folder mới
    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        file_metadata["parents"] = [parent_id]

    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder["id"]


def ensure_folder_tree(service, path_parts, root_folder_name: str = "VideoDownloaderRoot") -> str:
    """Đảm bảo tồn tại cây thư mục trên Drive theo path_parts.

    Ví dụ:
        path_parts = ["YouTube", "KenhA"]
        root_folder_name = "VideoDownloaderRoot"

    Trả về: ID của folder cuối cùng (KenhA).
    """
    # Tạo/tìm root riêng cho app để đỡ lẫn với các folder khác của user
    current_parent = find_or_create_folder(service, root_folder_name, parent_id=None)

    for part in path_parts:
        if not part:
            continue
        current_parent = find_or_create_folder(service, part, parent_id=current_parent)

    return current_parent


def upload_file_to_drive(local_path: str, folder_parts: list[str], subfolder: Optional[str] = None, status_callback=None) -> Optional[str]:
    """Upload file local_path lên Drive, theo cây thư mục folder_parts.

    - folder_parts: ví dụ ["YouTube", "KenhA"]
    - subfolder: ví dụ "Original" / "Parts" / "Assets" (optional)
    - Tự động tạo root "VideoDownloaderRoot" nếu chưa có.

    Trả về: file_id trên Drive (hoặc None nếu lỗi).
    """
    def log(msg):
        print(msg)
        if status_callback and callable(status_callback):
            status_callback(msg)

    if not os.path.exists(local_path):
        log(f"[ERROR] File not found: {local_path}")
        raise FileNotFoundError(local_path)

    log(f"[UPLOAD] Bắt đầu upload file: {local_path} lên Google Drive...")
    try:
        service = get_drive_service()
        log("[UPLOAD] Đã lấy service Google Drive.")

        parent_id = ensure_folder_tree(service, folder_parts)
        log(f"[UPLOAD] Đã đảm bảo cây thư mục: {folder_parts}, parent_id={parent_id}")
        if subfolder:
            parent_id = find_or_create_folder(service, subfolder, parent_id=parent_id)
            log(f"[UPLOAD] Đã tạo/tìm subfolder: {subfolder}, parent_id={parent_id}")

        file_metadata = {
            "name": os.path.basename(local_path),
            "parents": [parent_id],
        }

        media = MediaFileUpload(local_path, resumable=True)
        log(f"[UPLOAD] Đang upload file: {local_path}...")
        created = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        log(f"[UPLOAD] Upload thành công! File ID: {created.get('id')}")
        return created.get("id")
    except Exception as e:
        log(f"[ERROR] Upload lên Google Drive thất bại: {e}")
        return None

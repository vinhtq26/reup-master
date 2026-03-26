"""Google Drive uploader helper.

- Sử dụng OAuth2 (credentials.json) để tạo service Drive.
- Tự động lưu token vào token.json để lần sau dùng lại.
- Hỗ trợ tạo cây thư mục theo cấu trúc local (Platform/Channel/...)

YÊU CẦU:
- Đặt file credentials.json ở cùng thư mục project (hoặc chỉnh CREDENTIALS_FILE bên dưới).
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
BASE_DIR = os.path.dirname(__file__)
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def get_drive_service():
    """Tạo service Google Drive, tự xử lý refresh token / login lần đầu.

    Trả về: googleapiclient.discovery.Resource
    """
    creds: Optional[Credentials] = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Không tìm thấy {CREDENTIALS_FILE}. Hãy tải credentials.json từ Google Cloud Console và đặt cạnh project."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
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

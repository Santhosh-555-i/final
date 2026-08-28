import os
import re
import urllib.parse
import requests
from typing import List, Dict, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

class GoogleDriveHelper:
    """
    Unified Google Drive integration helper.
    Supports:
    1. Google Drive API v3 (via Service Account / API Key when credentials are provided).
    2. High-speed Direct Google CDN stream & folder downloader for public Drive links.
    """

    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.heic'}

    def __init__(self, service_account_json_path: Optional[str] = None, api_key: Optional[str] = None):
        self.service_account_path = service_account_json_path or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        self.api_key = api_key or os.getenv("GOOGLE_DRIVE_API_KEY", "")
        self.drive_service = None
        self._init_client()

    def _init_client(self):
        """Initializes Google Drive API v3 client if credentials exist"""
        if self.service_account_path and os.path.exists(self.service_account_path):
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                scopes = ['https://www.googleapis.com/auth/drive.readonly']
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_path, scopes=scopes
                )
                self.drive_service = build('drive', 'v3', credentials=creds)
                print("[Google Drive API] Initialized Drive API v3 client with Service Account.")
            except Exception as e:
                print(f"[Google Drive API Notice] Could not init official client ({e}). Fallback active.")

    @staticmethod
    def extract_id(url_or_id: str) -> Tuple[Optional[str], str]:
        """
        Parses a Drive link or ID and returns (id, type) where type is 'folder', 'file', or 'id'.
        """
        text = url_or_id.strip().strip("'\"`")
        if not text:
            return None, "invalid"

        # Check folder pattern (handles folders/1abc, olders/1abc, /folders/1abc, etc.)
        match_folder = re.search(r'(?:folders|olders)/([a-zA-Z0-9_-]{15,})', text)
        if match_folder:
            return match_folder.group(1), "folder"

        # Check file pattern
        match_file = re.search(r'/file/d/([a-zA-Z0-9_-]{15,})', text)
        if match_file:
            return match_file.group(1), "file"

        match_open = re.search(r'[?&]id=([a-zA-Z0-9_-]{15,})', text)
        if match_open:
            return match_open.group(1), "file"

        # Raw ID or partial URL containing 25+ char ID
        match_raw = re.search(r'([a-zA-Z0-9_-]{25,45})', text)
        if match_raw:
            return match_raw.group(1), "folder"

        return None, "invalid"

    def list_folder_files(self, folder_id: str) -> List[Dict[str, str]]:
        """
        Lists image files in a Google Drive folder using API v3 if available,
        or via public scraper.
        """
        # Method 1: Official API v3
        if self.drive_service:
            try:
                query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
                results = self.drive_service.files().list(
                    q=query,
                    pageSize=1000,
                    fields="files(id, name, mimeType, webViewLink, webContentLink)"
                ).execute()
                items = results.get('files', [])
                if items:
                    print(f"[Google Drive API v3] Found {len(items)} image files via Drive API v3.")
                    return items
            except Exception as e:
                print(f"[Google Drive API v3 Notice] Drive API list failed ({e}). Using public scraper.")

        # Method 2: Public scraper
        return self._scrape_folder_items(folder_id)

    def _scrape_folder_items(self, folder_id: str) -> List[Dict[str, str]]:
        """Scrapes file IDs from a public Google Drive folder HTML response"""
        target_url = f"https://drive.google.com/drive/folders/{folder_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        items: List[Dict[str, str]] = []
        try:
            resp = requests.get(target_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                html_text = resp.text
                candidate_ids = set()
                candidate_ids.update(re.findall(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]{25,})', html_text))
                candidate_ids.update(re.findall(r'data-id=[\"\']([a-zA-Z0-9_-]{25,})[\"\']', html_text))
                candidate_ids.update(re.findall(r'\[[\"\']([a-zA-Z0-9_-]{25,45})[\"\'],[\"\']image/', html_text))
                candidate_ids.update(re.findall(r'\[[\"\']([a-zA-Z0-9_-]{28,45})[\"\'],null', html_text))
                candidate_ids.discard(folder_id)

                for fid in candidate_ids:
                    if len(fid) >= 25 and not fid.startswith("AF_") and not fid.startswith("IZ"):
                        items.append({
                            "id": fid,
                            "name": f"drive_{fid[:8]}.jpg",
                            "mimeType": "image/jpeg"
                        })
        except Exception as e:
            print(f"[Google Drive Scraper Notice] {e}")

        return items

    def download_file_bytes(self, file_id: str) -> Optional[bytes]:
        """
        Downloads high-resolution file bytes using high-speed CDN direct endpoints or API v3.
        """
        if self.drive_service:
            try:
                from googleapiclient.http import MediaIoBaseDownload
                import io
                request = self.drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                return fh.getvalue()
            except Exception:
                pass

        # High-Speed Direct Google CDN Endpoints
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        direct_endpoints = [
            f"https://lh3.googleusercontent.com/d/{file_id}=w2560",
            f"https://drive.google.com/thumbnail?id={file_id}&sz=w2560",
            f"https://drive.google.com/uc?export=download&id={file_id}"
        ]

        for ep in direct_endpoints:
            try:
                r = requests.get(ep, headers=headers, timeout=8)
                if r.status_code == 200 and len(r.content) > 1500:
                    if not r.content.startswith(b"<!DOCTYPE") and not r.content.startswith(b"<html"):
                        return r.content
            except Exception:
                continue

        # Fallback to gdown
        try:
            import gdown
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp_path = tmp.name
            out = gdown.download(f"https://drive.google.com/uc?id={file_id}", tmp_path, quiet=True)
            if out and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1500:
                with open(tmp_path, "rb") as f:
                    data = f.read()
                os.remove(tmp_path)
                return data
        except Exception:
            pass

        return None

google_drive_helper = GoogleDriveHelper()

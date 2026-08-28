import os
import re
import requests
import gdown
from PIL import Image

def test_drive_helpers():
    print("Testing Google Drive helper logic...")
    from app.google_drive_api import google_drive_helper
    from app.drive_importer import drive_importer
    
    # Test URL parsing
    test_urls = [
        "https://drive.google.com/drive/folders/1ABC_XYZ123456789012345?usp=sharing",
        "https://drive.google.com/file/d/1FILE_ABC123456789012345/view",
        "https://drive.google.com/open?id=1OPEN_ABC123456789012345",
        "https://drive.google.com/drive/u/0/folders/1U0_ABC123456789012345"
    ]
    for u in test_urls:
        fid, ftype = google_drive_helper.extract_id(u)
        print(f"Extracted {u[:40]} -> ID: {fid}, Type: {ftype}")

if __name__ == "__main__":
    test_drive_helpers()

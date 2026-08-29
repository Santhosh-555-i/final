import sys
import os
import requests

def main():
    backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
    if len(sys.argv) > 1:
        backend_url = sys.argv[1]

    endpoint = f"{backend_url.rstrip('/')}/api/admin/backfill-embeddings"
    print(f"Triggering face embedding backfill at: {endpoint}...")
    try:
        resp = requests.post(endpoint, timeout=120)
        print(f"Status Code: {resp.status_code}")
        print("Response:")
        print(resp.json())
    except Exception as e:
        print(f"Error calling backfill endpoint: {e}")

if __name__ == "__main__":
    main()

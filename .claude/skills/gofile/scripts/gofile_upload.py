#!/usr/bin/env python3
"""
Gofile Uploader
Upload one or more files to gofile.io and print the share link(s).

Usage:
    python gofile_upload.py <file> [file2 ...]
    python gofile_upload.py --token ACCOUNT_TOKEN <file>   # upload into your account
    python gofile_upload.py --folder FOLDER_ID --token TKN <file>
    PROXY=http://user:pass@host:port python gofile_upload.py <file>

Notes:
    - With no --token, files upload to a fresh guest account. The guest
      token is printed so you can manage/group the uploads.
    - Output is JSON (one object per file) for easy machine parsing.
"""

import json
import os
import sys
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
HDRS = {"User-Agent": UA, "Accept": "*/*", "Origin": "https://gofile.io", "Referer": "https://gofile.io/"}
PROXY = os.environ.get("PROXY", "")
PROXIES = {"https": PROXY, "http": PROXY} if PROXY else None


def pick_server(proxies=None):
    """Ask gofile for an available upload server."""
    try:
        r = requests.get("https://api.gofile.io/servers", headers=HDRS, timeout=15, proxies=proxies).json()
        if r.get("status") == "ok":
            servers = r["data"]["servers"]
            if servers:
                return servers[0]["name"]
    except Exception:
        pass
    return "store1"  # sane fallback


def upload(path, token=None, folder=None, proxies=None):
    """Upload a single file. Returns gofile's data dict (downloadPage, code, etc.)."""
    if not os.path.isfile(path):
        return {"error": f"not a file: {path}"}

    px = proxies if proxies is not None else PROXIES
    server = pick_server(px)
    url = f"https://{server}.gofile.io/contents/uploadfile"

    headers = dict(HDRS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = {}
    if folder:
        data["folderId"] = folder

    with open(path, "rb") as fh:
        files = {"file": (os.path.basename(path), fh)}
        try:
            r = requests.post(url, headers=headers, files=files, data=data,
                              timeout=600, proxies=px).json()
        except Exception as e:
            return {"error": f"upload failed: {e}"}

    if r.get("status") != "ok":
        return {"error": r.get("status", "unknown"), "raw": r}

    d = r["data"]
    return {
        "status": "ok",
        "name": os.path.basename(path),
        "size": os.path.getsize(path),
        "downloadPage": d.get("downloadPage"),
        "code": d.get("code"),
        "fileId": d.get("id") or d.get("fileId"),
        "guestToken": d.get("guestToken"),
        "md5": d.get("md5"),
    }


def main():
    args = sys.argv[1:]
    token = None
    folder = None
    paths = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--token":
            token = args[i + 1]; i += 2
        elif a == "--folder":
            folder = args[i + 1]; i += 2
        else:
            paths.append(a); i += 1

    if not paths:
        print("Usage: python gofile_upload.py [--token TKN] [--folder ID] <file> [file2 ...]")
        sys.exit(1)

    token = token or os.environ.get("GOFILE_TOKEN")
    results = [upload(p, token=token, folder=folder) for p in paths]
    print(json.dumps(results, indent=2))
    if any("error" in r for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()

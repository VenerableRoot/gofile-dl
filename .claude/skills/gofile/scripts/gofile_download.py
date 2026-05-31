#!/usr/bin/env python3
"""
Gofile Downloader / Resolver

Resolve a gofile.io share link into direct download URLs, and optionally
download the file(s) to disk.

Usage:
    # Resolve only (print JSON of direct URLs + cookie):
    python gofile_download.py --resolve https://gofile.io/d/CODE

    # Download to a directory (default: current dir):
    python gofile_download.py https://gofile.io/d/CODE -o ./downloads

    # Reuse a known token instead of creating a guest account
    # (e.g. the guestToken returned by gofile_upload.py):
    python gofile_download.py --token TKN https://gofile.io/d/CODE

    PROXY=http://user:pass@host:port python gofile_download.py ...

Why the salt matters:
    gofile guards its contents API with X-Website-Token = SHA-256 of
    UA::lang::token::floor(epoch/14400)::SALT. SALT is a constant baked into
    gofile's obfuscated wt.obf.js. The JS hex-escapes its string literals, so
    the salt must be extracted AFTER decoding \\xNN escapes (a plain regex on
    the raw JS misses it and you get error-notPremium from a bad token).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
HDRS = {"User-Agent": UA, "Accept": "*/*", "Origin": "https://gofile.io",
        "Referer": "https://gofile.io/", "Accept-Language": "en-US,en;q=0.9"}
PROXY = os.environ.get("PROXY", "")
PROXIES = {"https": PROXY, "http": PROXY} if PROXY else None

FALLBACK_SALT = "g4f8fd9f12h14g"  # last-known-good salt (2026-05)


def get_salt(proxies=None):
    """Extract the website-token salt from gofile's obfuscated wt.obf.js.

    The literals are hex-escaped (\\xNN), so we decode first, then look for the
    salt assigned inside generateWT(). Falls back to the last-known value.
    """
    try:
        r = requests.get("https://gofile.io/dist/js/wt.obf.js", headers=HDRS,
                         timeout=15, proxies=proxies)
        js = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), r.text)
        idx = js.find("generateWT")
        window = js[idx:idx + 4000] if idx > -1 else js
        # salt is an alnum string (10-20 chars) with both letters and digits
        for m in re.findall(r"['\"]([a-z0-9]{10,20})['\"]", window):
            if any(c.isdigit() for c in m) and any(c.isalpha() for c in m):
                return m
    except Exception:
        pass
    return FALLBACK_SALT


def generate_wt(token, salt):
    ts = str(int(time.time()) // 14400)
    data = f"{UA}::en-US::{token}::{ts}::{salt}"
    return hashlib.sha256(data.encode()).hexdigest()


def _post_account(px, retries=4):
    for i in range(retries):
        r = requests.post("https://api.gofile.io/accounts", headers=HDRS,
                          timeout=15, proxies=px).json()
        if r.get("status") == "ok":
            return r["data"]["token"]
        if r.get("status") == "error-rateLimit" and i < retries - 1:
            time.sleep(15)
            continue
        raise RuntimeError(f"account: {r.get('status')}")
    raise RuntimeError("account: rate limited")


def extract_code(url):
    if "/d/" in url:
        return url.split("/d/")[1].strip("/ ")
    return url.strip()


def resolve(code, token=None, proxy=None):
    """Resolve a gofile code into a list of {name,size,url,cookie} dicts."""
    px = {"https": proxy, "http": proxy} if proxy else PROXIES
    salt = get_salt(px)
    if not token:
        token = _post_account(px)

    wt = generate_wt(token, salt)
    requests.get("https://api.gofile.io/accounts/website",
                 headers={**HDRS, "Authorization": f"Bearer {token}"},
                 timeout=15, proxies=px)

    r2 = requests.get(
        f"https://api.gofile.io/contents/{code}",
        headers={**HDRS, "Authorization": f"Bearer {token}",
                 "X-Website-Token": wt, "X-BL": "en-US"},
        params={"page": 1, "pageSize": 1000, "sortField": "name", "sortDirection": 1},
        timeout=15, proxies=px,
    ).json()

    if r2.get("status") != "ok":
        return {"error": r2.get("status"), "code": code}

    files = []
    for fid, f in r2["data"]["children"].items():
        if f.get("type") != "file":
            continue
        url = f.get("link") or (
            f"https://{f['serverSelected']}.gofile.io/download/web/{f['id']}/"
            + requests.utils.quote(f["name"]))
        files.append({"name": f["name"], "size": f["size"], "url": url,
                      "cookie": f"accountToken={token}"})
    return {"status": "ok", "code": code, "token": token, "files": files}


def download_file(f, out_dir, proxies=None):
    """Stream a resolved file dict to disk. Returns the output path."""
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f["name"])
    headers = {**HDRS, "Cookie": f["cookie"]}
    with requests.get(f["url"], headers=headers, stream=True, timeout=600,
                      proxies=proxies) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if chunk:
                    fh.write(chunk)
    return dest


def main():
    ap = argparse.ArgumentParser(description="Resolve / download gofile.io links")
    ap.add_argument("link", help="gofile share URL or bare code")
    ap.add_argument("-o", "--out", default=".", help="output directory")
    ap.add_argument("--token", help="reuse an existing account/guest token")
    ap.add_argument("--resolve", action="store_true",
                    help="only print direct URLs as JSON; do not download")
    args = ap.parse_args()

    code = extract_code(args.link)
    res = resolve(code, token=args.token)
    if "error" in res:
        print(json.dumps(res))
        sys.exit(1)

    if args.resolve:
        print(json.dumps(res, indent=2))
        return

    for f in res["files"]:
        path = download_file(f, args.out, proxies=PROXIES)
        size = os.path.getsize(path)
        print(f"saved {path} ({size} bytes)")


if __name__ == "__main__":
    main()

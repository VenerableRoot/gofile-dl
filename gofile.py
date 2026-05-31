#!/usr/bin/env python3
"""
Gofile Direct Link Resolver
Resolve gofile.io share links into direct download URLs.

Usage:
    python gofile.py https://gofile.io/d/dP2rRR
    python gofile.py dP2rRR
    PROXY=http://user:pass@host:port python gofile.py dP2rRR

As module:
    from gofile import resolve
    result = resolve("dP2rRR")
    for f in result["files"]:
        print(f["url"], f["cookie"])
"""

import hashlib, os, re, sys, time, requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
HDRS = {"User-Agent": UA, "Accept": "*/*", "Origin": "https://gofile.io", "Referer": "https://gofile.io/", "Accept-Language": "en-US,en;q=0.9"}
PROXY = os.environ.get("PROXY", "")
PROXIES = {"https": PROXY, "http": PROXY} if PROXY else None


def get_salt():
    """Fetch the website token salt from gofile's obfuscated JS.

    gofile hex-escapes the string literals in wt.obf.js, so we decode the
    \\xNN escapes first; otherwise the salt never matches a plain [a-z0-9]
    regex and you end up with a bad token (error-notPremium).
    """
    try:
        r = requests.get("https://gofile.io/dist/js/wt.obf.js", headers=HDRS, timeout=15, proxies=PROXIES)
        js = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), r.text)
        idx = js.find("generateWT")
        window = js[idx:idx+4000] if idx > -1 else js
        for m in re.findall(r"['\"]([a-z0-9]{10,20})['\"]", window):
            if any(c.isdigit() for c in m) and any(c.isalpha() for c in m):
                return m
    except Exception:
        pass
    return "g4f8fd9f12h14g"


def generate_wt(token, salt):
    """Generate X-Website-Token header value."""
    ts = str(int(time.time()) // 14400)
    data = f"{UA}::en-US::{token}::{ts}::{salt}"
    return hashlib.sha256(data.encode()).hexdigest()


def resolve(code, proxy=None):
    """
    Resolve a gofile code to direct download URLs.
    
    Args:
        code: Gofile content code (e.g., "dP2rRR")
        proxy: Optional proxy URL (overrides PROXY env var)
    
    Returns:
        dict with "status", "code", "files" (or "error")
    """
    px = {"https": proxy, "http": proxy} if proxy else PROXIES
    salt = get_salt()

    # Create guest account
    r = requests.post("https://api.gofile.io/accounts", headers=HDRS, timeout=15, proxies=px).json()
    if r["status"] != "ok":
        return {"error": f"account: {r['status']}"}
    token = r["data"]["token"]

    wt = generate_wt(token, salt)

    # Register session
    requests.get("https://api.gofile.io/accounts/website",
                 headers={**HDRS, "Authorization": f"Bearer {token}"}, timeout=15, proxies=px)

    # Get contents
    r2 = requests.get(
        f"https://api.gofile.io/contents/{code}",
        headers={**HDRS, "Authorization": f"Bearer {token}", "X-Website-Token": wt, "X-BL": "en-US"},
        params={"contentFilter": "", "page": 1, "pageSize": 1000, "sortField": "name", "sortDirection": 1},
        timeout=15, proxies=px
    ).json()

    if r2["status"] != "ok":
        return {"error": r2["status"]}

    files = []
    for fid, f in r2["data"]["children"].items():
        if f["type"] != "file":
            continue
        url = f.get("link") or f"https://{f['serverSelected']}.gofile.io/download/web/{f['id']}/{requests.utils.quote(f['name'])}"
        files.append({
            "name": f["name"],
            "size": f["size"],
            "url": url,
            "cookie": f"accountToken={token}"
        })

    return {"status": "ok", "code": code, "files": files}


def extract_code(url):
    """Extract gofile code from URL or return as-is."""
    if "/d/" in url:
        return url.split("/d/")[1].strip("/ ")
    return url.strip()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <gofile-url-or-code>")
        print(f"       PROXY=http://user:pass@host:port python {sys.argv[0]} <url>")
        sys.exit(1)

    code = extract_code(sys.argv[1])
    result = resolve(code)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    for f in result["files"]:
        size_mb = f["size"] / 1024 / 1024
        print(f"\n{f['name']} ({size_mb:.1f} MB)")
        print(f"  URL: {f['url']}")
        print(f"  Cookie: {f['cookie']}")

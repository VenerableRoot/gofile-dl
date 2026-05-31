---
name: gofile
description: Upload files to gofile.io and download/resolve gofile.io share links. Use when the user wants to upload a file to gofile, share a file via gofile, get a gofile link, or download/resolve a gofile.io/d/CODE share link to disk or to a direct URL.
---

# Gofile Upload & Download

Helper scripts for transferring files via [gofile.io](https://gofile.io) without
a browser or premium account. Two scripts live in `scripts/`:

- `gofile_upload.py` — upload local file(s) → share link
- `gofile_download.py` — resolve a share link to direct URL(s) and/or download to disk

Both need only Python 3 + `requests` (`pip install requests`).

## Upload a file

```bash
python scripts/gofile_upload.py <file> [more_files ...]
```

Prints one JSON object per file, e.g.:

```json
[{ "status": "ok", "name": "clip.mp4", "size": 12345,
   "downloadPage": "https://gofile.io/d/AbC123",
   "fileId": "….", "guestToken": "…" }]
```

- `downloadPage` is the shareable link — give this to the user.
- `guestToken` is the throwaway account the file landed in. Pass it back as
  `--token` to `gofile_download.py` to fetch the file without making a new
  account (handy, and dodges the guest-account rate limit).
- To upload into a real account: `--token <ACCOUNT_TOKEN>` (or set
  `GOFILE_TOKEN`), optionally `--folder <FOLDER_ID>`.

## Download / resolve a link

```bash
# Download the file(s) to a directory:
python scripts/gofile_download.py https://gofile.io/d/CODE -o ./downloads

# Just get the direct URL(s) + cookie as JSON, don't download:
python scripts/gofile_download.py --resolve https://gofile.io/d/CODE

# Reuse a token (e.g. the guestToken from an upload):
python scripts/gofile_download.py --token <TKN> https://gofile.io/d/CODE
```

A resolved file gives `{name, size, url, cookie}`. To download a `url` manually
you MUST send the cookie and a gofile referer:

```bash
curl -L -o out.bin -H "Cookie: <cookie>" -H "Referer: https://gofile.io/" "<url>"
```

## How it works (and the gotcha)

gofile guards its contents API with a header
`X-Website-Token = SHA-256(UA :: lang :: token :: floor(epoch/14400) :: SALT)`.

`SALT` is a constant baked into gofile's obfuscated `wt.obf.js`. **The JS
hex-escapes its string literals**, so the salt must be extracted *after*
decoding `\xNN` escapes — a naive regex over the raw JS misses it and you get
`error-notPremium` from the resulting bad token. `gofile_download.py` decodes
first and falls back to a last-known-good salt (`g4f8fd9f12h14g`) if extraction
fails.

## Rate limits & errors

- `error-rateLimit` — gofile throttles guest-account creation and the contents
  API per IP. The scripts retry account creation with backoff; if you keep
  hitting it, wait a few minutes, reuse an existing `--token`, or set a `PROXY`.
- `error-notPremium` — almost always a stale/wrong salt → bad website-token.
- `PROXY=http://user:pass@host:port` is honored by both scripts.

## Proxy

Set the `PROXY` env var for either script to route through a proxy (useful for
restricted networks or to sidestep IP rate limits).

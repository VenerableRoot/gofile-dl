<div align="center">

<img src="https://raw.githubusercontent.com/VenerableRoot/gofile-dl/main/.github/banner.png" alt="gofile-dl" width="600"/>

<br/>
<br/>

[![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?style=for-the-badge&logo=go&logoColor=white)](https://go.dev)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/VenerableRoot/gofile-dl?style=for-the-badge&color=yellow)](https://github.com/VenerableRoot/gofile-dl/stargazers)

**Resolve Gofile share links into direct download URLs — no browser, no premium, no bullshit.**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [How It Works](#-how-it-works) • [API](#-api)

</div>

---

## ⚡ Features

- 🔗 **Direct Links** — Convert any `gofile.io/d/CODE` into a direct download URL
- 🔑 **No Premium Required** — Works with free guest accounts
- 🔄 **Fresh Tokens** — Generates new auth token for every request
- 🐍 **Python + Go** — Use as CLI, module, or HTTP API server
- 🌐 **Proxy Support** — Built-in proxy support for restricted networks
- 🧠 **Smart Salt** — Auto-fetches website token salt (survives rotations)

## 📦 Installation

### Go (CLI + HTTP Server)

```bash
go install github.com/VenerableRoot/gofile-dl@latest
```

Or download from [Releases](https://github.com/VenerableRoot/gofile-dl/releases).

### Python

```bash
pip install requests
curl -O https://raw.githubusercontent.com/VenerableRoot/gofile-dl/main/gofile.py
```

## 🚀 Usage

### CLI Mode

```bash
# Go
gofile-dl https://gofile.io/d/dP2rRR

# Python
python gofile.py https://gofile.io/d/dP2rRR
```

**Output:**
```
Avatar Aang The Last Airbender.mp4 (3248.5 MB)
  URL: https://file-eu-par-1.gofile.io/download/web/2c82ae9d-.../Avatar%20Aang%20The%20Last%20Airbender.mp4
  Cookie: accountToken=abc123xyz
```

### Download with curl

```bash
curl -L -o "movie.mp4" \
  -H "Cookie: accountToken=TOKEN_FROM_OUTPUT" \
  -H "Referer: https://gofile.io/" \
  "DIRECT_URL_FROM_OUTPUT"
```

### Python Module

```python
from gofile import resolve

result = resolve("dP2rRR")
for f in result["files"]:
    print(f["name"], f["url"], f["cookie"])
```

### HTTP API Server (Go)

```bash
gofile-dl serve
# → Listening on :8899

# GET http://localhost:8899/?url=https://gofile.io/d/CODE
# GET http://localhost:8899/CODE
```

**Response:**
```json
{
  "status": "ok",
  "code": "dP2rRR",
  "files": [
    {
      "name": "Avatar Aang The Last Airbender.mp4",
      "size": 3406311653,
      "url": "https://file-eu-par-1.gofile.io/download/web/...",
      "cookie": "accountToken=abc123"
    }
  ]
}
```

## 🔧 How It Works

Gofile protects its content API with a **website token** (`X-Website-Token`) generated client-side. This tool reverse-engineers the token generation:

```
X-Website-Token = SHA-256(
    UserAgent + "::" +
    Language  + "::" +
    AccountToken + "::" +
    floor(epoch_seconds / 14400) + "::" +
    Salt
)
```

<details>
<summary><b>Full Flow</b></summary>

1. **Create Guest Account** → `POST api.gofile.io/accounts` → token
2. **Fetch Salt** → `GET gofile.io/dist/js/wt.obf.js` → extract salt via regex
3. **Generate WT** → SHA-256 hash of concatenated values
4. **Register Session** → `GET api.gofile.io/accounts/website`
5. **Get Contents** → `GET api.gofile.io/contents/{code}` with `Authorization`, `X-Website-Token`, `X-BL` headers
6. **Extract URLs** → Direct download URLs from response + `accountToken` cookie

</details>

## 🌐 Proxy Support

```bash
# Environment variable
PROXY=http://user:pass@host:port python gofile.py https://gofile.io/d/CODE

# Or disable proxy (for residential IPs)
PROXY="" python gofile.py https://gofile.io/d/CODE
```

## 🤖 Claude Skill

A [Claude Code](https://claude.com/claude-code) skill is bundled under
[`.claude/skills/gofile`](.claude/skills/gofile). Clone the repo into a project
(or copy that folder into `~/.claude/skills/`) and Claude can upload and
download gofile links on request — e.g. *"upload report.pdf to gofile"* or
*"download this gofile link"*. It ships two standalone scripts:

```bash
# Upload → share link
python .claude/skills/gofile/scripts/gofile_upload.py <file>

# Resolve / download a link
python .claude/skills/gofile/scripts/gofile_download.py https://gofile.io/d/CODE -o ./downloads
```

## 📄 License

MIT — do whatever you want.

---

<div align="center">
<sub>Built by reverse engineering gofile's <code>wt.obf.js</code> 🔬</sub>
</div>

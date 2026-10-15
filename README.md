<p align="center">
  <a href="https://github.com/Zayrix-bit/AnimePahe-API">
    <img src="./assets/animepahe-logo.svg" alt="AnimePahe Logo" width="340">
  </a>
</p>

<h1 align="center">⚡ AnimePahe High-Performance Stream Resolver & Web Lab</h1>

<p align="center">
  <img src="https://img.shields.io/badge/ANIMEPAHE-OFFICIAL%20ENGINE-d5015b?style=for-the-badge" alt="AnimePahe Engine">
  <img src="https://img.shields.io/badge/PYTHON-3.10%2B%20%7C%203.12-4c1?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/FASTAPI-FRAMEWORK-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/UVICORN-ASGI%20SERVER-499848?style=for-the-badge&logo=gunicorn&logoColor=white" alt="Uvicorn">
  <img src="https://img.shields.io/badge/PLAYWRIGHT-CHROMIUM-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/CURL__CFFI-CHROME%20124%20TLS-00599C?style=for-the-badge&logo=curl&logoColor=white" alt="curl-cffi">
  <img src="https://img.shields.io/badge/ARTPLAYER-5.1%20HTML5-8B5CF6?style=for-the-badge&logo=html5&logoColor=white" alt="ArtPlayer">
  <img src="https://img.shields.io/badge/HLS.JS-STREAMING%20CORE-FF6B6B?style=for-the-badge&logo=javascript&logoColor=white" alt="Hls.js">
  <img src="https://img.shields.io/badge/CLOUDFLARE-TURNSTILE%20BYPASS-F38020?style=for-the-badge&logo=cloudflare&logoColor=white" alt="Cloudflare Bypass">
  <img src="https://img.shields.io/badge/BANDWIDTH-0%20MB%20DIRECT%20CDN-10B981?style=for-the-badge&logo=speedtest&logoColor=white" alt="Zero Bandwidth">
  <img src="https://img.shields.io/badge/LICENSE-MIT-black?style=for-the-badge" alt="MIT License">
</p>

> **A production-ready, ultra-fast scraping engine, reverse proxy gateway, and modern HTML5 streaming test lab for [AnimePahe](https://animepahe.pw/).**  
> Resolves anime catalogs, paginated episodes, sub/dub options, direct AES-128 encrypted HLS master streams (`.m3u8`), and individual CDN video chunks (`.jpg` MPEG-TS segments) with **zero-delay fast-path unpacking** and **zero external bandwidth consumption**.

---

## 📑 Table of Contents
1. [Architecture & System Design](#-architecture--system-design)
2. [Why This Exists & Core Technical Challenges Solved](#-why-this-exists--core-technical-challenges-solved)
   - [Cloudflare Turnstile Bot Defense](#1-cloudflare-turnstile-bot-defense)
   - [Kwik.cx Iframe Embedding Block (`X-Frame-Options: SAMEORIGIN`)](#2-kwikcx-iframe-embedding-block-x-frame-options-sameorigin)
   - [Upstream CDN Header Constraint & CORS Policy](#3-upstream-cdn-header-constraint--cors-policy)
   - [Image Cross-Origin Resource Policy (`NotSameOrigin`)](#4-image-cross-origin-resource-policy-notsameorigin)
   - [15x Speedup: Fast-Path Packer Unpacker vs Playwright](#5-15x-speedup-fast-path-packer-unpacker-vs-playwright)
3. [Reverse Proxy vs Direct CDN: The VPS Bandwidth Dilemma](#-reverse-proxy-vs-direct-cdn-the-vps-bandwidth-dilemma)
4. [Project Structure & File Breakdown](#-project-structure--file-breakdown)
5. [API Documentation & Endpoints](#-api-documentation--endpoints)
6. [Frontend UI & Web Player Lab](#-frontend-ui--web-player-lab)
7. [Installation & Setup](#-installation--setup)
8. [Usage Guide](#-usage-guide)
   - [1. Running the FastAPI Server & Web Lab](#1-running-the-fastapi-server--web-lab)
   - [2. Interactive CLI Tool](#2-interactive-cli-tool)
   - [3. Python Library Integration](#3-python-library-integration)
9. [Context for AI Models / Future Pair Programmers](#-context-for-ai-models--future-pair-programmers)

---

## 🏛 Architecture & System Design

```
+--------------------------------------------------------------------------------------------------+
|                                    USER BROWSER / CLIENT                                         |
|                                                                                                  |
|   +--------------------+       +--------------------+       +--------------------------------+   |
|   | Search Catalog Grid|       | Episode Selector   |       | Modern ArtPlayer (HLS Engine)  |   |
|   +---------+----------+       +---------+----------+       +---------------+----------------+   |
+-------------|----------------------------|----------------------------------|--------------------+
              |                            |                                  |
              | REST JSON API              | REST JSON API                    | HLS Stream Requests
              v                            v                                  v
+--------------------------------------------------------------------------------------------------+
|                              LOCAL FASTAPI SERVER (127.0.0.1:8000)                               |
|                                                                                                  |
|  +--------------------------------------------------------------------------------------------+  |
|  | Multi-Tier In-Memory Cache (_SEARCH_CACHE, _EPISODES_CACHE, _STREAMS_CACHE, _RESOLVE_CACHE) |  |
|  +--------------------------------------------------------------------------------------------+  |
|                                                                                                  |
|  +---------------------------------------+      +---------------------------------------------+  |
|  |     AsyncAnimePaheScraper (Engine)    |      |      Stream Gateway Proxy (Zero VPS Cost)   |  |
|  |                                       |      |                                             |  |
|  |  [Fast Path]                          |      |  GET /stream/m3u8 -> Rewrites Key & Segments|  |
|  |   unpack_kwik_embed()                 |      |  GET /stream/key  -> Injects Referer: Kwik  |  |
|  |   Reverse-engineers JS Packer in 0.5s |      |  GET /stream/segment -> Proxies TS Chunks   |  |
|  |                                       |      |  GET /stream/image -> Proxies Posters/Snaps |  |
|  |  [Fallback Path]                      |      +---------------------------------------------+  |
|  |   Playwright Headless Chromium        |                             |                         |
|  |   (asyncio.Lock for thread safety)    |                             |                         |
|  +---------------------------------------+                             |                         |
+----------------------|-------------------------------------------------|-------------------------+
                       |                                                 |
                       v                                                 v
    +--------------------------------------+         +---------------------------------------+
    |   AnimePahe Server (animepahe.pw)    |         |   Upstream CDN (vault-*.uwucdn.top)   |
    |   - Catalog API                      |         |   - uwu.m3u8 (Master HLS playlist)    |
    |   - Cloudflare Clearance Profile     |         |   - mon.key  (AES-128 Encryption Key) |
    |   - Kwik Embed Player (kwik.cx)      |         |   - segment-*.jpg (MPEG-TS video)     |
    +--------------------------------------+         +---------------------------------------+
```

---

## 🔍 Why This Exists & Core Technical Challenges Solved

Scraping and playing anime streams from AnimePahe is notoriously tricky due to multiple layers of bot protection, browser cross-origin constraints, and encrypted CDN architecture. Below is the technical breakdown of how this codebase solves every layer:

### 1. Cloudflare Turnstile Bot Defense
- **The Problem**: AnimePahe protects its catalog and play pages with Cloudflare Turnstile challenges. Standard `requests` or `httpx` calls receive HTTP 403 / Cloudflare challenge interstitials.
- **The Solution**: 
  - `AsyncAnimePaheScraper` launches Chromium using `launch_persistent_context` stored in `c:\Users\Ritesh\Downloads\scrap\.browser_profile`.
  - Arguments include `--disable-blink-features=AutomationControlled` to eliminate the `navigator.webdriver` bot flag.
  - Clearance cookies (`cf_clearance`, `__cf_bm`) persist across runs, allowing seamless access.

### 2. Kwik.cx Iframe Embedding Block (`X-Frame-Options: SAMEORIGIN`)
- **The Problem**: AnimePahe’s video embed links point to `https://kwik.cx/e/{hash}`. If a web developer tries to embed this inside an `<iframe>` on their own web app (`http://127.0.0.1:8000`), Chrome/Edge blocks it with:
  ```
  Refused to display 'https://kwik.cx/' in a frame because it set 'X-Frame-Options' to 'sameorigin'.
  ```
- **The Solution**: We bypass the Kwik embed iframe completely! Instead of rendering their iframe, we extract the underlying encrypted master `.m3u8` playlist and render it inside a native **ArtPlayer (HLS)** instance.

### 3. Upstream CDN Header Constraint & CORS Policy
- **The Problem**: The actual video stream lives on high-speed CDNs like `https://vault-10.uwucdn.top/stream/.../uwu.m3u8`.
  - The CDN strictly inspects the HTTP request headers: it **requires** `Referer: https://kwik.cx/` and `Origin: https://kwik.cx`.
  - If a browser makes a direct `fetch` or `XHR` to the CDN from `http://127.0.0.1:8000`, the browser sends its own origin (`http://127.0.0.1:8000`).
  - Because W3C browser security rules prohibit JavaScript from altering unsafe headers (`Refused to set unsafe header "Referer"`), the CDN rejects the request with **HTTP 403 Forbidden** and omits CORS headers, causing the browser to throw:
    ```
    Access to XMLHttpRequest at 'https://vault-10.uwucdn.top/...' has been blocked by CORS policy.
    ```
- **The Solution (Local Loopback Stream Gateway)**:
  - `server.py` implements `/stream/m3u8`, `/stream/key`, and `/stream/segment`.
  - When Hls.js asks for `/stream/m3u8?url=...`, Python's `curl_cffi` (mimicking Chrome 124 TLS fingerprints) fetches the upstream playlist with `Referer: https://kwik.cx/`.
  - It rewrites every AES-128 key line (`#EXT-X-KEY:URI=...`) to route through `/stream/key?url=...` using full `urljoin`.
  - It rewrites every video chunk (`segment-*.jpg`) to route through `/stream/segment?url=...`.
  - It appends `Access-Control-Allow-Origin: *` headers.
  - **Zero Bandwidth**: Since this gateway runs on `127.0.0.1` (localhost loopback), video packets flow locally from computer to player without leaving the machine or incurring hosting bandwidth bills!

### 4. Image Cross-Origin Resource Policy (`NotSameOrigin`)
- **The Problem**: Anime posters and snapshot thumbnails from `https://i.animepahe.pw/` set `Cross-Origin-Resource-Policy: same-origin` (CORP). Browsers block them from rendering on third-party sites with `net::ERR_BLOCKED_BY_RESPONSE.NotSameOrigin`.
- **The Solution**:
  - `index.html` includes `<meta name="referrer" content="no-referrer">`.
  - `server.py` provides `/stream/image?url=...` with an in-memory image cache (`_IMAGE_CACHE`) and SVG fallback, eliminating broken image icons.

### 5. 15x Speedup: Fast-Path Packer Unpacker vs Playwright
- **The Problem**: In conventional scrapers, resolving an m3u8 stream requires Playwright to:
  1. Open the play URL (3–5s).
  2. Wait for Cloudflare/DOM (3s).
  3. Click `.click-to-load` button (1s).
  4. Poll network traffic until an `.m3u8` request is intercepted (2–5s).
  - **Total delay**: 10 to 15 seconds per episode!
- **The Solution (`unpack_kwik_embed`)**:
  - Inside `kwik.cx/e/{hash}`, the stream URL is packed inside Dean Edwards' JavaScript Packer: `eval(function(p,a,c,k,e,d){...})`.
  - We wrote a native Python regex + Base-N unpacker in `animepahe.py`.
  - When an episode is selected, `curl_cffi` fetches the Kwik embed page in **0.4s**, the unpacker decodes the tokens in **0.02s**, and extracts `https://vault-*.uwucdn.top/.../uwu.m3u8` instantly.
  - **Result**: Stream resolution drops from **15 seconds down to ~1.1 seconds**! If fast-path ever encounters a strange embed, it seamlessly falls back to Playwright headless clicking.

### 6. Cloudflare & Kwik Rate Limit Bypass (HTTP 429 & Anti-Bot Defense)
- **The Problem**: 
  - AnimePahe and Kwik enforce Cloudflare Bot Fight Mode and strict IP rate limiting. Tools that hammer endpoints sequentially or concurrently get slapped with `HTTP 429 Too Many Requests` or Turnstile challenge interstitials.
  - Standard HTTP requests lack valid clearance tokens (`cf_clearance`), causing Cloudflare to classify them as suspicious unverified bots.
- **The Solution**:
  1. **Cloudflare Session Cookie Synchronization**:
     - `get_cf_cookies()` extracts live `cf_clearance` and `__cf_bm` cookies from the verified Playwright persistent context and injects them into high-speed `curl_cffi` requests.
  2. **Adaptive Exponential Backoff & Jitter**:
     - When an upstream `429 Too Many Requests` is detected, the engine inspects the `Retry-After` header. If absent, it applies exponential backoff (`delay = 1.5 * 2^attempt + random_jitter`) and retries automatically up to 4 times.
  3. **Human Cadence & Jitter Pacing**:
     - Prevents mechanical burst patterns by introducing organic micro-delays between consecutive calls, keeping requests safely under Cloudflare's sliding-window thresholds.
  4. **Dynamic Proxy Routing**:
     - Supports optional HTTP/SOCKS5 proxy rotation via constructor parameters or `ANIMEPAHE_PROXY` environment variable for massive scraping workloads.
  5. **Resilient Browser Failover**:
     - If direct fast-path requests ever hit a hard Turnstile challenge, the engine automatically fails over to the Playwright browser context, where Turnstile auto-clears.

---

## ⚖ Reverse Proxy vs Direct CDN: The VPS Bandwidth Dilemma

If you or your team plan to deploy this scraper onto a public cloud server (VPS / Droplet), you must understand the distinction between **Proxying Video** vs **Direct CDN Streaming**:

| Architecture | How It Works | Browser Web App | Server Bandwidth | Hosting Cost |
| :--- | :--- | :---: | :---: | :---: |
| **Reverse Proxy (Current Web Mode)** | User $\to$ VPS $\to$ AnimePahe CDN | ✅ Works 100% (CORS & Referer bypassed) | ❌ **Heavy** (~350 MB per episode per user) | ❌ High (Bandwidth limits apply) |
| **Direct CDN (Native App Mode)** | User $\to$ AnimePahe CDN directly | ❌ Blocked by browser CORS/Referer |  **0 MB** (Server only sends 2KB JSON) |  **Free / Dirt Cheap** ($5 VPS can serve 100k users) |

### How Production Apps Achieve 0 MB Server Bandwidth:
1. **Mobile / Desktop Apps (Android, iOS, Electron, React Native, Flutter)**:
   - Native HTTP clients (e.g. OkHttp in Android, Axios in Node) are **not restricted by browser CORS or unsafe header bans**.
   - The app's video player can directly set `Referer: https://kwik.cx/` on ExoPlayer / IJKPlayer / AVPlayer!
   - Your backend server only serves the JSON API (`/api/resolve`), consuming **0 MB video bandwidth**.
2. **Serverless Cloudflare Workers**:
   - Instead of running video traffic through your VPS, a lightweight Cloudflare Worker intercepts the stream request, injects `Referer: https://kwik.cx/`, and forwards the stream directly to the user (utilizing Cloudflare's global edge network).
3. **External Media Players (VLC / MPV)**:
   - Users can stream directly without a proxy using CLI arguments:
     ```bash
     vlc "https://vault-10.uwucdn.top/.../uwu.m3u8" :http-referrer="https://kwik.cx/"
     ```

---

## 📁 Project Structure & File Breakdown

```
c:\Users\Ritesh\Downloads\scrap\
├── .browser_profile/          # Chromium user data directory (stores Cloudflare clearance cookies)
├── animepahe.py               # Core scraping engine (Sync AnimePaheScraper + AsyncAnimePaheScraper + unpacker)
├── server.py                  # FastAPI server, REST API endpoints, memory caches, & stream reverse proxy
├── cli.py                     # Interactive terminal CLI tool for search, episodes, and stream resolution
├── test_scrape.py             # Unit test script verifying search and stream options extraction
├── static/                    # Modern frontend UI
│   ├── index.html             # Single-page interface (Search hero, episode grid, ArtPlayer stage, inspector)
│   ├── style.css              # Glassmorphic dark UI, CSS variables, glowing badges, 16:9 responsive viewport
│   └── app.js                 # Frontend state manager, ArtPlayer lifecycle, Hls.js driver, quality switching
└── README.md                  # Comprehensive technical documentation & AI reference guide
```

### Deep Dive into Key Files:
- **`animepahe.py`**:
  - `unpack_kwik_embed(embed_url)`: High-speed base-N packer decoder that extracts m3u8 in ~0.5s.
  - `AsyncAnimePaheScraper`: Built on native `playwright.async_api`. Uses `self._lock = asyncio.Lock()` to serialize all browser page navigations and prevent page collision errors.
  - `AnimePaheScraper`: Synchronous wrapper for scripts and interactive CLI usage.
- **`server.py`**:
  - `_SEARCH_CACHE`, `_EPISODES_CACHE`, `_STREAMS_CACHE`, `_RESOLVE_CACHE`: RAM-based dictionaries delivering sub-5ms responses for cached queries.
  - `/stream/m3u8`: Fetches playlist, rewrites `#EXT-X-KEY` and `.jpg` chunk URLs to local endpoints.
  - `/stream/key`: Proxies AES-128 16-byte key with required Kwik headers.
  - `/stream/segment`: Relays MPEG-TS video chunks with caching headers.
  - `/stream/image`: Proxies thumbnails with Referer injection to bypass CORP.
- **`static/app.js`**:
  - Manages player mode switching (`artplayer`, `inspector`, `kwik`).
  - Safely destroys existing `Artplayer` and `Hls` instances before creating a clean wrapper element (`playerHolder`), preventing DOM collision crashes.
  - Forwards `stream.embed_url` to `/api/resolve` for instant fast-path playback.

---

## 🚀 API Documentation & Endpoints

Base URL: `http://127.0.0.1:8000`  
Interactive Swagger Docs: `http://127.0.0.1:8000/docs`

### 1. Search Anime
- **Endpoint**: `GET /api/search?q={query}`
- **Response**:
```json
{
  "status": "success",
  "query": "Solo Leveling",
  "total_results": 1,
  "results": [
    {
      "id": 5521,
      "title": "Ore dake Level Up na Ken",
      "type": "TV",
      "season": "Winter 2024",
      "year": 2024,
      "total_episodes": 12,
      "status": "Finished Airing",
      "score": 8.35,
      "poster_image": "https://i.animepahe.pw/uploads/posters/...",
      "anime_session": "32976d37-cf46-009e-e76b-332763f419ab",
      "episodes_api": "/api/episodes?session=32976d37-cf46-009e-e76b-332763f419ab&page=1"
    }
  ]
}
```

### 2. Get Episodes
- **Endpoint**: `GET /api/episodes?session={anime_session}&page=1`
- **Response**:
```json
{
  "status": "success",
  "anime_session": "32976d37-cf46-009e-e76b-332763f419ab",
  "total_episodes": 12,
  "current_page": 1,
  "last_page": 1,
  "per_page": 30,
  "episodes": [
    {
      "episode_number": 1,
      "duration": "00:23:40",
      "snapshot_url": "https://i.animepahe.pw/uploads/snapshots/...",
      "episode_session": "206af4f65e4505e216a9442267791c1b4ed83f109b59b8c46c55e8b5ce5ba128",
      "audio": "jpn",
      "disc": "",
      "filler": false,
      "created_at": "2024-01-06 17:30:00",
      "streams_api": "/api/streams?anime_session=...&episode_session=..."
    }
  ]
}
```

### 3. Get Stream Qualities & Download Options
- **Endpoint**: `GET /api/streams?anime_session={anime_session}&episode_session={episode_session}`
- **Response**:
```json
{
  "status": "success",
  "anime_session": "32976d37-cf46-009e-e76b-332763f419ab",
  "episode_session": "206af4f65e4505e216a9442267791c1b4ed83f109b59b8c46c55e8b5ce5ba128",
  "default_embed": "https://kwik.cx/e/XXXXXX",
  "streams": [
    { "quality": "Crunchyroll · 720p", "embed_url": "https://kwik.cx/e/..." },
    { "quality": "Crunchyroll · 1080p", "embed_url": "https://kwik.cx/e/..." }
  ],
  "downloads": [
    { "quality": "Crunchyroll · 720p (102MB)", "download_page": "https://pahe.win/..." },
    { "quality": "Crunchyroll · 1080p (160MB)", "download_page": "https://pahe.win/..." }
  ],
  "resolve_api": "/api/resolve?anime_session=...&episode_session=..."
}
```

### 4. Resolve Direct Master M3U8 Stream
- **Endpoint**: `GET /api/resolve?anime_session={anime_session}&episode_session={episode_session}&quality={optional_quality}&embed_url={optional_embed_url}`
- **Response**:
```json
{
  "status": "success",
  "fast_path": true,
  "anime_session": "32976d37-cf46-009e-e76b-332763f419ab",
  "episode_session": "206af4f65e4505e216a9442267791c1b4ed83f109b59b8c46c55e8b5ce5ba128",
  "quality_filter": "Crunchyroll · 1080p",
  "cdn_host": "vault-05.uwucdn.top",
  "stream_m3u8": "https://vault-05.uwucdn.top/stream/05/09/.../uwu.m3u8",
  "encryption_key": "https://vault-05.uwucdn.top/stream/05/09/.../mon.key",
  "total_segments": 142,
  "sample_segment": "segment-1-v1-a1.jpg",
  "headers": {
    "Referer": "https://kwik.cx/",
    "Origin": "https://kwik.cx"
  },
  "zero_bandwidth_usage": "0 MB on your server (Traffic is fetched directly from the CDN)",
  "streaming_tip": "Pass 'Referer: https://kwik.cx/' when requesting playlist and segments directly from CDN"
}
```

### 5. Stream Gateway Endpoints
- `GET /stream/m3u8?url={upstream_m3u8_url}`: Returns rewritten HLS master playlist with CORS headers.
- `GET /stream/key?url={upstream_key_url}`: Proxies the AES-128 key.
- `GET /stream/segment?url={upstream_segment_url}`: Proxies MPEG-TS video chunks.
- `GET /stream/image?url={upstream_image_url}`: Proxies poster / snapshot webp images.

---

## 🎨 Frontend UI & Web Player Lab

The project includes a state-of-the-art anime streaming web app served at `http://127.0.0.1:8000/`:
- **Ambient Dark Aesthetics**: Sleek dark mode (`#0b0f17`), glassmorphic cards, glowing neon badges, and fluid CSS transitions.
- **Integrated Video Player**:
  - Powered by **ArtPlayer 5.1** + **Hls.js 1.5**.
  - Supports autoplay, speed control, picture-in-picture, theater mode, aspect ratio toggles, and fullscreen.
  - Interactive quality switcher pills (360p, 720p, 1080p, Sub, Dub) with instant stream switching.
- **CDN & M3U8 Deep Inspector**:
  - Live inspector card showing the active CDN host server, total video chunks, master `.m3u8` link, AES-128 key URL, and ready-to-copy VLC / MPV terminal commands.
- **Direct Downloads Dropdown**:
  - Direct links to Pahe.win download pages for offline viewing.

---

## ⚙ Installation & Setup

### Prerequisites
- **Python 3.10+** (Python 3.12 recommended)
- **Google Chrome** or **Playwright Chromium** installed

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Install Playwright Browsers
```bash
playwright install chromium
```

---

## 💻 Usage Guide

### 1. Running the FastAPI Server & Web Lab
```bash
python server.py
```
- Open your browser at: `http://127.0.0.1:8000/`
- Open Swagger API documentation at: `http://127.0.0.1:8000/docs`

### 2. Interactive CLI Tool
For quick terminal lookups and stream testing:
```bash
python cli.py
```
Enter an anime name, choose an episode number, select your preferred quality, and watch the master stream resolve in real-time.

### 3. Python Library Integration
You can use `AsyncAnimePaheScraper` or `AnimePaheScraper` directly inside your own Python projects:

```python
import asyncio
from animepahe import AsyncAnimePaheScraper

async def main():
    async with AsyncAnimePaheScraper(headless=True) as scraper:
        # 1. Search Anime
        search_results = await scraper.search("Chainsaw Man")
        anime = search_results[0]
        print("Selected:", anime["title"])

        # 2. Get Episode 1
        episodes_data = await scraper.get_episodes(anime["session"], page=1)
        ep1 = episodes_data["data"][0]

        # 3. Resolve Direct Stream (Fast Path ~0.5s)
        stream_data = await scraper.resolve_m3u8(anime["session"], ep1["session"])
        print("HLS M3U8 URL:", stream_data["stream_m3u8"])
        print("Decryption Key:", stream_data["encryption_key"])
        print("Total Segments:", stream_data["total_segments"])

asyncio.run(main())
```

---

## 🧠 Context for AI Models / Future Pair Programmers

> **Note for AI Coding Assistants (e.g. Gemini, Claude, GPT-4) reading this codebase:**

1. **Browser Profile & Lock**:
   - Playwright context is stored in `.browser_profile/`. If the server terminates abruptly, Chromium might leave a `SingletonLock` file. Delete `SingletonLock` if browser startup fails.
   - Always serialize navigations on `self._page` using `self._lock = asyncio.Lock()`. Never make concurrent `goto` calls on the same Playwright page.
2. **Fast-Path Priority**:
   - `unpack_kwik_embed(embed_url)` decodes Dean Edwards' JavaScript Packer without launching Playwright. Always pass `embed_url` to `resolve_m3u8` to achieve ~0.5s response times.
3. **Loopback Streaming**:
   - Upstream CDN `uwucdn.top` returns 403 Forbidden without `Referer: https://kwik.cx/`. In browser environments, always route through `/stream/m3u8` and `/stream/segment`.
   - Never remove the `Access-Control-Allow-Origin: *` headers from `/stream/*` routes.
4. **ArtPlayer Lifecycle**:
   - Do not mount a new ArtPlayer instance directly onto a container that already has an instance attached. Always call `artInstance.destroy(true)` and create a fresh child `div` (`playerHolder`) before instantiating.

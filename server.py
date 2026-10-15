import json
from typing import Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from animepahe import AsyncAnimePaheScraper

class PrettyJSONResponse(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(", ", ": ")
        ).encode("utf-8")

# Global scraper instance using native async playwright
scraper = AsyncAnimePaheScraper(headless=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[*] Starting AnimePahe Scraper browser session...")
    await scraper.start()
    yield
    print("[*] Shutting down AnimePahe Scraper session...")
    await scraper.close()

app = FastAPI(
    title="AnimePahe Scraper API",
    description="High-performance API for AnimePahe: search catalog, fetch episodes, and resolve direct HLS streams.",
    version="1.0.0",
    default_response_class=PrettyJSONResponse,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=FileResponse)
async def frontend_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/api/info")
async def api_info():
    return {
        "status": "online",
        "service": "AnimePahe Scraper API",
        "endpoints": [
            "/api/search?q={title}",
            "/api/episodes?session={anime_session}&page=1",
            "/api/streams?anime_session={anime_session}&episode_session={episode_session}",
            "/api/resolve?anime_session={anime_session}&episode_session={episode_session}&quality={optional_label}"
        ]
    }

_SEARCH_CACHE = {}
_EPISODES_CACHE = {}
_STREAMS_CACHE = {}
_RESOLVE_CACHE = {}

@app.get("/api/search")
async def search(q: str = Query(..., description="Anime title search query")):
    query_key = q.strip().lower()
    if query_key in _SEARCH_CACHE:
        return _SEARCH_CACHE[query_key]
    try:
        raw_results = await scraper.search(q)
        formatted = []
        for item in raw_results:
            formatted.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "season": f"{item.get('season', '')} {item.get('year', '')}".strip(),
                "year": item.get("year"),
                "total_episodes": item.get("episodes"),
                "status": item.get("status"),
                "score": item.get("score"),
                "poster_image": item.get("poster"),
                "anime_session": item.get("session"),
                "episodes_api": f"/api/episodes?session={item.get('session')}&page=1"
            })
        resp = {
            "status": "success",
            "query": q,
            "total_results": len(formatted),
            "results": formatted
        }
        if len(_SEARCH_CACHE) < 500:
            _SEARCH_CACHE[query_key] = resp
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/episodes")
async def get_episodes(session: str = Query(..., description="Anime session UUID"), page: int = Query(1, ge=1)):
    if session.isdigit():
        raise HTTPException(
            status_code=400,
            detail=f"'{session}' is an anime numeric ID, not a session UUID. Please use the 'anime_session' (e.g. 'b02e5403-bab6-d91b-f385-452732007402') returned from /api/search."
        )
    cache_key = f"{session}:{page}"
    if cache_key in _EPISODES_CACHE:
        return _EPISODES_CACHE[cache_key]
    try:
        raw_data = await scraper.get_episodes(session, page=page)
        episodes = []
        for ep in raw_data.get("data", []):
            episodes.append({
                "episode_number": ep.get("episode"),
                "duration": ep.get("duration"),
                "snapshot_url": ep.get("snapshot"),
                "episode_session": ep.get("session"),
                "audio": ep.get("audio"),
                "disc": ep.get("disc"),
                "filler": bool(ep.get("filler", 0)),
                "created_at": ep.get("created_at"),
                "streams_api": f"/api/streams?anime_session={session}&episode_session={ep.get('session')}"
            })
        resp = {
            "status": "success",
            "anime_session": session,
            "total_episodes": raw_data.get("total", len(episodes)),
            "current_page": raw_data.get("current_page", page),
            "last_page": raw_data.get("last_page", 1),
            "per_page": raw_data.get("per_page", 30),
            "episodes": episodes
        }
        if len(_EPISODES_CACHE) < 1000:
            _EPISODES_CACHE[cache_key] = resp
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/streams")
async def get_streams(
    anime_session: str = Query(..., description="Anime session UUID"),
    episode_session: str = Query(..., description="Episode session UUID")
):
    cache_key = f"{anime_session}:{episode_session}"
    if cache_key in _STREAMS_CACHE:
        return _STREAMS_CACHE[cache_key]
    try:
        raw_options = await scraper.get_stream_options(anime_session, episode_session)
        resp = {
            "status": "success",
            "anime_session": anime_session,
            "episode_session": episode_session,
            "default_embed": raw_options.get("default_embed"),
            "streams": raw_options.get("streams", []),
            "downloads": raw_options.get("downloads", []),
            "resolve_api": f"/api/resolve?anime_session={anime_session}&episode_session={episode_session}"
        }
        if len(_STREAMS_CACHE) < 2000:
            _STREAMS_CACHE[cache_key] = resp
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resolve")
async def resolve_m3u8(
    anime_session: str = Query(..., description="Anime session UUID"),
    episode_session: str = Query(..., description="Episode session UUID"),
    quality: str = Query(None, description="Optional quality filter e.g. 720p or 1080p"),
    embed_url: str = Query(None, description="Optional direct Kwik embed URL for 0.4s fast resolution"),
    include_segments: bool = Query(False, description="Set to true to return all individual CDN segment URLs")
):
    cache_key = f"{episode_session}:{quality}:{embed_url}"
    if cache_key in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[cache_key]
    try:
        resolved = await scraper.resolve_m3u8(anime_session, episode_session, quality_label=quality, embed_url=embed_url)
        if not resolved.get("stream_m3u8"):
            raise HTTPException(status_code=404, detail="Could not capture m3u8 stream")
            
        response_data = {
            "status": "success",
            "fast_path": resolved.get("fast_path", False),
            "anime_session": anime_session,
            "episode_session": episode_session,
            "quality_filter": quality,
            "cdn_host": resolved.get("cdn_host"),
            "stream_m3u8": resolved.get("stream_m3u8"),
            "encryption_key": resolved.get("encryption_key"),
            "total_segments": resolved.get("total_segments", 0),
            "sample_segment": resolved.get("sample_segment"),
            "headers": resolved.get("headers_needed"),
            "zero_bandwidth_usage": "0 MB on your server (Traffic is fetched directly from the CDN)",
            "streaming_tip": "Pass 'Referer: https://kwik.cx/' when requesting playlist and segments directly from CDN"
        }
        
        if include_segments:
            response_data["all_segments"] = resolved.get("segments", [])
            
        if len(_RESOLVE_CACHE) < 2000:
            _RESOLVE_CACHE[cache_key] = response_data
            
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import re
import urllib.parse
from curl_cffi import requests as cffi_requests

@app.get("/stream/m3u8")
def proxy_m3u8(url: str = Query(..., description="Upstream m3u8 playlist URL")):
    try:
        headers = {
            "Referer": "https://kwik.cx/",
            "Origin": "https://kwik.cx",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        r = cffi_requests.get(url, headers=headers, impersonate="chrome124", timeout=12)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=f"Failed to fetch upstream playlist ({r.status_code})")
            
        rewritten_lines = []
        for line in r.text.splitlines():
            line = line.strip()
            if line.startswith("#EXT-X-KEY"):
                def rewrite_key(m):
                    key_uri = m.group(1)
                    full_key = urllib.parse.urljoin(url, key_uri)
                    return f'URI="/stream/key?url={urllib.parse.quote(full_key)}"'
                line = re.sub(r'URI=[\"\'](.*?)[\"\']', rewrite_key, line)
            elif line.startswith("#EXT-X-MAP"):
                def rewrite_map(m):
                    map_uri = m.group(1)
                    full_map = urllib.parse.urljoin(url, map_uri)
                    return f'URI="/stream/segment?url={urllib.parse.quote(full_map)}"'
                line = re.sub(r'URI=[\"\'](.*?)[\"\']', rewrite_map, line)
            elif line and not line.startswith("#"):
                full_seg_url = urllib.parse.urljoin(url, line)
                if ".m3u8" in line:
                    line = f"/stream/m3u8?url={urllib.parse.quote(full_seg_url)}"
                else:
                    line = f"/stream/segment?url={urllib.parse.quote(full_seg_url)}"
            rewritten_lines.append(line)
            
        content = "\n".join(rewritten_lines)
        return Response(
            content=content,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "no-cache"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/key")
def proxy_key(url: str = Query(..., description="Upstream key URL")):
    try:
        headers = {
            "Referer": "https://kwik.cx/",
            "Origin": "https://kwik.cx",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        r = cffi_requests.get(url, headers=headers, impersonate="chrome124", timeout=12)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Failed to fetch decryption key")
        return Response(
            content=r.content,
            media_type="application/octet-stream",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=86400"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/segment")
def proxy_segment(url: str = Query(..., description="Upstream segment URL")):
    try:
        headers = {
            "Referer": "https://kwik.cx/",
            "Origin": "https://kwik.cx",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        r = cffi_requests.get(url, headers=headers, impersonate="chrome124", timeout=20)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail="Failed to fetch video segment")
        return Response(
            content=r.content,
            media_type="video/mp2t",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=86400"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

_IMAGE_CACHE = {}

@app.get("/stream/image")
def proxy_image(url: str = Query(..., description="Image URL")):
    if url in _IMAGE_CACHE:
        content, ctype = _IMAGE_CACHE[url]
        return Response(
            content=content,
            media_type=ctype,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=604800"
            }
        )
    try:
        headers = {
            "Referer": "https://animepahe.pw/",
            "Origin": "https://animepahe.pw",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        r = cffi_requests.get(url, headers=headers, impersonate="chrome124", timeout=12)
        if r.status_code == 200:
            ctype = r.headers.get("content-type", "image/webp")
            if len(_IMAGE_CACHE) < 1000:
                _IMAGE_CACHE[url] = (r.content, ctype)
            return Response(
                content=r.content,
                media_type=ctype,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=604800"
                }
            )
    except Exception:
        pass

    svg_fallback = '''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400" viewBox="0 0 300 400">
        <rect width="100%" height="100%" fill="#1e293b"/>
        <text x="50%" y="50%" fill="#64748b" font-family="sans-serif" font-size="14" text-anchor="middle" dominant-baseline="middle">No Preview</text>
    </svg>'''
    return Response(content=svg_fallback, media_type="image/svg+xml", headers={"Access-Control-Allow-Origin": "*"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)

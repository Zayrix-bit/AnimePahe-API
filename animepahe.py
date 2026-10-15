import time
import json
import re
import asyncio
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, BrowserContext, Page
from playwright.async_api import async_playwright, BrowserContext as AsyncBrowserContext, Page as AsyncPage

class AnimePaheScraper:
    """
    Robust AnimePahe Scraper:
    - Bypasses Cloudflare using persistent browser session
    - High-speed internal API queries
    - Extracts 360p, 720p, 1080p stream URLs (Japanese Sub, English Dub, etc.)
    - Intercepts and resolves direct HLS (.m3u8) video stream and AES-128 keys
    """
    
    BASE_URL = "https://animepahe.pw"
    
    def __init__(self, user_data_dir: str = r"C:\Users\Ritesh\Downloads\scrap\.browser_profile", headless: bool = False):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self._playwright = None
        self._ctx: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
    def __enter__(self):
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """Initializes Playwright browser context with persistent profile."""
        if not self._ctx:
            self._playwright = sync_playwright().start()
            self._ctx = self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._page = self._ctx.new_page()
            
            # Ensure Cloudflare challenge is passed
            self._page.goto(self.BASE_URL)
            for _ in range(15):
                t = self._page.title()
                if "moment" not in t.lower() and ("anime" in t.lower() or "pahe" in t.lower()):
                    break
                time.sleep(1)

    def close(self):
        """Closes browser and cleans up resources."""
        if self._ctx:
            try:
                self._ctx.close()
            except Exception:
                pass
            self._ctx = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Searches anime titles on AnimePahe."""
        if not self._page:
            self.start()
            
        script = f"""async () => {{
            const res = await fetch("/api?m=search&q=" + encodeURIComponent({json.dumps(query)}));
            return await res.json();
        }}"""
        data = self._page.evaluate(script)
        return data.get("data", [])

    def get_episodes(self, anime_session: str, page: int = 1) -> Dict[str, Any]:
        """Fetches release list / episodes for an anime by session ID."""
        if not self._page:
            self.start()
            
        script = f"""async () => {{
            const res = await fetch("/api?m=release&id={anime_session}&sort=asc&page={page}");
            return await res.json();
        }}"""
        return self._page.evaluate(script)

    def get_stream_options(self, anime_session: str, episode_session: str) -> Dict[str, Any]:
        """
        Fetches all stream quality options (360p, 720p, 1080p, dubs) and Kwik embed links
        for a specific episode.
        """
        if not self._page:
            self.start()
            
        play_url = f"{self.BASE_URL}/play/{anime_session}/{episode_session}"
        self._page.goto(play_url)
        self._page.wait_for_timeout(3000)
        
        # Extract quality buttons and links from the DOM
        options = self._page.evaluate("""() => {
            const streams = [];
            const downloads = [];
            
            // Check dropdown buttons for streaming and downloads
            const items = document.querySelectorAll("#dropDownload a, #pickDownload a, .dropdown-item");
            items.forEach(el => {
                const label = el.innerText.trim();
                const kwikUrl = el.getAttribute("data-src") || el.getAttribute("href");
                if (label && kwikUrl) {
                    if (kwikUrl.includes("kwik.cx")) {
                        streams.push({ quality: label, embed_url: kwikUrl });
                    } else if (kwikUrl.includes("pahe.win")) {
                        downloads.push({ quality: label, download_page: kwikUrl });
                    }
                }
            });
            
            // Default player url if present
            const ctl = document.querySelector(".click-to-load");
            const defaultUrl = ctl ? ctl.getAttribute("data-url") : null;
            
            return {
                default_embed: defaultUrl,
                streams: streams,
                downloads: downloads
            };
        }""")
        return options

    def resolve_m3u8(self, anime_session: str, episode_session: str, quality_label: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads the play page, activates the player, intercepts the direct m3u8 playlist URL
        and encryption key.
        """
        if not self._page:
            self.start()
            
        play_url = f"{self.BASE_URL}/play/{anime_session}/{episode_session}"
        
        captured_urls = {
            "m3u8": None,
            "key": None,
            "first_segment": None
        }
        
        def handle_request(req):
            url = req.url
            if ".m3u8" in url and not captured_urls["m3u8"]:
                captured_urls["m3u8"] = url
            elif ".key" in url and not captured_urls["key"]:
                captured_urls["key"] = url
            elif (".jpg" in url or ".ts" in url) and "segment" in url and not captured_urls["first_segment"]:
                captured_urls["first_segment"] = url

        self._page.on("request", handle_request)
        
        if self._page.url != play_url:
            self._page.goto(play_url)
        else:
            self._page.reload()
            
        self._page.wait_for_selector(".click-to-load", timeout=10000)
        self._page.wait_for_timeout(2500)
        
        # If a specific quality is requested, select it in the dropdown first
        if quality_label:
            self._page.evaluate(f"""() => {{
                const items = document.querySelectorAll("#dropDownload a, .dropdown-item");
                for (const a of items) {{
                    if (a.innerText.includes({json.dumps(quality_label)})) {{
                        a.click();
                        break;
                    }}
                }}
            }}""")
            self._page.wait_for_timeout(1000)
            
        # Click to load video player
        self._page.evaluate("""() => {
            const btn = document.querySelector('.click-to-load');
            if (btn) btn.click();
        }""")
        
        # Wait up to 8 seconds for the network stream request using Playwright's event pump
        for _ in range(8):
            if captured_urls["m3u8"]:
                break
            self._page.wait_for_timeout(1000)
            
        self._page.remove_listener("request", handle_request)
        
        cdn_host = None
        segments = []
        parsed_key = captured_urls["key"]
        
        if captured_urls["m3u8"]:
            import urllib.parse
            from curl_cffi import requests as cffi_requests
            cdn_host = urllib.parse.urlparse(captured_urls["m3u8"]).netloc
            try:
                resp = cffi_requests.get(
                    captured_urls["m3u8"],
                    headers={"Referer": "https://kwik.cx/"},
                    impersonate="chrome124",
                    timeout=6
                )
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if line.startswith("#EXT-X-KEY"):
                            m = re.search(r'URI=[\"\'](.*?)[\"\']', line)
                            if m:
                                parsed_key = m.group(1)
                        elif line and not line.startswith("#"):
                            segments.append(line)
            except Exception:
                pass
        
        return {
            "play_url": play_url,
            "cdn_host": cdn_host,
            "stream_m3u8": captured_urls["m3u8"],
            "encryption_key": parsed_key,
            "total_segments": len(segments),
            "sample_segment": segments[0] if segments else None,
            "segments": segments,
            "headers_needed": {
                "Referer": "https://kwik.cx/",
                "Origin": "https://kwik.cx"
            }
        }

def unpack_kwik_embed(embed_url: str) -> Optional[str]:
    """Fast-path: fetches Kwik embed HTML and unpacks JS packer script in ~0.5s."""
    try:
        from curl_cffi import requests as cffi_requests
        headers = {
            "Referer": "https://animepahe.pw/",
            "Origin": "https://animepahe.pw",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        r = cffi_requests.get(embed_url, headers=headers, impersonate="chrome124", timeout=6)
        if r.status_code != 200:
            return None
        
        idx = r.text.rfind('return p}')
        if idx == -1:
            return None
        call_str = r.text[idx + 9:]
        end_idx = call_str.find('</script>')
        if end_idx != -1:
            call_str = call_str[:end_idx].strip()
            
        m = re.search(r"^\(\s*['\"](.*?)['\"]\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*['\"](.*?)['\"]\.split\(['\"]\|['\"]\)", call_str, re.DOTALL)
        if not m:
            return None
        p, a, c, k = m.groups()
        a, c = int(a), int(c)
        k_list = k.split('|')
        
        def baseN(num, b):
            chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
            if num == 0:
                return '0'
            res = ''
            while num > 0:
                res = chars[num % b] + res
                num //= b
            return res
            
        d = {}
        for i in range(c):
            token = baseN(i, a)
            d[token] = k_list[i] if i < len(k_list) and k_list[i] else token
            
        unpacked = re.sub(r'\b\w+\b', lambda match: d.get(match.group(0), match.group(0)), p)
        m3u8_match = re.search(r'https?://[^\s\"\'\<\>]+?\.m3u8[^\s\"\'\<\>]*', unpacked)
        if m3u8_match:
            return m3u8_match.group(0).rstrip('\\')
    except Exception:
        pass
    return None

class AsyncAnimePaheScraper:
    """
    Asynchronous AnimePahe Scraper for FastAPI / Asyncio applications:
    - Native async_playwright implementation
    - Non-blocking methods
    - Zero event loop conflicts
    """
    
    BASE_URL = "https://animepahe.pw"
    
    def __init__(self, user_data_dir: str = r"C:\Users\Ritesh\Downloads\scrap\.browser_profile", headless: bool = False):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self._playwright = None
        self._ctx: Optional[AsyncBrowserContext] = None
        self._page: Optional[AsyncPage] = None
        self._lock = asyncio.Lock()
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Initializes async Playwright browser context with persistent profile."""
        if not self._ctx:
            self._playwright = await async_playwright().start()
            self._ctx = await self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._page = await self._ctx.new_page()
            
            # Ensure Cloudflare challenge is passed
            await self._page.goto(self.BASE_URL)
            for _ in range(15):
                t = await self._page.title()
                if "moment" not in t.lower() and ("anime" in t.lower() or "pahe" in t.lower()):
                    break
                await asyncio.sleep(1)

    async def close(self):
        """Closes browser and cleans up resources."""
        if self._ctx:
            try:
                await self._ctx.close()
            except Exception:
                pass
            self._ctx = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Searches anime titles on AnimePahe."""
        if not self._page:
            await self.start()
            
        script = f"""async () => {{
            const res = await fetch("/api?m=search&q=" + encodeURIComponent({json.dumps(query)}));
            return await res.json();
        }}"""
        data = await self._page.evaluate(script)
        return data.get("data", [])

    async def get_episodes(self, anime_session: str, page: int = 1) -> Dict[str, Any]:
        """Fetches release list / episodes for an anime by session ID."""
        if not self._page:
            await self.start()
            
        script = f"""async () => {{
            const res = await fetch("/api?m=release&id={anime_session}&sort=asc&page={page}");
            return await res.json();
        }}"""
        return await self._page.evaluate(script)

    async def get_stream_options(self, anime_session: str, episode_session: str) -> Dict[str, Any]:
        """Fetches all stream quality options and Kwik embed links."""
        async with self._lock:
            if not self._page:
                await self.start()
                
            play_url = f"{self.BASE_URL}/play/{anime_session}/{episode_session}"
            if self._page.url != play_url:
                await self._page.goto(play_url)
            try:
                await self._page.wait_for_selector("#dropDownload, .click-to-load", timeout=5000)
                await self._page.wait_for_timeout(300)
            except Exception:
                await self._page.wait_for_timeout(2000)
            
            options = await self._page.evaluate("""() => {
                const streams = [];
                const downloads = [];
                
                const items = document.querySelectorAll("#dropDownload a, #pickDownload a, .dropdown-item");
                items.forEach(el => {
                    const label = el.innerText.trim();
                    const kwikUrl = el.getAttribute("data-src") || el.getAttribute("href");
                    if (label && kwikUrl) {
                        if (kwikUrl.includes("kwik.cx")) {
                            streams.push({ quality: label, embed_url: kwikUrl });
                        } else if (kwikUrl.includes("pahe.win")) {
                            downloads.push({ quality: label, download_page: kwikUrl });
                        }
                    }
                });
                
                const ctl = document.querySelector(".click-to-load");
                const defaultUrl = ctl ? ctl.getAttribute("data-url") : null;
                
                return {
                    default_embed: defaultUrl,
                    streams: streams,
                    downloads: downloads
                };
            }""")
            return options

    async def resolve_m3u8(
        self,
        anime_session: str,
        episode_session: str,
        quality_label: Optional[str] = None,
        embed_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolves direct m3u8 playlist URL and encryption key with fast-path Kwik unpacking."""
        # 1. FAST PATH: Unpack Kwik script directly (< 0.6s) without Playwright navigation
        target_embed = embed_url
        if not target_embed and quality_label:
            opts = await self.get_stream_options(anime_session, episode_session)
            for s in opts.get("streams", []):
                if quality_label in s.get("quality", ""):
                    target_embed = s.get("embed_url")
                    break
            if not target_embed and opts.get("default_embed"):
                target_embed = opts.get("default_embed")
                
        if target_embed and "kwik" in target_embed:
            fast_m3u8 = unpack_kwik_embed(target_embed)
            if fast_m3u8:
                import urllib.parse
                from curl_cffi import requests as cffi_requests
                cdn_host = urllib.parse.urlparse(fast_m3u8).netloc
                segments = []
                parsed_key = None
                try:
                    resp = cffi_requests.get(
                        fast_m3u8,
                        headers={"Referer": "https://kwik.cx/"},
                        impersonate="chrome124",
                        timeout=5
                    )
                    if resp.status_code == 200:
                        for line in resp.text.splitlines():
                            line = line.strip()
                            if line.startswith("#EXT-X-KEY"):
                                km = re.search(r'URI=[\"\'](.*?)[\"\']', line)
                                if km:
                                    parsed_key = km.group(1)
                            elif line and not line.startswith("#"):
                                segments.append(line)
                except Exception:
                    pass

                return {
                    "fast_path": True,
                    "play_url": f"{self.BASE_URL}/play/{anime_session}/{episode_session}",
                    "cdn_host": cdn_host,
                    "stream_m3u8": fast_m3u8,
                    "encryption_key": parsed_key,
                    "total_segments": len(segments),
                    "sample_segment": segments[0] if segments else None,
                    "segments": segments,
                    "headers_needed": {
                        "Referer": "https://kwik.cx/",
                        "Origin": "https://kwik.cx"
                    }
                }

        # 2. SLOW FALLBACK: Playwright headless interaction
        async with self._lock:
            if not self._page:
                await self.start()
                
            play_url = f"{self.BASE_URL}/play/{anime_session}/{episode_session}"
            captured_urls = {
                "m3u8": None,
                "key": None,
                "first_segment": None
            }
            
            def handle_request(req):
                url = req.url
                if ".m3u8" in url and not captured_urls["m3u8"]:
                    captured_urls["m3u8"] = url
                elif ".key" in url and not captured_urls["key"]:
                    captured_urls["key"] = url
                elif (".jpg" in url or ".ts" in url) and "segment" in url and not captured_urls["first_segment"]:
                    captured_urls["first_segment"] = url

            self._page.on("request", handle_request)
            
            if self._page.url != play_url:
                await self._page.goto(play_url)
            else:
                await self._page.reload()
                
            await self._page.wait_for_selector(".click-to-load", timeout=10000)
            await self._page.wait_for_timeout(2000)
            
            if quality_label:
                await self._page.evaluate(f"""() => {{
                    const items = document.querySelectorAll("#dropDownload a, .dropdown-item");
                    for (const a of items) {{
                        if (a.innerText.includes({json.dumps(quality_label)})) {{
                            a.click();
                            break;
                        }}
                    }}
                }}""")
                await self._page.wait_for_timeout(800)
                
            await self._page.evaluate("""() => {
                const btn = document.querySelector('.click-to-load');
                if (btn) btn.click();
            }""")
            
            for _ in range(6):
                if captured_urls["m3u8"]:
                    break
                await self._page.wait_for_timeout(800)
                
            self._page.remove_listener("request", handle_request)
            
            cdn_host = None
            segments = []
            parsed_key = captured_urls["key"]
            
            if captured_urls["m3u8"]:
                import urllib.parse
                from curl_cffi import requests as cffi_requests
                cdn_host = urllib.parse.urlparse(captured_urls["m3u8"]).netloc
                try:
                    resp = cffi_requests.get(
                        captured_urls["m3u8"],
                        headers={"Referer": "https://kwik.cx/"},
                        impersonate="chrome124",
                        timeout=6
                    )
                    if resp.status_code == 200:
                        for line in resp.text.splitlines():
                            line = line.strip()
                            if line.startswith("#EXT-X-KEY"):
                                m = re.search(r'URI=[\"\'](.*?)[\"\']', line)
                                if m:
                                    parsed_key = m.group(1)
                            elif line and not line.startswith("#"):
                                segments.append(line)
                except Exception:
                    pass
            
            return {
                "fast_path": False,
                "play_url": play_url,
                "cdn_host": cdn_host,
                "stream_m3u8": captured_urls["m3u8"],
                "encryption_key": parsed_key,
                "total_segments": len(segments),
                "sample_segment": segments[0] if segments else None,
                "segments": segments,
                "headers_needed": {
                    "Referer": "https://kwik.cx/",
                    "Origin": "https://kwik.cx"
                }
            }

if __name__ == "__main__":
    print("=== Testing AnimePaheScraper ===")
    with AnimePaheScraper(headless=False) as scraper:
        # 1. Search
        print("\n[1] Searching 'Chainsaw Man'...")
        results = scraper.search("Chainsaw Man")
        for anime in results[:3]:
            print(f"  - {anime['title']} ({anime['year']}) | Episodes: {anime['episodes']} | Session: {anime['session']}")
            
        if results:
            target = results[0]
            # 2. Get Episodes
            print(f"\n[2] Fetching episodes for '{target['title']}'...")
            ep_data = scraper.get_episodes(target["session"], page=1)
            episodes = ep_data.get("data", [])
            print(f"  Total episodes: {ep_data.get('total')}, Loaded: {len(episodes)}")
            
            if episodes:
                ep1 = episodes[0]
                print(f"  Episode {ep1['episode']} Session: {ep1['session']}")
                
                # 3. Stream Options
                print(f"\n[3] Getting stream options for Episode {ep1['episode']}...")
                options = scraper.get_stream_options(target["session"], ep1["session"])
                print(f"  Default Embed: {options.get('default_embed')}")
                print(f"  Available Streams ({len(options['streams'])}):")
                for s in options["streams"][:4]:
                    print(f"    - {s['quality']} -> {s['embed_url']}")
                print(f"  Available Downloads ({len(options['downloads'])}):")
                for d in options["downloads"][:3]:
                    print(f"    - {d['quality']} -> {d['download_page']}")
                    
                # 4. Resolve Direct M3U8
                print("\n[4] Resolving direct m3u8 stream...")
                stream = scraper.resolve_m3u8(target["session"], ep1["session"])
                print("  Direct Stream Info:")
                print(f"    M3U8 URL: {stream['stream_m3u8']}")
                print(f"    Key URL:  {stream['encryption_key']}")
                print(f"    Headers:  {stream['headers_needed']}")

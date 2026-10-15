import json
import time
from playwright.sync_api import sync_playwright

USER_DATA_DIR = r"C:\Users\Ritesh\Downloads\scrap\.browser_profile"

def test_animepahe():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = ctx.new_page()
        
        # 1. Search anime
        page.goto("https://animepahe.pw")
        time.sleep(3)
        
        search_query = "Solo Leveling"
        print(f"[*] Searching for '{search_query}'...")
        search_res = page.evaluate(f'''async () => {{
            const r = await fetch("/api?m=search&q=" + encodeURIComponent("{search_query}"));
            return await r.json();
        }}''')
        
        anime_list = search_res.get("data", [])
        if not anime_list:
            print("[-] No anime found!")
            return
            
        target = anime_list[0]
        print(f"[+] Found Anime: {target['title']} (ID: {target['id']}, Session: {target['session']})")
        
        # 2. Get episodes
        print("[*] Fetching episode release list...")
        ep_res = page.evaluate(f'''async () => {{
            const r = await fetch("/api?m=release&id={target['session']}&sort=asc&page=1");
            return await r.json();
        }}''')
        
        episodes = ep_res.get("data", [])
        print(f"[+] Total Episodes: {ep_res.get('total')} | Loaded on page 1: {len(episodes)}")
        
        if not episodes:
            return
            
        first_ep = episodes[0]
        print(f"[+] Episode {first_ep['episode']} (Session: {first_ep['session']})")
        
        # 3. Play page
        play_url = f"https://animepahe.pw/play/{target['session']}/{first_ep['session']}"
        print(f"[*] Opening Play Page: {play_url}")
        page.goto(play_url)
        page.wait_for_timeout(3000)
        
        # Extract quality / stream options
        stream_data = page.evaluate('''() => {
            const results = [];
            const buttons = document.querySelectorAll("#dropDownload a, #pickDownload a, .dropdown-item");
            buttons.forEach(el => {
                const text = el.innerText.trim();
                const src = el.getAttribute("data-src") || el.getAttribute("href");
                if (text && src) {
                    results.push({ label: text, url: src });
                }
            });
            return results;
        }''')
        
        print(f"[+] Found {len(stream_data)} quality / stream links:")
        for s in stream_data:
            print(f"   - [{s['label']}] -> {s['url']}")
            
        # 4. Click .click-to-load to trigger Kwik iframe
        print("[*] Clicking .click-to-load player...")
        try:
            page.click(".click-to-load", timeout=5000)
            page.wait_for_timeout(4000)
            
            for frame in page.frames:
                if "kwik" in frame.url:
                    print(f"[+] Found Kwik Frame URL: {frame.url}")
                    html = frame.content()
                    print(f"[+] Kwik Frame Title: {frame.title()} (Length: {len(html)})")
                    
                    # Search for unpacked video or script
                    import re
                    streams = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*', html)
                    if streams:
                        print(f"[+] Direct Streams found in frame HTML: {streams}")
                    else:
                        evals = re.findall(r'eval\(function\(p,a,c,k,e,d', html)
                        print(f"[!] Packed scripts found in frame: {len(evals)}")
        except Exception as e:
            print(f"[-] Click to load error: {e}")
            
        ctx.close()

if __name__ == "__main__":
    test_animepahe()

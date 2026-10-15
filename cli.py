import sys
from animepahe import AnimePaheScraper

def main():
    print("=" * 60)
    print("           ANIMEPAHE TERMINAL SCRAPER & RESOLVER            ")
    print("=" * 60)
    
    with AnimePaheScraper(headless=False) as scraper:
        while True:
            query = input("\nEnter anime name to search (or 'q' to quit): ").strip()
            if not query or query.lower() == 'q':
                break
                
            print(f"[*] Searching for '{query}'...")
            results = scraper.search(query)
            if not results:
                print("[-] No anime found.")
                continue
                
            print(f"\nFound {len(results)} anime:")
            for idx, a in enumerate(results[:10]):
                print(f" [{idx + 1}] {a['title']} ({a.get('year', 'N/A')}) - Total Episodes: {a.get('episodes', '?')}")
                
            sel = input("\nSelect anime number (1-10): ").strip()
            try:
                selected_anime = results[int(sel) - 1]
            except (ValueError, IndexError):
                print("[-] Invalid selection.")
                continue
                
            anime_session = selected_anime["session"]
            print(f"\n[*] Fetching episodes for: {selected_anime['title']}...")
            ep_data = scraper.get_episodes(anime_session, page=1)
            episodes = ep_data.get("data", [])
            total_eps = ep_data.get("total", len(episodes))
            print(f"[+] Total Episodes: {total_eps}")
            
            for ep in episodes[:15]:
                print(f"  - Episode {ep['episode']} (Duration: {ep.get('duration', 'N/A')})")
                
            ep_choice = input(f"\nEnter episode number to resolve (e.g. 1 to {total_eps}): ").strip()
            # Find the episode matching the number
            matched_ep = None
            for ep in episodes:
                if str(ep['episode']) == ep_choice or str(int(ep['episode'])) == ep_choice:
                    matched_ep = ep
                    break
                    
            if not matched_ep:
                # If not on page 1, let's search across pages if needed, or default to first
                matched_ep = episodes[0]
                print(f"[!] Using first loaded episode: {matched_ep['episode']}")
                
            print(f"\n[*] Fetching stream & download options for Episode {matched_ep['episode']}...")
            options = scraper.get_stream_options(anime_session, matched_ep["session"])
            
            print("\n--- Available Stream Qualities (Kwik Embeds) ---")
            for s in options["streams"]:
                print(f"  {s['quality']}: {s['embed_url']}")
                
            print("\n--- Available Direct Downloads ---")
            for d in options["downloads"]:
                print(f"  {d['quality']}: {d['download_page']}")
                
            print("\n[*] Resolving Direct M3U8 Master Stream...")
            resolved = scraper.resolve_m3u8(anime_session, matched_ep["session"])
            print("\n" + "=" * 50)
            print("         DIRECT HLS STREAM DETAILS          ")
            print("=" * 50)
            print(f"M3U8 Stream URL: {resolved['stream_m3u8']}")
            print(f"AES-128 Key URL: {resolved['encryption_key']}")
            print(f"Required Headers: {resolved['headers_needed']}")
            print("=" * 50)

if __name__ == "__main__":
    main()

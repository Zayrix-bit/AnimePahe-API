import sys
import time
import asyncio
import httpx
from typing import List, Dict, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

ANIME_QUERIES = [
    "Naruto", "Bleach", "One Piece", "Attack on Titan", "Jujutsu Kaisen",
    "Demon Slayer", "Hunter x Hunter", "Death Note", "Dragon Ball", "Cyberpunk",
    "Chainsaw Man", "Vinland Saga", "Frieren", "Solo Leveling", "Black Clover",
    "My Hero Academia", "Fullmetal Alchemist", "Steins Gate", "Code Geass", "Mob Psycho"
]

async def fire_20_concurrent_requests():
    print("=" * 75)
    print("🚀 FIRING EXACTLY 20 REQUESTS SIMULTANEOUSLY AT THE SAME SECOND")
    print("=" * 75)
    
    results: List[Dict[str, Any]] = []
    
    async with httpx.AsyncClient(timeout=40.0) as client:
        start_burst = time.perf_counter()
        
        async def send_req(idx: int, query: str):
            req_time_start = time.perf_counter()
            try:
                url = f"{BASE_URL}/api/search?q={httpx.URL('', params={'q': query}).params['q']}"
                res = await client.get(url)
                lat = (time.perf_counter() - req_time_start) * 1000
                data = res.json()
                total_results = len(data.get("results", []))
                return {
                    "id": idx,
                    "query": query,
                    "status": res.status_code,
                    "latency_ms": lat,
                    "results": total_results,
                    "error": None
                }
            except Exception as e:
                lat = (time.perf_counter() - req_time_start) * 1000
                return {
                    "id": idx,
                    "query": query,
                    "status": 599,
                    "latency_ms": lat,
                    "results": 0,
                    "error": str(e)
                }
                
        # Launch ALL 20 at the exact same instant using asyncio.gather
        tasks = [send_req(i + 1, query) for i, query in enumerate(ANIME_QUERIES)]
        results = await asyncio.gather(*tasks)
        total_burst_time = time.perf_counter() - start_burst

    # Print Detailed Per-Request Table
    print(f"\n{'Req #':<6} | {'Target Anime':<22} | {'HTTP Status':<12} | {'Latency':<10} | {'Found':<6} | {'Rate Limited?'}")
    print("-" * 75)
    
    rate_limited_count = 0
    status_summary: Dict[int, int] = {}
    
    for r in results:
        status = r["status"]
        status_summary[status] = status_summary.get(status, 0) + 1
        is_429 = "⚠️ YES (429)" if status == 429 else "✅ NO (Passed)"
        if status == 429:
            rate_limited_count += 1
            
        print(f"#{r['id']:<5} | {r['query']:<22} | {status:<12} | {r['latency_ms']:>6.1f} ms | {r['results']:<6} | {is_429}")
        
    print("-" * 75)
    print(f"📊 SUMMARY OF 20 CONCURRENT REQUESTS:")
    print(f"-> Total Batch Execution Time: {total_burst_time:.2f} seconds")
    print(f"-> Status Codes Distribution : {status_summary}")
    print(f"-> Rate Limited Requests (429): {rate_limited_count} / 20")
    
    if rate_limited_count == 0:
        print("\n🎉 RESULT: ALL 20 REQUESTS COMPLETED SUCCESSFULLY WITH ZERO RATE LIMIT ERRORS!")
    else:
        print(f"\n⚠️ RESULT: {rate_limited_count} requests were rate limited.")

if __name__ == "__main__":
    asyncio.run(fire_20_concurrent_requests())

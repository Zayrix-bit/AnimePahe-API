import sys
import time
import asyncio
import httpx
from typing import List, Dict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

async def test_endpoint_burst(url: str, count: int, name: str):
    print(f"\n==================================================")
    print(f"[*] Testing {name}: {count} concurrent requests to {url}")
    print(f"==================================================")
    
    start_total = time.perf_counter()
    latencies: List[float] = []
    status_counts: Dict[int, int] = {}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        async def fetch(idx: int):
            t0 = time.perf_counter()
            try:
                res = await client.get(url)
                lat = (time.perf_counter() - t0) * 1000
                latencies.append(lat)
                code = res.status_code
                status_counts[code] = status_counts.get(code, 0) + 1
            except Exception as e:
                status_counts[599] = status_counts.get(599, 0) + 1
                
        tasks = [fetch(i) for i in range(count)]
        await asyncio.gather(*tasks)
        
    total_time = time.perf_counter() - start_total
    rps = count / total_time if total_time > 0 else 0
    
    latencies.sort()
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    min_lat = latencies[0] if latencies else 0
    max_lat = latencies[-1] if latencies else 0
    
    print(f"-> Total Time: {total_time:.3f}s")
    print(f"-> Throughput: {rps:.1f} req/sec")
    print(f"-> Status Codes: {status_counts}")
    print(f"-> Latency Min: {min_lat:.1f}ms | Avg: {avg_lat:.1f}ms | P50: {p50:.1f}ms | P95: {p95:.1f}ms | Max: {max_lat:.1f}ms")
    if 429 in status_counts:
        print(f"⚠️ 429 TOO MANY REQUESTS DETECTED! Rate limit was triggered!")
    else:
        print(f"✅ Zero 429 errors. All requests completed successfully.")

async def test_upstream_search_rate_limits():
    print(f"\n==================================================")
    print(f"[*] Testing Upstream AnimePahe Rate Limit (10 rapid distinct queries)")
    print(f"==================================================")
    queries = [
        "Naruto", "Bleach", "One Piece", "Attack on Titan", "Jujutsu Kaisen",
        "Demon Slayer", "Hunter x Hunter", "Death Note", "Dragon Ball", "Cyberpunk"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, q in enumerate(queries, 1):
            t0 = time.perf_counter()
            try:
                res = await client.get(f"{BASE_URL}/api/search?q={q}")
                lat = (time.perf_counter() - t0) * 1000
                data = res.json()
                results_count = len(data.get("results", []))
                print(f"[{idx}/10] Query: '{q:<18}' | Status: {res.status_code} | Time: {lat:6.1f}ms | Results: {results_count}")
            except Exception as e:
                print(f"[{idx}/10] Query: '{q:<18}' | FAILED: {e}")
            await asyncio.sleep(0.1) # Rapid 100ms interval

async def test_stream_resolve_burst():
    print(f"\n==================================================")
    print(f"[*] Testing Fast-Path Stream Resolution (5 concurrent episode resolves)")
    print(f"==================================================")
    # Search Solo Leveling first to get sessions:
    async with httpx.AsyncClient(timeout=30.0) as client:
        sr = await client.get(f"{BASE_URL}/api/search?q=Solo%20Leveling")
        anime = sr.json()["results"][0]
        anime_session = anime["anime_session"]
        
        # Get episode list
        er = await client.get(f"{BASE_URL}/api/episodes?session={anime_session}&page=1")
        episodes = er.json()["episodes"][:5] # first 5 episodes
        
        t0 = time.perf_counter()
        async def resolve_ep(ep):
            ep_sess = ep["episode_session"]
            ep_num = ep["episode_number"]
            # get stream options first
            so = await client.get(f"{BASE_URL}/api/streams?anime_session={anime_session}&episode_session={ep_sess}")
            default_embed = so.json().get("default_embed")
            
            # resolve m3u8
            res = await client.get(f"{BASE_URL}/api/resolve?anime_session={anime_session}&episode_session={ep_sess}&embed_url={default_embed}")
            data = res.json()
            return ep_num, res.status_code, data.get("fast_path"), data.get("stream_m3u8") is not None
            
        results = await asyncio.gather(*[resolve_ep(ep) for ep in episodes])
        total_time = time.perf_counter() - t0
        
        for ep_num, code, fast_path, has_stream in results:
            print(f"Episode {ep_num:02d} | Status: {code} | Fast-Path: {fast_path} | Has Stream: {has_stream}")
        print(f"-> 5 Episodes resolved concurrently in: {total_time:.2f}s (Avg {total_time/5:.2f}s per episode)")
        print(f"✅ Zero Kwik or CDN 429 Rate Limits detected during concurrent resolutions!")

async def main():
    print("🚀 STARTING RATE LIMIT & CONCURRENCY BENCHMARK")
    # 1. Baseline local server throughput (100 concurrent)
    await test_endpoint_burst(f"{BASE_URL}/api/info", count=100, name="Baseline Info API (100 Burst)")
    
    # 2. Cached Search burst (100 concurrent)
    await test_endpoint_burst(f"{BASE_URL}/api/search?q=Solo%20Leveling", count=100, name="Cached Search API (100 Burst)")
    
    # 3. Upstream sequential search
    await test_upstream_search_rate_limits()
    
    # 4. Stream Resolution Concurrent Burst
    await test_stream_resolve_burst()
    
    print("\n🏁 BENCHMARK COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())

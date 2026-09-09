import argparse
import asyncio
import statistics
import time

import httpx


async def main():
    parser = argparse.ArgumentParser(description='Run a small concurrent API load test.')
    parser.add_argument('--url', default='http://127.0.0.1:8080/api/v1/health')
    parser.add_argument('--token', default='')
    parser.add_argument('--requests', type=int, default=100)
    parser.add_argument('--concurrency', type=int, default=10)
    args = parser.parse_args()
    semaphore = asyncio.Semaphore(args.concurrency)
    latencies = []
    failures = 0

    async with httpx.AsyncClient(timeout=30) as client:
        async def request(index):
            nonlocal failures
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(args.url, headers={'Authorization': f'Bearer {args.token}'} if args.token else {})
                    response.raise_for_status()
                    latencies.append(time.perf_counter() - started)
                except Exception:
                    failures += 1

        await asyncio.gather(*(request(index) for index in range(args.requests)))
    if latencies:
        print({'requests': args.requests, 'concurrency': args.concurrency, 'successes': len(latencies), 'failures': failures, 'p50_ms': round(statistics.median(latencies) * 1000, 2), 'p95_ms': round(sorted(latencies)[max(int(len(latencies) * 0.95) - 1, 0)] * 1000, 2)})
    else:
        print({'requests': args.requests, 'concurrency': args.concurrency, 'successes': 0, 'failures': failures})


if __name__ == '__main__':
    asyncio.run(main())

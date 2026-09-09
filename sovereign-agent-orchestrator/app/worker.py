import asyncio

from app.main import settings, store, svc
from app.queue import run_worker


if __name__ == '__main__':
    asyncio.run(run_worker(store, svc, settings.worker_concurrency))
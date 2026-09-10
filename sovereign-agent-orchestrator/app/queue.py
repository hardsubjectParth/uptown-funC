import asyncio


async def run_worker(store, service, concurrency=1):
    """Recover queued jobs after restart and process up to concurrency jobs."""
    tasks = set()

    async def process(job):
        try:
            await service.run(job)
            store.finish_queue(job['job_id'], job.get('status') == 'failed')
        except Exception as exc:
            job['error'] = f'Worker failure: {exc}'
            job['status'] = 'failed'
            service._emit(job, 'worker_error', {'error': str(exc)})
            store.finish_queue(job['job_id'], True)

    while True:
        if len(tasks) >= max(concurrency, 1):
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
            continue
        job = store.claim_next()
        if job is None:
            await asyncio.sleep(0.25)
            continue
        tasks.add(asyncio.create_task(process(job)))
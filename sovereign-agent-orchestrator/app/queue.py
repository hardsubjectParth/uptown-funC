import asyncio


async def run_worker(store, service):
    """Recover queued jobs after restart and process one job at a time."""
    while True:
        job = store.claim_next()
        if job is None:
            await asyncio.sleep(0.25)
            continue
        try:
            await service.run(job)
            store.finish_queue(job['job_id'], job.get('status') == 'failed')
        except Exception as exc:
            job['error'] = f'Worker failure: {exc}'
            job['status'] = 'failed'
            service._emit(job, 'worker_error', {'error': str(exc)})
            store.finish_queue(job['job_id'], True)
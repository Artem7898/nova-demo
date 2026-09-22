"""A bounded, in-process engine run. No orphan workers or cross-process task IDs."""

import asyncio

from nova.tasks.engine import NovaTaskEngine


async def execute_report(prices, *, retry=False):
    engine = NovaTaskEngine(max_concurrent=1)
    attempts = 0

    async def work():
        nonlocal attempts
        attempts += 1
        if retry and attempts == 1:
            raise ValueError("Controlled first-attempt failure")
        await asyncio.sleep(0)
        return {"products": len(prices), "total": str(sum(prices)), "attempts": attempts}

    await engine.start()
    try:
        task_id = engine.submit(work, max_retries=1 if retry else 0, retry_delay=0.01)
        await asyncio.wait_for(engine.stop(), timeout=5)
        result = engine.get_status(task_id)
        if result is None or result.status != "SUCCESS":
            raise RuntimeError("Task did not complete successfully")
        return result.model_dump(mode="json")
    finally:
        await engine.stop()

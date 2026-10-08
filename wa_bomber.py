import asyncio
from utils.logger import setup_logger

logger = setup_logger()

class WABomber:
    def __init__(self):
        self.name = "WhatsApp Bomber"

    async def bomb(self, phone, count=10, msg=None):
        msg = msg or "OTP Verification Code: 123456"
        sent = 0
        try:
            import pywhatkit
        except Exception as e:
            logger.error(f"[WA] pywhatkit missing: {e}")
            return 0
        for i in range(count):
            try:
                pywhatkit.sendwhatmsg_instantly(
                    f"+{phone.lstrip('+')}", msg,
                    wait_time=8, tab_close=True
                )
                sent += 1
                logger.info(f"[WA] {i+1}/{count} -> {phone}")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"[WA] {e}")
        return sent

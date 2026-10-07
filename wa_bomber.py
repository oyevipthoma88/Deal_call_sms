# wa_bomber.py
import pywhatkit
import time
import random
from utils.logger import setup_logger
from config import WA_MESSAGE, WA_COUNT

logger = setup_logger()

class WABomber:
    async def bomb(self, phone, count=10):
        """
        WhatsApp bombing via pywhatkit.
        Note: Ye browser automation use karta hai, isliye Termux mein
        X11/desktop environment chahiye ya headless browser setup.
        """
        messages = [
            "🔥 OTP: 123456",
            "✅ Verification code: 7890",
            "🚨 Alert: Login detected. OTP: 4321",
            "📩 New message: Click to verify",
        ]

        success = 0
        for i in range(count):
            try:
                msg = random.choice(messages)
                # 15 seconds baad message bhejta hai (WhatsApp Web load hone ke liye)
                pywhatkit.sendwhatmsg_instantly(
                    phone_no=phone,
                    message=msg,
                    wait_time=15,
                    tab_close=True
                )
                success += 1
                logger.info(f"WA message {i+1}/{count} sent to {phone}")
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"WA send failed: {e}")
        return success

#!/usr/bin/env python3
"""
BomberBridge - Connects bot to multiple free bombing tools
Supports: Tsunami-Bomber, Sms-Bomb, XBomber, android-sms-gateway, Fast2SMS, SMSLocal
"""
import asyncio
import os
import json
import subprocess
import logging
import httpx

logger = logging.getLogger(__name__)

# ============================================================
# CONFIG - .env se read hota hai
# ============================================================
FAST2SMS_KEY = os.getenv("FAST2SMS_KEY", "")
SMSLOCAL_KEY = os.getenv("SMSLOCAL_KEY", "")
SMSGATEWAYHUB_KEY = os.getenv("SMSGATEWAYHUB_KEY", "")

# Android SMS Gateway (sms-gate.app)
SMSGATE_USER = os.getenv("SMSGATE_USER", "")
SMSGATE_PASS = os.getenv("SMSGATE_PASS", "")
SMSGATE_DEVICE = os.getenv("SMSGATE_DEVICE", "")
SMSGATE_MODE = os.getenv("SMSGATE_MODE", "cloud")  # cloud, local, private

# Tool paths
TSUNAMI_PATH = os.getenv("TSUNAMI_PATH", "/root/Tsunami-Bomber/Tsunami.sh")
SMSBOMB_PATH = os.getenv("SMSBOMB_PATH", "/root/Sms-Bomb/main.py")
XBOMBER_PATH = os.getenv("XBOMBER_PATH", "/root/XBomber/xbomber.py")


# ============================================================
# LAYER 1: Fast2SMS (India, no DLT, 100% working)
# ============================================================
async def send_fast2sms(phone: str, message: str = "Test") -> bool:
    if not FAST2SMS_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={
                    "authorization": FAST2SMS_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "route": "q",
                    "message": message,
                    "numbers": phone.lstrip("+").lstrip("91")[-10:],
                    "flash": 0,
                },
            )
            data = r.json()
            return data.get("return", False) is True
    except Exception as e:
        logger.error(f"Fast2SMS error: {e}")
        return False


# ============================================================
# LAYER 2: SMSLocal (India, ₹60 free, no DLT)
# ============================================================
async def send_smslocal(phone: str, message: str = "Test") -> bool:
    if not SMSLOCAL_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                "https://app.smslocal.in/api/smsapi",
                headers={"Content-Type": "application/json"},
                json={
                    "apiKey": SMSLOCAL_KEY,
                    "senderId": "SMSLCL",
                    "to": phone.lstrip("+"),
                    "message": message,
                },
            )
            return r.status_code == 200
    except Exception as e:
        logger.error(f"SMSLocal error: {e}")
        return False


# ============================================================
# LAYER 3: SMSGatewayHub (India, 100 free credits, no DLT)
# ============================================================
async def send_smsgatewayhub(phone: str, message: str = "Test") -> bool:
    if not SMSGATEWAYHUB_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.get(
                "https://www.smsgatewayhub.com/api/mt/SendSMS",
                params={
                    "APIKey": SMSGATEWAYHUB_KEY,
                    "senderid": "SMSHUB",
                    "channel": "2",
                    "DCS": "0",
                    "flashsms": "0",
                    "number": phone.lstrip("+"),
                    "text": message,
                    "route": "1",
                },
            )
            return r.status_code == 200
    except Exception as e:
        logger.error(f"SMSGatewayHub error: {e}")
        return False


# ============================================================
# LAYER 4: Android SMS Gateway (sms-gate.app)
# 100% Free - Apna phone = gateway
# ============================================================
async def send_android_gateway(phone: str, message: str = "Test") -> bool:
    """Requires android-sms-gateway app installed on Android phone"""
    if not SMSGATE_USER or not SMSGATE_PASS:
        return False

    # API endpoint based on mode
    if SMSGATE_MODE == "cloud":
        base = "https://api.sms-gate.app/3rdparty/v1"
    elif SMSGATE_MODE == "local":
        base = os.getenv("SMSGATE_LOCAL_URL", "http://192.168.1.100:8080/3rdparty/v1")
    else:  # private
        base = os.getenv("SMSGATE_PRIVATE_URL", "")

    if not base:
        return False

    try:
        async with httpx.AsyncClient(timeout=20) as cli:
            # Send message
            payload = {
                "message": message,
                "phoneNumbers": [phone],
            }
            if SMSGATE_DEVICE:
                payload["deviceId"] = SMSGATE_DEVICE

            r = await cli.post(
                f"{base}/message",
                auth=(SMSGATE_USER, SMSGATE_PASS),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            return r.status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"Android Gateway error: {e}")
        return False


# ============================================================
# LAYER 5: Subprocess Tools (Tsunami, Sms-Bomb, XBomber)
# ============================================================
async def run_subprocess_tool(script_path: str, phone: str, count: int = 1) -> bool:
    """Run bash/python bombing tool with input"""
    if not os.path.exists(script_path):
        logger.warning(f"Tool not found: {script_path}")
        return False

    try:
        # Determine runner
        if script_path.endswith(".sh"):
            cmd = ["bash", script_path]
        elif script_path.endswith(".py"):
            cmd = ["python3", script_path]
        else:
            cmd = [script_path]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send input (number + count)
        input_data = f"{phone}\n{count}\n".encode()
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_data),
                timeout=60,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return False

        return proc.returncode == 0
    except Exception as e:
        logger.error(f"Subprocess tool error: {e}")
        return False


# ============================================================
# MASTER SENDER - Tries all layers
# ============================================================
async def send_sms_bridge(phone: str, message: str = "Test SMS") -> dict:
    """
    Try all available methods. Returns dict with results.
    """
    results = {
        "fast2sms": False,
        "smslocal": False,
        "smsgatewayhub": False,
        "android_gateway": False,
        "tsunami": False,
        "smsbomb": False,
        "xbomber": False,
    }

    # Layer 1-3: API-based (parallel)
    tasks = [
        ("fast2sms", send_fast2sms(phone, message)),
        ("smslocal", send_smslocal(phone, message)),
        ("smsgatewayhub", send_smsgatewayhub(phone, message)),
        ("android_gateway", send_android_gateway(phone, message)),
    ]
    for name, coro in tasks:
        try:
            results[name] = await coro
        except Exception as e:
            logger.error(f"{name} failed: {e}")

    # Layer 4-6: Subprocess tools (try one at a time)
    if not any(results.values()):
        if os.path.exists(TSUNAMI_PATH):
            results["tsunami"] = await run_subprocess_tool(TSUNAMI_PATH, phone, 10)
        if os.path.exists(SMSBOMB_PATH):
            results["smsbomb"] = await run_subprocess_tool(SMSBOMB_PATH, phone, 10)
        if os.path.exists(XBOMBER_PATH):
            results["xbomber"] = await run_subprocess_tool(XBOMBER_PATH, phone, 10)

    return results

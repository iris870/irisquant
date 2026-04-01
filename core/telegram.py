import httpx
import asyncio
import logging
import sys

# Constants for Telegram Bot
TOKEN = "8739557323:AAHiAQRgtrTG1iL7h0oy270LrN-JRyWSzdU"
CHAT_ID = "7177920417"

logger = logging.getLogger("telegram")

def send_alert(message: str):
    """Synchronous wrapper for sending alerts"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False

async def send_alert_async(message: str):
    """Asynchronous version for agents using asyncio"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        print(f"Failed to send Telegram alert (async): {e}")
        return False

if __name__ == "__main__":
    msg = "Test from IrisQuant Core"
    if len(sys.argv) > 1:
        msg = sys.argv[1]
    
    print(f"Sending test message: {msg}")
    test_msg = "<b>[IrisQuant Test]</b>
" + msg
    if send_alert(test_msg):
        print("Success")
    else:
        print("Failed")

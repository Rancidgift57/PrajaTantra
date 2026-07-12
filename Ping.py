import os
import requests
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

def run_ping():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    # Night mode (optional tweak)
    if now.hour >= 1 and now.hour < 6:
        print(f"[{now.strftime('%H:%M:%S')}] Night mode active. Skipping.")
        return

    url = os.getenv("RENDER_URL", "https://edurpg.onrender.com")

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1",
        "Mozilla/5.0 (Linux; Android 10; SM-A505F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]

    headers = {'User-Agent': random.choice(user_agents)}

    # Random delay
    time.sleep(random.uniform(0, 60))

    # Update time AFTER delay
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            print(f"[{now.strftime('%H:%M:%S')}] Ping Success: {response.status_code}")
            break
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_ping()

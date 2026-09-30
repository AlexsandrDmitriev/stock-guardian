import asyncio
import json
import subprocess
import urllib.request

import websockets

USER_ID = "12345678-1234-5678-1234-567812345678"
API = "http://localhost:8080"


async def main():
    async with websockets.connect(f"ws://localhost:8080/ws/{USER_ID}") as ws:
        print("WebSocket connected")

        # Create alert (NVDA stub returns 1000, target=1000 triggers "above")
        payload = json.dumps({
            "symbol": "NVDA",
            "target_price": 1000,
            "direction": "above",
            "user_id": USER_ID,
        }).encode()
        req = urllib.request.Request(
            f"{API}/alerts",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req)
        print("Alert created:", resp.read().decode()[:60], "...")

        # Trigger worker task manually
        subprocess.run([
            "docker", "exec", "stock-guardian-api-1",
            "python", "-c",
            "from app.workers.quotes import check_alerts; check_alerts.delay()",
        ], timeout=10)
        print("Task triggered, waiting for notification...")

        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            print("NOTIFY:", msg)
        except asyncio.TimeoutError:
            print("No notification received within 10s")


asyncio.run(main())
import asyncio
import json
import urllib.request

import websockets

USER_ID = "12345678-1234-5678-1234-567812345678"
API = "http://localhost:8080"


async def main():
    ws_url = f"ws://localhost:8080/ws/{USER_ID}"
    print(f"Connecting to {ws_url}...")

    async with websockets.connect(ws_url) as ws:
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
        alert = json.loads(resp.read())
        print(f"Alert created: {alert['id']}")

        # Trigger check_alerts via HTTP debug endpoint
        trigger_req = urllib.request.Request(
            f"{API}/debug/trigger",
            method="POST",
        )
        resp = urllib.request.urlopen(trigger_req)
        result = json.loads(resp.read())
        print(f"Trigger: {result['status']}")

        # Wait for notification via WebSocket
        print("Waiting for notification...")
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            print(f"NOTIFY: {msg}")
        except asyncio.TimeoutError:
            print("TIMEOUT — no notification received")


asyncio.run(main())
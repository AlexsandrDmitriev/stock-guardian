import asyncio
import json
import sys

import websockets


async def main() -> None:
    user_id = sys.argv[1] if len(sys.argv) > 1 else "12345678-1234-5678-1234-567812345678"
    uri = f"ws://localhost:8080/ws/{user_id}"
    async with websockets.connect(uri) as ws:
        print("Connected. Waiting for notifications...")
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                print("NOTIFY:", msg)
            except asyncio.TimeoutError:
                print("Timeout — no message")
                break


asyncio.run(main())
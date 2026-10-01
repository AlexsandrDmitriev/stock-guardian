import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 1.0


@router.websocket("/ws/{user_id}")
async def alerts_ws(ws: WebSocket, user_id: str) -> None:
    await ws.accept()
    redis = ws.app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe(user_id)
    logger.info("WS connected for user %s", user_id)

    async def watch_disconnect() -> None:
        while True:
            await ws.receive_text()

    watcher = asyncio.create_task(watch_disconnect())
    try:
        while not watcher.done():
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=_POLL_TIMEOUT,
            )
            if msg is None:
                continue
            data = msg["data"]
            await ws.send_text(data if isinstance(data, str) else data.decode())
            logger.info("WS message delivered to user %s", user_id)
    except (WebSocketDisconnect, RuntimeError) as exc:
        logger.info("WS closed for user %s: %s", user_id, exc)
    finally:
        watcher.cancel()
        with contextlib.suppress(Exception):
            await watcher
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(user_id)
        with contextlib.suppress(Exception):
            await pubsub.aclose()
        logger.info("WS cleanup done for user %s", user_id)

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{user_id}")
async def alerts_ws(ws: WebSocket, user_id: str) -> None:
    await ws.accept()
    redis = ws.app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe(user_id)
    try:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                data = msg["data"]
                await ws.send_text(data if isinstance(data, str) else data.decode())
    except WebSocketDisconnect:
        await pubsub.unsubscribe(user_id)
    finally:
        await pubsub.close()
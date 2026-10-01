import asyncio
import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

USER_ID = "12345678-1234-5678-1234-567812345678"


def test_debug_trigger_reports_success(client: TestClient) -> None:
    with patch("app.workers.quotes.check_alerts", return_value=None):
        resp = client.post("/debug/trigger")
    assert resp.status_code == 200
    assert resp.json() == {"status": "triggered"}


def test_debug_trigger_returns_500_on_failure(client: TestClient) -> None:
    with patch("app.workers.quotes.check_alerts", side_effect=RuntimeError("redis down")):
        resp = client.post("/debug/trigger")
    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == "error"
    assert "redis down" in body["detail"]


def test_debug_prices_reports_stored_quotes(client: TestClient, mock_redis) -> None:
    mock_redis.hgetall = AsyncMock(return_value={"NVDA": "997.42"})
    resp = client.get("/debug/prices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["prices"] == {"NVDA": "997.42"}


def test_debug_prices_never_run(client: TestClient) -> None:
    resp = client.get("/debug/prices")
    assert resp.status_code == 200
    body = resp.json()
    assert body["prices"] == {}
    assert body["last_check_age_seconds"] is None


def test_websocket_closes_cleanly_on_client_disconnect(client: TestClient) -> None:
    with client.websocket_connect(f"/ws/{USER_ID}") as ws:
        ws.send_text("ping")


def test_websocket_delivers_published_alert(client: TestClient, mock_redis) -> None:
    payload = json.dumps(
        {
            "alert_id": "35c4e14c-49f4-48bc-857b-c6b2b9f94d05",
            "symbol": "NVDA",
            "price": 1001.5,
            "target_price": 1000.0,
            "direction": "above",
        }
    )
    pubsub = mock_redis.pubsub()

    async def get_message(*args, **kwargs):
        if pubsub.get_message.await_count == 1:
            return {"type": "message", "data": payload}
        await asyncio.sleep(0.05)
        return None

    pubsub.get_message = AsyncMock(side_effect=get_message)

    with client.websocket_connect(f"/ws/{USER_ID}") as ws:
        ws.send_text("ping")
        assert json.loads(ws.receive_text())["symbol"] == "NVDA"

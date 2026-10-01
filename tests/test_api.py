from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_alert(client: TestClient) -> None:
    resp = client.post(
        "/alerts",
        json={
            "symbol": "NVDA",
            "target_price": 1000,
            "direction": "above",
            "user_id": "12345678-1234-5678-1234-567812345678",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["symbol"] == "NVDA"
    assert data["target_price"] == 1000
    assert data["direction"] == "above"


def test_list_alerts(client: TestClient) -> None:
    resp = client.get("/alerts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_delete_alert(client: TestClient) -> None:
    alert_id = uuid4()
    resp = client.delete(f"/alerts/{alert_id}")
    assert resp.status_code == 204
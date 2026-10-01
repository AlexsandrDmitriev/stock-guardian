import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


async def _poll(*_args, **_kwargs):
    await asyncio.sleep(0.01)


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.aclose = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.hset = AsyncMock()
    redis.hdel = AsyncMock()
    redis.publish = AsyncMock()
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    pubsub.get_message = AsyncMock(side_effect=_poll)
    redis.pubsub = lambda: pubsub
    return redis


@pytest.fixture
def client(mock_redis):
    with patch("app.main.Redis.from_url", return_value=mock_redis), TestClient(app) as c:
        yield c
import json
from uuid import UUID

from redis.asyncio import Redis

from app.core.models import Alert


class AlertService:
    """Manages alerts in Redis so API and Celery worker share state."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._key = "stock_guardian:alerts"

    async def create(self, alert: Alert) -> Alert:
        await self._redis.hset(self._key, str(alert.id), alert.model_dump_json())
        return alert

    async def list_active(self) -> list[Alert]:
        raw = await self._redis.hgetall(self._key)
        return [Alert.model_validate_json(v) for v in raw.values()]

    async def deactivate(self, alert_id: UUID) -> None:
        await self._redis.hdel(self._key, str(alert_id))

    async def get_active_by_user(self, user_id: UUID) -> list[Alert]:
        alerts = await self.list_active()
        return [a for a in alerts if a.user_id == user_id]

    async def load_active_alerts(self) -> list[Alert]:
        return await self.list_active()
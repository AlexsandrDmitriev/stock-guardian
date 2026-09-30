import asyncio
import json
import logging

from celery import Celery
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


app = Celery(
    "stock_guardian",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["app.workers.quotes"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-alerts-every-30-seconds": {
            "task": "app.workers.quotes.check_alerts",
            "schedule": 30.0,
        },
    },
)


def fetch_batch_prices() -> dict[str, float]:
    """Stub: replace with real broker API call."""
    return {"NVDA": 1000.0, "AAPL": 200.0, "MSFT": 300.0}


async def _load_active_alerts() -> list:
    """Load active alerts from Redis (shared with API)."""
    from app.services.alert_service import AlertService

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        service = AlertService(redis)
        alerts = await service.load_active_alerts()
        logger.info("Loaded %d active alerts from Redis", len(alerts))
        return alerts
    finally:
        await redis.aclose()


async def _deactivate(alert_id) -> None:
    """Mark alert as inactive in Redis."""
    from app.services.alert_service import AlertService

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        service = AlertService(redis)
        await service.deactivate(alert_id)
    finally:
        await redis.aclose()


@app.task(name="app.workers.quotes.check_alerts")
def check_alerts() -> None:
    quotes = fetch_batch_prices()
    logger.info("check_alerts started, quotes=%s", quotes)

    async def run() -> None:
        alerts = await _load_active_alerts()
        pub = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            for alert in alerts:
                price = quotes.get(alert.symbol)
                if price is None:
                    continue
                hit = (
                    price >= alert.target_price
                    if alert.direction == "above"
                    else price <= alert.target_price
                )
                if hit:
                    logger.info(
                        "Alert %s triggered: %s hit %s", alert.id, alert.symbol, price
                    )
                    await pub.publish(
                        str(alert.user_id),
                        json.dumps({"symbol": alert.symbol, "price": price}),
                    )
                    await _deactivate(alert.id)
                else:
                    logger.info(
                        "Alert %s not triggered: %s=%s target=%s",
                        alert.id, alert.symbol, price, alert.target_price,
                    )
        finally:
            await pub.aclose()

    asyncio.run(run())
    logger.info("check_alerts finished")

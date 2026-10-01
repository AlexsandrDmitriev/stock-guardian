import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

from celery import Celery
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

LAST_CHECK_FILE = os.environ.get(
    "LAST_CHECK_FILE", str(Path(tempfile.gettempdir()) / "stock_guardian_last_check")
)


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
    """Fetch current quotes with simulated price movement.
    
    In production, replace with a real broker API call.
    Prices are stored in Redis and drift slightly each call,
    so alerts trigger automatically as prices cross thresholds.
    """
    from random import uniform

    import redis as sync_redis

    base_prices = {"NVDA": 995.0, "AAPL": 195.0, "MSFT": 295.0}
    r = sync_redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        current = r.hgetall("stock_guardian:prices")
        quotes: dict[str, float] = {}
        for symbol, base in base_prices.items():
            price = float(current[symbol]) if symbol in current else base
            # Symmetric random walk so thresholds are crossed in both directions.
            price += uniform(-1.5, 1.5)
            quotes[symbol] = round(max(price, 0.01), 2)
        r.hset("stock_guardian:prices", mapping={k: str(v) for k, v in quotes.items()})
        logger.info("Quotes fetched: %s", quotes)
        return quotes
    finally:
        r.close()


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
                        json.dumps(
                            {
                                "alert_id": str(alert.id),
                                "symbol": alert.symbol,
                                "price": price,
                                "target_price": alert.target_price,
                                "direction": alert.direction,
                            }
                        ),
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
    Path(LAST_CHECK_FILE).touch()
    logger.info("check_alerts finished")

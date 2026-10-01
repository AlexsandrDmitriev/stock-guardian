import asyncio
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.api.alerts import router as alerts_router
from app.api.ws import router as ws_router
from app.core.config import settings

app = FastAPI(title="Stock Guardian", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(alerts_router)
app.include_router(ws_router)


@app.get("/", response_class=HTMLResponse)
async def root() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.on_event("startup")
async def startup() -> None:
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await app.state.redis.ping()


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.redis.aclose()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/debug/redis")
async def debug_redis(request: Request) -> dict:
    redis = request.app.state.redis
    info: dict[str, object] = {
        "redis_url_configured": bool(settings.redis_url),
        "broker_url_configured": bool(settings.broker_url),
        "result_backend_configured": bool(settings.result_backend),
        "database_url_configured": bool(settings.database_url),
    }
    try:
        await redis.ping()
        info["redis_ping"] = "ok"
    except Exception as e:  # noqa: BLE001 - debug endpoint must never 500 silently
        info["redis_ping"] = f"error: {e}"

    from app.services.alert_service import AlertService
    service = AlertService(redis)
    alerts = await service.list_active()
    info["active_alerts_count"] = len(alerts)
    return info


@app.get("/debug/prices")
async def debug_prices(request: Request) -> dict:
    """Last prices written by the checker — reveals a stale/missing scheduler."""
    redis = request.app.state.redis
    try:
        prices = await redis.hgetall("stock_guardian:prices")
    except Exception as e:  # noqa: BLE001 - surface the driver error to the caller
        return {"error": f"{type(e).__name__}: {e}"}
    return {
        "prices": prices,
        "last_check_age_seconds": _last_check_age_seconds(),
    }


def _last_check_age_seconds() -> float | None:
    from app.workers.quotes import LAST_CHECK_FILE

    try:
        mtime = os.path.getmtime(LAST_CHECK_FILE)
    except OSError:
        return None
    return round(time.time() - mtime, 1)


@app.post("/debug/trigger")
async def debug_trigger() -> JSONResponse:
    from app.workers.quotes import check_alerts

    try:
        await asyncio.to_thread(check_alerts)
    except Exception as e:  # noqa: BLE001 - any checker failure must become a 500
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"{type(e).__name__}: {e}"},
        )
    return JSONResponse(content={"status": "triggered"})
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
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
async def root() -> HTMLResponse:
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
    info = {
        "redis_url_configured": bool(settings.redis_url),
        "broker_url_configured": bool(settings.broker_url),
        "result_backend_configured": bool(settings.result_backend),
        "database_url_configured": bool(settings.database_url),
    }
    try:
        await redis.ping()
        info["redis_ping"] = "ok"
    except Exception as e:
        info["redis_ping"] = f"error: {e}"

    from app.services.alert_service import AlertService
    service = AlertService(redis)
    alerts = await service.list_active()
    info["active_alerts_count"] = len(alerts)
    return info


@app.post("/debug/trigger")
async def debug_trigger() -> dict:
    from app.workers.quotes import check_alerts
    import asyncio

    try:
        await asyncio.to_thread(check_alerts)
        return {"status": "triggered"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
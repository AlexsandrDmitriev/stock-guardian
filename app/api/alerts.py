from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from app.core.models import Alert
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    symbol: str
    target_price: float
    direction: str  # "above" | "below"
    user_id: UUID


class AlertResponse(BaseModel):
    id: UUID
    symbol: str
    target_price: float
    direction: str
    user_id: UUID


def get_alert_service(request: Request) -> AlertService:
    return AlertService(request.app.state.redis)


AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(payload: AlertCreate, service: AlertServiceDep) -> Alert:
    alert = Alert(**payload.model_dump())
    return await service.create(alert)


@router.get("", response_model=list[AlertResponse])
async def list_alerts(service: AlertServiceDep) -> list[Alert]:
    return await service.list_active()


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: UUID, service: AlertServiceDep) -> None:
    await service.deactivate(alert_id)
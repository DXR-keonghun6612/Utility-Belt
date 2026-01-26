from typing import List, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.automation.scheduler import AutomationManager
from web.dependencies import get_automation_manager, get_current_user_id

router = APIRouter(prefix="/automation", tags=["Automation"])

class RecurringTxCreateRequest(BaseModel):
    name: str
    day_of_month: int
    description: str
    debits: List[Dict[str, Any]]
    credits: List[Dict[str, Any]]

class RecurringTxResponse(BaseModel):
    id: str
    name: str
    day_of_month: int
    last_run_date: date | None
    is_active: int

    class Config:
        from_attributes = True

class RunTaskRequest(BaseModel):
    target_date: date

@router.post("/recurring", response_model=RecurringTxResponse)
def create_recurring_transaction(
    req: RecurringTxCreateRequest,
    automation: AutomationManager = Depends(get_automation_manager),
    user_id: str = Depends(get_current_user_id)
):
    task = automation.create_recurring_tx(
        user_id=user_id,
        name=req.name,
        day_of_month=req.day_of_month,
        description=req.description,
        debits=req.debits,
        credits=req.credits
    )
    return task

@router.post("/run")
def run_daily_tasks(
    req: RunTaskRequest,
    automation: AutomationManager = Depends(get_automation_manager)
):
    """
    수동 트리거: 특정 날짜의 스케줄을 즉시 실행합니다.
    (실제 운영 시에는 시스템 크론잡이 이 API를 호출하거나 내부 함수를 실행해야 함)
    """
    results = automation.process_daily_tasks(req.target_date)
    return {"results": results}

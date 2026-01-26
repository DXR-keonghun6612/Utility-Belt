from typing import List, Optional
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.finance.service import FinanceManager
from web.dependencies import get_finance_manager, get_current_user_id

router = APIRouter(prefix="/finance", tags=["Finance (Advanced)"])

# --- Installments Schemas ---

class InstallmentCreateRequest(BaseModel):
    date: date
    description: str
    asset_account_code: str
    liability_account_code: str
    total_amount: Decimal
    months: int
    card_name: str

class InstallmentPaymentRequest(BaseModel):
    date: date
    payment_account_code: str 

class InstallmentResponse(BaseModel):
    id: str
    card_name: str
    description: str
    total_months: int
    current_month: int
    monthly_amount: Decimal
    total_amount: Decimal
    is_completed: bool
    
    class Config:
        from_attributes = True

# --- Stocks Schemas ---

class StockBuyRequest(BaseModel):
    date: date
    ticker: str
    name: str
    quantity: Decimal
    unit_price: Decimal
    asset_account_code: str
    payment_account_code: str

class StockSellRequest(BaseModel):
    date: date
    ticker: str
    quantity: Decimal
    unit_price: Decimal
    asset_account_code: str
    deposit_account_code: str
    income_account_code: str
    expense_account_code: str

class StockLotResponse(BaseModel):
    id: str
    ticker: str
    name: str
    remaining_quantity: Decimal
    unit_price: Decimal
    buy_date: date
    is_sold_out: bool

    class Config:
        from_attributes = True

# --- Group Dues Schemas ---

class DueAssignRequest(BaseModel):
    date: date
    member_name: str
    description: str
    amount: Decimal
    receivable_account_code: str # 미수금
    revenue_account_code: str # 수익
    due_date: Optional[date] = None

class DueCollectRequest(BaseModel):
    date: date
    deposit_account_code: str # 입금 계좌

class DueResponse(BaseModel):
    id: str
    member_name: str
    description: str
    amount: Decimal
    due_date: Optional[date]
    is_paid: bool

    class Config:
        from_attributes = True


# --- Endpoints ---

# ... (Installment & Stock Endpoints are skipped but preserved)
@router.post("/installments", response_model=InstallmentResponse)
def create_installment(
    req: InstallmentCreateRequest,
    finance: FinanceManager = Depends(get_finance_manager),
    user_id: str = Depends(get_current_user_id)
):
    try:
        plan = finance.create_installment(
            user_id=user_id,
            date=req.date,
            description=req.description,
            asset_account_code=req.asset_account_code,
            liability_account_code=req.liability_account_code,
            total_amount=req.total_amount,
            months=req.months,
            card_name=req.card_name
        )
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/installments/{plan_id}/payment")
def pay_installment(
    plan_id: str,
    req: InstallmentPaymentRequest,
    finance: FinanceManager = Depends(get_finance_manager),
    user_id: str = Depends(get_current_user_id)
):
    try:
        finance.process_installment_payment(
            user_id=user_id,
            plan_id=plan_id,
            payment_date=req.date,
            payment_account_code=req.payment_account_code
        )
        return {"status": "success", "message": "Payment processed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stocks/buy", response_model=StockLotResponse)
def buy_stock(
    req: StockBuyRequest,
    finance: FinanceManager = Depends(get_finance_manager),
    user_id: str = Depends(get_current_user_id)
):
    try:
        lot = finance.buy_stock(
            user_id=user_id,
            date=req.date,
            ticker=req.ticker,
            name=req.name,
            quantity=req.quantity,
            unit_price=req.unit_price,
            asset_account_code=req.asset_account_code,
            payment_account_code=req.payment_account_code
        )
        return lot
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stocks/sell")
def sell_stock(
    req: StockSellRequest,
    finance: FinanceManager = Depends(get_finance_manager),
    user_id: str = Depends(get_current_user_id)
):
    try:
        finance.sell_stock(
            user_id=user_id,
            date=req.date,
            ticker=req.ticker,
            quantity=req.quantity,
            unit_price=req.unit_price,
            asset_account_code=req.asset_account_code,
            deposit_account_code=req.deposit_account_code,
            income_account_code=req.income_account_code,
            expense_account_code=req.expense_account_code
        )
        return {"status": "success", "message": "Stock sold successfully (FIFO applied)"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Dues Endpoints ---

@router.post("/dues", response_model=DueResponse)
def assign_due(
    req: DueAssignRequest,
    finance: FinanceManager = Depends(get_finance_manager),
    user_id: str = Depends(get_current_user_id)
):
    try:
        due = finance.assign_due(
            user_id=user_id,
            date=req.date,
            member_name=req.member_name,
            description=req.description,
            amount=req.amount,
            receivable_account_code=req.receivable_account_code,
            revenue_account_code=req.revenue_account_code,
            due_date=req.due_date
        )
        return due
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/dues/{due_id}/payment")
def collect_due(
    due_id: str,
    req: DueCollectRequest,
    finance: FinanceManager = Depends(get_finance_manager),
    user_id: str = Depends(get_current_user_id)
):
    try:
        finance.collect_due(
            user_id=user_id,
            due_id=due_id,
            payment_date=req.date,
            deposit_account_code=req.deposit_account_code
        )
        return {"status": "success", "message": "Due collected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
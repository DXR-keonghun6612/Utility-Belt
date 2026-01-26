from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.accounting.ledger import Ledger
from core.finance.service import FinanceManager

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_ledger(db: Session = Depends(get_db)) -> Ledger:
    return Ledger(db)

def get_finance_manager(db: Session = Depends(get_db), ledger: Ledger = Depends(get_ledger)) -> FinanceManager:
    return FinanceManager(db, ledger)

def get_current_user_id(x_user_id: str = Header(..., description="User ID for Multi-tenancy (Mock Auth)")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    return x_user_id

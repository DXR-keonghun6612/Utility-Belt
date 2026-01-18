from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.accounting.ledger import Ledger

def get_db() -> Generator[Session, None, None]:
    """
    DB 세션 생성 및 종료 관리
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_ledger(db: Session = Depends(get_db)) -> Ledger:
    """
    Ledger 인스턴스 주입
    """
    return Ledger(db)

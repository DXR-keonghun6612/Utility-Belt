from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from core.database import Base

class InstallmentPlanModel(Base):
    """
    신용카드 할부 관리 테이블
    (발생주의: 결제 시점에 부채 전액 인식 후, 매월 상환)
    """
    __tablename__ = "installment_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True) # Multi-tenancy

    # 최초 할부 결제 트랜잭션 (부채 발생 거래)
    origin_tx_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    
    card_name = Column(String, nullable=False)  # 카드사 이름 (예: 삼성카드)
    description = Column(String, nullable=False) # 할부 내용 (예: 맥북 할부)
    
    total_months = Column(Integer, nullable=False) # 총 할부 개월 수 (예: 10)
    current_month = Column(Integer, default=0)     # 현재 납부 완료한 회차 (예: 1)
    
    monthly_amount = Column(Numeric(precision=15, scale=2), nullable=False) # 월 납부액
    total_amount = Column(Numeric(precision=15, scale=2), nullable=False)   # 총 금액
    
    start_date = Column(Date, nullable=False) # 할부 시작일
    is_completed = Column(Boolean, default=False) # 완납 여부

    created_at = Column(DateTime, default=datetime.utcnow)


class StockLotModel(Base):
    """
    주식/코인 개별 매수분 (Lot) 관리 테이블
    (수익률 계산 및 선입선출 관리를 위함)
    """
    __tablename__ = "stock_lots"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True) # Multi-tenancy

    # 매수 트랜잭션 ID
    buy_tx_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    
    ticker = Column(String, nullable=False) # 종목 코드 (예: AAPL, BTC)
    name = Column(String, nullable=True)    # 종목명 (예: Apple Inc.)
    
    initial_quantity = Column(Numeric(precision=15, scale=8), nullable=False) # 최초 매수 수량 (코인은 소수점 가능)
    remaining_quantity = Column(Numeric(precision=15, scale=8), nullable=False) # 현재 보유 수량
    
    unit_price = Column(Numeric(precision=15, scale=4), nullable=False) # 매수 단가
    
    currency = Column(String, default="KRW") # 통화 (KRW, USD)
    
    buy_date = Column(Date, nullable=False)
    is_sold_out = Column(Boolean, default=False) # 전량 매도 여부

    created_at = Column(DateTime, default=datetime.utcnow)


class GroupDueModel(Base):
    """
    그룹 회비/분담금 관리 테이블
    (미수금 관리: 부과 시점에 자산 인식, 납부 시점에 자산 감소)
    """
    __tablename__ = "group_dues"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True) # 그룹 ID (Ledger Scope)

    # 회비 부과 트랜잭션 ID (미수금 발생)
    claim_tx_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    
    member_name = Column(String, nullable=False) # 멤버 이름 (또는 ID)
    description = Column(String, nullable=False) # 내용 (예: 1월 회비)
    amount = Column(Numeric(precision=15, scale=2), nullable=False) # 청구 금액
    
    due_date = Column(Date, nullable=True) # 납부 기한
    is_paid = Column(Boolean, default=False) # 납부 완료 여부
    paid_at = Column(DateTime, nullable=True) # 납부 일시

    created_at = Column(DateTime, default=datetime.utcnow)
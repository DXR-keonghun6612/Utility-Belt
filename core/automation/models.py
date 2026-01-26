from sqlalchemy import Column, String, Integer, Numeric, Date, ForeignKey, JSON
import uuid
from core.database import Base

class RecurringTransactionModel(Base):
    """
    반복 거래(정기 구독, 고정 지출) 템플릿
    """
    __tablename__ = "recurring_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False, index=True)

    name = Column(String, nullable=False) # 예: 넷플릭스 구독
    cron_expression = Column(String, nullable=False) # 예: "0 0 1 * *" (매월 1일)
    # 편의상 '매월 n일'만 지원하려면 integer day 컬럼을 써도 됨
    day_of_month = Column(Integer, nullable=True) # 1~31

    # 거래 템플릿 (JSON으로 저장)
    # {
    #   "description": "넷플릭스 결제",
    #   "debits": [{"code": "5001", "amount": 17000}],
    #   "credits": [{"code": "2100", "amount": 17000}]
    # }
    template = Column(JSON, nullable=False)
    
    last_run_date = Column(Date, nullable=True)
    is_active = Column(Integer, default=1) # Boolean 대신 Integer 사용 (SQLite 호환)

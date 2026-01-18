from sqlalchemy import Column, String, Integer, Date, ForeignKey, Enum, Numeric, Text
from sqlalchemy.orm import relationship
import uuid

from core.database import Base
from core.accounting.typing import Account_Type, Account_Side

class AccountModel(Base):
    __tablename__ = "accounts"

    code = Column(String, primary_key=True, index=True) # 계정 코드 (예: '1001')
    name = Column(String, nullable=False)
    category = Column(Enum(Account_Type), nullable=False) # ASSET, LIABILITY...
    side = Column(Enum(Account_Side), nullable=False)     # DEBIT/CREDIT
    description = Column(String, nullable=True)

    # Relationship
    entries = relationship("JournalEntryModel", back_populates="account")


class TransactionModel(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False) # 적요
    
    # 추후 assets, geo 모듈과 연동될 FK (지금은 단순 String 처리하거나 생략 가능)
    evidence_id = Column(String, nullable=True)
    location_id = Column(String, nullable=True)

    # Relationship
    # cascade="all, delete-orphan": 트랜잭션 삭제 시 연결된 분개들도 같이 삭제됨
    entries = relationship("JournalEntryModel", back_populates="transaction", cascade="all, delete-orphan")


class JournalEntryModel(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    account_code = Column(String, ForeignKey("accounts.code"), nullable=False)
    
    side = Column(Enum(Account_Side), nullable=False) # DEBIT / CREDIT
    amount = Column(Numeric(precision=15, scale=2), nullable=False) # 금액 (Decimal)
    description = Column(String, nullable=True) # 라인별 적요

    # Relationship
    transaction = relationship("TransactionModel", back_populates="entries")
    account = relationship("AccountModel", back_populates="entries")

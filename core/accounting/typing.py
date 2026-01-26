from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import date
from decimal import Decimal

class Account_Side(Enum):
    """
    계정의 잔액이 증가하는 방향 (차변/대변)
    """
    DEBIT = "DEBIT"   # 차변 (왼쪽)
    CREDIT = "CREDIT" # 대변 (오른쪽)

class Account_Type(Enum):
    """
    복식부기 4대 핵심 요소
    """
    ASSET = "ASSET"             # 자산
    LIABILITY = "LIABILITY"     # 부채
    EQUITY = "EQUITY"           # 자본
    NOMINAL = "NOMINAL"         # 명목 계정 (수익/비용 등)

@dataclass
class Account:
    """
    모든 계정 과목의 기본 클래스 (Base Account)
    """
    code: str           # 계정 코드 (예: '1001')
    name: str           # 계정 명칭 (예: '현금')
    category: Account_Type # 계정 유형 (자산/부채/자본/명목)
    side: Account_Side  # 계정의 잔액 증가 방향 (차변/대변)
    owner_id: str       # 소유자 ID (Multi-tenancy)
    id: Optional[str] = None # DB 내부 ID (Optional)
    description: str | None = None # 설명
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "code": self.code,
            "name": self.name,
            "category": self.category.value,
            "side": self.side.value,
            "description": self.description
        }

@dataclass
class Journal_Entry:
    """
    분개 (Journal Entry):
    거래의 한 줄을 구성하는 최소 단위입니다.
    """
    account_code: str       # 계정 코드 (Display용)
    side: Account_Side      # 차변/대변
    amount: Decimal         # 금액 (항상 양수여야 함)
    description: str| None = None # 적요
    
    # DB 조회 시 채워질 수 있음
    account_name: str | None = None 

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "side": self.side.value,
            "amount": str(self.amount),
            "description": self.description
        }

@dataclass
class Transaction:
    """
    거래 (Transaction):
    복식부기 원칙에 따라 발생한 하나의 재무적 사건입니다.
    """
    id: str                 # 거래 고유 ID (UUID)
    owner_id: str           # 소유자 ID
    date: date              # 거래 발생일
    description: str        # 거래 설명 (적요)
    debits: List[Journal_Entry] = field(default_factory=list)  # 차변 분개 리스트
    credits: List[Journal_Entry] = field(default_factory=list) # 대변 분개 리스트
    
    evidence_id: str| None = None # 증빙 자료 ID (core.assets)
    location_id: str| None = None # 위치 정보 ID (core.geo)

    @property
    def is_balanced(self) -> bool:
        debit_sum = sum(entry.amount for entry in self.debits)
        credit_sum = sum(entry.amount for entry in self.credits)
        return debit_sum == credit_sum

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "date": self.date.isoformat(),
            "description": self.description,
            "debits": [entry.to_dict() for entry in self.debits],
            "credits": [entry.to_dict() for entry in self.credits],
            "evidence_id": self.evidence_id,
            "location_id": self.location_id
        }
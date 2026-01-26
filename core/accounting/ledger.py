from typing import Dict, List, Optional
from datetime import date
from uuid import uuid4
from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

# Submodule Import
from python_toolbox.file import Process

from .typing import (
    Account, Account_Side, Account_Type,
    Transaction, Journal_Entry
)
from .models import AccountModel, TransactionModel, JournalEntryModel

class Ledger:
    """
    원장 (General Ledger):
    모든 계정 과목과 거래 내역을 관리하는 핵심 컨트롤러입니다.
    SQLAlchemy Session을 통해 DB와 상호작용합니다.
    모든 작업은 user_id(owner_id)를 기준으로 격리됩니다.
    """
    def __init__(self, db: Session):
        self.db = db

    # --- 계정 관리 (Chart of Accounts) ---
    
    def add_account(self, user_id: str, account: Account) -> Account:
        """
        새로운 계정 과목을 DB에 등록합니다. (User Scope)
        """
        # DTO에서 넘어온 owner_id가 없으면 user_id로 덮어씌움 (안전장치)
        if not account.owner_id:
            account.owner_id = user_id
            
        if account.owner_id != user_id:
            raise ValueError("Account owner_id does not match the requesting user_id.")

        db_account = AccountModel(
            owner_id=user_id,
            code=account.code,
            name=account.name,
            category=account.category,
            side=account.side,
            description=account.description
        )
        try:
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_account)
        except IntegrityError:
            self.db.rollback()
            raise ValueError(f"Account code '{account.code}' already exists for this user.")
        
        # ID 업데이트 후 반환
        account.id = db_account.id
        return account

    def get_account(self, user_id: str, code: str) -> Account:
        """
        DB에서 계정을 조회하여 DTO로 반환합니다. (User Scope)
        """
        db_account = self.db.query(AccountModel).filter(
            AccountModel.owner_id == user_id,
            AccountModel.code == code
        ).first()
        
        if not db_account:
            raise ValueError(f"Account code '{code}' not found for user '{user_id}'.")
        
        return Account(
            id=db_account.id,
            owner_id=db_account.owner_id,
            code=db_account.code,
            name=db_account.name,
            category=db_account.category,
            side=db_account.side,
            description=db_account.description
        )

    # --- 트랜잭션 기록 (Journalizing) ---

    def record_transaction(
        self, 
        user_id: str,
        tx_date: date, 
        description: str, 
        debits: List[Dict], # [{'code': '1001', 'amount': 10000}, ...]
        credits: List[Dict], # [{'code': '2001', 'amount': 10000}, ...]
        evidence_id: Optional[str] = None,
        location_id: Optional[str] = None
    ) -> Transaction:
        """
        새로운 거래를 기록합니다.
        대차평형을 검증한 뒤 DB에 저장합니다.
        """
        
        tx_id = str(uuid4())
        
        new_tx_model = TransactionModel(
            id=tx_id,
            owner_id=user_id,
            date=tx_date,
            description=description,
            evidence_id=evidence_id,
            location_id=location_id
        )

        entries_to_add = []
        
        total_debit = Decimal('0')
        total_credit = Decimal('0')

        # 계정 코드 캐싱 (한 트랜잭션 내 동일 계정 반복 사용 시 DB 조회 최소화)
        account_map = {} # code -> AccountModel

        def get_account_model(code: str) -> AccountModel:
            if code not in account_map:
                acc = self.db.query(AccountModel).filter(
                    AccountModel.owner_id == user_id,
                    AccountModel.code == code
                ).first()
                if not acc:
                    raise ValueError(f"Account code '{code}' not found.")
                account_map[code] = acc
            return account_map[code]

        # 2. 차변(Debits) 처리
        for item in debits:
            acc = get_account_model(item['code'])
            
            amount = Decimal(str(item['amount']))
            total_debit += amount
            
            entries_to_add.append(JournalEntryModel(
                account_id=acc.id, # FK는 UUID 사용
                side=Account_Side.DEBIT,
                amount=amount,
                description=item.get('description')
            ))

        # 3. 대변(Credits) 처리
        for item in credits:
            acc = get_account_model(item['code'])
            
            amount = Decimal(str(item['amount']))
            total_credit += amount
            
            entries_to_add.append(JournalEntryModel(
                account_id=acc.id, # FK는 UUID 사용
                side=Account_Side.CREDIT,
                amount=amount,
                description=item.get('description')
            ))

        # 4. 대차평형 검증
        if total_debit != total_credit:
            raise ValueError(
                f"Transaction is not balanced! (Debit: {total_debit}, Credit: {total_credit})"
            )

        # 5. 저장
        new_tx_model.entries = entries_to_add
        
        self.db.add(new_tx_model)
        self.db.commit()
        self.db.refresh(new_tx_model)

        # 6. 결과 반환 (Eager Loading을 안 했다면 relationship 접근 시 쿼리 발생)
        # 여기서는 이미 메모리에 있는 정보와 account_map을 활용해 구성 가능하지만,
        # 정석대로 모델에서 변환
        return self._model_to_dto(new_tx_model)

    def get_transaction(self, user_id: str, tx_id: str) -> Transaction:
        """
        특정 거래를 조회합니다.
        """
        # joinedload로 N+1 문제 방지 (entries와 그 안의 account까지 한 번에 로딩)
        tx_model = self.db.query(TransactionModel).options(
            joinedload(TransactionModel.entries).joinedload(JournalEntryModel.account)
        ).filter(
            TransactionModel.owner_id == user_id,
            TransactionModel.id == tx_id
        ).first()

        if not tx_model:
            raise ValueError(f"Transaction {tx_id} not found.")
            
        return self._model_to_dto(tx_model)

    def get_all_transactions(self, user_id: str) -> List[Transaction]:
        """
        사용자의 모든 거래 내역을 조회합니다.
        """
        tx_models = self.db.query(TransactionModel).options(
            joinedload(TransactionModel.entries).joinedload(JournalEntryModel.account)
        ).filter(
            TransactionModel.owner_id == user_id
        ).order_by(TransactionModel.date.desc()).all()
        
        return [self._model_to_dto(tx) for tx in tx_models]

    def get_all_accounts(self, user_id: str) -> List[Account]:
        """
        사용자의 모든 계정 과목을 조회합니다.
        """
        account_models = self.db.query(AccountModel).filter(
            AccountModel.owner_id == user_id
        ).order_by(AccountModel.code).all()

        return [
            Account(
                id=a.id,
                owner_id=a.owner_id,
                code=a.code,
                name=a.name,
                category=a.category,
                side=a.side,
                description=a.description
            ) for a in account_models
        ]

    def _model_to_dto(self, tx_model: TransactionModel) -> Transaction:
        """
        내부 헬퍼: TransactionModel -> Transaction DTO 변환
        """
        res_debits = []
        res_credits = []
        
        for e in tx_model.entries:
            # account 정보가 로딩되어 있어야 함 (joinedload 권장)
            # 만약 lazy loading 상태라면 여기서 쿼리 발생
            
            je = Journal_Entry(
                account_code=e.account.code, # AccountModel에 접근
                account_name=e.account.name,
                side=e.side,
                amount=e.amount,
                description=e.description
            )
            if e.side == Account_Side.DEBIT:
                res_debits.append(je)
            else:
                res_credits.append(je)

        return Transaction(
            id=tx_model.id,
            owner_id=tx_model.owner_id,
            date=tx_model.date,
            description=tx_model.description,
            debits=res_debits,
            credits=res_credits,
            evidence_id=tx_model.evidence_id,
            location_id=tx_model.location_id
        )
    
    # --- Export ---

    def export_to_json(self, user_id: str, file_path: str) -> bool:
        transactions = self.get_all_transactions(user_id)
        data_list = [tx.to_dict() for tx in transactions]
        
        return Process.Json.Write_to(
            file=Path(file_path),
            data=data_list,
            indent=4
        )
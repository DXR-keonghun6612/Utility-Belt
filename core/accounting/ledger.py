from typing import Dict, List, Optional
from datetime import date
from uuid import uuid4
from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session
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
    """
    def __init__(self, db: Session):
        self.db = db

    # --- 계정 관리 (Chart of Accounts) ---
    
    def add_account(self, account: Account) -> Account:
        """
        새로운 계정 과목을 DB에 등록합니다.
        """
        db_account = AccountModel(
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
            raise ValueError(f"Account code '{account.code}' already exists.")
        
        return account

    def get_account(self, code: str) -> Account:
        """
        DB에서 계정을 조회하여 DTO로 반환합니다.
        """
        db_account = self.db.query(AccountModel).filter(AccountModel.code == code).first()
        if not db_account:
            raise ValueError(f"Account code '{code}' not found.")
        
        # DB Model -> DTO 변환
        return Account(
            code=db_account.code,
            name=db_account.name,
            category=db_account.category,
            side=db_account.side,
            description=db_account.description
        )

    # --- 트랜잭션 기록 (Journalizing) ---

    def record_transaction(
        self, 
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
        
        # 1. Transaction Model 생성
        # ID는 DB 저장 시 자동 생성되거나 여기서 지정 가능. 
        # 모델에서 default=uuid4 설정을 했으므로 여기선 자동 생성에 맡기거나 명시적으로 생성 가능.
        # DTO 반환을 위해 명시적으로 생성하는 것이 좋음.
        tx_id = str(uuid4())
        
        new_tx_model = TransactionModel(
            id=tx_id,
            date=tx_date,
            description=description,
            evidence_id=evidence_id,
            location_id=location_id
        )

        entries_to_add = []
        
        # 검증용 합계
        total_debit = Decimal('0')
        total_credit = Decimal('0')

        # 2. 차변(Debits) 처리
        for item in debits:
            # 계정 존재 여부 확인 (없으면 에러 발생)
            self.get_account(item['code']) 
            
            amount = Decimal(str(item['amount']))
            total_debit += amount
            
            entries_to_add.append(JournalEntryModel(
                account_code=item['code'],
                side=Account_Side.DEBIT,
                amount=amount,
                description=item.get('description')
            ))

        # 3. 대변(Credits) 처리
        for item in credits:
            self.get_account(item['code'])
            
            amount = Decimal(str(item['amount']))
            total_credit += amount
            
            entries_to_add.append(JournalEntryModel(
                account_code=item['code'],
                side=Account_Side.CREDIT,
                amount=amount,
                description=item.get('description')
            ))

        # 4. 대차평형 검증 (Validation)
        if total_debit != total_credit:
            raise ValueError(
                f"Transaction is not balanced! (Debit: {total_debit}, Credit: {total_credit})"
            )

        # 5. 모델 연결 및 저장 (Commit)
        new_tx_model.entries = entries_to_add
        
        self.db.add(new_tx_model)
        self.db.commit()
        self.db.refresh(new_tx_model)

        # 6. 결과 반환 (Model -> DTO 변환)
        # DB에는 통합되어 저장되지만, DTO는 debits/credits가 분리되어 있으므로 다시 나눠줌
        res_debits = []
        res_credits = []
        
        for e in new_tx_model.entries:
            je = Journal_Entry(
                account_code=e.account_code,
                side=e.side,
                amount=e.amount,
                description=e.description
            )
            if e.side == Account_Side.DEBIT:
                res_debits.append(je)
            else:
                res_credits.append(je)

        return Transaction(
            id=new_tx_model.id,
            date=new_tx_model.date,
            description=new_tx_model.description,
            debits=res_debits,
            credits=res_credits,
            evidence_id=new_tx_model.evidence_id,
            location_id=new_tx_model.location_id
        )

    def update_transaction_metadata(
        self, 
        transaction_id: str, 
        description: Optional[str] = None,
        evidence_id: Optional[str] = None,
        location_id: Optional[str] = None
    ) -> Transaction:
        """
        거래의 메타데이터(설명, 증빙, 위치)를 수정합니다.
        금액이나 계정 등 회계적 중요 정보는 수정하지 않습니다.
        """
        tx_model = self.db.query(TransactionModel).filter(TransactionModel.id == transaction_id).first()
        if not tx_model:
            raise ValueError(f"Transaction {transaction_id} not found.")

        if description is not None:
            tx_model.description = description
        if evidence_id is not None:
            tx_model.evidence_id = evidence_id
        if location_id is not None:
            tx_model.location_id = location_id
            
        self.db.commit()
        self.db.refresh(tx_model)
        
        # DTO 변환 및 반환 (기존 로직 재사용)
        res_debits = []
        res_credits = []
        for e in tx_model.entries:
            je = JournalEntry(
                account_code=e.account_code,
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
            date=tx_model.date,
            description=tx_model.description,
            debits=res_debits,
            credits=res_credits,
            evidence_id=tx_model.evidence_id,
            location_id=tx_model.location_id
        )

    def get_all_transactions(self) -> List[Transaction]:
        """
        모든 거래 내역을 조회하여 DTO 리스트로 반환합니다.
        """
        tx_models = self.db.query(TransactionModel).all()
        results = []
        
        for tx in tx_models:
            res_debits = []
            res_credits = []
            for e in tx.entries:
                je = Journal_Entry(
                    account_code=e.account_code,
                    side=e.side,
                    amount=e.amount,
                    description=e.description
                )
                if e.side == Account_Side.DEBIT:
                    res_debits.append(je)
                else:
                    res_credits.append(je)
            
            results.append(Transaction(
                id=tx.id,
                date=tx.date,
                description=tx.description,
                debits=res_debits,
                credits=res_credits,
                evidence_id=tx.evidence_id,
                location_id=tx.location_id
            ))
            
        return results

    def get_all_accounts(self) -> List[Account]:
        """
        모든 계정 과목을 조회하여 DTO 리스트로 반환합니다.
        """
        account_models = self.db.query(AccountModel).all()
        return [
            Account(
                code=a.code,
                name=a.name,
                category=a.category,
                side=a.side,
                description=a.description
            ) for a in account_models
        ]

    def export_to_json(self, file_path: str) -> bool:
        """
        모든 거래 내역을 JSON 파일로 내보냅니다.
        Returns:
            bool: 성공 여부
        """
        transactions = self.get_all_transactions()
        data_list = [tx.to_dict() for tx in transactions]
        
        # python_toolbox의 Json.Write_to 사용
        # (이미 Handle_exp 데코레이터가 있어서 예외 처리됨)
        return Process.Json.Write_to(
            file=Path(file_path),
            data=data_list,
            indent=4
        )

    def export_accounts_to_json(self, file_path: str) -> bool:
        """
        모든 계정 정보를 JSON 파일로 내보냅니다.
        """
        accounts = self.get_all_accounts()
        data_list = [a.to_dict() for a in accounts]
        
        return Process.Json.Write_to(
            file=Path(file_path),
            data=data_list,
            indent=4
        )

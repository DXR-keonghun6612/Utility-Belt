from typing import List, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import uuid4

from core.accounting.ledger import Ledger
from core.accounting.typing import Account_Side, Account_Type
from core.finance.models import InstallmentPlanModel, StockLotModel, GroupDueModel

class FinanceManager:
    """
    고급 금융 거래(할부, 투자, 그룹 회비)를 관리하는 서비스
    """
    def __init__(self, db: Session, ledger: Ledger):
        self.db = db
        self.ledger = ledger

    # --- 할부(Installments) ---

    def create_installment(
        self,
        user_id: str,
        date: date,
        description: str,
        asset_account_code: str, 
        liability_account_code: str, 
        total_amount: Decimal,
        months: int,
        card_name: str
    ) -> InstallmentPlanModel:
        tx = self.ledger.record_transaction(
            user_id=user_id,
            tx_date=date,
            description=f"{description} (할부 {months}개월)",
            debits=[{'code': asset_account_code, 'amount': total_amount}],
            credits=[{'code': liability_account_code, 'amount': total_amount}]
        )

        monthly_amt = round(total_amount / months, 2)
        
        plan = InstallmentPlanModel(
            id=str(uuid4()),
            owner_id=user_id,
            origin_tx_id=tx.id,
            card_name=card_name,
            description=description,
            total_months=months,
            current_month=0,
            monthly_amount=monthly_amt,
            total_amount=total_amount,
            start_date=date,
            is_completed=False
        )
        
        self.db.add(plan)
        self.db.commit()
        return plan

    def process_installment_payment(
        self,
        user_id: str,
        plan_id: str,
        payment_date: date,
        payment_account_code: str 
    ):
        plan = self.db.query(InstallmentPlanModel).filter_by(id=plan_id, owner_id=user_id).first()
        if not plan:
            raise ValueError("Installment plan not found.")
        
        if plan.is_completed:
            raise ValueError("This plan is already completed.")

        amount = plan.monthly_amount
        
        origin_tx = self.ledger.get_transaction(user_id, plan.origin_tx_id)
        liability_code = origin_tx.credits[0].account_code 

        self.ledger.record_transaction(
            user_id=user_id,
            tx_date=payment_date,
            description=f"{plan.description} 할부 납부 ({plan.current_month + 1}/{plan.total_months})",
            debits=[{'code': liability_code, 'amount': amount}], 
            credits=[{'code': payment_account_code, 'amount': amount}] 
        )

        plan.current_month += 1
        if plan.current_month >= plan.total_months:
            plan.is_completed = True
        
        self.db.commit()

    # --- 투자(Investment) ---

    def buy_stock(
        self,
        user_id: str,
        date: date,
        ticker: str,
        name: str,
        quantity: Decimal,
        unit_price: Decimal,
        asset_account_code: str, 
        payment_account_code: str 
    ) -> StockLotModel:
        total_cost = quantity * unit_price
        
        tx = self.ledger.record_transaction(
            user_id=user_id,
            tx_date=date,
            description=f"매수: {ticker} {quantity}주 @ {unit_price}",
            debits=[{'code': asset_account_code, 'amount': total_cost}],
            credits=[{'code': payment_account_code, 'amount': total_cost}]
        )
        
        lot = StockLotModel(
            id=str(uuid4()),
            owner_id=user_id,
            buy_tx_id=tx.id,
            ticker=ticker,
            name=name,
            initial_quantity=quantity,
            remaining_quantity=quantity,
            unit_price=unit_price,
            buy_date=date
        )
        
        self.db.add(lot)
        self.db.commit()
        return lot

    def sell_stock(
        self,
        user_id: str,
        date: date,
        ticker: str,
        quantity: Decimal,
        unit_price: Decimal,
        asset_account_code: str, 
        deposit_account_code: str, 
        income_account_code: str, 
        expense_account_code: str 
    ):
        lots = self.db.query(StockLotModel).filter(
            StockLotModel.owner_id == user_id,
            StockLotModel.ticker == ticker,
            StockLotModel.is_sold_out == False
        ).order_by(StockLotModel.buy_date.asc()).all()
        
        remaining_to_sell = quantity
        total_cost_basis = Decimal('0') 
        
        lots_updated = []

        for lot in lots:
            if remaining_to_sell <= 0:
                break
            qty_from_lot = min(lot.remaining_quantity, remaining_to_sell)
            total_cost_basis += qty_from_lot * lot.unit_price
            lot.remaining_quantity -= qty_from_lot
            remaining_to_sell -= qty_from_lot
            if lot.remaining_quantity == 0:
                lot.is_sold_out = True
            lots_updated.append(lot)
            
        if remaining_to_sell > 0:
            raise ValueError(f"Not enough stock quantity to sell. (Short: {remaining_to_sell})")

        total_sell_amount = quantity * unit_price
        pnl = total_sell_amount - total_cost_basis 
        
        debits = [{'code': deposit_account_code, 'amount': total_sell_amount}] 
        credits = [{'code': asset_account_code, 'amount': total_cost_basis}] 
        
        if pnl > 0:
            credits.append({'code': income_account_code, 'amount': pnl, 'description': f'{ticker} 매도익'})
        elif pnl < 0:
            debits.append({'code': expense_account_code, 'amount': abs(pnl), 'description': f'{ticker} 매도손'})
            
        self.ledger.record_transaction(
            user_id=user_id,
            tx_date=date,
            description=f"매도: {ticker} {quantity}주 @ {unit_price}",
            debits=debits,
            credits=credits
        )
        self.db.commit()

    # --- 그룹 회비(Dues) ---

    def assign_due(
        self,
        user_id: str, # Group Ledger ID
        date: date,
        member_name: str,
        description: str,
        amount: Decimal,
        receivable_account_code: str, # 미수금 계정 (자산)
        revenue_account_code: str, # 수익 계정
        due_date: Optional[date] = None
    ) -> GroupDueModel:
        """
        특정 멤버에게 회비를 청구합니다.
        (차) 미수금 / (대) 회비수익
        """
        # 1. 회계 처리
        tx = self.ledger.record_transaction(
            user_id=user_id,
            tx_date=date,
            description=f"회비 청구 ({member_name}) - {description}",
            debits=[{'code': receivable_account_code, 'amount': amount}],
            credits=[{'code': revenue_account_code, 'amount': amount}]
        )

        # 2. 관리 모델 생성
        due = GroupDueModel(
            id=str(uuid4()),
            owner_id=user_id,
            claim_tx_id=tx.id,
            member_name=member_name,
            description=description,
            amount=amount,
            due_date=due_date,
            is_paid=False
        )

        self.db.add(due)
        self.db.commit()
        return due

    def collect_due(
        self,
        user_id: str,
        due_id: str,
        payment_date: date,
        deposit_account_code: str # 입금 계좌 (자산)
    ):
        """
        멤버가 회비를 납부했음을 확인 처리합니다.
        (차) 예금 / (대) 미수금
        """
        due = self.db.query(GroupDueModel).filter_by(id=due_id, owner_id=user_id).first()
        if not due:
            raise ValueError("Due record not found.")
        
        if due.is_paid:
            raise ValueError("This due is already paid.")

        # 미수금 계정 찾기 (원천 거래의 차변)
        origin_tx = self.ledger.get_transaction(user_id, due.claim_tx_id)
        receivable_code = origin_tx.debits[0].account_code

        # 회계 처리
        self.ledger.record_transaction(
            user_id=user_id,
            tx_date=payment_date,
            description=f"회비 납부 ({due.member_name}) - {due.description}",
            debits=[{'code': deposit_account_code, 'amount': due.amount}],
            credits=[{'code': receivable_code, 'amount': due.amount}]
        )

        # 상태 업데이트
        due.is_paid = True
        due.paid_at = datetime.utcnow()
        self.db.commit()
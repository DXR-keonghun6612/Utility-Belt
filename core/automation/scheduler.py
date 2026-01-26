from datetime import date
from sqlalchemy.orm import Session
from typing import List

from core.accounting.ledger import Ledger
from core.automation.models import RecurringTransactionModel

class AutomationManager:
    def __init__(self, db: Session, ledger: Ledger):
        self.db = db
        self.ledger = ledger

    def create_recurring_tx(
        self,
        user_id: str,
        name: str,
        day_of_month: int,
        description: str,
        debits: List[dict],
        credits: List[dict]
    ) -> RecurringTransactionModel:
        """
        정기 결제 등록 (매월 특정 일자)
        """
        template = {
            "description": description,
            "debits": debits,
            "credits": credits
        }
        
        task = RecurringTransactionModel(
            owner_id=user_id,
            name=name,
            cron_expression="monthly", # placeholder
            day_of_month=day_of_month,
            template=template,
            is_active=1
        )
        self.db.add(task)
        self.db.commit()
        return task

    def process_daily_tasks(self, target_date: date):
        """
        오늘 날짜에 실행해야 할 모든 반복 거래를 처리합니다.
        """
        day = target_date.day
        
        # 1. 오늘 날짜(day)에 해당하고, 활성화된 태스크 조회
        tasks = self.db.query(RecurringTransactionModel).filter(
            RecurringTransactionModel.day_of_month == day,
            RecurringTransactionModel.is_active == 1
        ).all()

        results = []
        for task in tasks:
            # 이미 오늘 실행했는지 확인 (중복 방지)
            if task.last_run_date == target_date:
                continue

            # 2. 템플릿 로드
            tpl = task.template
            
            # 3. Ledger 기록
            try:
                tx = self.ledger.record_transaction(
                    user_id=task.owner_id,
                    tx_date=target_date,
                    description=tpl['description'],
                    debits=tpl['debits'],
                    credits=tpl['credits']
                )
                
                # 4. 상태 업데이트
                task.last_run_date = target_date
                results.append(f"Success: {task.name} ({tx.id})")
                
            except Exception as e:
                results.append(f"Failed: {task.name} - {str(e)}")
        
        self.db.commit()
        return results

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.accounting.ledger import Ledger
from core.accounting.typing import Account, Account_Type, Account_Side
from core.finance.service import FinanceManager

# In-memory DB for testing
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="module")
def ledger(db):
    return Ledger(db)

@pytest.fixture(scope="module")
def finance(db, ledger):
    return FinanceManager(db, ledger)

# --- Test Data ---
USER_A = "user_a_123"
USER_B = "user_b_456"

def test_setup_accounts(ledger):
    """
    기초 계정 설정 테스트 (멀티 유저)
    """
    # User A의 계정
    ledger.add_account(USER_A, Account("1001", "현금", Account_Type.ASSET, Account_Side.DEBIT, USER_A))
    ledger.add_account(USER_A, Account("1002", "보통예금", Account_Type.ASSET, Account_Side.DEBIT, USER_A))
    ledger.add_account(USER_A, Account("2001", "미지급금", Account_Type.LIABILITY, Account_Side.CREDIT, USER_A))
    ledger.add_account(USER_A, Account("4001", "급여", Account_Type.NOMINAL, Account_Side.CREDIT, USER_A))
    ledger.add_account(USER_A, Account("5001", "식비", Account_Type.NOMINAL, Account_Side.DEBIT, USER_A))
    
    # 투자 관련 계정 (User A)
    ledger.add_account(USER_A, Account("1200", "주식", Account_Type.ASSET, Account_Side.DEBIT, USER_A))
    ledger.add_account(USER_A, Account("4200", "투자수익", Account_Type.NOMINAL, Account_Side.CREDIT, USER_A))
    ledger.add_account(USER_A, Account("5200", "투자손실", Account_Type.NOMINAL, Account_Side.DEBIT, USER_A))

    # User B의 계정 (User A와 코드는 같지만 별개)
    ledger.add_account(USER_B, Account("1001", "현금", Account_Type.ASSET, Account_Side.DEBIT, USER_B))

    # 검증
    accounts_a = ledger.get_all_accounts(USER_A)
    assert len(accounts_a) == 8
    
    accounts_b = ledger.get_all_accounts(USER_B)
    assert len(accounts_b) == 1
    assert accounts_b[0].code == "1001"

def test_basic_transaction(ledger):
    """
    기본 거래(식비 지출) 테스트
    """
    tx = ledger.record_transaction(
        USER_A,
        date(2026, 1, 1),
        "점심 식사",
        debits=[{'code': '5001', 'amount': 10000}], # 식비
        credits=[{'code': '1001', 'amount': 10000}] # 현금
    )
    
    assert tx.is_balanced
    assert tx.owner_id == USER_A
    assert len(tx.debits) == 1
    assert len(tx.credits) == 1

def test_installment_scenario(finance, ledger):
    """
    할부 거래 시나리오 테스트
    """
    # 1. 할부 결제 (노트북 구입, 100만원, 10개월)
    plan = finance.create_installment(
        USER_A,
        date(2026, 1, 5),
        "맥북 에어",
        asset_account_code="5001", # 편의상 식비/비품 계정 사용
        liability_account_code="2001", # 미지급금
        total_amount=Decimal("1000000"),
        months=10,
        card_name="삼성카드"
    )
    
    assert plan.total_amount == 1000000
    assert plan.monthly_amount == 100000
    assert plan.current_month == 0
    assert plan.is_completed == False

    # 원장에 부채가 잡혔는지 확인
    txs = ledger.get_all_transactions(USER_A)
    latest_tx = txs[0] # date desc 정렬이므로 최신
    assert "맥북 에어" in latest_tx.description
    
    # 2. 1회차 납부
    finance.process_installment_payment(
        USER_A,
        plan.id,
        date(2026, 2, 1),
        payment_account_code="1002" # 보통예금에서 이체
    )
    
    # 상태 확인
    assert plan.current_month == 1
    assert plan.is_completed == False
    
    # 원장에 납부 기록 확인
    txs_after = ledger.get_all_transactions(USER_A)
    payment_tx = txs_after[0]
    assert "할부 납부 (1/10)" in payment_tx.description

def test_stock_scenario(finance, ledger):
    """
    주식 투자(매수/매도 FIFO) 시나리오 테스트
    """
    # 1. 매수 (삼성전자 10주 @ 50,000원)
    lot1 = finance.buy_stock(
        USER_A,
        date(2026, 1, 10),
        "005930", "삼성전자",
        Decimal("10"), Decimal("50000"),
        "1200", "1002" # 주식(자산) / 보통예금
    )
    
    # 2. 추가 매수 (삼성전자 10주 @ 60,000원) - 물타기 아님 불타기
    lot2 = finance.buy_stock(
        USER_A,
        date(2026, 1, 15),
        "005930", "삼성전자",
        Decimal("10"), Decimal("60000"),
        "1200", "1002"
    )

    assert lot1.remaining_quantity == 10
    assert lot2.remaining_quantity == 10

    # 3. 매도 (15주 @ 70,000원) - 익절
    # 예상: lot1(10주) 전량 매도 + lot2(5주) 부분 매도
    # 총 매도액: 15 * 70,000 = 1,050,000
    # 총 원가: (10 * 50,000) + (5 * 60,000) = 500,000 + 300,000 = 800,000
    # 실현 이익: 250,000
    
    finance.sell_stock(
        USER_A,
        date(2026, 1, 20),
        "005930",
        Decimal("15"), Decimal("70000"),
        "1200", "1002", "4200", "5200" # 자산/입금/수익/손실 계정
    )

    # 상태 검증
    assert lot1.remaining_quantity == 0
    assert lot1.is_sold_out == True
    
    assert lot2.remaining_quantity == 5
    assert lot2.is_sold_out == False

    # 원장 검증
    txs = ledger.get_all_transactions(USER_A)
    sell_tx = txs[0]
    assert "매도: 005930" in sell_tx.description
    
    # 수익 계정(4200)에 250,000원이 찍혔는지 확인
    # 대변(Credits)에 있어야 함
    income_entry = next(c for c in sell_tx.credits if c.account_code == "4200")
    assert income_entry.amount == Decimal("250000")

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))
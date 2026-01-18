import sys
import os
from datetime import date
from decimal import Decimal

# 프로젝트 루트 디렉토리를 path에 추가하여 모듈 import가 가능하게 함
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import Base, engine, SessionLocal
from core.accounting.typing import (
    Asset_Account, Nominal_Account, Account_Side
)
from core.accounting.ledger import Ledger

def run_test():
    print("=== [TEST START] Accounting Module Test ===")

    # 1. DB 초기화 (테이블 생성)
    print("\n1. Initializing Database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ledger = Ledger(db)
    print("   -> DB Connected & Tables Created.")

    try:
        # 2. 계정 등록 (Chart of Accounts Setup)
        print("\n2. Setting up Accounts...")
        
        # 현금 계정 (자산) 생성
        try:
            cash_acc = Asset_Account(code="1001", name="Cash", description="Main Wallet")
            ledger.add_account(cash_acc)
            print(f"   -> Account Added: {cash_acc.name} ({cash_acc.code})")
        except ValueError:
            print("   -> Account 'Cash' already exists. Skipping.")

        # 식비 계정 (비용) 생성
        try:
            food_acc = Nominal_Account(
                code="5001", 
                name="Food Expense", 
                side=Account_Side.DEBIT, 
                description="Lunch & Dinner"
            )
            ledger.add_account(food_acc)
            print(f"   -> Account Added: {food_acc.name} ({food_acc.code})")
        except ValueError:
            print("   -> Account 'Food Expense' already exists. Skipping.")


        # 3. 정상 거래 테스트 (Valid Transaction)
        print("\n3. Testing Valid Transaction (Lunch: 10,000 KRW)...")
        tx = ledger.record_transaction(
            tx_date=date.today(),
            description="Lunch at Gangnam",
            debits=[
                {"code": "5001", "amount": 10000, "description": "Kimchi Stew"}
            ],
            credits=[
                {"code": "1001", "amount": 10000, "description": "Paid by Cash"}
            ]
        )
        print(f"   -> Transaction Recorded Successfully! ID: {tx.id}")
        print(f"      Description: {tx.description}")
        print(f"      Debits: {[f'{d.amount} ({d.account_code})' for d in tx.debits]}")
        print(f"      Credits: {[f'{c.amount} ({c.account_code})' for c in tx.credits]}")


        # 4. 비정상 거래 테스트 (Unbalanced Transaction)
        print("\n4. Testing Unbalanced Transaction (Error Expected)...")
        try:
            ledger.record_transaction(
                tx_date=date.today(),
                description="Broken Transaction",
                debits=[{"code": "5001", "amount": 10000}],
                credits=[{"code": "1001", "amount": 9999}] # 1원 부족
            )
            print("   -> [FAIL] Transaction should have failed but succeeded.")
        except ValueError as e:
            print(f"   -> [PASS] Caught expected error: {e}")


        # 5. 조회 테스트 (Retrieve All)
        print("\n5. Retrieving All Transactions...")
        all_txs = ledger.get_all_transactions()
        print(f"   -> Total Transactions stored: {len(all_txs)}")
        for t in all_txs:
            print(f"      - [{t.date}] {t.description} (ID: {t.id[:8]}...)")

        # 6. JSON 내보내기 테스트 (Export Transactions)
        print("\n6. Testing Export Transactions to JSON...")
        export_tx_path = "test_ledger_export.json"
        
        if os.path.exists(export_tx_path):
            os.remove(export_tx_path)

        if ledger.export_to_json(export_tx_path) and os.path.exists(export_tx_path):
            print(f"   -> [PASS] Transactions exported successfully to '{export_tx_path}'")
        else:
            print(f"   -> [FAIL] Transactions export failed.")

        # 7. 계정 정보 내보내기 테스트 (Export Accounts)
        print("\n7. Testing Export Accounts to JSON...")
        export_acc_path = "test_accounts_export.json"

        if os.path.exists(export_acc_path):
            os.remove(export_acc_path)

        if ledger.export_accounts_to_json(export_acc_path) and os.path.exists(export_acc_path):
            print(f"   -> [PASS] Accounts exported successfully to '{export_acc_path}'")
        else:
            print(f"   -> [FAIL] Accounts export failed.")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        # 테스트용 생성 파일 정리
        for p in ["test_ledger_export.json", "test_accounts_export.json"]:
            if os.path.exists(p):
                os.remove(p)
                print(f"   -> [CLEANUP] Deleted {p}")
        print("\n=== [TEST END] ===")

if __name__ == "__main__":
    run_test()

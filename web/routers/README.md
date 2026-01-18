# API Routers

## 개요
FastAPI의 `APIRouter`를 사용하여 기능별로 분리된 API 엔드포인트 정의 파일들입니다.

## 파일 목록

### 1. `accounts.py` (/accounts)
*   **GET /**: 전체 계정 목록 조회
*   **POST /**: 새로운 계정 생성

### 2. `transactions.py` (/transactions)
*   **GET /**: 전체 거래 내역 조회 (상세 내역 포함)
*   **POST /**: 새로운 거래(Transaction) 기록 (차변/대변 포함)

## 의존성
모든 라우터는 `web.dependencies.get_ledger`를 통해 `core.accounting.ledger.Ledger` 인스턴스를 주입받아 비즈니스 로직을 수행합니다.

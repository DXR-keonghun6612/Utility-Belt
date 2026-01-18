# Core Accounting Module

## 개요
이 모듈(`core/accounting`)은 CACHE 프로젝트의 핵심 비즈니스 로직을 담당합니다. 데이터베이스 모델링과 API 사이에서 데이터의 무결성을 보장하고, 복식부기 원칙에 따른 트랜잭션 처리 및 재무 리포팅 기능을 제공합니다.

## 주요 구성 요소

### 1. Accounting Rules (`rules.py`)
*   **4대 핵심 요소:** 자산(Asset), 부채(Liability), 자본(Equity), 손익(Income/Expense) 정의.
*   거래의 8요소 검증 로직.
*   계정 과목(Account Types) 상수 및 열거형 데이터 관리.

### 2. General Ledger (`ledger.py`)
*   **트랜잭션 기록:** 모든 거래 내역(Journal Entry)의 생성 및 저장.
*   **대차평형 검증 (Validation):** 트랜잭션 저장 전 `차변 합계 == 대변 합계` 여부 확인.
*   **무결성 보장:** 필수 데이터(날짜, 적요, 금액 등) 누락 여부 확인.

### 3. Reporting Engine (`report.py`)
*   **재무상태표 (Balance Sheet):** 특정 시점의 자산, 부채, 자본 상태 산출.
*   **손익계산서 (Income Statement):** 특정 기간 동안의 손익 계정 집계를 통해 순이익 산출.
*   **기간별 집계:** 일별/월별/연별 지출 및 수입 통계 데이터 생성.

## 모듈 간 의존성
이 모듈은 `core/assets`(증빙 자료) 및 `core/geo`(위치 정보) 모듈과 연동될 수 있으나, 회계 로직 자체는 독립적으로 동작할 수 있도록 설계되어야 합니다.
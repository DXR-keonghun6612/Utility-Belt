# Core Module

## 개요
`core` 디렉토리는 어플리케이션의 핵심 비즈니스 로직(Domain Logic)이 모여 있는 곳입니다. UI(프론트엔드)나 DB(데이터 저장소)의 구체적인 구현 기술에 의존하지 않고, 순수한 파이썬 코드로 어플리케이션의 규칙과 기능을 정의합니다.

## 구조 및 역할

### 1. `accounting/` (회계 엔진)
*   **역할:** 복식부기 가계부의 핵심 로직 담당.
*   **주요 기능:**
    *   **Ledger:** 거래 기록의 총괄 관리자. 트랜잭션의 대차평형을 검증하고 저장합니다.
    *   **Models:** `Account`, `Transaction`, `JournalEntry` 등의 데이터 모델 정의.
*   **연동:** 거래 기록 시 `evidence_id`와 `location_id`를 외래키로 저장하여 다른 모듈과 연결됩니다.

### 2. `assets/` (자산/증빙 관리)
*   **역할:** 영수증 이미지, 계약서 등 거래와 관련된 파일(Hard Evidence) 처리.
*   **주요 기능:**
    *   **FileManager:** 실제 파일을 `data/uploads/` 경로에 안전하게 저장합니다.
    *   **AssetService:** 파일의 메타데이터(크기, 타입, 경로)를 DB에 기록하고 ID를 발급합니다.

### 3. `geo/` (지리 정보)
*   **역할:** 지출 장소에 대한 위치 데이터 처리.
*   **주요 기능:**
    *   **LocationService:** 위도/경도 데이터를 검증하고 DB에 저장하여 `Transaction`과 연결할 수 있게 합니다.

## 모듈 간 상호작용 (Interaction)

### 거래 생성 흐름 (Transaction Flow)
1.  **Frontend:** 사용자가 이미지 업로드 -> `API (Assets)` 호출 -> `asset_id` 획득.
2.  **Frontend:** 사용자가 위치 저장 -> `API (Geo)` 호출 -> `location_id` 획득.
3.  **Frontend:** 획득한 ID들과 거래 내역을 `API (Accounting)`에 전송.
4.  **Core (Ledger):** 대차평형 검증 후, `evidence_id`, `location_id`를 포함하여 트랜잭션 저장.

이러한 **느슨한 결합(Loose Coupling)** 구조 덕분에, 추후 이미지 서버를 분리하거나 위치 정보 서비스를 변경하더라도 회계 로직에는 영향을 주지 않습니다.
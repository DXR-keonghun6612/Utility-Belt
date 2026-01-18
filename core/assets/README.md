# Core Assets Module (Evidence Handler)

## 개요
이 모듈(`core/assets`)은 사용자가 거래 내역에 첨부하는 '증빙 자료(Hard Evidence)'인 이미지 파일이나 문서를 통합 관리합니다. 단순히 물리적인 파일을 디스크에 저장하는 것뿐만 아니라, **파일의 메타데이터(경로, 타입, 크기 등)를 데이터베이스에 기록하고 관리하는 역할**까지 전담합니다.

이를 통해 다른 모듈(예: `accounting`)은 파일 시스템의 세부 사항을 알 필요 없이, `Asset ID`만으로 증빙 자료를 참조하고 사용할 수 있습니다.

## 주요 기능

### 1. File I/O Manager (`storage.py`)
*   **물리적 저장:** 실제 파일을 로컬 디스크(`data/uploads/`)나 클라우드 스토리지에 저장합니다.
*   **보안 및 정리:** 파일명 난수화(UUID), 확장자 검증, 삭제 시 실제 파일 제거 기능을 제공합니다.

### 2. Asset Metadata Manager (`models.py`, `service.py`)
*   **DB 기록:** 저장된 파일의 정보(Original Name, Stored Path, Mime Type, Size, Created At)를 DB 테이블(`assets`)에 저장합니다.
*   **조회 및 연결:** `Asset ID`를 통해 파일 정보를 조회하며, `accounting` 모듈의 트랜잭션과 1:N 또는 1:1 관계로 연결될 수 있도록 지원합니다.

### 3. Lifecycle Management
*   **업로드 프로세스:** 파일 수신 -> 물리적 저장 -> DB 메타데이터 생성 -> ID 반환.
*   **삭제 프로세스:** 자산 삭제 요청 -> DB 레코드 삭제 -> 물리적 파일 삭제 (트랜잭션 보장 필요).

## 데이터 구조 (예시)
*   **Table:** `assets`
    *   `id` (PK): UUID
    *   `file_path`: 저장된 물리적 경로 (또는 S3 Key)
    *   `original_filename`: 사용자가 올린 원본 파일명
    *   `mime_type`: 파일 형식 (image/jpeg, application/pdf 등)
    *   `size_bytes`: 파일 크기
    *   `created_at`: 생성 일시

## 확장성 고려
*   스토리지 백엔드(Local, S3, GCS 등)가 변경되더라도 `Asset Metadata Manager`의 로직이나 DB 구조는 영향을 받지 않도록 설계합니다.
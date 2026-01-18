# Utility Belt (CACHE)

**Cash Accounting with Coordinates & Hard Evidence**

이 프로젝트는 **복식부기(Double-entry bookkeeping)** 기반의 가계부 어플리케이션입니다. 단순한 금전 기록을 넘어, 소비의 **증빙 자료(영수증 이미지)**와 **위치 정보(Coordinates)**를 함께 기록하여 "언제, 어디서, 무엇을" 소비했는지에 대한 명확한 맥락을 저장하는 것을 목표로 합니다.

## ✨ 주요 기능

### 1. 복식부기 엔진 (Core Accounting)
*   **완전한 복식부기:** 자산, 부채, 자본, 수익, 비용의 5대 요소를 기반으로 차변/대변의 평형을 유지합니다.
*   **무결성 검증:** 모든 거래 기록 시 대차평형(`Debit == Credit`)을 강제로 검증하여 데이터 오류를 원천 차단합니다.

### 2. 증빙 자료 관리 (Hard Evidence)
*   **이미지 아카이빙:** 영수증, 계약서 등의 실물 증빙 자료를 업로드하여 거래 내역과 1:1로 연결합니다.
*   **체계적 관리:** 업로드된 파일은 UUID 기반으로 안전하게 저장되며 데이터베이스에서 메타데이터로 관리됩니다.

### 3. 위치 정보 추적 (Geolocation)
*   **좌표 기록:** 거래가 발생한 시점의 위도/경도 정보를 브라우저 API를 통해 자동으로 수집합니다.
*   **위치 시각화:** (추후 예정) 지도 위에 소비 동선을 시각화할 수 있는 기반 데이터를 제공합니다.

### 4. Modern Web UI
*   **FastAPI 백엔드:** 고성능 비동기 Python API 서버.
*   **React 프론트엔드:** Vite 기반의 빠른 React 앱으로, 직관적인 대시보드와 입력 폼을 제공합니다.

---

## 🛠️ 시스템 구조 (Architecture)

이 프로젝트는 **모듈러 모놀리스(Modular Monolith)** 아키텍처를 따릅니다.

```
Utility_Belt/
├── core/               # 핵심 비즈니스 로직 (Domain Layer)
│   ├── accounting/     # 복식부기 규칙, 장부(Ledger) 관리
│   ├── assets/         # 파일 저장 및 관리
│   └── geo/            # 위치 정보 처리
├── web/                # 웹 인터페이스 (Presentation Layer)
│   ├── frontend/       # React UI (Vite)
│   ├── routers/        # FastAPI 엔드포인트
│   └── main.py         # 서버 진입점
├── data/               # 런타임 데이터 (DB, 업로드 파일)
└── docs/               # 상세 문서
```

---

## 🚀 설치 및 실행 가이드

### 1. 사전 요구사항 (Prerequisites)
*   Python 3.11+
*   Node.js 18+ (프론트엔드 빌드용)
*   Git

### 2. 백엔드 설정 (Backend Setup)

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 서버 실행
uvicorn web.main:app --reload
```
*   서버가 실행되면 `http://127.0.0.1:8000`에서 대기합니다.
*   API 문서(Swagger): `http://127.0.0.1:8000/docs`

### 3. 프론트엔드 설정 (Frontend Setup)

```bash
# 1. 디렉토리 이동
cd web/frontend

# 2. 패키지 설치
npm install

# 3. 개발 서버 실행
npm run dev
```
*   브라우저에서 `http://localhost:5173`으로 접속하여 사용합니다.

---

## 📖 사용 방법 (Quick Start)

1.  **계정 생성 (Accounts):** `Accounts` 탭에서 자산(예: 현금, 통장)과 비용(예: 식비, 교통비) 계정을 확인하거나 생성합니다.
2.  **거래 입력 (New Entry):**
    *   날짜와 적요를 입력합니다.
    *   **차변(Left):** 돈이 나간 이유 (비용) 또는 자산의 증가를 입력합니다.
    *   **대변(Right):** 돈이 나간 원천 (자산의 감소) 또는 부채의 증가를 입력합니다.
    *   **증빙/위치:** `Evidence` 버튼으로 영수증을 올리거나 `Get Location`으로 현재 위치를 저장합니다.
    *   `Save` 버튼을 누르면 대차평형이 맞을 경우 저장됩니다.
3.  **조회 및 수정 (Transactions):** `Transactions` 탭에서 내역을 확인하고, 연필 아이콘을 눌러 이미지나 설명을 수정할 수 있습니다.

---

## 📄 라이선스 & 기여
이 프로젝트는 개인적인 유틸리티 벨트 구축을 위해 시작되었습니다.
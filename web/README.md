# Web Application (FastAPI + React)

## 개요
이 디렉토리(`web`)는 CACHE 프로젝트의 사용자 인터페이스와 백엔드 API 서버를 포함합니다.
**FastAPI**를 사용하여 REST API를 제공하고, **React (Vite)**를 사용하여 모던한 웹 프론트엔드를 제공합니다.

## 구조
*   **`main.py`**: FastAPI 어플리케이션 진입점 (Server Entrypoint).
*   **`dependencies.py`**: DB 세션 등 의존성 주입(DI) 관리.
*   **`routers/`**: API 엔드포인트 라우터 모음.
*   **`frontend/`**: React 프론트엔드 프로젝트 소스 코드.

## 실행 방법

### 1. 백엔드 실행 (FastAPI)
프로젝트 루트(`Utility_Belt/`)에서 실행합니다.
```bash
uvicorn web.main:app --reload
```
*   서버 주소: `http://127.0.0.1:8000`
*   API 문서: `http://127.0.0.1:8000/docs`

### 2. 프론트엔드 실행 (React)
`web/frontend/` 디렉토리로 이동하여 실행합니다.
```bash
cd web/frontend
npm install  # (최초 1회)
npm run dev
```
*   웹 주소: `http://localhost:5173` (기본값)

# Frontend (React + Vite)

## 개요
CACHE 프로젝트의 웹 프론트엔드입니다. 사용자가 계정을 관리하고 거래를 입력하며, 재무 상태를 시각적으로 확인할 수 있는 인터페이스를 제공합니다.

## 기술 스택
*   **Core:** React 19, TypeScript
*   **Build Tool:** Vite 7
*   **Styling:** Bootstrap 5, React-Bootstrap
*   **Icons:** Lucide React
*   **API Client:** Axios

## 주요 디렉토리 구조
```
frontend/
├── src/
│   ├── api/        # 백엔드 통신용 클라이언트 및 타입 정의
│   ├── assets/     # 이미지 등 정적 자원
│   ├── App.tsx     # 메인 어플리케이션 컴포넌트 (레이아웃)
│   └── main.tsx    # React 진입점
├── public/         # 정적 파일 (favicon 등)
└── package.json    # 의존성 관리
```

## 개발 서버 실행
```bash
npm run dev
```

## 빌드
```bash
npm run build
```
빌드된 파일은 `dist/` 폴더에 생성됩니다.
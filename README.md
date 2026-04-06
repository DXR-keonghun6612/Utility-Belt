# FOCUS — 3D Simulation

3D 가상 시뮬레이션 환경을 구축하고, 알고리즘 사전 검증 및 학습 데이터 생성을 수행함.

## 진행 사항

- [ ] 정적 편집기
  - [x] 기본 구조 (데이터 입출력, 공간 배치, pose 편집)
  - [x] 멀티패스 렌더링 파이프라인 (RGB, Depth, Segmentation, Normal)
  - [ ] 편집 결과 저장 및 읽기 (*.usd)
- [x] 리팩토링 및 아키텍처 최적화 (1차 완료)
  - [x] 변환 행렬 연산 누수 방지를 위한 캐싱 (Dirty Flag 패턴) 도입
  - [x] GPU 대역폭 최적화를 위한 VBO 및 렌더 리소스 매니저 도입
  - [x] 제너레이터 기반 트리 탐색 유틸리티로 중복 코드 일원화
  - [x] 씬 초기화 시 Asset_Registry 캐시 해제를 통한 메모리 누수 차단
  - [x] 명시적 slice 객체 사용으로 파이썬 슬라이싱 규정 준수
  - [x] 그래픽스 렌더 익스포터의 UI 라이브러리(PySide6.QImage) 의존성 제거 및 순수 모듈(PIL) 교체
  - [x] 렌더 파이프라인의 오프스크린 컨텍스트(FBO) 생성부를 PySide6에서 순수 OpenGL 라이브러리(EGL)로 완전 분리 (테스트 필요)
- [ ] 향후 리팩토링 과제
  - [ ] BVH 또는 비동기 처리를 통한 픽킹 성능 개선
  - [ ] Command 패턴 기반 상태 제어층을 도입하여 UI의 데이터 직접 변경 방지
  - [ ] 에셋 인스턴스화 로직을 Stage_Controller로 이관하여 비즈니스 로직 캡슐화
  - [ ] UI 아키텍처 및 도메인 상호작용 구조의 전면적인 정리 (UI 의존성 분리)
- [ ] 기능 고도화 과제
  - [ ] 씬 내 객체(Mesh) 간 데이터 중복 및 형상 유사도(일치율) 분석 시스템 구축

## 구조

```txt
FOCUS/
├── app.py                  # UI 진입점
├── capture_cli.py          # 헤드리스 데이터 생성 진입점
├── data/                   # 데이터 모델, I/O, 캐시
│   ├── scene/              #   Scene_Node, Stage_Controller
│   ├── model/              #   Camera_Intrinsic
│   ├── io/                 #   OBJ 파서, 확장자 라우팅
│   └── registry.py         #   에셋 캐시
└── graphics/               # 시각화, 렌더링, UI
    ├── core/               #   공용 드로우 (Draw_mesh, Walk_scene)
    ├── viewport/           #   편집기 뷰포트 (카메라, 기즈모, 픽킹)
    ├── render/             #   멀티패스 파이프라인 (데이터셋 생성)
    └── ui/                 #   PySide6 편집기
```

의존 방향: `data/ <-- graphics/` (단방향, 순환 없음)

## 환경

- Python >= 3.11
- UI: PySide6
- 3D 시각화: OpenGL (고정 파이프라인)
- 3D 데이터 처리: numpy, scipy (rotation)
- 데이터 입출력: trimesh (*.obj)

## 기능별 분류

### 정적 편집기

3D 객체 데이터를 배치, 교체, 편집하는 정적 편집기. 멀티패스 렌더링을 통해 학습 데이터셋(RGB, Depth, Segmentation, Normal + 메타데이터)을 생성함.

### 동적 분석기

3D 객체 모델을 단위시간 간격으로 시뮬레이션하고 결과를 확인하는 분석기. (미구현)

### AI 모델 학습기

시뮬레이션 환경에서 생성된 데이터를 활용한 모델 학습. (미구현)

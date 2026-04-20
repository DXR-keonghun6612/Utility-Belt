# FOCUS — 3D Simulation

3D 가상 시뮬레이션 환경을 구축하고, 알고리즘 사전 검증 및 학습 데이터 생성을 수행함.

## 프로젝트 목표

- **정적 편집기**: 3D 객체를 배치/교체/편집하고, 멀티패스 렌더링으로 학습 데이터셋(RGB, Depth, Segmentation, Normal + 메타데이터)을 생성함.
- **동적 분석기**: 3D 객체 모델을 단위시간 간격으로 시뮬레이션하고 결과를 확인함. (미구현)
- **AI 모델 학습기**: 시뮬레이션 환경에서 생성된 데이터를 활용한 모델 학습. (미구현)

## 설계 이념

- **단방향 의존**: `spatial_toolbox ← {viewport, simulation} ← ui`. 순환 참조 없음. 상위 레이어가 하위만 소비하며, 하위는 상위를 알지 못함.
- **서브모듈 도메인 격리**: 씬 그래프 / 에셋 캐시 / OpenGL 렌더 코어는 `submodules/spatial_toolbox/` 서브모듈이 제공함. 프로젝트 최상위는 어댑터 성격의 `viewport/`(편집기 뷰포트)·`simulation/`(오프라인 캡처 파이프라인)·`ui/`(PySide6 편집기)만 보유함.
- **Zero-dependency 지향**: 표준 라이브러리와 네이티브 기능을 우선함. 외부 라이브러리는 명확한 이득이 있을 때만 도입함.
- **Mediator 기반 UI**: 위젯 간 직접 참조를 금지하고, `Main_Window`가 시그널을 중계하여 결합도를 낮춤.
- **재사용 가능한 코어**: 렌더 패스 구현체(`rgb`/`depth`/`segmentation`/`normal`)가 `spatial_toolbox.graphics.openGL.pass_`에 집약되어, 편집기 뷰포트와 오프라인 파이프라인이 동일 코드를 공유함.
- **캐시·풀링 우선**: 변환 행렬은 Dirty Flag로, GPU 리소스는 `id(mesh)` 키 기반 VBO 캐시로 누수와 중복 전송을 차단함.
- **확장 가능한 등록 구조**: 노드/에셋/렌더 패스는 데코레이터 기반 레지스트리로 등록되어, 새 타입 추가 시 파이프라인 코드 수정이 불필요함.

## 환경

- Python ≥ 3.11
- UI: PySide6
- 3D 시각화: OpenGL 고정 파이프라인 (PyOpenGL, EGL)
- 3D 데이터 처리: numpy, scipy (KDTree, rotation), trimesh
- 이미지 입출력: PIL (PySide6 비의존)

## 문서

- [ROADMAP.md](ROADMAP.md) — 진행 사항 및 향후 과제
- [COOKBOOK.md](COOKBOOK.md) — 실행 방법 및 사용 예시
- [ARCHITECTURE.md](ARCHITECTURE.md) — 구조 의사결정·확장 지점
- [viewport/README.md](viewport/README.md) — 편집기 실시간 뷰포트
- [simulation/README.md](simulation/README.md) — 오프라인 멀티패스 캡처 파이프라인
- [ui/README.md](ui/README.md) — PySide6 편집기 UI 및 Mediator 시그널 흐름
- [submodules/spatial_toolbox/spatial_toolbox/scene/README.md](submodules/spatial_toolbox/spatial_toolbox/scene/README.md) — 씬 그래프·에셋 캐시·파일 I/O 레이어
- [submodules/spatial_toolbox/spatial_toolbox/graphics/COOKBOOK.md](submodules/spatial_toolbox/spatial_toolbox/graphics/COOKBOOK.md) — OpenGL 렌더 코어 사용법
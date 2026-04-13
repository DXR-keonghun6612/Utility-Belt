# Roadmap

FOCUS 프로젝트의 진행 사항 및 향후 과제 목록임.

## 정적 편집기

- [x] 기본 구조 (데이터 입출력, 공간 배치, pose 편집)
- [x] 멀티패스 렌더링 파이프라인 (RGB, Depth, Segmentation, Normal)
- [ ] 편집 결과 저장 및 읽기 (`*.usd`)

## 리팩토링 및 아키텍처 최적화 (1차 완료)

- [x] 변환 캐싱(Dirty Flag) + GPU VBO 리소스 매니저 도입
- [x] `walk_nodes` 제너레이터 기반 트리 탐색 일원화
- [x] 씬 초기화 시 Asset 캐시 해제로 메모리 누수 차단
- [x] 렌더 익스포터 UI 의존성(PySide6.QImage) 제거 → PIL 교체
- [x] 오프스크린 컨텍스트(FBO)를 PySide6 → 순수 EGL로 분리
- [x] 도메인 재구성 — `data/node`, `data/asset/cache` 타입 버킷, `graphics/core/pass_/` 이관

## 학습 데이터 생성 (2차 완료)

- [x] `Resolve_meshes` — 전역 `ASSET_CACHE` + share 모드로 디스크/VBO 단일화
- [x] `Render_Config.output_layout` (`per_object`/`flat`) 도입, `obj_dir`/`target_node_label` 제거
- [x] capture_cli 재작성 — `target` 그룹 직속 자식 visible 토글 순회로 객체별 N프레임 캡처
- [x] RGB 패스 specular 항목 추가 — `Render_Config` → `Base_Pass.Configure` 훅 → `RGB_Pass`가 `glLightfv`/`glMaterialfv` 적용

## 향후 리팩토링 과제

### graphics/ 도메인

- [x] 트리 순회 통합 — `Walk_gl(root, on_node)` 헬퍼(`graphics/core/traversal_gl.py`)로 push/mult/pop + is_renderable 체크 일원화. `Base_Pass`/`Normal_Pass`/`Segmentation_Pass`/`Scene_Renderer` 5개 사이트 적용
- [x] ID 패스 통합 — `Id_Pass_Driver`(`graphics/core/id_pass.py`)로 인코딩/매핑 단일화. `Segmentation_Pass`와 viewport 픽킹이 동일 드라이버 위임
- [x] Phong 조명 헬퍼 분리 — `Apply_phong_lighting`(`graphics/core/lighting.py`)로 viewport `Initialize`와 `RGB_Pass._On_setup`이 동일 진입점 사용
- [ ] `Render_Pipeline` 비대화 해소 — 246 LOC 중 ~180 LOC가 EGL/Qt 컨텍스트 관리. `graphics/render/context/` 하위로 `Egl_Context`/`Qt_Context`/`Embedded_Context` 전략 분리
- [ ] `Gizmo_Controller` SRP 위반 해소 — Pick/Render/Drag 세 책임을 단일 클래스가 보유. `Gizmo_Picker`/`Gizmo_Renderer`/`Gizmo_Dragger`로 분리
- [ ] 와일드카드 임포트 제거 — `graphics/viewport/renderer.py`, `graphics/viewport/tool/camera_gizmo.py`의 `from OpenGL.GL import *` 제거
- [ ] `selection.py` → `Scene_Renderer` 직접 의존 해소 — ID 패스 인터페이스를 추상화하여 순환 의존 위험 차단
- [ ] `graphics/core/pass_/build.py` 수동 import 제거 — 패스 모듈 자동 발견(import_module 순회) 도입

### 도메인 전반

- [x] UI 측 `Asset_Cache` 인스턴스화 지점을 전역 `ASSET_CACHE` 싱글톤으로 마이그레이션 (capture와 캐시 일원화)
- [ ] capture_cli `_Find_camera_node` 탐색 범위를 `target`의 형제 노드로 한정 (현재는 root 전체 walk)
- [ ] BVH 또는 비동기 처리를 통한 픽킹 성능 개선
- [ ] Command 패턴 기반 상태 제어층을 도입하여 UI의 데이터 직접 변경 방지
- [ ] 에셋 인스턴스화 로직을 `Stage_Controller`로 이관하여 비즈니스 로직 캡슐화
- [ ] UI 아키텍처 및 도메인 상호작용 구조의 전면적인 정리 (UI 의존성 분리)

## 기능 고도화 과제

- [x] 메시 형상 유사도(일치율) 계측 함수군 구축 (`data/asset/utils/similarity.py`)
- [ ] 씬 내 중복 에셋 감지 시스템 (similarity 함수 활용)
- [ ] Point Cloud 데이터 입출력 및 시각화

## 미구현 모듈

- [ ] 동적 분석기 — 3D 객체 모델의 단위시간 시뮬레이션
- [ ] AI 모델 학습기 — 생성 데이터 기반 모델 학습 파이프라인

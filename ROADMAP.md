# Roadmap

FOCUS 프로젝트의 진행 사항 및 향후 과제 목록임.

## 완료 (차수별 히스토리)

### 1차 — 리팩토링 및 아키텍처 최적화

- [x] 변환 캐싱(Dirty Flag) + GPU VBO 리소스 매니저 도입
- [x] `walk_nodes` 제너레이터 기반 트리 탐색 일원화
- [x] 씬 초기화 시 Asset 캐시 해제로 메모리 누수 차단
- [x] 렌더 익스포터 UI 의존성(PySide6.QImage) 제거 → PIL 교체
- [x] 오프스크린 컨텍스트(FBO)를 PySide6 → 순수 EGL로 분리
- [x] 도메인 재구성 — `data/node`, `data/asset/cache` 타입 버킷, `graphics/core/pass_/` 이관

### 2차 — 학습 데이터 생성

- [x] `Resolve_meshes` — 전역 `ASSET_CACHE` + share 모드로 디스크/VBO 단일화
- [x] `Render_Config.output_layout` (`per_object`/`flat`) 도입, `obj_dir`/`target_node_label` 제거
- [x] capture_cli 재작성 — `target` 그룹 직속 자식 visible 토글 순회로 객체별 N프레임 캡처
- [x] RGB 패스 specular 항목 추가 — `Render_Config` → `Base_Pass.Configure` 훅 → `RGB_Pass`가 `glLightfv`/`glMaterialfv` 적용

### 3차 — graphics/core 통합

- [x] 트리 순회 통합 — `Walk_gl(root, on_node)` 헬퍼(`graphics/core/traversal_gl.py`)로 push/mult/pop + is_renderable 체크 일원화. `Base_Pass`/`Normal_Pass`/`Segmentation_Pass`/`Scene_Renderer` 5개 사이트 적용
- [x] ID 패스 통합 — `Id_Pass_Driver`(`graphics/core/id_pass.py`)로 인코딩/매핑 단일화. `Segmentation_Pass`와 viewport 픽킹이 동일 드라이버 위임
- [x] Phong 조명 헬퍼 분리 — `Apply_phong_lighting`(`graphics/core/lighting.py`)로 viewport `Initialize`와 `RGB_Pass._On_setup`이 동일 진입점 사용

### 4차 — 캐시 일원화

- [x] UI 측 `Asset_Cache` 인스턴스화 지점을 전역 `ASSET_CACHE` 싱글톤으로 마이그레이션 (capture와 캐시 일원화)

## 정적 편집기 기본 기능

- [x] 기본 구조 (데이터 입출력, 공간 배치, pose 편집)
- [x] 멀티패스 렌더링 파이프라인 (RGB, Depth, Segmentation, Normal)
- [ ] 편집 결과 저장 및 읽기 (`*.usd`) — 단위 체계 선결

## 진행 중 리팩토링

### graphics/ 도메인

- [ ] `Render_Pipeline` 비대화 해소 — 246 LOC 중 ~180 LOC가 EGL/Qt 컨텍스트 관리. `graphics/render/context/` 하위로 `Egl_Context`/`Qt_Context`/`Embedded_Context` 전략 분리
- [ ] `Gizmo_Controller` SRP 위반 해소 — Pick/Render/Drag 세 책임을 단일 클래스가 보유. `Gizmo_Picker`/`Gizmo_Renderer`/`Gizmo_Dragger`로 분리
- [ ] 와일드카드 임포트 제거 — `graphics/viewport/renderer.py`, `graphics/viewport/tool/camera_gizmo.py`의 `from OpenGL.GL import *` 제거
- [ ] `selection.py` → `Scene_Renderer` 직접 의존 해소 — ID 패스 인터페이스를 추상화하여 순환 의존 위험 차단 (BVH 픽킹의 선결 조건)
- [ ] `graphics/core/pass_/build.py` 수동 import 제거 — 패스 모듈 자동 발견(`import_module` 순회) 도입

### data/ · ui/ 도메인

- [ ] capture_cli `_Find_camera_node` 탐색 범위를 `target`의 형제 노드로 한정 (현재는 root 전체 walk)
- [ ] Command 패턴 기반 상태 제어층 도입 — UI의 데이터 직접 변경 방지 (에셋 인스턴스화 이관의 선결 조건)
- [ ] 에셋 인스턴스화 로직을 `Stage_Controller`로 이관하여 비즈니스 로직 캡슐화
- [ ] UI 아키텍처 및 도메인 상호작용 구조 전면 정리 (UI 의존성 분리)
- [ ] 카메라 노드를 에셋 체계로 분리 — 현재 scene에 직접 통합 저장 중. 전체 UI 개선 작업에 통합하여 Asset_Browser 계열에 편입

## 기능 과제

### 단위 체계

> `*.usd` 저장 및 `similarity` 튜닝의 선결 조건. 먼저 처리 시 이후 과제 단순화됨.

- [ ] `Mesh_Asset.source_unit` 메타 기록 — 로더에서 감지/지정 (OBJ의 경우 사용자 지정, 기본 `"m"`)
- [ ] `Stage_Controller.meters_per_unit` 필드 도입 및 직렬화 (USD `metersPerUnit` 관례 준수)
- [ ] 인스턴스화 시점 스케일 보정 — `asset.source_unit` ↔ `stage.meters_per_unit` 변환을 `Stage_Controller` 이관 경로에 내장
- [ ] `data/asset/utils/similarity.py` threshold를 m 단위로 고정 후 호출부에서 stage 단위로 환산
- [ ] Inspector/뷰포트에 stage 단위 라벨 노출 (기즈모 그리드 눈금 단위 표기 포함)

### 메시 노멀 복구

> 현재 `data/io/obj.py`에서 `merge_vertices + fix_normals`를 호출하여 connected component 내 winding은 일관화되지만, non-watertight 메시는 volume 부호로 "외향"을 판정할 수 없어 component별 전역 방향이 랜덤하게 결정됨. 증상: 대칭/미러 모델에서 반쪽만 정상 조명, 반대쪽은 반전. 임시 우회로 `GL_LIGHT_MODEL_TWO_SIDE`를 상시 켜둔 상태이며(`graphics/core/lighting.py`), 근본 수정 완료 시 제거 필요.

- [ ] 로드 시 메시별 watertight 여부 판정 및 비-watertight 분기 파이프라인 수립
- [ ] 외향 판정 휴리스틱 선택 — 후보: ray-casting 기반 voting, 카메라 뷰 의존 추정, convex hull normal 참조, 사용자 지정 "외향 기준점"
- [ ] 전역 방향이 틀린 경우 자동 flip (`mesh.faces = mesh.faces[:, ::-1]`) 또는 전용 서명 저장
- [ ] 수정 적용 후 `GL_LIGHT_MODEL_TWO_SIDE` 제거 및 성능/품질 검증
- [ ] 복구 실패 시 사용자가 노드 단위로 노멀 반전을 토글할 수 있는 UI 진입점 (Inspector)

### 카메라 왜곡 모델

- [ ] `Camera_Intrinsic.distortion`(OpenCV 8슬롯: k1,k2,p1,p2,k3,k4,k5,k6) 반영 — 현재는 메타 보관만. RGB 패스 셰이더화 또는 후처리 단계로 렌즈 왜곡을 적용. 고정 파이프라인 한계로 인해 셰이더 이전과 함께 진행해야 함

### 성능

- [ ] BVH 또는 비동기 처리를 통한 픽킹 성능 개선 (`selection.py` 추상화 이후)

### 데이터 및 시각화

- [x] 메시 형상 유사도(일치율) 계측 함수군 구축 (`data/asset/utils/similarity.py`)
- [ ] 씬 내 중복 에셋 감지 시스템 (similarity 함수 활용)
- [ ] Point Cloud 데이터 입출력 및 시각화

## 미구현 모듈

- [ ] 동적 분석기 — 3D 객체 모델의 단위시간 시뮬레이션
- [ ] AI 모델 학습기 — 생성 데이터 기반 모델 학습 파이프라인

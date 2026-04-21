# Roadmap

FOCUS 프로젝트의 진행 사항 및 향후 과제 목록임.

## 완료 (차수별 히스토리)

### 1차 — 리팩토링 및 아키텍처 최적화

- [x] Dirty Flag 변환 캐싱 + VBO 리소스 매니저 도입, `walk_nodes` 트리 탐색 일원화, 씬 초기화 시 Asset 캐시 해제로 누수 차단
- [x] 오프스크린 컨텍스트를 PySide6 → 순수 EGL로 분리, `PySide6.QImage` 의존 제거(PIL 교체), `data/`·`graphics/core/pass_/` 도메인 재편

### 2차 — 학습 데이터 생성

- [x] 전역 `ASSET_CACHE` 기반 `Resolve_meshes`와 `Render_Config.output_layout` 도입으로 `target` 그룹 자식 순회 + 객체별 N프레임 캡처 파이프라인 구축
- [x] RGB 패스 specular 경로 연결 — `Render_Config` → `Base_Pass.Configure` → `RGB_Pass`의 `glLightfv`/`glMaterialfv` 적용

### 3차 — graphics/core 통합

- [x] `Walk_gl` 트리 순회 헬퍼, `Id_Pass_Driver` ID 인코딩/매핑, `Apply_phong_lighting` 조명 헬퍼로 viewport·패스·픽킹이 단일 진입점 공유

### 4차 — 캐시 일원화

- [x] UI `Asset_Cache` 인스턴스화를 전역 `ASSET_CACHE` 싱글톤으로 통합하여 capture와 편집기가 동일 캐시 사용

### 5차 — 서브모듈 분리 (spatial_toolbox)

- [x] `data/`·`graphics/core/`를 `spatial_toolbox` 서브모듈로 추출, `viewport/`·`simulation/`을 최상위로 승격, `spatial_toolbox ← {viewport, simulation} ← ui` 단방향 의존 확정
- [x] 헤드리스 진입점(`capture_cli.py` + `Run_batch_capture`) 및 카메라/객체/광원 독립 `Randomize_Range` 도입

### 6차 — 렌더 파이프라인 정합성 복구

- [x] `Draw_mesh` 인자명(`draw_mode` → `mode`) 및 `_draw_mode` 기본값 누락 수정으로 `RGB_Pass`/`Depth_Pass` AttributeError 차단
- [x] 월드 행렬 이중 적용 제거 — 행렬 스택 책임을 Pass로 일원화, `Draw_mesh`는 프리미티브 드로우만 담당

## 정적 편집기 기본 기능

- [x] 기본 구조 (데이터 입출력, 공간 배치, pose 편집)
- [x] 멀티패스 렌더링 파이프라인 (RGB, Depth, Segmentation, Normal)
- [ ] 씬 번들 영속화 (커스텀 JSON + NPY, ZIP 컨테이너) — 현재는 씬 그래프 JSON만 저장되어 외부 에셋 파일이 유실되면 복원 불가. 번들 구성: `graph.json`(노드 트리 + `unit_length`), `assets/<id>.npy`(지오메트리 버퍼), `meta.json`(에셋별 `unit_length` 등 메타). 저장 시 `ASSET_CACHE` 키(절대경로 기반)를 번들 내부 식별자로 리매핑하고, 로드 시 역방향 복원 수행. 이후 `*.usd` 출력은 별개 과제로 분리

## 진행 중 리팩토링

### spatial_toolbox 도메인

- [ ] `Render_Pipeline` 비대화 해소 — EGL/Qt 컨텍스트 관리 로직을 `simulation/context/` 하위 `Egl_Context`/`Qt_Context`/`Embedded_Context` 전략으로 분리
- [ ] 패스 자동 발견 — `spatial_toolbox.graphics.openGL.pass_` 수동 import 제거 (`importlib` 순회 도입)
- [ ] `selection.py` → `Scene_Renderer` 직접 의존 해소 — ID 패스 인터페이스 추상화 (BVH 픽킹의 선결 조건)
- [ ] 프리미티브 확장 — `Draw_points`/`Draw_lines` 진입점 및 `Points`/`Line` 노드 타입 도입. `create_mesh_vbos`를 vertex/color 공통부와 프리미티브별 인덱스부로 분리하여 재사용

### viewport/ 도메인

- [ ] `Gizmo_Controller` SRP 위반 해소 — Pick/Render/Drag 세 책임을 `Gizmo_Picker`/`Gizmo_Renderer`/`Gizmo_Dragger`로 분리
- [ ] 와일드카드 임포트 제거 — `viewport/renderer.py`, `viewport/tool/camera_gizmo.py`의 `from OpenGL.GL import *` 제거
- [ ] 렌더 모드 오버라이드 UI — 패스별 기본 `_draw_mode`를 런타임에 덮어쓰는 옵션 진입점 (뷰포트 전용 옵션 패널에 배치, 기본값은 패스 선언 유지)

### simulation/ · ui/ 도메인

- [ ] `simulation.engine._Find_camera_node` 탐색 범위를 `target`의 형제 노드로 한정 (현재는 root 전체 walk)
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
- [ ] `spatial_toolbox.scene.asset.utils.similarity` threshold를 m 단위로 고정 후 호출부에서 stage 단위로 환산
- [ ] Inspector/뷰포트에 stage 단위 라벨 노출 (기즈모 그리드 눈금 단위 표기 포함)

### 메시 노멀 복구

> 현재 OBJ 로더에서 `merge_vertices + fix_normals`를 호출하여 connected component 내 winding은 일관화되지만, non-watertight 메시는 volume 부호로 "외향"을 판정할 수 없어 component별 전역 방향이 랜덤하게 결정됨. 증상: 대칭/미러 모델에서 반쪽만 정상 조명, 반대쪽은 반전. 임시 우회로 `GL_LIGHT_MODEL_TWO_SIDE`를 상시 켜둔 상태이며(`spatial_toolbox.graphics.openGL` 조명 진입점), 근본 수정 완료 시 제거 필요.

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

- [x] 메시 형상 유사도(일치율) 계측 함수군 구축 (`spatial_toolbox.scene.asset.utils.similarity`)
- [ ] 씬 내 중복 에셋 감지 시스템 (similarity 함수 활용)
- [ ] Point Cloud 데이터 입출력 및 시각화

## 미구현 모듈

- [ ] 동적 분석기 — 3D 객체 모델의 단위시간 시뮬레이션
- [ ] AI 모델 학습기 — 생성 데이터 기반 모델 학습 파이프라인

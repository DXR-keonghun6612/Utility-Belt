# Roadmap

FOCUS 프로젝트의 향후 과제 목록임.

---

## spatial_toolbox

### Phase 1 — 씬 번들 영속화 → Phase 3 USD로 대체됨

> 커스텀 ZIP 번들 포맷 대신 USD를 씬 영속화 포맷으로 채택함. `Controller.Load` ASSET_CACHE 미복원 버그는 Phase 3 USD Import 구현 시 함께 해소됨.

- [ ] `Controller.Load` 시 `ASSET_CACHE` 미복원 임시 핫픽스 (Phase 3 완료 전 운용 필요 시에만)

### Phase 2 — 비동기 로딩

> trimesh 파싱이 동기로 동작하여 에셋 로드 시 메인 스레드가 블로킹됨. spatial_toolbox는 워커 호환 인터페이스를 제공하고, FOCUS 어댑터 레이어에서 Qt 스레드와 연동함.

- [ ] `ASSET_CACHE.Add_from_file` 을 워커 스레드에서 호출 가능한 인터페이스로 분리 (GL 컨텍스트 미접촉 보장)
- [ ] 동일 `source_key` 중복 요청 방지 — in-flight 상태 추적

### Phase 3 — USD 직렬화 레이어

> Blender 백엔드(FOCUS Phase 4)의 선결 조건. 단위 체계 확립이 선행되어야 USD `metersPerUnit` 필드가 정확함.

**단위 체계 (선결)**

> `Controller.unit_length` / `Base_Asset.unit_length` / `Base_Node.unit_scale` 핵심 3종은 이미 구현됨. 미구현 항목만 남음.

- [x] `obj.py` 로더에서 `unit_length` 명시적 지정 — `Read_and_parse_obj(file, unit_length)` 추가, `Load_and_register` / `Register_from_file` 까지 전파됨
- [ ] `similarity` threshold m 단위 고정 — `Calculate_match_rate` / `Calculate_scan_match_rate` 호출부에서 stage 단위로 환산

**USD I/O**

> 내부 노드 구조는 현행 유지. USD는 교환 포맷으로만 사용하며 `pxr` 의존성은 이 경로에만 한정됨.

- [x] `Controller.Export_usd` — 씬 그래프 → USD 변환 (지오메트리·계층 구조 보존, 머티리얼 없음)
  - `Controller.unit_length` → `UsdStage.SetMetersPerUnit()`
  - `Base_Node.scale` → `xformOp:scale`
  - `Base_Node.unit_scale` → `xformOp:scale:unitFix` (custom suffix, 등방 스칼라 → float3)
  - `source_key` 동일 그룹 → `/_Prototypes/proto_N` + USD Reference + `instanceable = true`
  - geometry는 원본 좌표 그대로 유지 (unit_scale bake 없음 — 점군 정밀도 보존)
  - `focusSourceKey` / `focusProtoRef` custom metadata로 round-trip 보장
- [x] `Controller.Import_usd` — USD → 씬 그래프 역방향 복원
  - `xformOp:scale` → `Base_Node.scale`
  - `xformOp:scale:unitFix` → `Base_Node.unit_scale` (부재 시 `1.0`)
  - `/_Prototypes` geometry 추출 → `trimesh.Trimesh` → ASSET_CACHE 등록
  - `UsdStage.GetMetersPerUnit()` → `Controller.unit_length`
- [x] 변환기 위치: `Controller` 레벨 (`scene/file/` 레이어는 단일 지오메트리 변환만 유지)

### 리팩토링

- [ ] **노드 Transform 표현을 TQS(Translation / Quaternion / Scale) 분리 저장으로 전환** — 현재 `Base_Node.local_rigid`(4×4 행렬) + `scale`(vec3) 구조에서 `translation`(vec3) + `quaternion`(vec4 WXYZ) + `scale`(vec3)으로 변경. 회전을 행렬로 변환 후 다시 분해하는 round-trip이 없어져 scipy normalize에 의한 값 변형이 사라짐. Inspector 쿼터니언 편집 시 `_writing` 플래그로 피드백 루프를 차단하는 현 workaround(`ui/panels/scene/property.py`)의 근본 해소 조건임. World-matrix 캐시(`_Mark_dirty` / Dirty Flag 패턴)와 `Export_usd`/`Import_usd` 변환 로직 수정 필요.
- [ ] `I_Renderer` 인터페이스 분리 — `Render(queue, camera) → dict` 단일 계약만 정의. 현재 `Base_Renderer`는 이를 상속하는 multi-pass 생명주기 구현체로 격하. `Blender_Renderer`는 multi-pass 우회가 필요하므로 `I_Renderer`를 직접 구현 (`Base_Pass` 인터페이스 분리와 동일한 방향)
- [ ] 패스 자동 발견 — `graphics.openGL.pass_` 수동 import 제거 (`importlib` 순회 도입)
- [ ] `selection.py` → `Scene_Renderer` 직접 의존 해소 — ID 패스 인터페이스 추상화 (BVH 픽킹의 선결 조건)
- [ ] 프리미티브 확장 — `Draw_points`/`Draw_lines` 진입점 및 `Points`/`Line` 노드 타입 도입. `create_mesh_vbos`를 vertex/color 공통부와 프리미티브별 인덱스부로 분리하여 재사용

### 기능 과제

**메시 노멀 복구**

> OBJ 로더에서 non-watertight 메시의 외향 판정이 불가하여 component별 전역 방향이 랜덤하게 결정됨. 임시 우회로 `GL_LIGHT_MODEL_TWO_SIDE` 상시 활성 중이며 근본 수정 완료 시 제거 필요.

- [ ] 로드 시 메시별 watertight 여부 판정 및 비-watertight 분기 파이프라인 수립
- [ ] 외향 판정 휴리스틱 선택 — 후보: ray-casting 기반 voting, convex hull normal 참조, 사용자 지정 "외향 기준점"
- [ ] 전역 방향이 틀린 경우 자동 flip 또는 전용 서명 저장
- [ ] 수정 적용 후 `GL_LIGHT_MODEL_TWO_SIDE` 제거 및 검증

**카메라 왜곡 모델**

- [ ] `Camera_Intrinsic.distortion` (OpenCV 8슬롯) 실제 적용 — 현재는 메타 보관만. 고정 파이프라인 한계로 셰이더 이전 작업과 함께 진행 필요

**데이터 및 시각화**

- [ ] 씬 내 중복 에셋 감지 시스템 (`similarity` 함수 활용)
- [ ] Point Cloud 데이터 입출력 및 시각화

---

## FOCUS

### Phase 4 — Blender 렌더러 백엔드

> `simulation/` 전용. `viewport/`는 OpenGL 유지. OBJ 머티리얼 없음으로 상정하므로 USD 교환 포맷은 지오메트리·계층 구조만 보존.

- [ ] `Blender_Renderer` — `I_Renderer` 직접 구현체 (multi-pass 우회). 출력 채널(RGB / Depth / Normal / Segmentation)을 선언적으로 지정
- [ ] Blender 프로세스 전략: 장수명 단일 프로세스 + stdin/소켓 통신 (샘플마다 기동 비용 제거)
- [ ] USD를 씬 교환 포맷으로 사용 — `Controller.Export_usd` → Blender 로드 → 렌더 → 결과 수신
- [ ] `Render_Pipeline` 에 `backend: "opengl" | "blender"` 명시적 선택 인자 추가. EGL/Qt fallback 체인은 OpenGL 백엔드 내부로 한정

### Phase 2 연동 — 비동기 로딩 Qt 통합

- [ ] `QThread` (또는 `ThreadPoolExecutor`) 워커에서 `ASSET_CACHE.Add_from_file` 호출
- [ ] 완료 시 Qt 시그널로 메인 스레드에 통보 → VBO 업로드 (OpenGL 컨텍스트 스레드 귀속 준수)
- [ ] 로딩 진행 상태 UI 노출

### 리팩토링

**simulation/ 도메인**

- [ ] `Render_Pipeline` 비대화 해소 — EGL/Qt 컨텍스트 관리 로직을 `simulation/context/` 하위 `Egl_Context`/`Qt_Context`/`Embedded_Context` 전략으로 분리
- [ ] simulation 패턴 분리 — 현재 한 `Sim_Config` 안에 섞여 있는 rigid-body drop 단계와 image rendering/capture 단계를 별도 패턴으로 분해
  `Drop Simulation`, `Image Capture Simulation`처럼 목적이 다른 실행 흐름을 독립 패턴으로 정의하고, 필요 시 순차 조합 가능하게 재구성
- [ ] `Sim_Config` 구조 재설계 — 단일 평면 설정 대신 `simulation_pattern` 또는 `stages[]` 기반 구성으로 확장
  각 패턴이 요구하는 필드만 선언적으로 가지게 하고, drop 전용 설정(ground/collision/settle)과 capture 전용 설정(camera/output/channels/sample)을 분리
- [ ] UI의 sim_config 생성기를 패턴 선택형으로 개편
  config 생성 시 먼저 simulation 패턴을 고르고, 선택한 패턴에 맞는 입력 폼만 노출하도록 재구성
- [ ] physics settle을 pre-capture 옵션이 아니라 명시적 simulation stage로 승격
  "drop 후 render"는 하나의 숨은 플래그 조합이 아니라 `Drop -> Capture` 파이프라인으로 읽히게 명문화
- [ ] simulation 실행 진입점 정리 — `Run_batch_capture`를 패턴/스테이지 해석기 역할로 축소하고, 실제 실행은 패턴별 runner로 위임
  향후 `Drop Only`, `Capture Only`, `Drop + Capture`, `Analysis` 계열 simulation 추가를 수용 가능한 구조로 전환

**viewport/ 도메인**

- [ ] `Gizmo_Controller` SRP 위반 해소 — Pick/Render/Drag 를 `Gizmo_Picker`/`Gizmo_Renderer`/`Gizmo_Dragger`로 분리
- [ ] 와일드카드 임포트 제거 — `viewport/renderer.py`, `viewport/tool/camera_gizmo.py`의 `from OpenGL.GL import *`
- [ ] 렌더 모드 오버라이드 UI — 패스별 기본 `_draw_mode`를 런타임에 덮어쓰는 옵션 진입점

**ui/ 도메인**

- [ ] Command 패턴 기반 상태 제어층 도입 — UI의 데이터 직접 변경 방지 (에셋 인스턴스화 이관의 선결 조건)
- [ ] 에셋 인스턴스화 로직을 `Stage_Controller`로 이관하여 비즈니스 로직 캡슐화
- [ ] UI 아키텍처 및 도메인 상호작용 구조 전면 정리 (UI 의존성 분리)
- [ ] 카메라 노드를 에셋 체계로 분리 — Asset_Browser 계열에 편입

### 기능 과제

- [ ] BVH 또는 비동기 처리를 통한 픽킹 성능 개선 (`selection.py` 추상화 이후)
- [ ] Inspector 뷰포트에 stage 단위 라벨 노출 (기즈모 그리드 눈금 단위 표기 포함)
- [ ] 노드 단위 노멀 반전 토글 UI (메시 노멀 복구 실패 시 수동 보정 진입점)

### 미구현 모듈

- [ ] 동적 분석기 — 3D 객체 모델의 단위시간 시뮬레이션
- [ ] AI 모델 학습기 — 생성 데이터 기반 모델 학습 파이프라인

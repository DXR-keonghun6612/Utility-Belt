# 설계 문서

AI 학습 데이터 생성용 3D 시뮬레이션 환경을 구축하려는 사람을 위한 설계 가이드임. 본 문서는 구현 코드가 아닌 결정과 그 이유를 기록함.

---

## 1. 시스템 목적

3D 객체 모델을 가상 공간에 배치하고, 다양한 카메라·조명 조건에서 멀티패스 렌더링(RGB / Depth / Segmentation / Normal)을 수행하여 AI 학습 데이터셋을 생성하는 시스템임. 편집기(정적 씬 구성)와 헤드리스 캡처 파이프라인(배치 렌더링)을 하나의 코드베이스로 제공함.

---

## 2. 핵심 설계 원칙

### 씬 그래프와 렌더링 백엔드를 반드시 분리할 것

씬 데이터(노드 트리, 에셋 캐시)가 특정 렌더러의 API에 의존하면 백엔드 교체가 불가능해짐. 씬 그래프는 순수 데이터 모델이어야 하고 렌더러는 이를 소비(consume)하는 구조여야 함.

```
scene graph (data)  →  renderer (consumer)
```

### 에셋과 노드를 분리할 것

같은 지오메트리를 씬에 여러 번 배치하는 경우 지오메트리 본체를 복제하지 말고 참조를 복제해야 함. 이를 위해 지오메트리 캐시(`ASSET_CACHE`)와 씬 노드(`Mesh`)를 별도 레이어로 분리함. 노드는 `source_key`만 보유하고 실제 데이터는 캐시에 1벌만 존재함.

- N개의 `Mesh` 노드 → 공유 1개의 캐시 엔트리
- VBO도 1벌만 생성되어 draw call 인스턴싱의 기반이 됨

### 의존성 방향은 단방향으로 고정할 것

```
spatial_toolbox  ←  { viewport/, simulation/ }  ←  ui/
```

도메인 레이어(`spatial_toolbox`)가 어댑터나 UI를 참조하는 순간 테스트·재사용이 불가능해짐. 이 방향을 어기면 나중에 분리 비용이 매우 커짐.

---

## 3. 레이어 구조

### 3.1 도메인 레이어 — `spatial_toolbox`

렌더러나 UI에 의존하지 않는 순수 도메인 모델. 별도 저장소·패키지로 관리하는 것을 권장함.

```
spatial_toolbox/
├── scene/
│   ├── node/       씬 그래프 트리 (Base_Node, Group, Mesh, Camera, Controller)
│   ├── asset/      지오메트리 캐시 (ASSET_CACHE 싱글톤, similarity 유틸)
│   └── file/       파일 → trimesh 변환 디스패처 (Read_from)
└── graphics/
    ├── core/       렌더러·패스 API 무관 ABC (I_Renderer, Base_Renderer, Base_Pass)
    ├── openGL/     OpenGL 고정 파이프라인 구현체
    └── registry.py 패스 이름 → 클래스 매핑
```

### 3.2 어댑터 레이어 — 최상위 계층

도메인을 특정 런타임(Qt, EGL, Blender)에 연결하는 어댑터. 도메인을 참조하지만 역방향은 없음.

```
viewport/       QOpenGLWidget 기반 실시간 편집기 뷰포트
simulation/     EGL/Qt/Blender 오프스크린 배치 캡처 파이프라인
```

### 3.3 UI 레이어 — `ui/`

PySide6 편집기. 어댑터 레이어만 참조하고, 위젯끼리는 `Main_Window` Mediator를 통해서만 통신함.

---

## 4. 씬 그래프 설계

### Dirty Flag 패턴으로 월드 행렬 캐싱

노드의 `local_matrix`가 변경되면 해당 노드와 모든 자손의 `world_matrix` 캐시를 무효화함(`_Mark_dirty` 전파). 렌더 시점에 루트에서 한 번만 재계산함. 이 패턴 없이는 트리 순회마다 행렬 곱셈이 반복되어 대형 씬에서 성능이 급격히 하락함.

### Controller가 유일한 씬 조립 진입점

파일 로드, 노드 추가, 이동, 삭제, 저장/복원 모두 `Controller`를 통해서만 수행함. 외부에서 노드 트리를 직접 조작하면 캐시 일관성이 깨짐.

```python
ctrl = Controller()
ctrl.Add_from_file("model.obj")  # 캐시 등록 + 트리 조립 동시 처리
ctrl.Save("scene.bundle")        # 번들로 저장
ctrl.Load("scene.bundle")        # 번들에서 완전 복원
```

### 씬 영속화는 USD로

절대 경로 기반 JSON 저장은 치명적인 함정임. 파일이 이동하거나 다른 머신에서 열면 에셋이 전부 소실됨. 커스텀 ZIP 번들 대신 USD를 씬 영속화 포맷으로 채택하여 이 문제를 해소함.

`Controller.Export_usd` / `Controller.Import_usd`가 씬 영속화와 Blender 렌더러 교환을 모두 담당함. 내부 노드 구조는 현행 유지하고 변환은 export/import 경로에만 한정됨.

---

## 5. 렌더링 파이프라인 설계

### 렌더러 계층 구조

```
I_Renderer                      단일 계약: Render(queue, camera) → dict
└── Base_Renderer(I_Renderer)   multi-pass 생명주기 (_Setup_camera, _Clear_buffer)
        └── OpenGL_Renderer     OpenGL 고정 파이프라인 구현체

Blender_Renderer(I_Renderer)    multi-pass 우회, 채널 일괄 렌더
```

`I_Renderer`를 최상위 계약으로 두는 이유: OpenGL의 패스별 실행·readback 모델과 Blender의 채널 일괄 렌더 모델이 근본적으로 다르기 때문임. 두 백엔드를 동일한 multi-pass 추상화로 강제하면 Blender 통합이 왜곡됨.

### Multi-Pass 패턴 (OpenGL 전용)

OpenGL 백엔드는 패스별로 `Execute → Readback` 루프를 돌림. 각 패스는 클래스 속성 선언만으로 정의되는 구조가 가장 유지보수가 쉬움.

```python
@Pass_Registry.Register_module("rgb")
class RGB_Pass(OpenGL_Base_Pass):
    name            = "rgb"
    _use_lighting   = True
    _draw_mode      = "default"
    _readback_format= "rgb"
    _clear_color    = (0.0, 0.0, 0.0, 1.0)
```

특수 처리가 필요한 경우에만 훅(`_On_setup`, `_On_draw`, `_On_readback`, `_On_cleanup`)을 오버라이드함.

### 실시간 뷰포트와 오프라인 캡처 백엔드를 분리할 것

| 용도 | 백엔드 | 이유 |
|------|--------|------|
| 편집기 실시간 뷰포트 | OpenGL (QOpenGLWidget) | 임베드·인터랙션 필수 |
| 오프라인 AI 데이터셋 생성 | Blender headless | 렌더 품질·속도 |

Blender를 뷰포트에 쓰려는 시도는 기술적으로 불가능하다고 함. 두 경로의 백엔드를 명확히 구분해야 함.

### Blender 프로세스 전략

샘플마다 `subprocess`로 Blender를 기동하면 N샘플 배치에서 기동 비용이 지배적이 됨. 장수명 단일 프로세스 + stdin/소켓 통신 방식을 써야 함.

```
Capture_Project
    → Export_usd()          씬을 USD로 직렬화
    → [Blender 프로세스]    USD 로드 → N샘플 렌더 루프 → 결과 전송
    → Result_Exporter       PNG/NPY/JSON 저장
```

Blender 1회 기동으로 N샘플 전체를 처리해야 기동 오버헤드를 상각할 수 있음.

### USD를 씬 교환 포맷으로 사용

OBJ를 Blender에 직접 전달할 수도 있지만, USD는 계층 구조·단위·카메라 정보를 표준화된 방식으로 보존함. OBJ 파일에 머티리얼 정보가 없다고 가정하는 경우(스캔 데이터, 단순 기하 모델)에도 USD가 올바른 교환 포맷임.

**내부 모델 → USD 매핑 규약:**

| 내부 필드 | USD 표현 |
|---|---|
| `Controller.unit_length` | `UsdStage.metersPerUnit` |
| `Base_Node.scale` | `xformOp:scale` |
| `Base_Node.unit_scale` | `xformOp:scale:unitFix` (custom suffix, 등방 스칼라) |
| `source_key` 동일 그룹 | USD Reference + `instanceable = true` |

geometry는 원본 좌표 그대로 유지함. unit_scale을 geometry에 bake하지 않는 이유: 점군(LiDAR / 포토그래메트리) 원본 좌표의 정밀도 보존 및 역방향 복원 가능성 확보.

USD는 Blender와의 씬 교환 및 씬 영속화에만 사용하며, 편집기 내부 씬 그래프는 현행 구조를 유지함. `pxr` 의존성은 Export/Import 경로에만 한정됨.

---

## 6. 에셋 로딩 성능

### 동기 로딩은 즉각적인 UI 블로킹을 유발함

trimesh 파싱은 수십~수백 ms 소요될 수 있음. 메인 스레드에서 직접 호출하면 편집기 뷰포트가 멈춤.

### 올바른 비동기 로딩 구조

```
워커 스레드              메인 스레드 (GL)
─────────────────        ────────────────
ASSET_CACHE              (대기)
.Add_from_file()
  └─ trimesh 파싱
  └─ 캐시 등록
  └─ signal 발송  ──→   VBO 업로드
                         뷰포트 갱신
```

OpenGL VBO 업로드는 GL 컨텍스트가 귀속된 메인 스레드에서만 수행해야 함. `ASSET_CACHE.Add_from_file`이 GL을 접촉하지 않도록 설계하고, 완료 시 시그널로 메인 스레드에 위임하는 구조가 핵심임.

동일 `source_key`에 대한 중복 요청(in-flight 추적)도 반드시 처리해야 함. 처리하지 않으면 동일 파일이 병렬 파싱됨.

---

## 7. 현재까지 확인된 문제

### 노멀 방향이 랜덤하게 결정되는 문제

OBJ 로더에서 `merge_vertices + fix_normals`를 적용해도 non-watertight 메시(열린 표면)는 "외향"을 자동으로 판정할 수 없어 component별 노멀 방향이 뒤집힐 수 있음. 증상은 대칭·미러 모델에서 한쪽 면만 정상 조명이 들어오는 현상으로 나타남.

임시 우회책인 `GL_LIGHT_MODEL_TWO_SIDE` 상시 활성은 양면 조명을 강제하여 증상을 감추지만 렌더링 품질과 성능 모두에 영향을 줌. 근본 해결책은 로드 시 watertight 여부 판정 후 외향 판정 휴리스틱(ray-casting voting, convex hull 참조 등)을 분기 적용하는 것임.

### 씬 저장 시 절대 경로 의존

위 4절 참조. 씬 JSON에 `/home/user/models/box.obj` 같은 절대 경로를 저장하면 경로가 달라지는 순간 복원이 불가능함. 개발 초기부터 번들 포맷을 설계해야 함.

### OpenGL 고정 파이프라인의 구조적 한계

렌즈 왜곡 모델(`Camera_Intrinsic.distortion`)을 고정 파이프라인에서 실시간으로 적용할 수 없음. 셰이더 기반 파이프라인으로 전환하거나 후처리 단계를 추가해야 하며, 이는 상당한 리팩토링 비용을 수반함.

### 카메라 탐색 범위

배치 캡처 시 씬에서 카메라를 찾는 로직의 탐색 범위를 불필요하게 제한하지 말 것. 카메라 배치 위치를 씬 구조 제약으로 강제하면 편집기 사용 유연성이 떨어짐. 루트 전체를 탐색하는 것이 올바름.

---

## 8. 기술 스택 선택 근거

| 선택 | 이유 |
|------|------|
| Python ≥ 3.11 | 빠른 프로토타이핑, numpy/trimesh 생태계 |
| PySide6 | Qt 공식 Python 바인딩, 상용 라이선스 문제 없음 |
| PyOpenGL 고정 파이프라인 | 초기 구현 속도. 단, 셰이더 없이는 왜곡·SSAO 등 불가 |
| trimesh | OBJ·STL·GLB 로딩, 노멀 복구, ICP 기반 유사도 측정까지 커버 |
| numpy | 행렬 연산, VBO 버퍼 직접 조작 |
| PIL | 렌더 결과 PNG 저장. PySide6 이미지 의존 없이 가능 |
| Blender headless (예정) | 오프라인 렌더 품질. Python API(`bpy`) 또는 소켓 통신으로 제어 |
| USD (예정) | 씬 교환 포맷. Blender 네이티브 지원, 계층·단위 보존 |

---

## 9. 단위 체계

단위를 무시하면 두 가지 문제가 발생함:

1. 서로 다른 소스(mm 단위 CAD, m 단위 스캔)를 혼합할 때 스케일이 100~1000배 어긋남
2. USD `metersPerUnit`, Blender 내부 단위, 카메라 near/far clip 등이 모두 어긋남

설계 초기에 `Mesh_Asset.source_unit`(로더 시점)과 `Stage_Controller.meters_per_unit`(스테이지 시점)을 확립하고, 인스턴스화 시점에 변환을 일괄 적용하는 구조를 잡아야 함. 나중에 붙이면 모든 수치 계산 경로를 재검토해야 함.

---

## 10. 확장 경로 요약

```
현재 (OpenGL 단일 백엔드)
    ↓
I_Renderer 계층 분리
    ↓
씬 번들 영속화 + 비동기 로딩
    ↓
USD 직렬화 (단위 체계 선행)
    ↓
Blender 렌더러 (장수명 프로세스 + USD 교환)
    ↓
셰이더 파이프라인 전환 (렌즈 왜곡, 고급 머티리얼)
```

각 단계는 독립적으로 배포 가능하며, I_Renderer 분리가 이후 모든 백엔드 확장의 선결 조건임.
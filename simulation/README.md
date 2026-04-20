# simulation

오프라인 멀티패스 렌더링 파이프라인. 헤드리스 환경에서 하나의 장면(씬 + 카메라)으로부터 RGB·Depth·Segmentation·Normal 등 다수의 정답 데이터를 동시에 생성함.

렌더 코어(`Base_Pass`·패스 구현체·`OpenGL_Renderer`)는 `spatial_toolbox.graphics`에 위치하며, 본 모듈은 **컨텍스트 관리 · 배치 시퀀싱 · 결과 저장 · 랜덤화 샘플링**만 담당함.

## 구조

```text
simulation/
├── config.py     # Render_Config — 패스 목록 · 카메라/객체/광원 랜덤화 범위
├── engine.py     # Capture_Project / Run_batch_capture — 배치 캡처 진입점
├── pipeline.py   # Render_Pipeline — EGL/Qt 헤드리스 컨텍스트 + 패스 실행
└── exporter.py   # Result_Exporter — PNG/NPY/JSON 저장
```

관련 서브모듈 진입점:

```text
spatial_toolbox.graphics.openGL.pass_.base.OpenGL_Base_Pass   # 패스 추상 (Template Method)
spatial_toolbox.graphics.openGL.renderer.OpenGL_Renderer      # 패스 실행 + 조명/VBO 관리
spatial_toolbox.graphics.registry.Pass_Registry               # 데코레이터 기반 패스 레지스트리
```

## 실행 진입점

### CLI (`capture_cli.py`)

```bash
python capture_cli.py --render_cfg path/to/render.json
```

내부 흐름: `Run_batch_capture` → `Render_Config.Read_from_file` → `Stage_Controller.Load(scene_path)` → `target` 그룹 탐색 → 자식 객체별 visible 토글 + `Capture_Project.Render_target` 반복.

### 프로그램 호출

```python
from pathlib import Path
from simulation.engine import Run_batch_capture

Run_batch_capture(Path("path/to/render.json"))
```

### 저수준 직접 제어

```python
from spatial_toolbox.scene import Controller as Stage_Controller
from simulation.config import Render_Config
from simulation.pipeline import Render_Pipeline
from simulation.exporter import Result_Exporter

config = Render_Config(passes=["rgb", "depth", "segmentation", "normal"])
pipeline = Render_Pipeline(config)
pipeline.Setup_headless_context(width=640, height=480, use_egl=True)

stage = Stage_Controller()
stage.Load("scene.json")
root = stage.root
camera = next(n for n in root.children if n.prim_type == "Camera")

results = pipeline.Execute(root, camera, 640, 480)

exporter = Result_Exporter("./out")
exporter.Save(frame_id=0, results=results, camera_node=camera, config=config)
pipeline.Teardown_headless_context()
```

## 실행 흐름

```text
Render_Config(passes=[...], cam=Randomize_Range(...), ...)
    │
    ▼
Render_Pipeline(config)
    │
    ├── Setup_headless_context(w, h, use_egl=True)   ── EGL 시도 → 실패 시 Qt 폴백
    │
    ├── Execute(root_node, camera_node, w, h)        ── OpenGL_Renderer.Render 위임
    │       │
    │       ├── rgb           → uint8  (H×W×3)
    │       ├── depth         → float32 (H×W)
    │       ├── segmentation  → uint8  (H×W×3)
    │       └── normal        → uint8  (H×W×3)
    │
    └── Teardown_headless_context()

Result_Exporter(output_dir).Save(frame_id, results, camera_node, config)
    │
    ├── rgb_000000.png
    ├── depth_000000.npy            # float32 선형 미터
    ├── segmentation_000000.png
    ├── normal_000000.png
    └── metadata_000000.json        # intrinsic + extrinsic + render config + id_map
```

## 컨텍스트 관리 (pipeline.py)

`Render_Pipeline`은 세 가지 OpenGL 컨텍스트 모드를 지원함:

| 모드 | 트리거 | 백엔드 |
| --- | --- | --- |
| **EGL** (우선) | `Setup_headless_context(use_egl=True)` 성공 시 | PyOpenGL EGL + 직접 FBO/렌더버퍼 생성 (PySide6 비의존) |
| **Qt 폴백** | EGL 초기화 실패 시 자동 전환 | `QOffscreenSurface` + `QOpenGLFramebufferObject` |
| **UI 임베드** | `Setup_headless_context()` 미호출 | 호출 측의 기존 컨텍스트(`makeCurrent` 된 상태) 재사용 |

EGL 모드에서는 컬러 `GL_RGBA8` + 24-bit 뎁스 렌더버퍼를 직접 생성/연결하며, `Teardown_headless_context()`가 모든 GL 객체와 EGL 디스플레이를 해제함.

## 배치 캡처 (engine.py)

`Capture_Project`는 `python_toolbox.project.Project_Template`를 상속하여 `./result/capture/<timestamp>_<uuid>/` 워크스페이스를 자동 생성함.

- `_Find_target_group(root)` — `label="target"`, `prim_type="Xform"`인 그룹을 탐색
- `_Set_isolated_visibility(group, index)` — 그룹 직속 자식 중 index만 visible=True로 설정
- `Render_target(...)` — target 자식 각각에 대해 `num_samples` 프레임을 캡처. 샘플마다 카메라·객체·광원 델타를 `Sample_delta_matrix` / `Sample_translation`으로 독립 샘플링

`output_layout="per_object"`는 target 자식별 서브디렉토리 생성, `"flat"`은 단일 디렉토리에 평탄화함.

## 패스 결과 스펙

패스 구현은 `spatial_toolbox.graphics.openGL.pass_` 에 위치함. 본 모듈은 이름으로만 참조함.

| 패스 이름 | dtype / shape | 인코딩 / 배경 |
| --- | --- | --- |
| `rgb` | uint8 (H×W×3) | Phong 조명 (light_position/diffuse/ambient/specular 외부 주입) |
| `depth` | float32 (H×W) | NDC → 선형 미터 변환. 배경(NDC≥1.0) = 0.0 |
| `segmentation` | uint8 (H×W×3) | 인스턴스 카운터를 24-bit RGB로 분해. 배경 = (0,0,0) |
| `normal` | uint8 (H×W×3) | `(n+1)*127.5` (VBO 사전 인코딩). 배경 = (128,128,255) |

`Render_Pipeline.Get_segmentation_id_map()`은 `(R,G,B) → (label, prim_path)` 매핑을 JSON 직렬화 가능한 리스트로 반환함 (segmentation 패스 등록 시).

`OpenGL_Renderer`가 모든 패스 결과에 `np.flipud`를 적용하여 OpenGL 좌하단 기준 → 좌상단 기준으로 정규화함.

## 새 패스 추가 방법

1. `spatial_toolbox.graphics.openGL.pass_` 에 새 파일 생성
2. `OpenGL_Base_Pass` 를 상속하고 `@Pass_Registry.Register_module("이름")`으로 등록
3. 클래스 속성(`name`, `_readback_format`, `_draw_mode`, `_use_lighting`, `_clear_color`) 선언. 필요 시 훅 오버라이드
4. `Render_Config.passes` 에 이름 추가 — 파이프라인이 `Pass_Registry.Get(name)` 으로 자동 인스턴스화 + `Configure` 훅 호출

```python
from spatial_toolbox.graphics.openGL.pass_.base import OpenGL_Base_Pass
from spatial_toolbox.graphics.registry import Pass_Registry

@Pass_Registry.Register_module("optical_flow")
class Optical_Flow_Pass(OpenGL_Base_Pass):
    name = "optical_flow"
    _use_lighting = False
    _draw_mode = "default"
    _readback_format = "rgb"
```

자세한 훅 오버라이드 규칙은 [../submodules/spatial_toolbox/spatial_toolbox/graphics/openGL/COOKBOOK.md](../submodules/spatial_toolbox/spatial_toolbox/graphics/openGL/COOKBOOK.md) 참조.

## Render_Config 주요 필드

| 필드 | 기본값 | 설명 |
| --- | --- | --- |
| `passes` | `["rgb","depth","segmentation","normal"]` | 실행할 패스 이름 목록 |
| `bg_color` | `[0.0, 0.0, 0.0]` | 배경색 (RGB, 0.0~1.0) |
| `scene_path` | `""` | 장면 JSON 파일 경로 |
| `num_samples` | `1` | target 객체 1개당 샘플 프레임 수 |
| `camera_label` | `"main_camera"` | 장면 내 카메라 노드 식별자 |
| `output_layout` | `"per_object"` | `"per_object"` / `"flat"` |
| `light_position` | `[0.0, 1.0, 0.0, 0.0]` | 광원 기준 위치(4성분, w=0 방향광 / w=1 점광원) |
| `cam` | `Randomize_Range()` | 카메라 extrinsic 델타 범위 |
| `obj` | `Randomize_Range()` | 객체 local 델타 범위 |
| `light` | `Randomize_Range()` | 광원 위치 델타 범위 (tx/ty/tz만 사용, 회전 무시) |
| `seed` | `None` | RNG 시드. 정수 지정 시 `np.random.seed` 주입으로 재현성 확보 |

`Randomize_Range`의 각 필드(tx/ty/tz/rx/ry/rz)는 고정값(`float`) 또는 `[min, max]` 리스트로 지정함. `Sample_delta_matrix` / `Sample_translation`이 균일 샘플링하여 4×4 델타 행렬 또는 3-벡터를 생성함.

`Render_Config`는 `Base_Config` 상속이므로 `Serialize()`, `Write_to()`, `Read_from_file()` 사용 가능함.

## UI 임베드 모드

편집기에서 이미 GL 컨텍스트가 활성화된 경우 `Setup_headless_context`를 호출하지 않고 바로 `Execute`함.

```python
# QOpenGLWidget.paintGL 내부 등 makeCurrent 이후
pipeline = Render_Pipeline(config)
results = pipeline.Execute(root_node, camera_node, w, h)
```

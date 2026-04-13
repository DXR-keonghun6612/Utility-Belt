# graphics/render

학습 데이터 생성을 위한 오프라인 멀티패스 렌더링 파이프라인.

하나의 장면(씬 + 카메라)에서 여러 렌더 패스를 순차 실행하여 RGB, Depth, Segmentation, Normal 등의 정답 데이터를 동시에 생성함.

> **중요**: 패스 구현체(`rgb`, `depth`, `normal`, `segmentation`)는 **`graphics/core/pass_/`** 에 위치함. `render/`는 컨텍스트 관리, 패스 시퀀싱, 결과 저장만 담당함.

## 구조

```
render/
├── config.py     # Render_Config — 패스 목록, 카메라 랜덤화 범위
├── pipeline.py   # Render_Pipeline — EGL/Qt 헤드리스 컨텍스트 + 패스 실행
└── exporter.py   # Result_Exporter — PNG/NPY/JSON 저장
```

관련 패스 코어:

```
graphics/core/pass_/
├── base.py          # Base_Pass (ABC, Template Method)
├── registry.py      # Pass_Registry
├── build.py         # Get_render(name) — name → Base_Pass 인스턴스
├── rgb.py           # RGB_Pass
├── depth.py         # Depth_Pass
├── normal.py        # Normal_Pass
└── segmentation.py  # Segmentation_Pass
```

## 실행 흐름

```
Render_Config(passes=["rgb","depth","segmentation","normal"], …)
    │
    ▼
Render_Pipeline(config)
    │
    ├── Setup_headless_context(w, h, use_egl=True)  ─── EGL 시도 → 실패 시 Qt 폴백
    │
    ├── Execute(root_node, camera_node, w, h)       ─── 등록 패스 순차 실행
    │       │
    │       ├── RGB_Pass.Render()           → np.uint8  (H×W×3)
    │       ├── Depth_Pass.Render()         → np.float32 (H×W)
    │       ├── Segmentation_Pass.Render()  → np.uint8  (H×W×3)
    │       └── Normal_Pass.Render()        → np.uint8  (H×W×3)
    │
    └── Teardown_headless_context()

Result_Exporter(output_dir).Save(frame_id, results, camera_node, config)
    │
    ├── rgb_000000.png
    ├── depth_000000.npy            (float32 → npy)
    ├── segmentation_000000.png
    ├── normal_000000.png
    └── metadata_000000.json        (intrinsic + extrinsic + render config)
```

## 컨텍스트 관리 (pipeline.py)

`Render_Pipeline`은 세 가지 OpenGL 컨텍스트 모드를 지원함:

| 모드 | 트리거 | 백엔드 |
|---|---|---|
| **EGL** (우선) | `Setup_headless_context(use_egl=True)` 성공 시 | PyOpenGL EGL + 직접 FBO 생성 (PySide6 비의존) |
| **Qt 폴백** | EGL 실패 시 자동 전환 | `QOffscreenSurface` + `QOpenGLFramebufferObject` |
| **UI 임베드** | `Setup_headless_context()` 미호출 | 호출 측의 기존 컨텍스트(makeCurrent된 상태) |

EGL 모드에서는 컬러 + 24-bit 뎁스 렌더버퍼를 직접 생성/연결하며, `Teardown_headless_context()`가 모든 GL 객체와 EGL 디스플레이를 해제함.

## 렌더 패스 상세 (graphics/core/pass_/)

| 패스 | dtype / shape | 인코딩 / 배경 |
|---|---|---|
| `rgb` | uint8 (H×W×3) | Phong 조명 (light_position/diffuse/ambient 외부 주입) |
| `depth` | float32 (H×W) | NDC → 선형 미터 변환. 배경(NDC≥1.0) = 0.0 |
| `segmentation` | uint8 (H×W×3) | 인스턴스 카운터를 24-bit RGB로 분해. 배경 = (0,0,0) |
| `normal` | uint8 (H×W×3) | `(n+1)*127.5` (VBO 사전 인코딩 사용). 배경 = (128,128,255) |

`Segmentation_Pass.last_id_map`은 `(R,G,B) → Base_Node` 딕셔너리를 제공하여 ID 색상으로부터 노드를 역추적할 수 있음.

`Base_Pass.Render()`는 모든 패스 결과에 `np.flipud`를 적용하여 OpenGL 좌하단 기준 → 좌상단 기준으로 정규화함.

## 새 패스 추가 방법

1. `graphics/core/pass_/` 에 새 파일 생성
2. `Base_Pass`를 상속하고 `@Pass_Registry.Register_module("이름")`으로 등록
3. `Name` 프로퍼티와 `_On_readback` 구현 (선택적으로 `_On_setup`/`_On_draw`/`_On_cleanup`)
4. `graphics/core/pass_/build.py` import 목록에 추가
5. `Render_Config.passes` 리스트에 이름 추가 — `pipeline.py` 수정 불필요

```python
from graphics.core.pass_.base import Base_Pass
from graphics.core.pass_.registry import Pass_Registry

@Pass_Registry.Register_module("optical_flow")
class Optical_Flow_Pass(Base_Pass):
    @property
    def Name(self) -> str:
        return "optical_flow"

    def _On_setup(self) -> None:
        ...

    def _On_readback(self, width, height, **kwargs):
        return self._Read_rgb(width, height)
```

## Render_Config 주요 필드

| 필드 | 기본값 | 설명 |
|---|---|---|
| `passes` | `["rgb","depth","segmentation","normal"]` | 실행할 패스 이름 목록 |
| `bg_color` | `[0.0, 0.0, 0.0]` | 배경색 (RGB, 0.0~1.0) |
| `scene_path` | `""` | 장면 JSON 파일 경로 |
| `num_samples` | `1` | 카메라 랜덤화 반복 횟수 |
| `camera_label` | `"main_camera"` | 장면 내 타깃 카메라 노드 라벨 |
| `obj_dir` | `""` | OBJ 디렉토리 스캔 모드 (빈 문자열이면 비활성) |
| `target_node_label` | `""` | OBJ 삽입 대상 노드 라벨 |
| `tx`/`ty`/`tz`, `rx`/`ry`/`rz` | `0.0` | 카메라 Extrinsic 델타. 고정값 또는 `[min, max]` |

`Sample_delta_matrix(config)`는 위 6개 필드에서 균일 샘플링하여 4x4 델타 행렬을 생성함 (랜덤 카메라 변동 적용용).

`Base_Config` 상속이므로 `Serialize()`, `Write_to()`, `Read_from_file()` 사용 가능.

## 실행 모드

**헤드리스 (capture_cli.py)**

```python
config = Render_Config(passes=["rgb", "depth"])
pipeline = Render_Pipeline(config)
pipeline.Setup_headless_context(width=640, height=480, use_egl=True)

results = pipeline.Execute(root_node, camera_node, 640, 480)

exporter = Result_Exporter("./out")
exporter.Save(frame_id=0, results=results, camera_node=camera_node, config=config)

pipeline.Teardown_headless_context()
```

**UI 임베드 (편집기 내)**

```python
# 호출 측에서 GL 컨텍스트 makeCurrent 후
pipeline = Render_Pipeline(config)
results = pipeline.Execute(root_node, camera_node, w, h)
```

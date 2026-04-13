# Cookbook

FOCUS 프로젝트의 실행 방법 및 사용 예시 모음임.

## 정적 편집기 실행

PySide6 기반 편집기 UI를 실행함.

```bash
python app.py
```

진입점: `app.py` → `ui/editor/main.py`의 `Main_Window`. 좌측 Activity Bar에서 Scene / Asset / Viewport 패널을 토글할 수 있음.

## 헤드리스 데이터셋 생성

`capture_cli.py`를 통해 GUI 없이 멀티패스 렌더링을 수행함.

```bash
python capture_cli.py
```

내부적으로 `Render_Config` → `Render_Pipeline.Setup_headless_context(use_egl=True)` → `Execute()` → `Result_Exporter.Save()` 순으로 실행됨. EGL 초기화 실패 시 Qt `QOffscreenSurface` 백엔드로 자동 폴백함.

### 프로그램 코드로 실행

```python
from graphics.render.config import Render_Config
from graphics.render.pipeline import Render_Pipeline
from graphics.render.exporter import Result_Exporter

config = Render_Config(passes=["rgb", "depth", "segmentation", "normal"])
pipeline = Render_Pipeline(config)
pipeline.Setup_headless_context(width=640, height=480, use_egl=True)

results = pipeline.Execute(root_node, camera_node, 640, 480)

exporter = Result_Exporter("./out")
exporter.Save(frame_id=0, results=results, camera_node=camera_node, config=config)

pipeline.Teardown_headless_context()
```

출력 산출물:

- `rgb_000000.png` — uint8 RGB
- `depth_000000.npy` — float32 선형 미터
- `segmentation_000000.png` — 인스턴스 ID RGB 인코딩
- `normal_000000.png` — 로컬 법선 RGB 인코딩
- `metadata_000000.json` — 카메라 intrinsic/extrinsic + 렌더 설정

## UI 임베드 모드 렌더링

호출 측에서 이미 GL 컨텍스트가 활성화된 경우 `Setup_headless_context`를 호출하지 않고 바로 `Execute`함.

```python
# QOpenGLWidget.paintGL 내부 등 makeCurrent 이후
pipeline = Render_Pipeline(config)
results = pipeline.Execute(root_node, camera_node, w, h)
```

## 새 렌더 패스 추가

1. `graphics/core/pass_/` 에 새 파일 생성
2. `Base_Pass`를 상속하고 `@Pass_Registry.Register_module("name")`으로 등록
3. `Name` 프로퍼티와 `_On_readback` 구현 (선택적으로 `_On_setup`/`_On_draw`/`_On_cleanup`)
4. `graphics/core/pass_/build.py`의 import 목록에 추가
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

## 카메라 랜덤화

`Render_Config`의 `tx/ty/tz`, `rx/ry/rz` 필드는 고정값(`float`) 또는 범위(`[min, max]`)를 받음. `Sample_delta_matrix(config)`가 균일 샘플링하여 4×4 델타 행렬을 생성함.

```python
config = Render_Config(
    passes=["rgb", "depth"],
    num_samples=100,
    tx=[-0.5, 0.5],
    ty=[-0.5, 0.5],
    rz=[-3.14, 3.14],
)
```

## 메시 유사도 계측

`data/asset/utils/similarity.py`는 세 가지 비교 함수를 제공함.

```python
from data.asset.utils.similarity import (
    Is_exact_match,
    Calculate_match_rate,
    Calculate_scan_match_rate,
)

Is_exact_match(mesh_a, mesh_b)             # 정점/면 정확 일치 여부
Calculate_match_rate(mesh_a, mesh_b)       # 표면 샘플링 기반 일치율
Calculate_scan_match_rate(mesh_a, mesh_b)  # SVD 기반 ICP 정합 후 일치율
```

`Asset_Browser_Panel`의 임포트 흐름은 위 함수를 사용해 중복 후보를 `Duplicate_Dialog`에 표시함.
